export type FieldDataType =
  | "text"
  | "number"
  | "money"
  | "date"
  | "boolean"
  | "select"
  | "multi_select"
  | "image";

export type FieldDefinition = {
  id: string;
  code: string;
  label: string;
  data_type: FieldDataType;
  scope: "customer" | "internal";
  is_system: boolean;
  is_core: boolean;
  is_required: boolean;
  options: {
    choices?: string[];
    currency?: string;
    price_basis?: string;
    source_kind?: string;
    sources?: string[];
  };
  sort_order: number;
  status: "active" | "archived";
};

export type Product = {
  id: string;
  tenant_id: string;
  sku: string;
  product_name: string;
  description: string | null;
  category: string | null;
  brand: string | null;
  status: "draft" | "active" | "archived";
  custom_fields: Record<string, string | number | boolean | string[] | null>;
  image_count: number;
  primary_image_url: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductDictionary = {
  id: string;
  kind: "category" | "brand";
  name: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type ProductImage = {
  id: string;
  product_id: string;
  product_sku: string;
  product_name: string;
  image_type:
    | "main"
    | "white_background"
    | "lifestyle"
    | "detail"
    | "packaging"
    | "certificate"
    | "other";
  sort_order: number;
  is_primary: boolean;
  original_filename: string;
  safe_filename: string;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  match_method: string;
  match_confidence: number;
  match_source: string;
  content_url: string;
  processed_content_url: string | null;
  processed_sha256: string | null;
  processed_mime_type: string | null;
  background_removed: boolean;
  created_at: string;
};
