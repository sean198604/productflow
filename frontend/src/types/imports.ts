export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type ImportTransform =
  | "text"
  | "trim"
  | "uppercase"
  | "lowercase"
  | "decimal"
  | "integer"
  | "boolean"
  | "date"
  | "normalize_dimension";

export type ImportFieldMapping = {
  source: string;
  target: string;
  transform: ImportTransform | null;
  default_value: JsonValue;
  required: boolean;
  validation: Record<string, JsonValue>;
  formatter: string | null;
};

export type ImportMappingConfig = {
  version: string;
  sheet_names: string[] | null;
  header_row: number;
  data_start_row: number;
  fields: ImportFieldMapping[];
};

export type ImportTemplate = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  source_type: "xlsx";
  mapping_config: ImportMappingConfig;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type WorkbookHeader = {
  column: string;
  column_index: number;
  value: string | number | boolean | null;
};

export type SuggestedMapping = {
  source: string;
  source_header: string;
  target: string;
  transform: ImportTransform;
  required: boolean;
  confidence: number;
  method: string;
};

export type WorkbookSheetAnalysis = {
  name: string;
  max_row: number;
  max_column: number;
  merged_cells: string[];
  headers: WorkbookHeader[];
  sample_rows: Array<{
    row: number;
    cells: Record<string, JsonValue>;
    formats: Record<string, JsonValue>;
  }>;
  images: Array<{
    source_filename: string;
    source_sheet: string;
    source_row: number;
    source_column: number;
    width: number;
    height: number;
    mime_type: string;
    sha256: string;
  }>;
  suggested_mapping: SuggestedMapping[];
};

export type WorkbookAnalysis = {
  workbook_filename: string;
  workbook_sha256: string;
  sheets: WorkbookSheetAnalysis[];
  markitdown: Record<string, JsonValue>;
};

export type ImportRow = {
  id: string;
  source_sheet: string;
  source_row: number;
  source_data: Record<string, JsonValue>;
  mapped_data: Record<string, JsonValue>;
  status: string;
  action: string;
  errors: JsonValue[];
  product_id: string | null;
};

export type ImportImageCandidate = {
  id: string;
  stored_file_id: string;
  matched_product_id: string | null;
  matched_sku: string | null;
  original_filename: string;
  safe_filename: string;
  sha256: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  source_sheet: string;
  source_row: number;
  source_column: number;
  image_type:
    | "main"
    | "white_background"
    | "lifestyle"
    | "detail"
    | "packaging"
    | "certificate"
    | "other";
  is_primary: boolean;
  match_method: string;
  match_confidence: number;
  match_source: string;
  status: string;
  content_url: string;
};

export type ImportJob = {
  id: string;
  tenant_id: string;
  import_template_id: string | null;
  source_file_id: string;
  source_filename: string;
  source_sha256: string;
  status:
    | "analyzing"
    | "analyzed"
    | "preview_ready"
    | "importing"
    | "completed"
    | "failed";
  analysis: WorkbookAnalysis;
  mapping_snapshot: ImportMappingConfig | null;
  duplicate_strategy: "overwrite" | "update_non_empty" | "skip" | null;
  total_rows: number;
  valid_rows: number;
  imported_rows: number;
  skipped_rows: number;
  conflict_rows: number;
  error_message: string | null;
  rows: ImportRow[];
  images: ImportImageCandidate[];
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};
