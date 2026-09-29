import { ChevronLeft, ChevronRight, PackageSearch, Plus, Search } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { Product } from "../types/catalog";

type ProductList = { items: Product[]; total: number; page: number; page_size: number };

const statusLabel = { active: "有效", draft: "草稿", archived: "已归档" };

export function ProductsPage() {
  const { reportError } = useGlobalError();
  const [data, setData] = useState<ProductList>({ items: [], total: 0, page: 1, page_size: 20 });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadProducts = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search.trim()) params.set("search", search.trim());
    if (status) params.set("status", status);
    apiRequest<ProductList>(`/products?${params}`)
      .then(setData)
      .catch(() => reportError("产品列表加载失败，请稍后重试。"))
      .finally(() => setLoading(false));
  }, [page, reportError, search, status]);

  useEffect(() => loadProducts(), [loadProducts]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Products"
        title="产品资料"
        description="维护标准字段、自定义字段及产品图片。SKU 在每个租户内保持唯一。"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="size-4" /> 新建产品
          </Button>
        }
      />

      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="搜索 SKU 或产品名称"
              value={search}
              onChange={(event) => { setSearch(event.target.value); setPage(1); }}
            />
          </label>
          <select
            className="input sm:w-40"
            aria-label="产品状态"
            value={status}
            onChange={(event) => { setStatus(event.target.value); setPage(1); }}
          >
            <option value="">全部状态</option>
            <option value="active">有效</option>
            <option value="draft">草稿</option>
            <option value="archived">已归档</option>
          </select>
        </div>
      </Card>

      <div className="table-shell">
        {loading ? (
          <div className="p-12 text-center text-sm text-slate-500">正在加载产品…</div>
        ) : data.items.length ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse text-left">
                <thead className="bg-slate-50/80">
                  <tr className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-3">产品</th>
                    <th className="px-4 py-3">分类 / 品牌</th>
                    <th className="px-4 py-3">图片</th>
                    <th className="px-4 py-3">状态</th>
                    <th className="px-5 py-3 text-right">更新时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((product) => (
                    <tr key={product.id} className="transition-colors hover:bg-slate-50/70">
                      <td className="px-5 py-3.5">
                        <Link to={`/products/${product.id}`} className="flex items-center gap-3">
                          <ProtectedImage src={product.primary_image_url} alt={product.product_name} className="size-12 shrink-0 rounded-lg border border-slate-200" />
                          <span className="min-w-0">
                            <span className="block truncate text-sm font-bold text-slate-900">{product.product_name}</span>
                            <span className="mt-0.5 block font-mono text-[11px] text-slate-500">{product.sku}</span>
                          </span>
                        </Link>
                      </td>
                      <td className="px-4 py-3.5 text-xs text-slate-600">
                        <div>{product.category ?? "未分类"}</div>
                        <div className="mt-0.5 text-slate-400">{product.brand ?? "未设置品牌"}</div>
                      </td>
                      <td className="px-4 py-3.5 text-xs tabular-nums text-slate-600">{product.image_count} 张</td>
                      <td className="px-4 py-3.5">
                        <Badge tone={product.status === "active" ? "green" : product.status === "draft" ? "amber" : "slate"}>
                          {statusLabel[product.status]}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 text-right text-xs text-slate-500">{new Date(product.updated_at).toLocaleDateString("zh-CN")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
              <p className="text-xs text-slate-500">共 {data.total} 个产品</p>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className="size-9 px-0" disabled={page === 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="size-4" /></Button>
                <span className="text-xs font-semibold tabular-nums text-slate-600">第 {page} 页</span>
                <Button variant="secondary" className="size-9 px-0" disabled={page * data.page_size >= data.total} onClick={() => setPage((value) => value + 1)}><ChevronRight className="size-4" /></Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            icon={<PackageSearch className="size-5" />}
            title="没有找到产品"
            description={search || status ? "调整搜索条件后重试。" : "创建第一个产品并开始维护完整资料。"}
            action={!search && !status ? <Button onClick={() => setShowCreate(true)}>创建产品</Button> : undefined}
          />
        )}
      </div>

      {showCreate ? <CreateProductModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); loadProducts(); }} /> : null}
    </div>
  );
}

function CreateProductModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ sku: "", product_name: "", category: "", brand: "", status: "active" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest<Product>("/products", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) });
      onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "产品创建失败。")
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="新建产品" description="先建立核心资料，随后进入详情页维护自定义字段和图片。" onClose={onClose}>
      <form className="space-y-4 p-5" onSubmit={submit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="label">SKU *</span><input className="input" required value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></label>
          <label><span className="label">状态</span><select className="input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option value="active">有效</option><option value="draft">草稿</option></select></label>
        </div>
        <label><span className="label">产品名称 *</span><input className="input" required value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label><span className="label">分类</span><input className="input" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
          <label><span className="label">品牌</span><input className="input" value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></label>
        </div>
        {error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4">
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button type="submit" disabled={submitting}>{submitting ? "正在创建…" : "创建产品"}</Button>
        </div>
      </form>
    </Modal>
  );
}
