from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.conftest import IdentityFixture


def _login(client: TestClient, identifier: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _pptx_bytes(label: str = "Product Name") -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Default Extension="xml" ContentType="application/xml"/>
            </Types>""",
        )
        archive.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <p:presentation
              xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:sldSz cx="12192000" cy="6858000"/>
            </p:presentation>""",
        )
        archive.writestr(
            "ppt/slides/slide1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <p:sld
              xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
              <p:cSld><p:spTree>
                <p:nvGrpSpPr/><p:grpSpPr/>
                <p:sp>
                  <p:nvSpPr><p:cNvPr id="2" name="Product title"/></p:nvSpPr>
                  <p:spPr><a:xfrm><a:off x="127000" y="254000"/>
                    <a:ext cx="2540000" cy="635000"/></a:xfrm></p:spPr>
                  <p:txBody><a:p><a:r><a:rPr sz="1800" b="1"/>
                    <a:t>{label}</a:t></a:r></a:p></p:txBody>
                </p:sp>
                <p:pic>
                  <p:nvPicPr><p:cNvPr id="3" name="Product image"/></p:nvPicPr>
                  <p:spPr><a:xfrm><a:off x="127000" y="1016000"/>
                    <a:ext cx="3810000" cy="3810000"/></a:xfrm></p:spPr>
                </p:pic>
                <p:graphicFrame>
                  <p:nvGraphicFramePr><p:cNvPr id="4" name="Sales chart"/></p:nvGraphicFramePr>
                  <a:graphic><a:graphicData
                    uri="http://schemas.openxmlformats.org/drawingml/2006/chart"/>
                  </a:graphic>
                </p:graphicFrame>
              </p:spTree></p:cSld>
            </p:sld>""",
        )
    return output.getvalue()


def _xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Quotation"
    sheet["A1"] = "Product name"
    sheet["B1"] = "Price"
    sheet["B2"] = "=1+1"
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_pptx_template_upload_validation_mapping_and_versioning(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(
        client, identity_fixture.owner_username, identity_fixture.password
    )
    created_response = client.post(
        "/api/v1/output-templates",
        headers=headers,
        data={"name": "Customer quotation", "description": "Standard customer deck"},
        files={"file": ("quotation.pptx", _pptx_bytes())},
    )
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    template_id = created["id"]
    version = created["current_version"]
    report = version["validation_report"]
    assert created["output_type"] == "pptx"
    assert created["current_version_number"] == 1
    assert version["status"] == "needs_mapping"
    assert report["parameterizable_count"] == 3
    assert report["unsupported_count"] == 1
    assert any(
        item["shape_id"] == 2 and item["shape_name"] == "Product title"
        for item in report["objects"]
    )
    assert any(
        item["object_type"] == "chart" and not item["supported"]
        for item in report["objects"]
    )

    text_object = next(
        item for item in report["objects"] if item["object_type"] == "text"
    )
    image_object = next(
        item for item in report["objects"] if item["object_type"] == "image"
    )
    mapping = {
        "version": "1.0",
        "template_sha256": version["template_sha256"],
        "bindings": [
            {
                "object_key": text_object["object_key"],
                "source": "selling_price",
                "label": "FOB PRICE",
                "formatter": "currency",
            },
            {
                "object_key": image_object["object_key"],
                "source": "image.main",
                "fit": "contain",
                "position": "center",
                "fallback": ["image.white_background", "image.lifestyle"],
            },
        ],
    }
    mapping_response = client.put(
        f"/api/v1/output-templates/versions/{version['id']}/mapping",
        headers=headers,
        json=mapping,
    )
    assert mapping_response.status_code == 200, mapping_response.text
    assert mapping_response.json()["status"] == "ready"
    assert mapping_response.json()["validation_report"]["mapped_object_count"] == 2

    internal_mapping = {
        **mapping,
        "bindings": [
            {
                "object_key": text_object["object_key"],
                "source": "supplier_cost",
                "visible": False,
            }
        ],
    }
    internal_response = client.put(
        f"/api/v1/output-templates/versions/{version['id']}/mapping",
        headers=headers,
        json=internal_mapping,
    )
    assert internal_response.status_code == 400
    assert "禁止绑定内部" in internal_response.json()["message"]

    stale_mapping = {**mapping, "template_sha256": "0" * 64}
    stale_response = client.put(
        f"/api/v1/output-templates/versions/{version['id']}/mapping",
        headers=headers,
        json=stale_mapping,
    )
    assert stale_response.status_code == 409
    assert "模板文件发生变化" in stale_response.json()["message"]

    new_version_response = client.post(
        f"/api/v1/output-templates/{template_id}/versions",
        headers=headers,
        files={"file": ("quotation-v2.pptx", _pptx_bytes("Updated Product Name"))},
    )
    assert new_version_response.status_code == 201, new_version_response.text
    updated = new_version_response.json()
    assert updated["current_version_number"] == 2
    assert updated["current_version"]["status"] == "needs_mapping"
    assert updated["current_version"]["validation_report"]["template_changed"] is True
    assert (
        updated["current_version"]["validation_report"]["fingerprint_message"]
        == "模板文件发生变化，请重新验证字段映射。"
    )
    assert updated["current_version"]["mapping_config"]["bindings"] == []


def test_xlsx_template_validation_and_member_permissions(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    member_headers = _login(client, identity_fixture.member_email, identity_fixture.password)
    forbidden = client.post(
        "/api/v1/output-templates",
        headers=member_headers,
        data={"name": "Member template"},
        files={"file": ("quotation.xlsx", _xlsx_bytes())},
    )
    assert forbidden.status_code == 403

    owner_headers = _login(
        client, identity_fixture.owner_username, identity_fixture.password
    )
    created_response = client.post(
        "/api/v1/output-templates",
        headers=owner_headers,
        data={"name": "Excel quotation"},
        files={"file": ("quotation.xlsx", _xlsx_bytes())},
    )
    assert created_response.status_code == 201, created_response.text
    report = created_response.json()["current_version"]["validation_report"]
    assert report["format"] == "xlsx"
    assert any(
        item["object_key"].endswith("cell:A1") and item["supported"]
        for item in report["objects"]
    )
    assert any(
        item["object_key"].endswith("cell:B2") and not item["supported"]
        for item in report["objects"]
    )

    listed = client.get("/api/v1/output-templates", headers=member_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    template_id = created_response.json()["id"]
    forbidden_delete = client.delete(
        f"/api/v1/output-templates/{template_id}", headers=member_headers
    )
    assert forbidden_delete.status_code == 403
    deleted = client.delete(
        f"/api/v1/output-templates/{template_id}", headers=owner_headers
    )
    assert deleted.status_code == 204, deleted.text
    missing = client.get(
        f"/api/v1/output-templates/{template_id}", headers=owner_headers
    )
    assert missing.status_code == 404
