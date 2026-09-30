from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from openpyxl.drawing.image import Image as WorksheetImage
from PIL import Image

from tests.conftest import IdentityFixture


def _login(client: TestClient, fixture: IdentityFixture) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": fixture.owner_username,
            "password": fixture.password,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _workbook_bytes() -> bytes:
    image_buffer = BytesIO()
    Image.new("RGB", (32, 24), color=(30, 70, 110)).save(image_buffer, format="PNG")
    image_buffer.seek(0)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(
        [
            "Status",
            "Supplier SKU #",
            "Item Photo",
            "Package photo for reference only",
            "Item Descriptions with Specifications",
            "Buyer Notes",
            "Material",
        ]
        + [None] * 12
        + ["FOB (US$)"]
    )
    sheet.append(
        ["NEW", "IMP-001", None, None, "Blue garden stake", None, "Iron"]
        + [None] * 12
        + ["4.25"]
    )
    sheet.append(
        ["NEW", "IMP-002", None, None, "Green garden stake", None, "Iron"]
        + [None] * 12
        + ["4.75"]
    )
    image = WorksheetImage(image_buffer)
    image.width = 32
    image.height = 24
    sheet.add_image(image, "C2")
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _workbook_with_instruction_row_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Products"
    sheet.append(
        [
            "Status",
            "Supplier SKU #",
            "Item Photo",
            "Package photo for reference only",
            "Item Descriptions with Specifications",
            "Buyer Notes",
            "Material",
        ]
        + [None] * 12
        + ["FOB (US$)"]
    )
    # A typical supplier instruction row can contain text in the mapped
    # product-name column while the SKU is blank.  It is still not a product.
    sheet.append(
        [None, None, None, None, "第2行为说明行，导入时应忽略", None, "FOB XIAMEN"]
        + [None] * 12
        + ["x 0.96"]
    )
    sheet.append(
        ["NEW", "IMP-003", None, None, "Blue wall decor", None, "Iron"]
        + [None] * 12
        + ["5.25"]
    )
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _mapping() -> dict:
    return {
        "version": "1.0",
        "sheet_names": ["Products"],
        "header_row": 1,
        "data_start_row": 2,
        "fields": [
            {"source": "B", "target": "sku", "transform": "trim", "required": True},
            {
                "source": "E",
                "target": "product_name",
                "transform": "trim",
                "required": True,
            },
            {"source": "G", "target": "material", "transform": "trim"},
            {"source": "T", "target": "supplier_cost", "transform": "decimal"},
        ],
    }


