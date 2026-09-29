import {
  Building2,
  Database,
  FileArchive,
  FileSpreadsheet,
  Loader2,
  PackageSearch,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { Button } from "../components/ui/button";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui/primitives";
import { apiRequest, ApiError } from "../lib/api";
import { cn } from "../lib/utils";
import type {
  AdminFile,
  AdminDataTable,
  AdminImportJob,
  AdminListResponse,
  AdminOverview,
  AdminProduct,
  AdminTenant,
  AdminUser,
} from "../types/admin";

type Section = "tenants" | "users" | "products" | "import-jobs" | "files";
type AdminData = {
  tenants: AdminListResponse<AdminTenant>;
  users: AdminListResponse<AdminUser>;
  products: AdminListResponse<AdminProduct>;
  "import-jobs": AdminListResponse<AdminImportJob>;
  files: AdminListResponse<AdminFile>;
};

const sections: { key: Section; label: string; icon: typeof Building2 }[] = [
  { key: "tenants", label: "租户", icon: Building2 },
  { key: "users", label: "账号", icon: Users },
  { key: "products", label: "产品", icon: PackageSearch },
  { key: "import-jobs", label: "导入任务", icon: FileSpreadsheet },
  { key: "files", label: "文件", icon: FileArchive },
];

const countLabels: Record<string, string> = {
  tenants: "租户",
  users: "账号",
  customers: "客户",
  customer_settings: "客户设置",
  customer_template_bindings: "客户模板绑定",
  field_definitions: "字段定义",
  products: "产品",
  product_sets: "产品组合",
  product_set_items: "组合产品",
  product_field_values: "字段值",
  stored_files: "文件",
  product_images: "产品图片",
  import_templates: "导入模板",
  import_jobs: "导入任务",
  import_rows: "导入数据行",
  import_image_candidates: "图片候选",
  output_templates: "输出模板",
  output_template_versions: "输出模板版本",
  generation_tasks: "生成任务",
  generation_task_products: "任务产品快照",
};

const rawEntities = [
  ["customers", "客户"],
  ["customer_settings", "客户设置"],
  ["customer_template_bindings", "客户模板绑定"],
  ["field_definitions", "字段定义"],
  ["product_field_values", "产品字段值"],
  ["product_images", "产品图片"],
  ["product_sets", "产品组合"],
  ["product_set_items", "组合产品"],
  ["import_templates", "导入模板"],
  ["import_rows", "导入数据行"],
  ["import_image_candidates", "图片匹配候选"],
  ["output_templates", "输出模板"],
  ["output_template_versions", "输出模板版本"],
  ["generation_tasks", "生成任务"],
  ["generation_task_products", "任务产品快照"],
] as const;

function dateTime(value: string | null) {
  return value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "—";
}

function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function TenantCell({ name, slug }: { name: string; slug: string }) {
  return (
    <div>
      <p className="font-semibold text-slate-900">{name}</p>
      <p className="mt-0.5 font-mono text-[11px] text-slate-400">{slug}</p>
    </div>
  );
}

function TableShell({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>;
}

function DataTable({ section, data }: { section: Section; data: AdminData[Section] }) {
  if (data.items.length === 0) {
    return <EmptyState icon={<Database className="size-5" />} title="暂无数据" description="该数据表目前没有记录。" />;
  }

  if (section === "tenants") {
    const items = data.items as AdminTenant[];
    return (
      <TableShell><table className="w-full min-w-[850px] text-left"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">租户</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">账号</th><th className="px-4 py-3">产品</th><th className="px-4 py-3">导入</th><th className="px-4 py-3">文件</th><th className="px-5 py-3">创建时间</th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.id}><td className="px-5 py-3"><TenantCell name={item.name} slug={item.slug} /></td><td className="px-4 py-3"><Badge tone={item.status === "active" ? "green" : "slate"}>{item.status}</Badge></td><td className="px-4 py-3 text-sm">{item.user_count}</td><td className="px-4 py-3 text-sm">{item.product_count}</td><td className="px-4 py-3 text-sm">{item.import_job_count}</td><td className="px-4 py-3 text-sm">{item.file_count}</td><td className="px-5 py-3 text-xs text-slate-500">{dateTime(item.created_at)}</td></tr>)}</tbody></table></TableShell>
    );
  }
  if (section === "users") {
    const items = data.items as AdminUser[];
    return (
      <TableShell><table className="w-full min-w-[940px] text-left"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">账号</th><th className="px-4 py-3">所属租户</th><th className="px-4 py-3">角色</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">最近登录</th><th className="px-5 py-3">创建时间</th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.id}><td className="px-5 py-3"><p className="font-semibold text-slate-900">{item.username}</p><p className="text-xs text-slate-500">{item.email}</p></td><td className="px-4 py-3"><TenantCell name={item.tenant_name} slug={item.tenant_slug} /></td><td className="px-4 py-3"><Badge tone={item.is_platform_admin ? "purple" : "blue"}>{item.is_platform_admin ? "平台管理员" : item.role}</Badge></td><td className="px-4 py-3"><Badge tone={item.status === "active" ? "green" : "red"}>{item.status}</Badge></td><td className="px-4 py-3 text-xs text-slate-500">{dateTime(item.last_login_at)}</td><td className="px-5 py-3 text-xs text-slate-500">{dateTime(item.created_at)}</td></tr>)}</tbody></table></TableShell>
    );
  }
  if (section === "products") {
    const items = data.items as AdminProduct[];
    return (
      <TableShell><table className="w-full min-w-[940px] text-left"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">产品</th><th className="px-4 py-3">所属租户</th><th className="px-4 py-3">分类 / 品牌</th><th className="px-4 py-3">图片</th><th className="px-4 py-3">状态</th><th className="px-5 py-3">更新时间</th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.id}><td className="px-5 py-3"><p className="font-semibold text-slate-900">{item.product_name}</p><p className="font-mono text-xs text-slate-500">{item.sku}</p></td><td className="px-4 py-3"><TenantCell name={item.tenant_name} slug={item.tenant_slug} /></td><td className="px-4 py-3 text-xs text-slate-500">{[item.category, item.brand].filter(Boolean).join(" / ") || "—"}</td><td className="px-4 py-3 text-sm">{item.image_count}</td><td className="px-4 py-3"><Badge tone={item.status === "active" ? "green" : "slate"}>{item.status}</Badge></td><td className="px-5 py-3 text-xs text-slate-500">{dateTime(item.updated_at)}</td></tr>)}</tbody></table></TableShell>
    );
  }
  if (section === "import-jobs") {
    const items = data.items as AdminImportJob[];
    return (
      <TableShell><table className="w-full min-w-[940px] text-left"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">源文件</th><th className="px-4 py-3">所属租户</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">总行数</th><th className="px-4 py-3">已导入 / 冲突</th><th className="px-5 py-3">创建时间</th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.id}><td className="px-5 py-3 font-semibold text-slate-900">{item.source_filename}</td><td className="px-4 py-3"><TenantCell name={item.tenant_name} slug={item.tenant_slug} /></td><td className="px-4 py-3"><Badge tone={item.status === "completed" ? "green" : "blue"}>{item.status}</Badge></td><td className="px-4 py-3 text-sm">{item.total_rows}</td><td className="px-4 py-3 text-sm">{item.imported_rows} / {item.conflict_rows}</td><td className="px-5 py-3 text-xs text-slate-500">{dateTime(item.created_at)}</td></tr>)}</tbody></table></TableShell>
    );
  }
  const items = data.items as AdminFile[];
  return (
    <TableShell><table className="w-full min-w-[980px] text-left"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">文件</th><th className="px-4 py-3">所属租户</th><th className="px-4 py-3">类型</th><th className="px-4 py-3">大小</th><th className="px-4 py-3">尺寸</th><th className="px-4 py-3">SHA256</th><th className="px-5 py-3">创建时间</th></tr></thead><tbody className="divide-y divide-slate-100">{items.map((item) => <tr key={item.id}><td className="px-5 py-3"><p className="max-w-64 truncate font-semibold text-slate-900" title={item.original_filename}>{item.original_filename}</p><p className="max-w-64 truncate text-[11px] text-slate-400">{item.safe_filename}</p></td><td className="px-4 py-3"><TenantCell name={item.tenant_name} slug={item.tenant_slug} /></td><td className="px-4 py-3 text-xs text-slate-500">{item.mime_type}</td><td className="px-4 py-3 text-xs">{fileSize(item.size_bytes)}</td><td className="px-4 py-3 text-xs">{item.width && item.height ? `${item.width} × ${item.height}` : "—"}</td><td className="px-4 py-3 font-mono text-[11px] text-slate-400">{item.sha256.slice(0, 12)}…</td><td className="px-5 py-3 text-xs text-slate-500">{dateTime(item.created_at)}</td></tr>)}</tbody></table></TableShell>
  );
}

