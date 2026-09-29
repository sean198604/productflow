import { CheckCircle2, Download, FileOutput, LoaderCircle, Play, XCircle } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiBlob, apiRequest } from "../lib/api";
import type { Product } from "../types/catalog";
import type { Customer, GenerationTask, ProductSet } from "../types/generation";
import type { OutputTemplate } from "../types/templates";

type GenerationList = { items: GenerationTask[]; total: number };
type CustomerList = { items: Customer[]; total: number };
type ProductSetList = { items: ProductSet[]; total: number };
type TemplateList = { items: OutputTemplate[]; total: number };
type ProductList = { items: Product[]; total: number; page: number; page_size: number };

const statusLabel = { queued: "排队中", processing: "生成中", completed: "已完成", failed: "失败" };

export function GenerationCenterPage() {
  const { reportError } = useGlobalError();
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sets, setSets] = useState<ProductSet[]>([]);
  const [templates, setTemplates] = useState<OutputTemplate[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<"set" | "selection">("set");
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [form, setForm] = useState({ name: "", customer_id: "", product_set_id: "", output_template_version_id: "", currency_symbol: "$" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [taskPayload, customerPayload, setPayload, templatePayload, productPayload] = await Promise.all([
        apiRequest<GenerationList>("/generation-tasks"),
        apiRequest<CustomerList>("/customers"),
        apiRequest<ProductSetList>("/product-sets"),
        apiRequest<TemplateList>("/output-templates"),
        apiRequest<ProductList>("/products?page=1&page_size=100&status=active"),
      ]);
      setTasks(taskPayload.items);
      setCustomers(customerPayload.items);
      setSets(setPayload.items);
      setTemplates(templatePayload.items);
      setProducts(productPayload.items);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "生成中心加载失败。");
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => { load(); }, [load]);

  const readyTemplates = templates.filter((item) => item.status === "active" && item.current_version.status === "ready");
  const activeCustomers = customers.filter((item) => item.status === "active");
  const availableSets = sets.filter((item) => item.status === "active" && (!form.customer_id || !item.customer_id || item.customer_id === form.customer_id));
  const selectedTemplate = templates.find((item) => item.current_version.id === form.output_template_version_id);
  const capacity = useMemo(() => {
    if (!selectedTemplate) return 0;
    const slots = selectedTemplate.current_version.mapping_config.bindings
      .filter((item) => item.visible && !item.source.startsWith("customer."))
      .map((item) => item.product_slot || 1);
    return slots.length ? Math.max(...slots) : 0;
  }, [selectedTemplate]);

  function chooseCustomer(customerId: string) {
    const customer = customers.find((item) => item.id === customerId);
    const defaultTemplate = templates.find((item) => item.id === customer?.default_ppt_template_id || item.id === customer?.default_xlsx_template_id);
    setForm((current) => ({ ...current, customer_id: customerId, product_set_id: "", output_template_version_id: defaultTemplate?.current_version.status === "ready" ? defaultTemplate.current_version.id : current.output_template_version_id }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const task = await apiRequest<GenerationTask>("/generation-tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: form.name, customer_id: form.customer_id, output_template_version_id: form.output_template_version_id, product_set_id: mode === "set" ? form.product_set_id || null : null, product_ids: mode === "selection" ? selectedProducts : [], output_parameters: { currency_symbol: form.currency_symbol } }),
        timeoutMs: 120_000,
      });
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
      if (task.status === "completed") setForm((current) => ({ ...current, name: "" }));
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "生成任务创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function download(task: GenerationTask) {
    if (!task.download_url || !task.output_filename) return;
    try {
      const blob = await apiBlob(task.download_url, 60_000);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = task.output_filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "生成文件下载失败。");
    }
  }

  if (loading) return <div className="py-20 text-center text-sm text-slate-500">正在加载生成中心…</div>;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Generation" title="生成中心" description="选择客户、产品组合和已验证模板。系统先冻结快照，再生成原生可编辑的 PPTX 或 XLSX 文件。" />
      <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader title="创建生成任务" description="任务创建后立即固化产品、图片、客户及模板版本" />
          <form className="space-y-4 p-5" onSubmit={submit}>
            <label><span className="label">任务名称 *</span><input className="input" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Customer A · 2026 Spring Quote" /></label>
            <label><span className="label">客户 *</span><select className="input" required value={form.customer_id} onChange={(event) => chooseCustomer(event.target.value)}><option value="">选择客户</option>{activeCustomers.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</select></label>
            <div><span className="label">产品来源</span><div className="grid grid-cols-2 rounded-lg bg-slate-100 p-1"><button type="button" onClick={() => setMode("set")} className={`rounded-md px-3 py-2 text-xs font-semibold ${mode === "set" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>产品组合</button><button type="button" onClick={() => setMode("selection")} className={`rounded-md px-3 py-2 text-xs font-semibold ${mode === "selection" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500"}`}>临时选择</button></div></div>
            {mode === "set" ? <label><span className="label">产品组合 *</span><select className="input" required value={form.product_set_id} onChange={(event) => setForm({ ...form, product_set_id: event.target.value })}><option value="">选择产品组合</option>{availableSets.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.items.length} 个产品</option>)}</select></label> : <div><span className="label">批量选择产品（{selectedProducts.length}）</span><div className="max-h-52 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">{products.map((product) => <label key={product.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 hover:bg-slate-50"><input type="checkbox" checked={selectedProducts.includes(product.id)} onChange={() => setSelectedProducts((current) => current.includes(product.id) ? current.filter((item) => item !== product.id) : [...current, product.id])} /><span className="min-w-0 truncate text-xs text-slate-700"><strong>{product.sku}</strong> · {product.product_name}</span></label>)}</div></div>}
            <label><span className="label">输出模板 *</span><select className="input" required value={form.output_template_version_id} onChange={(event) => setForm({ ...form, output_template_version_id: event.target.value })}><option value="">选择已验证模板</option>{readyTemplates.map((item) => <option key={item.current_version.id} value={item.current_version.id}>{item.name} · {item.output_type.toUpperCase()} · v{item.current_version.version_number}</option>)}</select></label>
            {selectedTemplate ? <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">当前模板容量：<strong>{capacity}</strong> 个产品槽位。产品按组合顺序进入槽位。</div> : null}
            {!readyTemplates.length ? <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">当前没有“映射已验证”的输出模板。请先到 <Link className="font-bold underline" to="/templates">模板中心</Link> 完成字段与产品槽位映射。</div> : null}
            <label><span className="label">货币符号</span><input className="input" value={form.currency_symbol} onChange={(event) => setForm({ ...form, currency_symbol: event.target.value })} /></label>
            <Button className="w-full" type="submit" disabled={submitting || !readyTemplates.length || (mode === "selection" && !selectedProducts.length)}>{submitting ? <><LoaderCircle className="size-4 animate-spin" /> 正在冻结快照并生成…</> : <><Play className="size-4" /> 创建并生成文件</>}</Button>
          </form>
        </Card>

        <Card>
          <CardHeader title="生成记录" description="历史任务固定引用创建时的快照，产品后续变化不会影响追溯" />
          {tasks.length ? <div className="divide-y divide-slate-100">{tasks.map((task) => <div key={task.id} className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-bold text-slate-900">{task.name}</p><Badge tone={task.status === "completed" ? "green" : task.status === "failed" ? "red" : "blue"}>{task.status === "completed" ? <CheckCircle2 className="mr-1 size-3" /> : task.status === "failed" ? <XCircle className="mr-1 size-3" /> : <LoaderCircle className="mr-1 size-3" />}{statusLabel[task.status]}</Badge><Badge>{task.output_type.toUpperCase()}</Badge></div><p className="mt-2 text-xs text-slate-500">{task.customer_name} · {task.product_set_name || "临时选择"} · {task.product_count} 个产品</p><p className="mt-1 text-[11px] text-slate-400">{task.template_name} v{task.template_version_number} · {new Date(task.created_at).toLocaleString("zh-CN")}</p>{task.error_message ? <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{task.error_message}</p> : null}</div>{task.download_url ? <Button variant="secondary" onClick={() => download(task)}><Download className="size-4" /> 下载文件</Button> : null}</div></div>)}</div> : <EmptyState icon={<FileOutput className="size-5" />} title="还没有生成任务" description="完成客户、产品组合和模板映射后即可生成第一个文件。" />}
        </Card>
      </div>
    </div>
  );
}
