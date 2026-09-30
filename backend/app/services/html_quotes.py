# ruff: noqa: E501

import base64
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.domain.currencies import currency_symbol, price_field_for_currency
from app.models import (
    FieldDefinition,
    Product,
    ProductFieldValue,
    ProductImage,
    StoredFile,
)
from app.schemas.generation import HtmlQuoteCreateRequest

settings = get_settings()

# The built-in HTML template binds only these customer-visible fields. Internal fields are
# intentionally absent, so supplier cost, purchase price, margin and supplier can never leak.
HTML_QUOTE_FIELD_CODES = (
    "model",
    "material",
    "color",
    "size",
    "weight",
    "battery",
    "moq",
    "selling_price",
    "price",
    "price_usd",
    "currency",
    "packing",
    "certification",
    "country_of_origin",
    "remark",
)
PRICE_FIELD_CODES = ("selling_price", "price", "price_usd")


@dataclass(frozen=True, slots=True)
class HtmlQuoteDocument:
    content: bytes
    filename: str


class HtmlQuoteService:
    """Build a portable, self-contained HTML quotation from an immutable in-memory snapshot."""

    @staticmethod
    def _storage_path(storage_key: str) -> Path:
        root = settings.storage_root.resolve()
        path = (root / storage_key).resolve()
        if root not in path.parents:
            raise BadRequestError("图片存储路径无效。")
        return path

    @staticmethod
    def _data_uri(path: Path, mime_type: str) -> str | None:
        if not path.is_file() or not mime_type.startswith("image/"):
            return None
        return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

    async def create_document(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        payload: HtmlQuoteCreateRequest,
    ) -> HtmlQuoteDocument:
        rows = list(
            await session.scalars(
                select(Product).where(
                    Product.tenant_id == tenant_id,
                    Product.id.in_(payload.product_ids),
                )
            )
        )
        products_by_id = {product.id: product for product in rows}
        missing = [
            product_id
            for product_id in payload.product_ids
            if product_id not in products_by_id
        ]
        if missing:
            raise BadRequestError("部分产品不存在或不属于当前租户。")
        products = [products_by_id[product_id] for product_id in payload.product_ids]
        inactive = [product.sku for product in products if product.status != "active"]
        if inactive:
            raise BadRequestError("HTML 报价单只能使用有效产品：" + "、".join(inactive))

        selected_price_fields = tuple(
            price_field_for_currency(currency) for currency in payload.currencies
        )
        visible_field_codes = tuple(
            dict.fromkeys((*HTML_QUOTE_FIELD_CODES, *selected_price_fields))
        )
        field_rows = (
            await session.execute(
                select(
                    ProductFieldValue.product_id,
                    FieldDefinition.code,
                    FieldDefinition.label,
                    ProductFieldValue.value,
                )
                .join(
                    FieldDefinition,
                    and_(
                        FieldDefinition.tenant_id == ProductFieldValue.tenant_id,
                        FieldDefinition.id == ProductFieldValue.field_definition_id,
                    ),
                )
                .where(
                    ProductFieldValue.tenant_id == tenant_id,
                    ProductFieldValue.product_id.in_(payload.product_ids),
                    FieldDefinition.scope == "customer",
                    FieldDefinition.status == "active",
                    FieldDefinition.code.in_(visible_field_codes),
                )
            )
        ).all()
        fields_by_product: dict[UUID, dict[str, dict[str, Any]]] = defaultdict(dict)
        for product_id, code, label, value in field_rows:
            fields_by_product[product_id][code] = {"label": label, "value": value}

        original_file = aliased(StoredFile, name="original_file")
        processed_file = aliased(StoredFile, name="processed_file")
        image_rows = (
            await session.execute(
                select(ProductImage, original_file, processed_file)
                .join(
                    original_file,
                    and_(
                        original_file.tenant_id == ProductImage.tenant_id,
                        original_file.id == ProductImage.stored_file_id,
                    ),
                )
                .outerjoin(
                    processed_file,
                    and_(
                        processed_file.tenant_id == ProductImage.tenant_id,
                        processed_file.id == ProductImage.processed_file_id,
                    ),
                )
                .where(
                    ProductImage.tenant_id == tenant_id,
                    ProductImage.product_id.in_(payload.product_ids),
                )
                .order_by(
                    ProductImage.product_id,
                    ProductImage.is_primary.desc(),
                    ProductImage.sort_order,
                    ProductImage.created_at,
                )
            )
        ).all()
        images_by_product: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        for image, source_file, transparent_file in image_rows:
            stored_file = transparent_file or source_file
            # Three images are enough for the main image plus two editorial detail views.
            if len(images_by_product[image.product_id]) >= 3:
                continue
            data_uri = self._data_uri(
                self._storage_path(stored_file.storage_key), stored_file.mime_type
            )
            if data_uri:
                images_by_product[image.product_id].append(
                    {
                        "data_uri": data_uri,
                        "type": image.image_type,
                        "is_primary": image.is_primary,
                        "width": stored_file.width,
                        "height": stored_file.height,
                    }
                )

        generated_at = datetime.now(UTC)
        snapshot = [
            {
                "id": str(product.id),
                "sku": product.sku,
                "name": product.product_name,
                "description": product.description,
                "category": product.category,
                "brand": product.brand,
                "fields": fields_by_product[product.id],
                "images": images_by_product[product.id],
            }
            for product in products
        ]
        renderers = {
            "editorial": render_html_quote,
            "journey": render_journey_html_quote,
            "energy": render_energy_html_quote,
        }
        template_key = payload.template_key.value
        html = renderers[template_key](
            products=snapshot,
            title=payload.title,
            subtitle=payload.subtitle,
            quote_currencies=payload.currencies,
            currency_symbols=payload.currency_symbols,
            note=payload.note,
            generated_at=generated_at,
        )
        safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", payload.title).strip("-._")
        filename = f"{(safe_title or 'productflow-quote')[:70]}-{template_key}-{generated_at:%Y%m%d}.html"
        return HtmlQuoteDocument(content=html.encode("utf-8"), filename=filename)


def _plain_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    return str(value).strip()


def _money_text(value: Any, currency: str) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return _plain_value(value)
    decimals = 0 if currency == "JPY" else 2
    return f"{amount:,.{decimals}f}"


def _product_prices(
    product: dict[str, Any],
    quote_currencies: list[str],
    currency_symbols: dict[str, str],
) -> list[str]:
    fields = product["fields"]
    prices: list[str] = []
    for quote_currency in quote_currencies:
        field = fields.get(price_field_for_currency(quote_currency))
        value = _plain_value(field.get("value")) if field else ""
        if not value:
            continue
        symbol = currency_symbols.get(quote_currency) or currency_symbol(quote_currency)
        prices.append(
            f"{quote_currency} {symbol}{_money_text(value, quote_currency)}"
        )
    return prices


