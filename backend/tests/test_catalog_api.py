from hashlib import sha256
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import IdentityFixture


def _login(client: TestClient, fixture: IdentityFixture, identifier: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": identifier,
            "password": fixture.password,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_field_definitions_and_product_crud(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    owner_headers = _login(client, identity_fixture, identity_fixture.owner_username)
    member_headers = _login(client, identity_fixture, identity_fixture.member_email)

    fields_response = client.get("/api/v1/field-definitions", headers=owner_headers)
    assert fields_response.status_code == 200
    fields = fields_response.json()["items"]
    assert any(
        field["code"] == "supplier_cost" and field["scope"] == "internal"
        for field in fields
    )
    assert any(
        field["code"] == "selling_price" and field["scope"] == "customer"
        for field in fields
    )

    member_create = client.post(
        "/api/v1/field-definitions",
        headers=member_headers,
        json={"code": "ip_rating", "label": "IP Rating", "data_type": "text"},
    )
    assert member_create.status_code == 403

    custom_field = client.post(
        "/api/v1/field-definitions",
        headers=owner_headers,
        json={
            "code": "ip_rating",
            "label": "IP Rating",
            "data_type": "select",
            "options": {"choices": ["IP44", "IP65", "IP67"]},
            "sort_order": 400,
        },
    )
    assert custom_field.status_code == 201

    product_response = client.post(
        "/api/v1/products",
        headers=owner_headers,
        json={
            "sku": "PF-TEST-001",
            "product_name": "Outdoor Wall Light",
            "category": "Lighting",
            "brand": "ProductFlow",
            "custom_fields": {
                "ip_rating": "IP65",
                "selling_price": "19.95",
                "supplier_cost": "10.25",
            },
        },
    )
    assert product_response.status_code == 201
    product = product_response.json()
    assert product["custom_fields"]["ip_rating"] == "IP65"
    assert product["custom_fields"]["selling_price"] == "19.95"

    duplicate = client.post(
        "/api/v1/products",
        headers=owner_headers,
        json={"sku": "pf-test-001", "product_name": "Duplicate"},
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/products?search=wall", headers=member_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == product["id"]

    invalid_value = client.patch(
        f"/api/v1/products/{product['id']}",
        headers=owner_headers,
        json={"custom_fields": {"ip_rating": "IP00"}},
    )
    assert invalid_value.status_code == 400

    updated = client.patch(
        f"/api/v1/products/{product['id']}",
        headers=owner_headers,
        json={"description": "Weather-resistant outdoor wall light."},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Weather-resistant outdoor wall light."

    fetched_after_update = client.get(
        f"/api/v1/products/{product['id']}", headers=member_headers
    )
    assert fetched_after_update.status_code == 200
    assert fetched_after_update.json()["description"] == updated.json()["description"]

    internal_field = next(field for field in fields if field["code"] == "supplier_cost")
    leaked_scope = client.patch(
        f"/api/v1/field-definitions/{internal_field['id']}",
        headers=owner_headers,
        json={"scope": "customer"},
    )
    assert leaked_scope.status_code == 400


def test_product_image_upload_metadata_and_content(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture, identity_fixture.owner_username)
    product_response = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": "PF-IMG-001", "product_name": "Image Product"},
    )
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]

    buffer = BytesIO()
    Image.new("RGB", (32, 24), color=(26, 54, 93)).save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    uploaded = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"image": ("产品 主图.png", image_bytes, "image/png")},
        data={"image_type": "main", "is_primary": "true"},
    )
    assert uploaded.status_code == 201
    image = uploaded.json()
    assert image["original_filename"] == "产品 主图.png"
    assert image["safe_filename"].endswith(".png")
    assert image["sha256"] == sha256(image_bytes).hexdigest()
    assert image["mime_type"] == "image/png"
    assert image["width"] == 32
    assert image["height"] == 24
    assert image["is_primary"] is True
    assert image["match_method"] == "manual"
    assert image["match_confidence"] == 1.0

    content = client.get(image["content_url"], headers=headers)
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.content == image_bytes

    library = client.get("/api/v1/product-images?image_type=main", headers=headers)
    assert library.status_code == 200
    assert library.json()["total"] == 1

    duplicate = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        files={"image": ("duplicate.png", image_bytes, "image/png")},
        data={"image_type": "main"},
    )
    assert duplicate.status_code == 409

    deleted = client.delete(f"/api/v1/products/{product_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    missing_product = client.get(f"/api/v1/products/{product_id}", headers=headers)
    assert missing_product.status_code == 404
    missing_image = client.get(image["content_url"], headers=headers)
    assert missing_image.status_code == 404
