export type CustomerSettings = {
  locale: string;
  currency: string;
  timezone: string;
  settings: Record<string, unknown>;
};

export type Customer = {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  logo_url: string | null;
  status: "active" | "inactive" | "archived";
  default_ppt_template_id: string | null;
  default_xlsx_template_id: string | null;
  settings: CustomerSettings;
  template_bindings: Array<{
    id: string;
    output_template_id: string;
    output_type: "pptx" | "xlsx";
    is_default: boolean;
    settings: Record<string, unknown>;
  }>;
  created_at: string;
  updated_at: string;
};

export type ProductSetItem = {
  product_id: string;
  sku: string;
  product_name: string;
  sort_order: number;
  primary_image_url: string | null;
};

export type ProductSet = {
  id: string;
  tenant_id: string;
  customer_id: string | null;
  name: string;
  description: string | null;
  status: "active" | "archived";
  items: ProductSetItem[];
  created_at: string;
  updated_at: string;
};

export type GenerationTask = {
  id: string;
  tenant_id: string;
  name: string;
  status: "queued" | "processing" | "completed" | "failed";
  output_type: "pptx" | "xlsx";
  customer_id: string;
  customer_name: string;
  product_set_id: string | null;
  product_set_name: string | null;
  output_template_version_id: string;
  template_name: string;
  template_version_number: number;
  product_count: number;
  output_filename: string | null;
  download_url: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};