def _image_markup(data_uri: str | None, alt: str, class_name: str = "") -> str:
    if not data_uri:
        return '<div class="image-placeholder"><span>PRODUCTFLOW</span></div>'
    return (
        f'<img class="{escape(class_name)}" src="{escape(data_uri)}" '
        f'alt="{escape(alt)}" loading="lazy">'
    )


def render_html_quote(
    *,
    products: list[dict[str, Any]],
    title: str,
    subtitle: str,
    quote_currencies: list[str],
    currency_symbols: dict[str, str],
    note: str | None,
    generated_at: datetime,
) -> str:
    """Render already-authorized snapshot data; all dynamic text is HTML-escaped."""
    title_text = escape(title)
    hero_title_markup = "".join(
        f"<span>{escape(part)}</span>" for part in title.split()
    ) or f"<span>{title_text}</span>"
    subtitle_text = escape(subtitle)
    issue_number = f"PF-{generated_at:%Y%m%d}-{len(products):02d}"
    first = products[0]
    first_images = first["images"]
    hero_image = first_images[0]["data_uri"] if first_images else None
    hero_thumbnails = "".join(
        f'<div class="hero-thumb">{_image_markup(product["images"][0]["data_uri"] if product["images"] else None, product["name"])}</div>'
        for product in products[:3]
    )

    cards: list[str] = []
    for index, product in enumerate(products, start=1):
        fields = product["fields"]
        specs = []
        for code in HTML_QUOTE_FIELD_CODES:
            if code in PRICE_FIELD_CODES or code == "currency":
                continue
            field = fields.get(code)
            value = _plain_value(field.get("value")) if field else ""
            if value:
                specs.append(
                    f'<div class="spec"><dt>{escape(str(field["label"]))}</dt><dd>{escape(value)}</dd></div>'
                )
            if len(specs) == 4:
                break
        if not specs:
            specs = [
                f'<div class="spec"><dt>SKU</dt><dd>{escape(product["sku"])}</dd></div>',
                '<div class="spec"><dt>STATUS</dt><dd>AVAILABLE FOR QUOTE</dd></div>',
            ]
        images = product["images"]
        main_image = images[0]["data_uri"] if images else None
        detail_images = "".join(
            f'<div class="detail-image">{_image_markup(image["data_uri"], product["name"])}</div>'
            for image in images[1:3]
        )
        description = (
            product.get("description") or "精选掌机产品，完整图片资料已随报价单固化。"
        )
        feature_class = " product-card--feature" if index == 1 else ""
        quoted_prices = _product_prices(product, quote_currencies, currency_symbols)
        price_markup = (
            f'<div class="price-row"><span>QUOTED PRICE</span><strong>{escape(" · ".join(quoted_prices))}</strong></div>'
            if quoted_prices
            else ""
        )
        cards.append(
            f"""
            <article class="product-card{feature_class}">
              <div class="product-media">
                <span class="product-index">{index:02d}</span>
                {_image_markup(main_image, product["name"], "product-main-image")}
                <div class="detail-strip">{detail_images}</div>
              </div>
              <div class="product-copy">
                <div class="product-kicker"><span>{escape(product.get("brand") or "NINTENDO ARCHIVE")}</span><span>{escape(product["sku"])}</span></div>
                <h3>{escape(product["name"])}</h3>
                <p class="product-description">{escape(description)}</p>
                <dl class="spec-grid">{"".join(specs)}</dl>
                {price_markup}
              </div>
            </article>
            """
        )

    note_markup = (
        escape(note)
        if note
        else "本报价为产品选型预览；最终价格、交期与贸易条款以双方确认版本为准。"
    )
    return f"""<!doctype html>
<html lang="zh-CN" data-template="editorial">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text} · ProductFlow</title>
  <style>
    :root {{ --ink:#201d1a; --muted:#776f68; --paper:#f2ede5; --cream:#fbf8f3; --clay:#985d49; --clay-dark:#704235; --line:rgba(32,29,26,.14); }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:#d9d1c6; font-family:Inter,"Helvetica Neue",Arial,"Microsoft YaHei",sans-serif; }}
    img {{ display:block; max-width:100%; }}
    .page {{ width:min(1440px,100%); margin:0 auto; background:var(--cream); box-shadow:0 32px 80px rgba(53,38,29,.18); }}
    .toolbar {{ position:fixed; z-index:20; right:22px; bottom:22px; display:flex; gap:8px; padding:8px; border:1px solid rgba(255,255,255,.5); border-radius:999px; background:rgba(32,29,26,.88); backdrop-filter:blur(12px); box-shadow:0 16px 40px rgba(0,0,0,.25); }}
    .toolbar button {{ border:0; border-radius:999px; padding:11px 17px; color:#fff; background:var(--clay); font:700 12px/1 inherit; letter-spacing:.08em; cursor:pointer; }}
    .toolbar a {{ padding:11px 14px; color:#fff; text-decoration:none; font:600 12px/1 inherit; }}
    .hero {{ position:relative; min-height:760px; display:grid; grid-template-columns:52% 48%; overflow:hidden; background:var(--paper); }}
    .hero-left {{ padding:42px 58px 58px; color:#fff; background:var(--clay); }}
    .hero-right {{ padding:42px 58px; background:var(--cream); }}
    .brand-row {{ position:absolute; inset:36px 48px auto; z-index:3; display:flex; align-items:center; justify-content:space-between; color:#fff; }}
    .wordmark {{ font-size:15px; font-weight:900; letter-spacing:.18em; }}
    .nav {{ display:flex; gap:26px; color:var(--ink); font-size:11px; font-weight:800; letter-spacing:.12em; }}
    .hero-title {{ position:absolute; z-index:2; left:56px; top:150px; width:70%; margin:0; color:#fff; font-family:Impact,"Arial Narrow",sans-serif; font-size:clamp(74px,10vw,154px); font-weight:900; line-height:.78; letter-spacing:-.045em; text-transform:uppercase; }}
    .hero-title span {{ display:block; }}
    .hero-product {{ position:absolute; z-index:4; left:40%; top:18%; width:42%; height:62%; filter:drop-shadow(0 40px 34px rgba(61,38,28,.26)); }}
    .hero-product img {{ width:100%; height:100%; object-fit:contain; }}
    .hero-product .image-placeholder {{ height:100%; }}
    .hero-meta {{ position:absolute; z-index:5; left:58px; bottom:54px; width:33%; }}
    .eyebrow {{ margin:0 0 13px; font-size:11px; font-weight:800; letter-spacing:.2em; text-transform:uppercase; }}
    .hero-meta p:last-child {{ margin:0; max-width:420px; color:rgba(255,255,255,.78); font-size:14px; line-height:1.75; }}
    .hero-side {{ position:absolute; z-index:5; right:46px; top:130px; width:108px; display:grid; gap:13px; }}
    .hero-thumb {{ aspect-ratio:1; padding:8px; border:1px solid var(--line); background:#fff; }}
    .hero-thumb img {{ width:100%; height:100%; object-fit:contain; }}
    .hero-thumb .image-placeholder {{ height:100%; }}
    .quote-meta {{ position:absolute; z-index:5; right:52px; bottom:54px; display:grid; grid-template-columns:repeat(2,minmax(110px,1fr)); gap:22px; }}
    .quote-meta div {{ border-top:1px solid var(--line); padding-top:9px; }}
    .quote-meta dt {{ color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.15em; }}
    .quote-meta dd {{ margin:5px 0 0; font-size:13px; font-weight:800; }}
    .intro {{ display:grid; grid-template-columns:.8fr 1.2fr; gap:80px; padding:110px 7vw 80px; }}
    .intro h2 {{ margin:0; max-width:550px; font-family:Georgia,"Songti SC",serif; font-size:clamp(42px,5vw,76px); font-weight:400; line-height:.98; letter-spacing:-.045em; }}
    .intro-copy {{ align-self:end; max-width:620px; }}
    .intro-copy p {{ margin:0; color:var(--muted); font-size:16px; line-height:1.8; }}
    .intro-rule {{ display:flex; justify-content:space-between; margin-top:28px; padding-top:14px; border-top:1px solid var(--line); font-size:10px; font-weight:800; letter-spacing:.15em; }}
    .catalog {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1px; padding:1px; background:var(--line); }}
    .product-card {{ min-width:0; background:var(--cream); break-inside:avoid; }}
    .product-media {{ position:relative; min-height:480px; padding:52px; overflow:hidden; background:var(--paper); }}
    .product-index {{ position:absolute; top:25px; left:28px; color:rgba(32,29,26,.35); font:800 11px/1 monospace; letter-spacing:.18em; }}
    .product-main-image {{ width:100%; height:360px; object-fit:contain; transition:transform .5s ease; }}
    .product-card:hover .product-main-image {{ transform:scale(1.025); }}
    .detail-strip {{ position:absolute; right:20px; bottom:20px; display:flex; gap:8px; }}
    .detail-image {{ width:68px; height:68px; padding:6px; border:1px solid rgba(32,29,26,.12); background:rgba(255,255,255,.78); }}
    .detail-image img {{ width:100%; height:100%; object-fit:contain; }}
    .product-copy {{ padding:34px 38px 42px; }}
    .product-kicker {{ display:flex; justify-content:space-between; gap:12px; color:var(--muted); font-size:9px; font-weight:900; letter-spacing:.16em; }}
    .product-copy h3 {{ margin:16px 0 10px; font-family:Georgia,"Songti SC",serif; font-size:34px; font-weight:400; line-height:1.08; }}
    .product-description {{ min-height:46px; margin:0; color:var(--muted); font-size:13px; line-height:1.7; }}
    .spec-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); margin:28px 0 0; border-top:1px solid var(--line); }}
    .spec {{ padding:13px 10px 13px 0; border-bottom:1px solid var(--line); }}
    .spec dt {{ color:var(--muted); font-size:8px; font-weight:900; letter-spacing:.12em; }}
    .spec dd {{ margin:5px 0 0; font-size:11px; font-weight:700; overflow-wrap:anywhere; }}
    .price-row {{ display:flex; align-items:end; justify-content:space-between; gap:18px; margin-top:28px; }}
    .price-row span {{ color:var(--muted); font-size:9px; font-weight:900; letter-spacing:.14em; }}
    .price-row strong {{ font-family:Georgia,serif; font-size:24px; font-weight:400; }}
    .product-card--feature {{ grid-column:1/-1; display:grid; grid-template-columns:1.25fr .75fr; }}
    .product-card--feature .product-media {{ min-height:640px; }}
    .product-card--feature .product-main-image {{ height:520px; }}
    .product-card--feature .product-copy {{ display:flex; flex-direction:column; justify-content:center; padding:70px; }}
    .product-card--feature .product-copy h3 {{ font-size:58px; }}
    .image-placeholder {{ display:grid; place-items:center; min-height:220px; color:rgba(32,29,26,.28); background:linear-gradient(135deg,#e5ddd2,#f7f2ec); }}
    .image-placeholder span {{ font-size:10px; font-weight:900; letter-spacing:.18em; }}
    .terms {{ display:grid; grid-template-columns:1fr 1fr; gap:80px; padding:100px 7vw; color:#f6efe7; background:var(--ink); }}
    .terms h2 {{ margin:0; font-family:Georgia,"Songti SC",serif; font-size:54px; font-weight:400; line-height:1.05; }}
    .terms p {{ margin:0; color:rgba(255,255,255,.66); font-size:14px; line-height:1.85; }}
    .footer {{ display:flex; justify-content:space-between; gap:20px; padding:28px 7vw; color:rgba(255,255,255,.55); background:var(--ink); border-top:1px solid rgba(255,255,255,.12); font-size:9px; font-weight:800; letter-spacing:.16em; }}
    @media (max-width:900px) {{ .hero {{ min-height:680px; grid-template-columns:62% 38%; }} .hero-title {{ width:80%; font-size:86px; }} .hero-product {{ left:31%; width:53%; }} .hero-side {{ right:20px; width:76px; }} .quote-meta {{ right:22px; grid-template-columns:1fr; }} .intro {{ grid-template-columns:1fr; gap:34px; }} .catalog {{ grid-template-columns:1fr; }} .product-card--feature {{ grid-column:auto; display:block; }} .product-card--feature .product-copy {{ padding:34px 38px 42px; }} .product-card--feature .product-copy h3 {{ font-size:40px; }} }}
    @media (max-width:620px) {{ .hero {{ min-height:760px; grid-template-columns:100%; }} .hero-right {{ display:none; }} .brand-row {{ inset:28px; }} .nav {{ display:none; }} .hero-title {{ left:28px; top:130px; width:90%; font-size:70px; }} .hero-product {{ left:13%; top:29%; width:80%; height:40%; }} .hero-meta {{ left:28px; bottom:34px; width:75%; }} .hero-side,.quote-meta {{ display:none; }} .product-media {{ min-height:360px; padding:36px; }} .product-main-image,.product-card--feature .product-main-image {{ height:290px; }} .product-card--feature .product-media {{ min-height:390px; }} .terms {{ grid-template-columns:1fr; gap:30px; }} }}
    @media print {{ @page {{ size:A4; margin:10mm; }} body {{ background:#fff; }} .page {{ width:100%; box-shadow:none; }} .toolbar {{ display:none; }} .hero {{ min-height:267mm; break-after:page; }} .intro {{ break-after:page; min-height:240mm; align-content:center; }} .catalog {{ display:block; background:#fff; }} .product-card,.product-card--feature {{ display:grid; grid-template-columns:1.05fr .95fr; min-height:132mm; margin-bottom:8mm; border:1px solid var(--line); break-inside:avoid; break-after:page; }} .product-media,.product-card--feature .product-media {{ min-height:132mm; padding:12mm; }} .product-main-image,.product-card--feature .product-main-image {{ height:94mm; }} .product-copy,.product-card--feature .product-copy {{ padding:14mm 10mm; }} .product-copy h3,.product-card--feature .product-copy h3 {{ font-size:30px; }} .terms {{ min-height:245mm; align-content:center; break-before:page; }} }}
  </style>
</head>
<body>
  <div class="toolbar"><a href="#catalog">查看选品</a><button onclick="window.print()">打印 / 导出 PDF</button></div>
  <main class="page">
    <section class="hero">
      <div class="hero-left"></div><div class="hero-right"></div>
      <div class="brand-row"><span class="wordmark">PRODUCTFLOW</span><nav class="nav"><span>COLLECTION</span><span>QUOTATION</span><span>CONTACT</span></nav></div>
      <h1 class="hero-title">{hero_title_markup}</h1>
      <div class="hero-product">{_image_markup(hero_image, first["name"])}</div>
      <div class="hero-meta"><p class="eyebrow">CURATED PRODUCT QUOTATION</p><p>{subtitle_text}</p></div>
      <div class="hero-side">{hero_thumbnails}</div>
      <dl class="quote-meta"><div><dt>ISSUE</dt><dd>{issue_number}</dd></div><div><dt>PRODUCTS</dt><dd>{len(products):02d} ITEMS</dd></div><div><dt>DATE</dt><dd>{generated_at:%Y.%m.%d}</dd></div><div><dt>FORMAT</dt><dd>HTML / PRINT</dd></div></dl>
    </section>
    <section class="intro">
      <h2>Everyday icons,<br>selected with intent.</h2>
      <div class="intro-copy"><p>{subtitle_text}。这份独立 HTML 文件固化了本次选择的产品资料与图片，可离线浏览，也可直接打印或导出为 PDF。</p><div class="intro-rule"><span>PRODUCTFLOW EDITORIAL SERIES</span><span>{len(products):02d} SELECTED PRODUCTS</span></div></div>
    </section>
    <section class="catalog" id="catalog">{"".join(cards)}</section>
    <section class="terms"><h2>Quotation<br>notes.</h2><p>{note_markup}</p></section>
    <footer class="footer"><span>GENERATED BY PRODUCTFLOW</span><span>{issue_number}</span><span>CONFIDENTIAL PRODUCT QUOTATION</span></footer>
  </main>
</body>
</html>"""


