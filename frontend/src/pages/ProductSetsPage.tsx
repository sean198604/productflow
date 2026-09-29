import { ArrowDown, ArrowUp, Layers3, Plus } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { Product } from "../types/catalog";
import type { Customer, ProductSet } from "../types/generation";

type ProductSetList = { items: ProductSet[]; total: number };
type ProductList = { items: Product[]; total: number; page: number; page_size: number };
type CustomerList = { items: Customer[]; total: number };

export function ProductSetsPage() {
  const { reportError } = useGlobalError();
  const [sets, setSets] = useState<ProductSet[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [setPayload, productPayload, customerPayload] = await Promise.all([
        apiRequest<ProductSetList>("/product-sets"),
        apiRequest<ProductList>("/products?page=1&page_size=100&status=active"),
        apiRequest<CustomerList>("/customers"),
      ]);
      setSets(setPayload.items);
      setProducts(productPayload.items);
      setCustomers(customerPayload.items);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "产品组合加载失败。");
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Collections" title="产品组合" description="按报价场景组织产品。一个产品可进入多个组合，组合内顺序会成为生成时的产品槽位顺序。" actions={<Button onClick={() => setShowCreate(true)}><Plus className="size-4" /> 新建组合</Button>} />
      <div className="grid gap-4 sm:grid-cols-3"><Card className="p-4"><p className="text-xs text-slate-500">组合总数</p><p className="mt-2 text-2xl font-black text-slate-950">{sets.length}</p></Card><Card className="p-4"><p className="text-xs text-slate-500">组合产品数</p><p className="mt-2 text-2xl font-black text-blue-700">{sets.reduce((sum, item) => sum + item.items.length, 0)}</p></Card><Card className="p-4"><p className="text-xs text-slate-500">绑定客户</p><p className="mt-2 text-2xl font-black text-emerald-700">{sets.filter((item) => item.customer_id).length}</p></Card></div>
      <div className="table-shell">
        {loading ? <div className="p-12 text-center text-sm text-slate-500">正在加载产品组合…</div> : sets.length ? <div className="overflow-x-auto"><table className="w-full min-w-[860px] border-collapse text-left"><thead className="bg-slate-50/80"><tr className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wide text-slate-500"><th className="px-5 py-3">组合</th><th className="px-4 py-3">关联客户</th><th className="px-4 py-3">产品顺序</th><th className="px-4 py-3">状态</th><th className="px-5 py-3 text-right">更新时间</th></tr></thead><tbody className="divide-y divide-slate-100">{sets.map((set) => <tr key={set.id} className="hover:bg-slate-50/70"><td className="px-5 py-4"><p className="text-sm font-bold text-slate-900">{set.name}</p><p className="mt-1 max-w-sm truncate text-xs text-slate-500">{set.description || "未填写说明"}</p></td><td className="px-4 py-4 text-xs text-slate-600">{customers.find((item) => item.id === set.customer_id)?.name || "通用组合"}</td><td className="px-4 py-4"><div className="flex items-center gap-1.5">{set.items.slice(0, 4).map((item, index) => item.primary_image_url ? <ProtectedImage key={item.product_id} src={item.primary_image_url} alt={item.product_name} className="size-9 rounded-md border border-white shadow-sm" /> : <span key={item.product_id} className="grid size-9 place-items-center rounded-md bg-slate-100 text-[10px] font-bold text-slate-500">{index + 1}</span>)}{set.items.length > 4 ? <span className="text-xs font-semibold text-slate-500">+{set.items.length - 4}</span> : null}</div><p className="mt-1.5 text-[11px] text-slate-400">{set.items.length} 个产品</p></td><td className="px-4 py-4"><Badge tone={set.status === "active" ? "green" : "slate"}>{set.status === "active" ? "有效" : "已归档"}</Badge></td><td className="px-5 py-4 text-right text-xs text-slate-500">{new Date(set.updated_at).toLocaleDateString("zh-CN")}</td></tr>)}</tbody></table></div> : <EmptyState icon={<Layers3 className="size-5" />} title="尚未建立产品组合" description="例如 Germany Outdoor、New Arrival 或某个客户的专属选品。" action={<Button onClick={() => setShowCreate(true)}>创建第一个组合</Button>} />}
      </div>
      {showCreate ? <CreateProductSetModal products={products} customers={customers} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} /> : null}
    </div>
  );
}

function CreateProductSetModal({ products, customers, onClose, onCreated }: { products: Product[]; customers: Customer[]; onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name: "", description: "", customer_id: "" });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filtered = useMemo(() => products.filter((item) => `${item.sku} ${item.product_name}`.toLowerCase().includes(search.toLowerCase())), [products, search]);

  function toggle(productId: string) {
    setSelected((current) => current.includes(productId) ? current.filter((item) => item !== productId) : [...current, productId]);
  }

  function move(productId: string, offset: number) {
    setSelected((current) => {
      const next = [...current];
      const index = next.indexOf(productId);
      const target = index + offset;
      if (index < 0 || target < 0 || target >= next.length) return current;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected.length) { setError("请至少选择一个产品。"); return; }
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest<ProductSet>("/product-sets", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, customer_id: form.customer_id || null, product_ids: selected, status: "active" }) });
      onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "产品组合创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return <Modal title="新建产品组合" description="勾选顺序即初始槽位顺序，也可以在右侧调整。" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}><div className="grid gap-4 sm:grid-cols-2"><label><span className="label">组合名称 *</span><input className="input" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label><span className="label">关联客户</span><select className="input" value={form.customer_id} onChange={(event) => setForm({ ...form, customer_id: event.target.value })}><option value="">通用组合</option>{customers.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div><label><span className="label">说明</span><textarea className="textarea" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label><div className="grid gap-4 lg:grid-cols-2"><div><span className="label">选择产品</span><input className="input mb-2" placeholder="搜索 SKU 或名称" value={search} onChange={(event) => setSearch(event.target.value)} /><div className="max-h-64 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">{filtered.map((product) => <label key={product.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 hover:bg-slate-50"><input type="checkbox" checked={selected.includes(product.id)} onChange={() => toggle(product.id)} /><span className="min-w-0"><span className="block truncate text-xs font-semibold text-slate-800">{product.product_name}</span><span className="font-mono text-[10px] text-slate-400">{product.sku}</span></span></label>)}</div></div><div><span className="label">产品顺序（{selected.length}）</span><div className="max-h-[314px] space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">{selected.map((productId, index) => { const product = products.find((item) => item.id === productId); return <div key={productId} className="flex items-center gap-2 rounded-md bg-slate-50 px-2 py-2"><span className="grid size-6 shrink-0 place-items-center rounded bg-white text-[10px] font-bold text-slate-500">{index + 1}</span><span className="min-w-0 flex-1 truncate text-xs font-semibold text-slate-700">{product?.sku} · {product?.product_name}</span><button type="button" aria-label="上移" disabled={index === 0} onClick={() => move(productId, -1)} className="text-slate-500 disabled:opacity-20"><ArrowUp className="size-3.5" /></button><button type="button" aria-label="下移" disabled={index === selected.length - 1} onClick={() => move(productId, 1)} className="text-slate-500 disabled:opacity-20"><ArrowDown className="size-3.5" /></button></div>; })}{!selected.length ? <p className="py-8 text-center text-xs text-slate-400">尚未选择产品</p> : null}</div></div></div>{error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}<div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={submitting}>{submitting ? "正在创建…" : "创建组合"}</Button></div></form></Modal>;
}
