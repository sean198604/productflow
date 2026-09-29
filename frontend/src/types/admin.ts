export type AdminOverview = {
  counts: Record<string, number>;
};

export type AdminTenant = {
  id: string;
  name: string;
  slug: string;
  status: string;
  user_count: number;
  product_count: number;
  import_job_count: number;
  file_count: number;
  created_at: string;
};

export type AdminUser = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  username: string;
  email: string;
  role: string;
  is_platform_admin: boolean;
  status: string;
  last_login_at: string | null;
  created_at: string;
};

export type AdminProduct = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  sku: string;
  product_name: string;
  category: string | null;
  brand: string | null;
  status: string;
  image_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminImportJob = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  source_filename: string;
  status: string;
  total_rows: number;
  imported_rows: number;
  conflict_rows: number;
  created_at: string;
  completed_at: string | null;
};

export type AdminFile = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  original_filename: string;
  safe_filename: string;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  created_at: string;
};

export type AdminListResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminDataTable = {
  entity: string;
  items: Record<string, unknown>[];
  total: number;
  page: number;
  page_size: number;
};