def render_journey_html_quote(
    *,
    products: list[dict[str, Any]],
    title: str,
    subtitle: str,
    quote_currencies: list[str],
    currency_symbols: dict[str, str],
    note: str | None,
    generated_at: datetime,
) -> str:
    """Airy journey-inspired quotation with ticket-shaped product records."""
    title_text = escape(title)
    subtitle_text = escape(subtitle)
    issue_number = f"PF-JR-{generated_at:%Y%m%d}-{len(products):02d}"
    first = products[0]
    hero_image = first["images"][0]["data_uri"] if first["images"] else None
    note_markup = escape(note) if note else "本报价为产品选型预览；最终价格、交期与贸易条款以双方确认版本为准。"

    hero_options = "".join(
        f'<div class="route-option"><span>{index:02d}</span>{_image_markup(product["images"][0]["data_uri"] if product["images"] else None, product["name"])}</div>'
        for index, product in enumerate(products[:5], start=1)
    )
    tickets: list[str] = []
    for index, product in enumerate(products, start=1):
        images = product["images"]
        main_image = images[0]["data_uri"] if images else None
        detail_images = "".join(
            f'<div class="ticket-thumb">{_image_markup(image["data_uri"], product["name"])}</div>'
            for image in images[1:3]
        )
        facts: list[str] = []
        for code in HTML_QUOTE_FIELD_CODES:
            if code in PRICE_FIELD_CODES or code == "currency":
                continue
            field = product["fields"].get(code)
            value = _plain_value(field.get("value")) if field else ""
            if value:
                facts.append(f'<span><small>{escape(str(field["label"]))}</small>{escape(value)}</span>')
            if len(facts) == 3:
                break
        if not facts:
            facts = [
                f'<span><small>PRODUCT CODE</small>{escape(product["sku"])}</span>',
                '<span><small>AVAILABILITY</small>READY TO QUOTE</span>',
            ]
        description = product.get("description") or "精选产品资料与三视图已固化在本次报价旅程中。"
        quoted_prices = _product_prices(product, quote_currencies, currency_symbols)
        price_markup = (
            f'<div class="ticket-price"><small>QUOTED PRICE</small><strong>{escape(" · ".join(quoted_prices))}</strong></div>'
            if quoted_prices
            else ""
        )
        tickets.append(
            f"""
            <article class="ticket">
              <div class="ticket-visual">
                <div class="ticket-number">BOARDING {index:02d}</div>
                {_image_markup(main_image, product["name"], "ticket-main-image")}
                <div class="ticket-thumbs">{detail_images}</div>
              </div>
              <div class="ticket-copy">
                <div class="route-line"><span>PRODUCTFLOW</span><span>→</span><span>{escape(product["sku"])}</span></div>
                <h3>{escape(product["name"])}</h3>
                <p>{escape(description)}</p>
                <div class="ticket-facts">{''.join(facts)}</div>
                {price_markup}
              </div>
              <div class="ticket-stub"><span>{issue_number}</span><b>{index:02d}</b><span>HTML PASS</span></div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN" data-template="journey">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text} · ProductFlow Journey</title>
  <style>
    :root {{ --ink:#1b1f0d; --olive:#4e5531; --moss:#8f946b; --sage:#bfc6ba; --sky:#b9cbd0; --paper:#f9f9f7; --line:rgba(27,31,13,.14); }}
    * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; }} body {{ margin:0; color:var(--ink); background:#e5e8e1; font-family:Inter,"Helvetica Neue",Arial,"Microsoft YaHei",sans-serif; }} img {{ display:block; max-width:100%; }}
    .page {{ width:min(1440px,100%); margin:auto; overflow:hidden; background:var(--paper); box-shadow:0 30px 90px rgba(27,31,13,.14); }}
    .toolbar {{ position:fixed; z-index:30; right:22px; bottom:22px; display:flex; gap:8px; padding:7px; border-radius:999px; background:rgba(27,31,13,.9); box-shadow:0 18px 40px rgba(27,31,13,.22); }} .toolbar a,.toolbar button {{ border:0; border-radius:999px; padding:12px 17px; color:#fff; background:transparent; font:800 11px/1 inherit; letter-spacing:.08em; text-decoration:none; cursor:pointer; }} .toolbar button {{ color:var(--ink); background:#dbe3c7; }}
    .hero {{ position:relative; min-height:820px; padding:34px 5vw 0; overflow:hidden; background:linear-gradient(#f9f9f7 0 35%,#eaf0ec 55%,#8ca19b 100%); }}
    .nav {{ position:relative; z-index:8; display:grid; grid-template-columns:1fr auto 1fr; align-items:center; }} .brand {{ font-size:15px; font-weight:950; letter-spacing:-.04em; }} .nav-links {{ display:flex; gap:6px; padding:5px; border-radius:999px; background:rgba(191,198,186,.42); }} .nav-links span {{ padding:8px 14px; border-radius:999px; font-size:10px; font-weight:800; }} .nav-links span:first-child {{ background:#fff; }} .nav-meta {{ justify-self:end; font-size:10px; font-weight:900; letter-spacing:.12em; }}
    .hero-copy {{ position:relative; z-index:7; width:min(760px,80%); margin:100px auto 0; text-align:center; }} .hero-copy .eyebrow {{ font-size:10px; font-weight:900; letter-spacing:.18em; }} .hero-copy h1 {{ margin:18px 0 12px; font-family:Georgia,"Songti SC",serif; font-size:clamp(58px,7vw,104px); font-weight:400; line-height:.92; letter-spacing:-.06em; }} .hero-copy p {{ margin:0 auto; max-width:560px; color:#68705b; font-size:14px; line-height:1.75; }}
    .landscape {{ position:absolute; inset:auto 0 0; height:460px; }} .hill {{ position:absolute; bottom:-120px; width:70%; height:380px; border-radius:55% 55% 0 0; filter:saturate(.82); }} .hill-a {{ left:-15%; background:#718152; transform:rotate(7deg); }} .hill-b {{ right:-20%; height:420px; background:#4e653d; transform:rotate(-8deg); }} .hill-c {{ left:22%; bottom:-210px; width:62%; background:#9cab79; }}
    .hero-product {{ position:absolute; z-index:5; left:50%; bottom:98px; width:390px; height:330px; padding:24px; border:1px solid rgba(255,255,255,.75); border-radius:50% 50% 24px 24px; background:rgba(249,249,247,.9); box-shadow:0 28px 70px rgba(27,31,13,.2); transform:translateX(-50%); backdrop-filter:blur(12px); }} .hero-product img {{ width:100%; height:100%; object-fit:contain; }} .hero-product .image-placeholder {{ height:100%; }}
    .route-options {{ position:absolute; z-index:7; left:50%; bottom:26px; display:flex; gap:12px; transform:translateX(-50%); }} .route-option {{ position:relative; width:58px; height:58px; padding:6px; border:1px solid rgba(255,255,255,.6); border-radius:50%; background:rgba(249,249,247,.7); }} .route-option img {{ width:100%; height:100%; border-radius:50%; object-fit:contain; }} .route-option span {{ position:absolute; top:-5px; right:-3px; display:grid; width:18px; height:18px; place-items:center; border-radius:50%; color:#fff; background:var(--ink); font-size:7px; font-weight:900; }}
    .search-card {{ position:relative; z-index:9; display:grid; grid-template-columns:repeat(3,1fr) auto; width:min(1120px,90%); margin:-34px auto 0; padding:11px 12px 11px 30px; border-radius:20px; background:#fff; box-shadow:0 20px 55px rgba(27,31,13,.16); }} .search-card div {{ padding:10px 24px; border-right:1px solid var(--line); }} .search-card small {{ display:block; color:#7a806e; font-size:8px; font-weight:900; letter-spacing:.14em; }} .search-card strong {{ display:block; margin-top:5px; font-size:13px; }} .search-card a {{ align-self:stretch; display:grid; place-items:center; padding:0 28px; border-radius:14px; color:#fff; background:var(--olive); font-size:11px; font-weight:900; text-decoration:none; }}
    .intro {{ display:grid; grid-template-columns:.9fr 1.1fr; gap:90px; padding:130px 7vw 90px; }} .intro h2 {{ margin:0; font-family:Georgia,"Songti SC",serif; font-size:clamp(42px,5vw,72px); font-weight:400; line-height:1; letter-spacing:-.05em; }} .intro p {{ align-self:end; margin:0; color:#69705e; font-size:15px; line-height:1.9; }}
    .tickets {{ padding:0 5vw 100px; }} .ticket {{ position:relative; display:grid; grid-template-columns:44% 1fr 90px; min-height:440px; margin:0 0 28px; overflow:hidden; border:1px solid var(--line); border-radius:28px; background:#fff; break-inside:avoid; box-shadow:0 12px 34px rgba(27,31,13,.06); }} .ticket::before,.ticket::after {{ content:""; position:absolute; z-index:4; right:76px; width:26px; height:26px; border-radius:50%; background:var(--paper); }} .ticket::before {{ top:-13px; }} .ticket::after {{ bottom:-13px; }}
    .ticket-visual {{ position:relative; min-width:0; padding:48px; background:linear-gradient(145deg,#dfe6de,#b9c8bd); }} .ticket-number {{ position:absolute; top:24px; left:26px; font-size:9px; font-weight:950; letter-spacing:.16em; }} .ticket-main-image {{ width:100%; height:300px; object-fit:contain; filter:drop-shadow(0 20px 18px rgba(27,31,13,.14)); }} .ticket-thumbs {{ position:absolute; right:20px; bottom:18px; display:flex; gap:7px; }} .ticket-thumb {{ width:60px; height:60px; padding:6px; border-radius:50%; background:rgba(255,255,255,.72); }} .ticket-thumb img {{ width:100%; height:100%; border-radius:50%; object-fit:contain; }}
    .ticket-copy {{ display:flex; flex-direction:column; justify-content:center; padding:48px 56px; }} .route-line {{ display:flex; align-items:center; gap:16px; color:var(--olive); font-size:9px; font-weight:950; letter-spacing:.14em; }} .ticket-copy h3 {{ margin:18px 0 10px; font-family:Georgia,"Songti SC",serif; font-size:42px; font-weight:400; line-height:1.06; }} .ticket-copy>p {{ margin:0; color:#707667; font-size:13px; line-height:1.7; }} .ticket-facts {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:28px; }} .ticket-facts span {{ padding-top:12px; border-top:1px solid var(--line); font-size:10px; font-weight:800; overflow-wrap:anywhere; }} .ticket-facts small,.ticket-price small {{ display:block; margin-bottom:5px; color:#8a907f; font-size:7px; font-weight:950; letter-spacing:.12em; }} .ticket-price {{ display:flex; align-items:end; justify-content:space-between; gap:16px; margin-top:34px; }} .ticket-price strong {{ font-family:Georgia,serif; font-size:24px; font-weight:400; }}
    .ticket-stub {{ display:flex; flex-direction:column; align-items:center; justify-content:space-around; border-left:1px dashed rgba(27,31,13,.28); color:var(--olive); background:#eef1e8; writing-mode:vertical-rl; }} .ticket-stub span {{ font-size:8px; font-weight:900; letter-spacing:.16em; }} .ticket-stub b {{ font:400 34px/1 Georgia,serif; }}
    .terms {{ display:grid; grid-template-columns:1fr 1.2fr; gap:80px; padding:90px 8vw; color:#fff; background:var(--ink); }} .terms h2 {{ margin:0; font-family:Georgia,"Songti SC",serif; font-size:52px; font-weight:400; }} .terms p {{ margin:0; color:rgba(255,255,255,.65); font-size:14px; line-height:1.9; }} .footer {{ display:flex; justify-content:space-between; padding:26px 8vw; color:#767d64; background:#f0f2eb; font-size:9px; font-weight:900; letter-spacing:.14em; }} .image-placeholder {{ display:grid; min-height:160px; place-items:center; color:#77806a; background:#dce2d8; font-size:9px; font-weight:900; letter-spacing:.16em; }}
    @media(max-width:900px) {{ .ticket {{ grid-template-columns:1fr; }} .ticket-stub {{ display:none; }} .ticket-copy {{ padding:36px; }} .search-card {{ grid-template-columns:1fr 1fr; }} .search-card a {{ min-height:56px; }} .intro {{ grid-template-columns:1fr; gap:30px; }} }} @media(max-width:620px) {{ .hero {{ min-height:760px; }} .nav-links,.nav-meta {{ display:none; }} .nav {{ grid-template-columns:1fr; }} .hero-copy {{ width:96%; margin-top:90px; }} .hero-copy h1 {{ font-size:58px; }} .hero-product {{ width:82%; }} .search-card {{ grid-template-columns:1fr; margin-top:0; border-radius:0; }} .search-card div {{ border-right:0; border-bottom:1px solid var(--line); }} .ticket-visual {{ padding:35px; }} .ticket-main-image {{ height:250px; }} .ticket-copy h3 {{ font-size:34px; }} }}
    @media print {{ @page {{ size:A4; margin:10mm; }} body {{ background:#fff; }} .page {{ width:100%; box-shadow:none; }} .toolbar {{ display:none; }} .hero {{ min-height:267mm; break-after:page; }} .search-card {{ margin-top:-50mm; }} .intro {{ break-after:page; min-height:230mm; align-content:center; }} .tickets {{ padding:0; }} .ticket {{ grid-template-columns:43% 1fr 16mm; min-height:128mm; margin-bottom:8mm; border-radius:5mm; break-after:page; }} .ticket-visual {{ padding:10mm; }} .ticket-main-image {{ height:86mm; }} .ticket-copy {{ padding:10mm; }} .ticket-copy h3 {{ font-size:28px; }} .terms {{ min-height:245mm; align-content:center; break-before:page; }} }}
  </style>
</head>
<body>
  <div class="toolbar"><a href="#catalog">查看路线</a><button onclick="window.print()">打印 / 导出 PDF</button></div>
  <main class="page">
    <section class="hero"><nav class="nav"><span class="brand">ProductFlow</span><div class="nav-links"><span>Home</span><span>Collection</span><span>Quote</span></div><span class="nav-meta">CURATED JOURNEY</span></nav><div class="hero-copy"><div class="eyebrow">ONE COLLECTION · EVERY PRODUCT</div><h1>{title_text}</h1><p>{subtitle_text}</p></div><div class="landscape"><div class="hill hill-a"></div><div class="hill hill-b"></div><div class="hill hill-c"></div></div><div class="hero-product">{_image_markup(hero_image, first["name"])}</div><div class="route-options">{hero_options}</div></section>
    <section class="search-card"><div><small>COLLECTION</small><strong>{title_text}</strong></div><div><small>PRODUCTS</small><strong>{len(products):02d} SELECTED</strong></div><div><small>ISSUED</small><strong>{generated_at:%Y.%m.%d}</strong></div><a href="#catalog">EXPLORE QUOTE →</a></section>
    <section class="intro"><h2>A thoughtful route<br>through every product.</h2><p>{subtitle_text}。产品、图片与报价信息已经按本次选择固化到独立 HTML 文件，离线打开仍能保持完整视觉与内容。</p></section>
    <section class="tickets" id="catalog">{''.join(tickets)}</section>
    <section class="terms"><h2>Before you<br>depart.</h2><p>{note_markup}</p></section><footer class="footer"><span>PRODUCTFLOW JOURNEY SERIES</span><span>{issue_number}</span><span>CONFIDENTIAL QUOTATION</span></footer>
  </main>
</body>
</html>"""


def render_energy_html_quote(
    *,
    products: list[dict[str, Any]],
    title: str,
    subtitle: str,
    quote_currencies: list[str],
    currency_symbols: dict[str, str],
    note: str | None,
    generated_at: datetime,
) -> str:
    """Bold performance-inspired quotation with energetic product compositions."""
    title_text = escape(title)
    subtitle_text = escape(subtitle)
    issue_number = f"PF-NRG-{generated_at:%Y%m%d}-{len(products):02d}"
    first = products[0]
    hero_image = first["images"][0]["data_uri"] if first["images"] else None
    hero_title_markup = "".join(
        f"<span>{escape(part)}</span>" for part in title.split()
    ) or f"<span>{title_text}</span>"
    note_markup = escape(note) if note else "本报价为产品选型预览；最终价格、交期与贸易条款以双方确认版本为准。"
    benefit_items = "".join(
        f'<div class="benefit"><div>{_image_markup(product["images"][0]["data_uri"] if product["images"] else None, product["name"])}</div><strong>{escape(product["name"])}</strong><span>{escape(product["sku"])}</span></div>'
        for product in products[:5]
    )

    cards: list[str] = []
    for index, product in enumerate(products, start=1):
        images = product["images"]
        main_image = images[0]["data_uri"] if images else None
        detail_images = "".join(
            f'<div class="energy-thumb">{_image_markup(image["data_uri"], product["name"])}</div>'
            for image in images[1:3]
        )
        facts: list[str] = []
        for code in HTML_QUOTE_FIELD_CODES:
            if code in PRICE_FIELD_CODES or code == "currency":
                continue
            field = product["fields"].get(code)
            value = _plain_value(field.get("value")) if field else ""
            if value:
                facts.append(f'<span><small>{escape(str(field["label"]))}</small>{escape(value)}</span>')
            if len(facts) == 3:
                break
        if not facts:
            facts = [
                f'<span><small>SKU</small>{escape(product["sku"])}</span>',
                '<span><small>STATUS</small>QUOTE READY</span>',
                f'<span><small>IMAGES</small>{len(images):02d} VIEWS</span>',
            ]
        description = product.get("description") or "高冲击力产品展示，完整三视图随报价文件一并固化。"
        quoted_prices = _product_prices(product, quote_currencies, currency_symbols)
        price_markup = (
            f'<div class="energy-price"><small>QUOTED PRICE</small><strong>{escape(" · ".join(quoted_prices))}</strong></div>'
            if quoted_prices
            else ""
        )
        cards.append(
            f"""
            <article class="energy-card">
              <div class="energy-copy"><span class="energy-index">DROP {index:02d}</span><h3>{escape(product["name"])}</h3><p>{escape(description)}</p><div class="energy-facts">{''.join(facts)}</div>{price_markup}</div>
              <div class="energy-visual"><span class="burst">{index:02d}</span>{_image_markup(main_image, product["name"], "energy-main-image")}<div class="energy-thumbs">{detail_images}</div></div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN" data-template="energy">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text} · ProductFlow Energy</title>
  <style>
    :root {{ --ink:#0c0302; --brown:#42170d; --orange:#fa4308; --red:#cf280f; --yellow:#f4db2c; --cream:#fff8ec; --green:#91a93d; }}
    * {{ box-sizing:border-box; }} html {{ scroll-behavior:smooth; }} body {{ margin:0; color:var(--ink); background:#2c0e08; font-family:Impact,"Arial Narrow",Arial,"Microsoft YaHei",sans-serif; }} img {{ display:block; max-width:100%; }} .page {{ width:min(1440px,100%); margin:auto; overflow:hidden; background:var(--cream); box-shadow:0 30px 80px rgba(0,0,0,.38); }}
    .toolbar {{ position:fixed; z-index:30; right:22px; bottom:22px; display:flex; gap:8px; padding:7px; border:2px solid #fff; border-radius:999px; background:var(--ink); box-shadow:0 16px 38px rgba(0,0,0,.3); }} .toolbar a,.toolbar button {{ border:0; padding:11px 16px; color:#fff; background:transparent; font:800 11px/1 Arial,sans-serif; text-decoration:none; cursor:pointer; }} .toolbar button {{ border-radius:999px; color:var(--ink); background:var(--yellow); }}
    .hero {{ position:relative; min-height:840px; overflow:hidden; color:#fff; background:var(--orange); }} .hero::after {{ content:""; position:absolute; z-index:2; inset:auto 0 -1px; height:28px; background:var(--cream); clip-path:polygon(0 100%,0 45%,2% 0,4% 45%,6% 0,8% 45%,10% 0,12% 45%,14% 0,16% 45%,18% 0,20% 45%,22% 0,24% 45%,26% 0,28% 45%,30% 0,32% 45%,34% 0,36% 45%,38% 0,40% 45%,42% 0,44% 45%,46% 0,48% 45%,50% 0,52% 45%,54% 0,56% 45%,58% 0,60% 45%,62% 0,64% 45%,66% 0,68% 45%,70% 0,72% 45%,74% 0,76% 45%,78% 0,80% 45%,82% 0,84% 45%,86% 0,88% 45%,90% 0,92% 45%,94% 0,96% 45%,98% 0,100% 45%,100% 100%); }}
    .nav {{ position:relative; z-index:7; display:flex; align-items:center; justify-content:space-between; padding:28px 5vw; color:#fff; background:var(--brown); }} .brand {{ font:900 28px/1 Georgia,serif; letter-spacing:-.08em; }} .nav div {{ display:flex; gap:28px; font:900 10px/1 Arial,sans-serif; letter-spacing:.1em; }} .nav-meta {{ padding:10px 16px; border:1px solid rgba(255,255,255,.45); font:900 9px/1 Arial,sans-serif; letter-spacing:.12em; }}
    .hero-grid {{ position:relative; z-index:4; display:grid; grid-template-columns:1.1fr .9fr; min-height:720px; padding:72px 5vw 60px; }} .hero-copy {{ position:relative; z-index:6; align-self:center; }} .hero-copy .eyebrow {{ display:inline-block; padding:9px 13px; color:var(--ink); background:var(--yellow); font:900 10px/1 Arial,sans-serif; letter-spacing:.16em; transform:rotate(-2deg); }} .hero-copy h1 {{ margin:20px 0 14px; font-size:clamp(82px,10vw,164px); line-height:.74; letter-spacing:-.055em; text-transform:uppercase; }} .hero-copy h1 span {{ display:block; }} .hero-copy h1 span:nth-child(2) {{ color:var(--yellow); }} .hero-copy p {{ max-width:540px; margin:0; font:700 15px/1.65 Arial,"Microsoft YaHei",sans-serif; }}
    .hero-visual {{ position:relative; display:grid; place-items:center; }} .hero-product {{ position:relative; z-index:5; width:94%; height:560px; padding:24px; transform:rotate(4deg); filter:drop-shadow(24px 32px 0 rgba(66,23,13,.55)); }} .hero-product img {{ width:100%; height:100%; object-fit:contain; }} .hero-product .image-placeholder {{ height:100%; }} .hero-ring {{ position:absolute; width:520px; height:520px; border:80px solid rgba(244,219,44,.94); border-radius:50%; }} .badge {{ position:absolute; z-index:8; display:grid; width:112px; height:112px; place-items:center; border:3px solid var(--ink); border-radius:50%; color:var(--ink); background:var(--yellow); font-size:31px; line-height:.82; text-align:center; transform:rotate(9deg); }} .badge small {{ display:block; font:900 8px/1 Arial,sans-serif; letter-spacing:.1em; }} .badge-a {{ top:45px; right:20px; }} .badge-b {{ left:0; bottom:38px; color:#fff; background:var(--brown); transform:rotate(-8deg); }}
    .benefits {{ display:grid; grid-template-columns:repeat(5,1fr); gap:22px; padding:80px 6vw 100px; background:var(--cream); }} .benefit {{ min-width:0; text-align:center; }} .benefit>div {{ width:150px; height:150px; margin:auto; padding:20px; border:3px solid var(--ink); border-radius:50%; background:var(--yellow); transition:transform .25s ease; }} .benefit:nth-child(even)>div {{ background:#efbca9; }} .benefit:hover>div {{ transform:rotate(5deg) scale(1.04); }} .benefit img {{ width:100%; height:100%; border-radius:50%; object-fit:contain; }} .benefit strong {{ display:block; margin-top:17px; overflow:hidden; font-size:22px; line-height:1; text-overflow:ellipsis; white-space:nowrap; }} .benefit span {{ display:block; margin-top:6px; font:900 9px/1 Arial,sans-serif; letter-spacing:.12em; }}
    .manifesto {{ display:grid; grid-template-columns:1fr .8fr; gap:80px; align-items:end; padding:90px 6vw; color:#fff; background:var(--brown); }} .manifesto h2 {{ margin:0; font-size:clamp(62px,8vw,124px); line-height:.78; letter-spacing:-.04em; text-transform:uppercase; }} .manifesto h2 em {{ color:var(--yellow); font-style:normal; }} .manifesto p {{ margin:0; font:700 15px/1.8 Arial,"Microsoft YaHei",sans-serif; color:rgba(255,255,255,.72); }}
    .catalog {{ background:var(--ink); }} .energy-card {{ display:grid; grid-template-columns:.8fr 1.2fr; min-height:650px; overflow:hidden; break-inside:avoid; }} .energy-card:nth-child(4n+1) {{ background:var(--orange); }} .energy-card:nth-child(4n+2) {{ background:var(--yellow); }} .energy-card:nth-child(4n+3) {{ background:#efbca9; }} .energy-card:nth-child(4n) {{ background:var(--green); }} .energy-copy {{ display:flex; flex-direction:column; justify-content:center; padding:70px 6vw; }} .energy-index {{ width:max-content; padding:7px 10px; border:2px solid var(--ink); font:900 9px/1 Arial,sans-serif; letter-spacing:.14em; }} .energy-copy h3 {{ margin:24px 0 14px; font-size:clamp(50px,6vw,92px); line-height:.8; letter-spacing:-.04em; text-transform:uppercase; overflow-wrap:anywhere; }} .energy-copy>p {{ margin:0; max-width:500px; font:700 13px/1.7 Arial,"Microsoft YaHei",sans-serif; }} .energy-facts {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:35px; }} .energy-facts span {{ padding-top:12px; border-top:2px solid var(--ink); font:900 11px/1.3 Arial,sans-serif; overflow-wrap:anywhere; }} .energy-facts small,.energy-price small {{ display:block; margin-bottom:5px; font-size:7px; letter-spacing:.12em; }} .energy-price {{ display:flex; align-items:end; justify-content:space-between; margin-top:34px; padding-top:15px; border-top:3px solid var(--ink); }} .energy-price strong {{ font-size:29px; font-weight:400; }}
    .energy-visual {{ position:relative; display:grid; min-width:0; place-items:center; padding:50px; }} .energy-main-image {{ position:relative; z-index:3; width:100%; height:500px; object-fit:contain; filter:drop-shadow(24px 26px 0 rgba(12,3,2,.24)); transform:rotate(3deg); }} .energy-card:nth-child(even) .energy-main-image {{ transform:rotate(-3deg); }} .burst {{ position:absolute; top:44px; right:44px; z-index:4; display:grid; width:110px; height:110px; place-items:center; color:#fff; background:var(--ink); font-size:42px; clip-path:polygon(50% 0,61% 21%,82% 8%,80% 32%,100% 35%,82% 51%,97% 68%,73% 70%,76% 94%,55% 81%,43% 100%,35% 77%,12% 89%,19% 64%,0 55%,23% 43%,5% 25%,30% 25%); }} .energy-thumbs {{ position:absolute; z-index:5; right:34px; bottom:32px; display:flex; gap:8px; }} .energy-thumb {{ width:78px; height:78px; padding:7px; border:3px solid var(--ink); background:var(--cream); }} .energy-thumb img {{ width:100%; height:100%; object-fit:contain; }}
    .terms {{ display:grid; grid-template-columns:1fr 1fr; gap:80px; padding:100px 7vw; color:#fff; background:var(--brown); }} .terms h2 {{ margin:0; color:var(--yellow); font-size:74px; line-height:.78; text-transform:uppercase; }} .terms p {{ margin:0; font:700 14px/1.9 Arial,"Microsoft YaHei",sans-serif; color:rgba(255,255,255,.72); }} .footer {{ display:flex; justify-content:space-between; padding:28px 7vw; color:#fff; background:var(--ink); font:900 9px/1 Arial,sans-serif; letter-spacing:.15em; }} .image-placeholder {{ display:grid; min-height:180px; place-items:center; color:#fff; background:rgba(66,23,13,.35); font:900 9px/1 Arial,sans-serif; letter-spacing:.16em; }}
    @media(max-width:920px) {{ .hero-grid,.manifesto,.energy-card {{ grid-template-columns:1fr; }} .hero-copy {{ text-align:center; }} .hero-copy p {{ margin:auto; }} .hero-visual {{ min-height:520px; }} .benefits {{ grid-template-columns:repeat(3,1fr); }} .energy-card {{ min-height:auto; }} .energy-copy {{ order:2; }} }} @media(max-width:620px) {{ .nav div,.nav-meta {{ display:none; }} .hero-copy h1 {{ font-size:76px; }} .hero-product {{ width:100%; height:430px; }} .hero-ring {{ width:350px; height:350px; border-width:52px; }} .benefits {{ grid-template-columns:repeat(2,1fr); }} .benefit>div {{ width:118px; height:118px; }} .manifesto h2 {{ font-size:64px; }} .energy-copy {{ padding:52px 28px; }} .energy-visual {{ padding:34px 20px; }} .energy-main-image {{ height:340px; }} .terms {{ grid-template-columns:1fr; }} }}
    @media print {{ @page {{ size:A4; margin:8mm; }} body {{ background:#fff; }} .page {{ width:100%; box-shadow:none; }} .toolbar {{ display:none; }} .hero {{ min-height:275mm; break-after:page; }} .benefits {{ min-height:250mm; align-content:center; break-after:page; }} .manifesto {{ min-height:250mm; align-content:center; break-after:page; }} .energy-card {{ grid-template-columns:.82fr 1.18fr; min-height:130mm; break-after:page; }} .energy-copy {{ order:initial; padding:12mm; }} .energy-copy h3 {{ font-size:38px; }} .energy-main-image {{ height:100mm; }} .terms {{ min-height:250mm; align-content:center; break-before:page; }} }}
  </style>
</head>
<body>
  <div class="toolbar"><a href="#catalog">查看产品</a><button onclick="window.print()">打印 / 导出 PDF</button></div>
  <main class="page">
    <section class="hero"><nav class="nav"><span class="brand">PF/ENERGY</span><div><span>COLLECTION</span><span>PRODUCTS</span><span>QUOTE</span></div><span class="nav-meta">{issue_number}</span></nav><div class="hero-grid"><div class="hero-copy"><span class="eyebrow">BUILT FOR HIGH IMPACT</span><h1>{hero_title_markup}</h1><p>{subtitle_text}</p></div><div class="hero-visual"><div class="hero-ring"></div><div class="hero-product">{_image_markup(hero_image, first["name"])}</div><div class="badge badge-a"><div>{len(products):02d}<small>PRODUCTS</small></div></div><div class="badge badge-b"><div>03<small>VIEWS EACH</small></div></div></div></div></section>
    <section class="benefits">{benefit_items}</section><section class="manifesto"><h2>Built to<br><em>stand out.</em></h2><p>{subtitle_text}。大胆配色服务于信息层级，所有产品图片仍以 contain 方式保持原始比例，并随独立 HTML 文件完整交付。</p></section>
    <section class="catalog" id="catalog">{''.join(cards)}</section><section class="terms"><h2>Quote<br>notes.</h2><p>{note_markup}</p></section><footer class="footer"><span>PRODUCTFLOW PERFORMANCE SERIES</span><span>{issue_number}</span><span>CONFIDENTIAL QUOTATION</span></footer>
  </main>
</body>
</html>"""
