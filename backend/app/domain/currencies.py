import re

CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")

CURRENCY_SYMBOLS = {
    "CNY": "¥",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "USD": "$",
}


def normalize_currency_code(value: str) -> str:
    currency = value.strip().upper()
    if not CURRENCY_CODE_PATTERN.fullmatch(currency):
        raise ValueError("报价币种必须是三位 ISO 货币代码")
    return currency


def normalize_currency_codes(values: object, *, default: str = "USD") -> list[str]:
    """Normalize and de-duplicate an ordered collection of ISO currency codes."""
    if values is None:
        values = [default]
    if not isinstance(values, (list, tuple)):
        raise ValueError("报价币种必须是数组")
    currencies: list[str] = []
    for value in values:
        currency = normalize_currency_code(str(value))
        if currency not in currencies:
            currencies.append(currency)
    if not currencies:
        raise ValueError("请至少选择一个报价币种")
    if len(currencies) > 12:
        raise ValueError("一次最多选择 12 个报价币种")
    return currencies


def price_field_for_currency(currency: str) -> str:
    """Return the canonical customer price field for an ISO currency code."""
    normalized = normalize_currency_code(currency)
    return "price" if normalized == "JPY" else f"price_{normalized.lower()}"


def currency_symbol(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(normalize_currency_code(currency), "")
