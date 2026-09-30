from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DefaultField:
    code: str
    label: str
    data_type: str
    scope: str = "customer"
    is_core: bool = False
    is_required: bool = False


DEFAULT_PRODUCT_FIELDS: tuple[DefaultField, ...] = (
    DefaultField("sku", "SKU", "text", is_core=True, is_required=True),
    DefaultField(
        "product_name", "Product Name", "text", is_core=True, is_required=True
    ),
    DefaultField("description", "Description", "text", is_core=True),
    DefaultField("category", "Category", "text", is_core=True),
    DefaultField("brand", "Brand", "text", is_core=True),
    DefaultField("model", "Model", "text"),
    DefaultField("material", "Material", "text"),
    DefaultField("color", "Color", "text"),
    DefaultField("size", "Size", "text"),
    DefaultField("weight", "Weight", "number"),
    DefaultField("voltage", "Voltage", "text"),
    DefaultField("wattage", "Wattage", "number"),
    DefaultField("lumens", "Lumens", "number"),
    DefaultField("battery", "Battery", "text"),
    DefaultField("moq", "MOQ", "number"),
    DefaultField("price", "Launch Price (JPY)", "money"),
    DefaultField("price_usd", "USD Quote", "money"),
    DefaultField("selling_price", "Selling Price", "money"),
    DefaultField("currency", "Currency", "select"),
    DefaultField("packing", "Packing", "text"),
    DefaultField("carton_qty", "Carton Qty", "number"),
    DefaultField("carton_size", "Carton Size", "text"),
    DefaultField("carton_weight", "Carton Weight", "number"),
    DefaultField("certification", "Certification", "multi_select"),
    DefaultField("country_of_origin", "Country of Origin", "text"),
    DefaultField("hs_code", "HS Code", "text"),
    DefaultField("remark", "Remark", "text"),
    DefaultField("supplier_cost", "Supplier Cost", "money", scope="internal"),
    DefaultField("purchase_price", "Purchase Price", "money", scope="internal"),
    DefaultField("margin", "Margin", "number", scope="internal"),
    DefaultField("supplier", "Supplier", "text", scope="internal"),
)

CORE_FIELD_CODES = frozenset(field.code for field in DEFAULT_PRODUCT_FIELDS if field.is_core)