function AllDataBrowser() {
  const [entity, setEntity] = useState<(typeof rawEntities)[number][0]>("field_definitions");
  const [result, setResult] = useState<AdminDataTable | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    apiRequest<AdminDataTable>(`/admin/data/${entity}?page=1&page_size=100`)
      .then((response) => { if (active) setResult(response); })
      .catch((caught) => {
        if (active) setError(caught instanceof ApiError ? caught.message : "数据表读取失败。");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [entity]);

  return (
    <Card>
      <div className="flex flex-col justify-between gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center">
        <div><h2 className="text-sm font-bold text-slate-900">完整数据表浏览</h2><p className="mt-1 text-xs text-slate-500">查看主列表之外的字段、图片和导入明细，JSON 配置保持完整展示。</p></div>
        <select className="input w-full sm:w-52" value={entity} onChange={(event) => setEntity(event.target.value as (typeof rawEntities)[number][0])} aria-label="选择后台数据表">
          {rawEntities.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      {loading ? <div className="grid min-h-40 place-items-center text-sm text-slate-500"><span className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" />正在读取数据表…</span></div> : null}
      {!loading && error ? <div role="alert" className="m-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
      {!loading && !error && result?.items.length === 0 ? <EmptyState icon={<Database className="size-5" />} title="暂无数据" description="该数据表目前没有记录。" /> : null}
      {!loading && !error && result?.items.length ? (
        <div className="max-h-[36rem] space-y-3 overflow-auto bg-slate-50/60 p-4">
          {result.items.map((item, index) => (
            <details key={String(item.id ?? index)} className="rounded-xl border border-slate-200 bg-white p-4" open={index === 0}>
              <summary className="cursor-pointer text-sm font-semibold text-slate-800">{String(item.tenant_name ?? "未知租户")} · {String(item.code ?? item.name ?? item.original_filename ?? item.id ?? `记录 ${index + 1}`)}</summary>
              <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-4 text-[11px] leading-5 text-slate-200">{JSON.stringify(item, null, 2)}</pre>
            </details>
          ))}
        </div>
      ) : null}
      {!loading && result ? <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500">共 {result.total} 条；当前显示前 {result.page_size} 条。</div> : null}
    </Card>
  );
}

export function AdminPage() {
  const [section, setSection] = useState<Section>("tenants");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [data, setData] = useState<AdminData[Section] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextOverview, nextData] = await Promise.all([
        apiRequest<AdminOverview>("/admin/overview"),
        apiRequest<AdminData[Section]>(`/admin/${section}?page=1&page_size=100`),
      ]);
      setOverview(nextOverview);
      setData(nextData);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "系统数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, [section]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Platform Administration" title="系统后台" description="跨租户查看平台数据。该入口为只读视图，所有业务写入仍受租户 RLS 隔离。" actions={<Button variant="secondary" onClick={() => void load()} disabled={loading}><RefreshCw className={cn("size-4", loading && "animate-spin")} />刷新</Button>} />

      <div className="rounded-xl border border-violet-200 bg-violet-50/80 px-4 py-3 text-sm text-violet-800">
        <div className="flex items-center gap-2 font-semibold"><ShieldCheck className="size-4" />平台管理员只读模式</div>
      </div>

      {overview ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
          {Object.entries(overview.counts).map(([key, value]) => (
            <Card key={key} className="p-4"><p className="text-[11px] font-semibold text-slate-500">{countLabels[key] ?? key}</p><p className="mt-1 text-2xl font-extrabold text-slate-950">{value.toLocaleString()}</p></Card>
          ))}
        </div>
      ) : null}

      <Card>
        <div className="flex gap-1 overflow-x-auto border-b border-slate-100 p-2">
          {sections.map(({ key, label, icon: Icon }) => (
            <button key={key} type="button" onClick={() => setSection(key)} className={cn("inline-flex h-10 shrink-0 items-center gap-2 rounded-lg px-3 text-sm font-semibold", section === key ? "bg-[#1a365d] text-white" : "text-slate-600 hover:bg-slate-100")}><Icon className="size-4" />{label}<span className={cn("rounded-full px-1.5 py-0.5 text-[10px]", section === key ? "bg-white/15" : "bg-slate-100")}>{overview?.counts[key === "files" ? "stored_files" : key] ?? 0}</span></button>
          ))}
        </div>
        {loading ? <div className="grid min-h-56 place-items-center text-sm text-slate-500"><span className="flex items-center gap-2"><Loader2 className="size-4 animate-spin" />正在读取跨租户数据…</span></div> : null}
        {!loading && error ? <div role="alert" className="m-5 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
        {!loading && !error && data ? <DataTable section={section} data={data} /> : null}
        {!loading && data ? <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-500">共 {data.total} 条；当前显示前 {data.page_size} 条。</div> : null}
      </Card>

      <AllDataBrowser />
    </div>
  );
}
