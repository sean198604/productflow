import base64

from fastapi.testclient import TestClient

from app.services.renderers.base import placeholder_png
from tests.conftest import IdentityFixture


def _login(client: TestClient, identifier: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_html_quote_is_portable_and_excludes_internal_fields(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture.owner_username, identity_fixture.password)
    product_response = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "HTML-001",
            "product_name": "Game <Boy> & Friends",
            "description": "Portable & iconic",
            "status": "active",
            "custom_fields": {
                "price_usd": "129.90",
                "currency": "USD",
                "moq": 12,
                "supplier_cost": "77.00",
            },
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]
    png = placeholder_png(72, 48)
    image_response = client.post(
        f"/api/v1/products/{product_id}/images",
        headers=headers,
        data={"image_type": "main", "is_primary": "true"},
        files={"image": ("game-boy.png", png, "image/png")},
    )
    assert image_response.status_code == 201, image_response.text
    processed_image = client.get(
        image_response.json()["processed_content_url"], headers=headers
    )
    assert processed_image.status_code == 200
    processed_png = processed_image.content

    for template_key in ("editorial", "journey", "energy"):
        response = client.post(
            "/api/v1/generation-tasks/html-quote",
            headers=headers,
            json={
                "template_key": template_key,
                "title": "Handheld <Archive>",
                "subtitle": "Selected & ready",
                "product_ids": [product_id],
                "currency": "USD",
                "currency_symbol": "$",
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["x-productflow-snapshot"] == "standalone-html"
        assert f"-{template_key}-" in response.headers["content-disposition"]
        html = response.content.decode("utf-8")
        assert f'data-template="{template_key}"' in html
        assert "Handheld &lt;Archive&gt;" in html
        assert "Game &lt;Boy&gt; &amp; Friends" in html
        assert "USD $129.90" in html
        assert "MOQ" in html
        assert "77.00" not in html
        assert "supplier_cost" not in html
        assert (
            f"data:image/png;base64,{base64.b64encode(processed_png).decode('ascii')}"
            in html
        )
        assert "window.print()" in html


def test_html_quote_selects_jpy_or_usd_product_price(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture.owner_username, identity_fixture.password)
    product_response = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "HTML-FX-001",
            "product_name": "Dual currency product",
            "status": "active",
            "custom_fields": {
                "price": "12500",
                "price_usd": "79.42",
                "currency": "JPY",
            },
        },
    )
    assert product_response.status_code == 201, product_response.text
    product_id = product_response.json()["id"]

    jpy = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product_id], "currency": "JPY"},
    )
    assert jpy.status_code == 200, jpy.text
    assert "JPY ¥12,500" in jpy.text

    usd = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product_id], "currency": "USD"},
    )
    assert usd.status_code == 200, usd.text
    assert "USD $79.42" in usd.text

    both = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product_id], "currencies": ["USD", "JPY"]},
    )
    assert both.status_code == 200, both.text
    assert "USD $79.42 · JPY ¥12,500" in both.text


def test_html_quote_omits_price_when_selected_currency_is_empty(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture.owner_username, identity_fixture.password)
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "HTML-JPY-ONLY",
            "product_name": "JPY only product",
            "status": "active",
            "custom_fields": {"price": "12500", "currency": "JPY"},
        },
    ).json()

    response = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product["id"]], "currency": "USD"},
    )

    assert response.status_code == 200, response.text
    assert "QUOTED PRICE" not in response.text
    assert "12,500" not in response.text
    assert "价格面议" not in response.text

    mixed = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product["id"]], "currencies": ["USD", "JPY"]},
    )
    assert mixed.status_code == 200, mixed.text
    assert "JPY ¥12,500" in mixed.text
    assert "USD $" not in mixed.text


def test_html_quote_supports_a_new_currency_price_field(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture.owner_username, identity_fixture.password)
    field = client.post(
        "/api/v1/field-definitions",
        headers=headers,
        json={
            "code": "price_eur",
            "label": "EU Launch Price",
            "data_type": "money",
            "scope": "customer",
            "options": {"currency": "eur"},
        },
    )
    assert field.status_code == 201, field.text
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "sku": "HTML-EUR-001",
            "product_name": "Euro product",
            "status": "active",
            "custom_fields": {"price_eur": "119.50"},
        },
    ).json()

    response = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product["id"]], "currency": "eur"},
    )

    assert response.status_code == 200, response.text
    assert "EUR €119.50" in response.text


def test_html_quote_rejects_duplicates_and_archived_products(
    client: TestClient,
    identity_fixture: IdentityFixture,
) -> None:
    headers = _login(client, identity_fixture.owner_username, identity_fixture.password)
    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={"sku": "HTML-ARCHIVED", "product_name": "Archived", "status": "archived"},
    ).json()

    duplicate = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product["id"], product["id"]]},
    )
    assert duplicate.status_code == 422

    archived = client.post(
        "/api/v1/generation-tasks/html-quote",
        headers=headers,
        json={"product_ids": [product["id"]]},
    )
    assert archived.status_code == 400
    assert "有效产品" in archived.json()["message"]
