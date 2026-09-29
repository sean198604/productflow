export type OutputTemplateType = "pptx" | "xlsx";
export type OutputTemplateStatus = "active" | "archived";
export type OutputTemplateVersionStatus = "needs_mapping" | "ready" | "invalid" | "archived";

export type TemplateObject = {
  object_key: string;
  container: string;
  slide_index?: number;
  sheet_name?: string;
  cell?: string;
  shape_id?: number | null;
  shape_name?: string;
  object_type: string;
  supported: boolean;
  reason: string | null;
  preview: string | number | boolean | null;
  position: Record<string, string | number | null>;
  size: Record<string, string | number | null>;
  font: Record<string, string | number | boolean | null>;
};

export type TemplateValidationReport = {
  format: OutputTemplateType;
  is_valid: boolean;
  object_count: number;
  parameterizable_count: number;
  unsupported_count: number;
  objects: TemplateObject[];
  warnings: string[];
  errors: string[];
  capabilities: string[];
  unsupported_capabilities: string[];
  template_changed?: boolean;
  fingerprint_message?: string;
  mapped_object_count?: number;
  mapping_verified?: boolean;
};

export type OutputTemplateBinding = {
  object_key: string;
  source: string;
  visible: boolean;
  label: string | null;
  formatter: "text" | "number" | "integer" | "currency" | "percent" | "date" | null;
  default_value: string | number | boolean | null;
  fallback: string[];
  transform: "trim" | "uppercase" | "lowercase" | "normalize_dimension" | null;
  fit: "contain" | "cover" | "stretch" | null;
  position: "center" | "top" | "right" | "bottom" | "left" | null;
  product_slot: number;
  image_index?: number;
  text_runs?: Array<{
    run_index: number;
    source: string;
    visible?: boolean;
    product_slot: number;
    formatter: "text" | "number" | "integer" | "currency" | "percent" | "date" | null;
    default_value: unknown;
    transform: "trim" | "uppercase" | "lowercase" | "normalize_dimension" | null;
    prefix: string;
    suffix: string;
  }>;
  allow_formula: boolean;
};

export type OutputTemplateMapping = {
  version: "1.0";
  template_sha256: string;
  bindings: OutputTemplateBinding[];
};

export type OutputTemplateVersion = {
  id: string;
  version_number: number;
  template_sha256: string;
  original_filename: string;
  safe_filename: string;
  mime_type: string;
  size_bytes: number;
  validation_report: TemplateValidationReport;
  mapping_config: OutputTemplateMapping;
  status: OutputTemplateVersionStatus;
  created_at: string;
  updated_at: string;
};

export type OutputTemplate = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  output_type: OutputTemplateType;
  status: OutputTemplateStatus;
  current_version_number: number;
  current_version: OutputTemplateVersion;
  created_at: string;
  updated_at: string;
};

export type OutputTemplateDetail = OutputTemplate & {
  versions: OutputTemplateVersion[];
};
