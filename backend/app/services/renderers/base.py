from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


@dataclass(frozen=True, slots=True)
class RenderRequest:
    template_path: Path
    destination: Path
    mapping: dict[str, Any]
    products: list[dict[str, Any]]
    customer: dict[str, Any]
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ResolvedImage:
    payload: bytes
    width: int
    height: int
    mime_type: str
    is_placeholder: bool = False


def product_for_binding(
    binding: dict[str, Any], products: list[dict[str, Any]]
) -> dict[str, Any] | None:
    slot = int(binding.get("product_slot") or 1)
    return products[slot - 1] if 0 < slot <= len(products) else None


def resolve_value(
    binding: dict[str, Any],
    products: list[dict[str, Any]],
    customer: dict[str, Any],
) -> Any:
    source = binding["source"]
    if source == "customer.name":
        value = customer.get("name")
    elif source == "customer.code":
        value = customer.get("code")
    else:
        product = product_for_binding(binding, products)
        value = product.get("fields", {}).get(source) if product else None
    if value is None or value == "":
        value = binding.get("default_value")
    transform = binding.get("transform")
    if value is not None and transform:
        text = str(value)
        if transform == "trim":
            value = text.strip()
        elif transform == "uppercase":
            value = text.upper()
        elif transform == "lowercase":
            value = text.lower()
        elif transform == "normalize_dimension":
            value = " × ".join(part.strip() for part in text.replace("*", "x").split("x"))
    return value


def render_text_runs(
    binding: dict[str, Any],
    products: list[dict[str, Any]],
    customer: dict[str, Any],
    parameters: dict[str, Any],
) -> list[tuple[int, str]]:
    rendered: list[tuple[int, str]] = []
    for item in binding.get("text_runs") or []:
        if not item.get("visible", True):
            rendered.append((int(item["run_index"]), ""))
            continue
        value = resolve_value(item, products, customer)
        text = format_text(item, value, customer=customer, parameters=parameters)
        rendered.append(
            (
                int(item["run_index"]),
                f"{item.get('prefix') or ''}{text}{item.get('suffix') or ''}",
            )
        )
    return rendered


def _number(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_text(
    binding: dict[str, Any],
    value: Any,
    *,
    customer: dict[str, Any],
    parameters: dict[str, Any],
) -> str:
    formatter = binding.get("formatter") or "text"
    if value is None:
        result = ""
    elif formatter in {"number", "integer", "currency", "percent"}:
        number = _number(value)
        if number is None:
            result = str(value)
        elif formatter == "integer":
            result = f"{number:,.0f}"
        elif formatter == "number":
            result = f"{number:,.2f}".rstrip("0").rstrip(".")
        elif formatter == "percent":
            result = f"{number * 100:,.1f}%"
        else:
            currency = (
                parameters.get("currency_symbol")
                or customer.get("settings", {}).get("currency_symbol")
                or {"USD": "$", "EUR": "€", "GBP": "£", "CNY": "¥"}.get(
                    customer.get("currency", "USD"), customer.get("currency", "USD") + " "
                )
            )
            result = f"{currency}{number:,.2f}"
    elif formatter == "date":
        if isinstance(value, (datetime, date)):
            result = value.strftime("%Y-%m-%d")
        else:
            result = str(value)
    else:
        result = str(value)
    label = binding.get("label")
    return f"{label}: {result}" if label else result


def placeholder_png(width: int = 800, height: int = 600) -> bytes:
    width = max(width, 64)
    height = max(height, 48)
    image = Image.new("RGB", (width, height), "#f1f5f9")
    draw = ImageDraw.Draw(image)
    border = max(2, min(width, height) // 100)
    draw.rectangle(
        (border, border, width - border - 1, height - border - 1),
        outline="#94a3b8",
        width=border,
    )
    label = "IMAGE NOT AVAILABLE"
    box = draw.textbbox((0, 0), label)
    draw.text(
        ((width - (box[2] - box[0])) / 2, (height - (box[3] - box[1])) / 2),
        label,
        fill="#64748b",
    )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _image_candidates(source: str, fallback: list[str]) -> list[str]:
    candidates = [source, *fallback]
    seen: set[str] = set()
    return [item for item in candidates if not (item in seen or seen.add(item))]


def resolve_image(
    binding: dict[str, Any],
    products: list[dict[str, Any]],
    customer: dict[str, Any],
    *,
    placeholder_width: int = 800,
    placeholder_height: int = 600,
) -> ResolvedImage:
    source = binding["source"]
    fallback = list(binding.get("fallback") or [])
    for candidate in _image_candidates(source, fallback):
        if candidate == "unmatched_placeholder":
            payload = placeholder_png(placeholder_width, placeholder_height)
            return ResolvedImage(
                payload=payload,
                width=placeholder_width,
                height=placeholder_height,
                mime_type="image/png",
                is_placeholder=True,
            )
        if candidate == "customer.logo":
            logo = customer.get("logo")
            if logo and logo.get("_path"):
                payload = Path(logo["_path"]).read_bytes()
                return ResolvedImage(
                    payload=payload,
                    width=int(logo.get("width") or placeholder_width),
                    height=int(logo.get("height") or placeholder_height),
                    mime_type=logo.get("mime_type") or "image/png",
                )
            continue
        if not candidate.startswith("image."):
            continue
        image_type = candidate.split(".", 1)[1]
        product = product_for_binding(binding, products)
        if product is None:
            continue
        images = list(product.get("images") or [])
        matches = sorted(
            [item for item in images if item.get("image_type") == image_type],
            key=lambda item: item.get("sort_order", 0),
        )
        if matches:
            requested_index = int(binding.get("image_index") or 0)
            selected_index = requested_index if candidate == source else 0
            if selected_index >= len(matches):
                continue
            selected = matches[selected_index]
            payload = Path(selected["_path"]).read_bytes()
            return ResolvedImage(
                payload=payload,
                width=int(selected.get("width") or placeholder_width),
                height=int(selected.get("height") or placeholder_height),
                mime_type=selected.get("mime_type") or "image/png",
            )
    payload = placeholder_png(placeholder_width, placeholder_height)
    return ResolvedImage(
        payload=payload,
        width=placeholder_width,
        height=placeholder_height,
        mime_type="image/png",
        is_placeholder=True,
    )


def as_png(payload: bytes) -> tuple[bytes, int, int]:
    with Image.open(BytesIO(payload)) as source:
        image = source.convert("RGBA" if source.mode in {"RGBA", "LA"} else "RGB")
        width, height = image.size
        output = BytesIO()
        image.save(output, format="PNG")
    return output.getvalue(), width, height