def test_excel_import_analyze_preview_confirm_and_duplicate_policy(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture)
    template_response = client.post(
        "/api/v1/import-templates",
        headers=headers,
        json={"name": "Supplier workbook", "mapping_config": _mapping()},
    )
    assert template_response.status_code == 201, template_response.text
    template_id = template_response.json()["id"]

    payload = _workbook_bytes()
    analysis_response = client.post(
        "/api/v1/import-jobs/analyze",
        headers=headers,
        files={
            "file": (
                "supplier-products.xlsx",
                payload,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert analysis_response.status_code == 201, analysis_response.text
    analyzed = analysis_response.json()
    assert analyzed["status"] == "analyzed"
    assert analyzed["analysis"]["sheets"][0]["name"] == "Products"
    assert analyzed["analysis"]["sheets"][0]["merged_cells"] == []
    assert analyzed["analysis"]["sheets"][0]["images"][0]["source_row"] == 2
    assert analyzed["analysis"]["sheets"][0]["images"][0]["source_column"] == 3
    assert analyzed["images"][0]["original_filename"].startswith("image")
    assert len(analyzed["images"][0]["sha256"]) == 64
    assert analyzed["images"][0]["width"] == 32
    assert analyzed["images"][0]["height"] == 24
    image_content = client.get(analyzed["images"][0]["content_url"], headers=headers)
    assert image_content.status_code == 200
    assert image_content.headers["content-type"] == "image/png"

    preview_response = client.post(
        f"/api/v1/import-jobs/{analyzed['id']}/preview",
        headers=headers,
        json={"import_template_id": template_id},
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["status"] == "preview_ready"
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["rows"][0]["mapped_data"]["supplier_cost"] == 4.25
    assert preview["images"][0]["match_method"] == "anchor"
    assert preview["images"][0]["match_confidence"] == 0.99
    assert preview["images"][0]["matched_sku"] == "IMP-001"
    assert preview["images"][0]["matched_product_id"] is None

    manual_match = client.patch(
        f"/api/v1/import-image-candidates/{preview['images'][0]['id']}",
        headers=headers,
        json={
            "matched_sku": "IMP-001",
            "image_type": "main",
            "is_primary": True,
        },
    )
    assert manual_match.status_code == 200, manual_match.text
    assert manual_match.json()["matched_sku"] == "IMP-001"
    assert manual_match.json()["match_method"] == "manual"
    assert manual_match.json()["matched_product_id"] is None

    confirm_response = client.post(
        f"/api/v1/import-jobs/{analyzed['id']}/confirm",
        headers=headers,
        json={"duplicate_strategy": "overwrite"},
    )
    assert confirm_response.status_code == 200, confirm_response.text
    confirmed = confirm_response.json()
    assert confirmed["status"] == "completed"
    assert confirmed["imported_rows"] == 2
    assert confirmed["images"][0]["status"] == "imported"
    assert confirmed["images"][0]["matched_product_id"] is not None

    products = client.get("/api/v1/products?search=IMP-", headers=headers)
    assert products.status_code == 200
    assert products.json()["total"] == 2
    assert [item["sku"] for item in products.json()["items"]] == ["IMP-002", "IMP-001"]
    first = next(item for item in products.json()["items"] if item["sku"] == "IMP-001")
    assert first["custom_fields"]["supplier_cost"] == "4.25"
    assert first["image_count"] == 1

    second_analysis = client.post(
        "/api/v1/import-jobs/analyze",
        headers=headers,
        files={"file": ("supplier-products.xlsx", payload)},
    )
    assert second_analysis.status_code == 201
    second_id = second_analysis.json()["id"]
    second_preview = client.post(
        f"/api/v1/import-jobs/{second_id}/preview",
        headers=headers,
        json={"import_template_id": template_id},
    )
    assert second_preview.status_code == 200
    assert second_preview.json()["conflict_rows"] == 2
    skipped = client.post(
        f"/api/v1/import-jobs/{second_id}/confirm",
        headers=headers,
        json={"duplicate_strategy": "skip"},
    )
    assert skipped.status_code == 200
    assert skipped.json()["skipped_rows"] == 2
    assert skipped.json()["imported_rows"] == 0

    deleted_product = client.delete(
        f"/api/v1/products/{first['id']}", headers=headers
    )
    assert deleted_product.status_code == 204, deleted_product.text
    first_job_after_delete = client.get(
        f"/api/v1/import-jobs/{analyzed['id']}", headers=headers
    )
    assert first_job_after_delete.status_code == 200
    assert all(
        row["product_id"] != first["id"]
        for row in first_job_after_delete.json()["rows"]
    )

    deleted_template = client.delete(
        f"/api/v1/import-templates/{template_id}", headers=headers
    )
    assert deleted_template.status_code == 204, deleted_template.text
    job_after_template_delete = client.get(
        f"/api/v1/import-jobs/{analyzed['id']}", headers=headers
    )
    assert job_after_template_delete.status_code == 200
    assert job_after_template_delete.json()["import_template_id"] is None


def test_excel_import_rejects_unreadable_or_protected_file(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture)
    response = client.post(
        "/api/v1/import-jobs/analyze",
        headers=headers,
        files={"file": ("protected.xlsx", b"not-an-office-file")},
    )
    assert response.status_code == 400
    assert "解除企业文档保护" in response.json()["message"]


def test_excel_import_ignores_instruction_row_without_product_identity(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture)
    template_response = client.post(
        "/api/v1/import-templates",
        headers=headers,
        json={"name": "Workbook with instruction row", "mapping_config": _mapping()},
    )
    assert template_response.status_code == 201, template_response.text

    analysis_response = client.post(
        "/api/v1/import-jobs/analyze",
        headers=headers,
        files={
            "file": (
                "instruction-row.xlsx",
                _workbook_with_instruction_row_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert analysis_response.status_code == 201, analysis_response.text

    preview_response = client.post(
        f"/api/v1/import-jobs/{analysis_response.json()['id']}/preview",
        headers=headers,
        json={"import_template_id": template_response.json()["id"]},
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["total_rows"] == 1
    assert preview["valid_rows"] == 1
    assert preview["rows"][0]["source_row"] == 3
    assert preview["rows"][0]["mapped_data"]["sku"] == "IMP-003"


def test_import_template_rejects_unknown_target(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture)
    mapping = _mapping()
    mapping["fields"].append({"source": "A", "target": "unknown_private_field"})
    response = client.post(
        "/api/v1/import-templates",
        headers=headers,
        json={"name": "Invalid mapping", "mapping_config": mapping},
    )
    assert response.status_code == 400
    assert "未知或已停用字段" in response.json()["message"]
