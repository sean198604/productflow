import { CheckCircle2, Download, FileCode2, FileOutput, LoaderCircle, Play, Sparkles, XCircle } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiBlob, apiDownload, apiRequest } from "../lib/api";
import type { FieldDefinition, Product } from "../types/catalog";
import type { Customer, GenerationTask, ProductSet } from "../types/generation";
import type { OutputTemplate } from "../types/templates";

type GenerationList = { items: GenerationTask[]; total: number };
type CustomerList = { items: Customer[]; total: number };
type ProductSetList = { items: ProductSet[]; total: number };
type TemplateList = { items: OutputTemplate[]; total: number };
type ProductList = { items: Product[]; total: number; page: number; page_size: number };
type HtmlTemplateKey = "editorial" | "journey" | "energy";
type QuoteCurrency = string;
type QuoteCurrencyOption = { code: string; label: string; symbol: string };

const statusLabel = { queued: "排队中", processing: "生成中", completed: "已完成", failed: "失败" };
const currencyNames: Record<string, string> = { CNY: "人民币", EUR: "欧元", GBP: "英镑", JPY: "日币", USD: "美金" };
const currencySymbols: Record<string, string> = { CNY: "¥", EUR: "€", GBP: "£", JPY: "¥", USD: "$" };
const htmlTemplates: Array<{ key: HtmlTemplateKey; name: string; description: string }> = [
  { key: "editorial", name: "Editorial Luxury", description: "暖棕分屏、杂志式留白与高级产品画册" },
  { key: "journey", name: "Curated Journey", description: "橄榄地景、圆角导航与票券式产品信息" },
  { key: "energy", name: "Bold Energy", description: "高饱和橙黄、超大字与强冲击产品构图" },
];

function quoteCurrency(currency: QuoteCurrency, options: QuoteCurrencyOption[]) {
  return options.find((item) => item.code === currency) ?? options[0];
}

function productQuotes(product: Product, currencies: QuoteCurrency[]) {
  const quotes = currencies.flatMap((currency) => {
    const field = currency === "JPY" ? "price" : `price_${currency.toLowerCase()}`;
    const raw = product.custom_fields[field];
    if (raw === null || raw === undefined || raw === "") return [];
    const amount = Number(raw);
    if (!Number.isFinite(amount)) return [`${currency} ${String(raw)}`];
    return [new Intl.NumberFormat(currency === "JPY" ? "ja-JP" : "en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: currency === "JPY" ? 0 : 2,
    }).format(amount)];
  });
  return quotes.length ? quotes.join(" · ") : "所选币种无报价";
}

function CurrencyMultiSelect({
  value,
  options,
  onChange,
  context,
}: {
  value: QuoteCurrency[];
  options: QuoteCurrencyOption[];
  onChange: (currencies: QuoteCurrency[]) => void;
  context: string;
}) {
  function toggle(currency: string) {
    if (value.includes(currency) && value.length === 1) return;
    const selected = new Set(value);
    if (selected.has(currency)) selected.delete(currency);
    else selected.add(currency);
    onChange(options.filter((item) => selected.has(item.code)).map((item) => item.code));
  }

  return <fieldset>
    <legend className="label">报价币种（可多选）</legend>
    <div className="flex flex-wrap gap-2 rounded-lg border border-slate-200 bg-white p-2">
      {options.map((item) => {
        const selected = value.includes(item.code);
        return <label key={item.code} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs font-bold transition ${selected ? "border-[#985d49] bg-[#f8eee9] text-[#7d4937]" : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"}`}>
          <input aria-label={`${context}：${item.label}`} className="size-3.5 accent-[#985d49]" type="checkbox" checked={selected} onChange={() => toggle(item.code)} />
          {item.label}
        </label>;
      })}
    </div>
    <p className="mt-1 text-[10px] text-slate-400">至少保留一个币种；默认选择 USD。</p>
  </fieldset>;
}

function HtmlTemplatePreview({ templateKey }: { templateKey: HtmlTemplateKey }) {
  if (templateKey === "journey") {
    return <div className="relative h-24 overflow-hidden rounded-lg bg-gradient-to-b from-[#f9f9f7] via-[#dce5e0] to-[#748d68]">
      <div className="absolute left-3 right-3 top-3 flex justify-between text-[5px] font-black text-[#1b1f0d]"><span>ProductFlow</span><span>COLLECTION · QUOTE</span></div>
      <div className="absolute inset-x-0 top-8 text-center font-serif text-[12px] font-semibold text-[#1b1f0d]">A CURATED JOURNEY</div>
      <div className="absolute -bottom-7 -left-5 h-16 w-3/4 rotate-6 rounded-[50%] bg-[#4e5531]" />
      <div className="absolute -bottom-9 -right-4 h-20 w-3/4 -rotate-6 rounded-[50%] bg-[#8f946b]" />
      <div className="absolute bottom-3 left-1/2 h-9 w-10 -translate-x-1/2 rounded-t-full border border-white/80 bg-white/85" />
    </div>;
  }
  if (templateKey === "energy") {
    return <div className="relative h-24 overflow-hidden rounded-lg bg-[#fa4308] text-white">
      <div className="absolute inset-x-0 top-0 flex h-6 items-center justify-between bg-[#42170d] px-3 text-[5px] font-black"><span>PF/ENERGY</span><span>PRODUCTS · QUOTE</span></div>
      <div className="absolute left-3 top-9 text-[19px] font-black leading-[.78] tracking-[-.06em]">BOLD<br /><span className="text-[#f4db2c]">ENERGY</span></div>
      <div className="absolute bottom-2 right-4 size-12 rounded-full border-[8px] border-[#f4db2c] bg-white/90 shadow-[6px_7px_0_#42170d]" />
      <div className="absolute inset-x-0 bottom-0 h-2 bg-[#fff8ec] [clip-path:polygon(0_100%,0_45%,5%_0,10%_45%,15%_0,20%_45%,25%_0,30%_45%,35%_0,40%_45%,45%_0,50%_45%,55%_0,60%_45%,65%_0,70%_45%,75%_0,80%_45%,85%_0,90%_45%,95%_0,100%_45%,100%_100%)]" />
    </div>;
  }
  return <div className="relative grid h-24 grid-cols-2 overflow-hidden rounded-lg bg-[#fbf8f3]">
    <div className="bg-[#985d49]" /><div />
    <div className="absolute left-3 top-3 text-[5px] font-black tracking-[.18em] text-white">PRODUCTFLOW</div>
    <div className="absolute left-3 top-9 text-[18px] font-black leading-[.78] tracking-[-.06em] text-white">EVERYDAY<br />LUXURY</div>
    <div className="absolute left-1/2 top-7 h-14 w-12 -translate-x-1/2 rounded bg-white/90 shadow-xl" />
    <div className="absolute right-3 top-3 text-[5px] font-black text-[#201d1a]">COLLECTION · QUOTE</div>
  </div>;
}

export function GenerationCenterPage() {
  const { reportError } = useGlobalError();
  const [tasks, setTasks] = useState<GenerationTask[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [sets, setSets] = useState<ProductSet[]>([]);
  const [templates, setTemplates] = useState<OutputTemplate[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [fieldDefinitions, setFieldDefinitions] = useState<FieldDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [htmlSubmitting, setHtmlSubmitting] = useState(false);
  const [mode, setMode] = useState<"set" | "selection">("set");
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [selectedHtmlProducts, setSelectedHtmlProducts] = useState<string[]>([]);
  const [form, setForm] = useState({ name: "", customer_id: "", product_set_id: "", output_template_version_id: "", currencies: ["USD"] as QuoteCurrency[] });
  const [htmlForm, setHtmlForm] = useState({
    template_key: "editorial" as HtmlTemplateKey,
    title: "HANDHELD ARCHIVE",
    subtitle: "任天堂掌机精选产品报价",
    currencies: ["USD"] as QuoteCurrency[],
    note: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [taskPayload, customerPayload, setPayload, templatePayload, productPayload, fieldPayload] = await Promise.all([
        apiRequest<GenerationList>("/generation-tasks"),
        apiRequest<CustomerList>("/customers"),
        apiRequest<ProductSetList>("/product-sets"),
        apiRequest<TemplateList>("/output-templates"),
        apiRequest<ProductList>("/products?page=1&page_size=100&status=active"),
        apiRequest<{ items: FieldDefinition[] }>("/field-definitions"),
      ]);
      setTasks(taskPayload.items);
      setCustomers(customerPayload.items);
      setSets(setPayload.items);
      setTemplates(templatePayload.items);
      setProducts(productPayload.items);
      setFieldDefinitions(fieldPayload.items);
      setSelectedHtmlProducts((current) => current.length ? current : productPayload.items.map((item) => item.id));
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "生成中心加载失败。");
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => { load(); }, [load]);

  const quoteCurrencies = useMemo<QuoteCurrencyOption[]>(() => {
    const configured = fieldDefinitions
      .filter((field) => field.status === "active" && field.scope === "customer" && field.data_type === "money" && field.options.currency)
      .map((field) => {
        const code = String(field.options.currency).toUpperCase();
        const symbol = currencySymbols[code] || "";
        return { code, symbol, label: `${currencyNames[code] || code} · ${code}${symbol ? ` ${symbol}` : ""}` };
      });
    const fallbacks: QuoteCurrencyOption[] = [
      { code: "USD", label: "美金 · USD $", symbol: "$" },
      { code: "JPY", label: "日币 · JPY ¥", symbol: "¥" },
    ];
    return [...configured, ...fallbacks]
      .filter((item, index, all) => all.findIndex((candidate) => candidate.code === item.code) === index)
      .sort((a, b) => (a.code === "USD" ? -1 : b.code === "USD" ? 1 : a.code === "JPY" ? -1 : b.code === "JPY" ? 1 : a.code.localeCompare(b.code)));
  }, [fieldDefinitions]);

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
    setForm((current) => ({
      ...current,
      customer_id: customerId,
      product_set_id: "",
      output_template_version_id: defaultTemplate?.current_version.status === "ready" ? defaultTemplate.current_version.id : current.output_template_version_id,
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const task = await apiRequest<GenerationTask>("/generation-tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          customer_id: form.customer_id,
          output_template_version_id: form.output_template_version_id,
          product_set_id: mode === "set" ? form.product_set_id || null : null,
          product_ids: mode === "selection" ? selectedProducts : [],
          output_parameters: {
            currencies: form.currencies,
            currency: form.currencies[0],
            currency_symbols: Object.fromEntries(form.currencies.map((currency) => [currency, quoteCurrency(currency, quoteCurrencies).symbol])),
            currency_symbol: quoteCurrency(form.currencies[0], quoteCurrencies).symbol,
          },
        }),
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

  async function generateHtmlQuote(event: FormEvent) {
    event.preventDefault();
    setHtmlSubmitting(true);
    try {
      const { blob, filename } = await apiDownload("/generation-tasks/html-quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...htmlForm,
          currency: htmlForm.currencies[0],
          currency_symbols: Object.fromEntries(htmlForm.currencies.map((currency) => [currency, quoteCurrency(currency, quoteCurrencies).symbol])),
          currency_symbol: quoteCurrency(htmlForm.currencies[0], quoteCurrencies).symbol,
          note: htmlForm.note || null,
          product_ids: selectedHtmlProducts,
        }),
        timeoutMs: 120_000,
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename || "productflow-html-quote.html";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "HTML 报价单生成失败。");
    } finally {
      setHtmlSubmitting(false);
    }
  }

  if (loading) return <div className="py-20 text-center text-sm text-slate-500">正在加载生成中心…</div>;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Generation" title="生成中心" description="直接生成内嵌图片的精品 HTML 报价单，或使用已验证模板输出原生可编辑的 PPTX / XLSX 文件。" />

      <Card className="overflow-hidden border-[#d7c8bd] bg-[#fbf8f3]">
        <CardHeader
          title="精品 HTML 报价单 · 3 套模板"
          description="选择设计语言后批量选品；文件内嵌图片，可离线打开、打印或导出 PDF"
          actions={<Badge tone="purple"><Sparkles className="mr-1 size-3" />高级版式</Badge>}
        />
        <form className="grid xl:grid-cols-[360px_minmax(0,1fr)]" onSubmit={generateHtmlQuote}>
          <div className="border-b border-[#e6ddd5] p-5 xl:col-span-2">
            <span className="label">选择 HTML 模板</span>
            <div className="grid gap-3 md:grid-cols-3">
              {htmlTemplates.map((template) => {
                const selected = htmlForm.template_key === template.key;
                return <label key={template.key} className={`cursor-pointer rounded-xl border p-2.5 transition ${selected ? "border-[#985d49] bg-white shadow-md ring-1 ring-[#985d49]/20" : "border-slate-200 bg-white/50 hover:border-slate-300 hover:bg-white"}`}>
                  <input className="sr-only" type="radio" name="html-template" value={template.key} checked={selected} onChange={() => setHtmlForm({ ...htmlForm, template_key: template.key })} />
                  <HtmlTemplatePreview templateKey={template.key} />
                  <span className="mt-2.5 flex items-center justify-between gap-2"><strong className="text-xs text-slate-900">{template.name}</strong>{selected ? <CheckCircle2 className="size-4 text-[#985d49]" /> : null}</span>
                  <span className="mt-1 block text-[10px] leading-4 text-slate-500">{template.description}</span>
                </label>;
              })}
            </div>
          </div>
          <div className="space-y-4 border-b border-[#e6ddd5] p-5 xl:border-b-0 xl:border-r">
            <label><span className="label">封面标题 *</span><input className="input" required maxLength={80} value={htmlForm.title} onChange={(event) => setHtmlForm({ ...htmlForm, title: event.target.value })} /></label>
            <label><span className="label">副标题 *</span><input className="input" required maxLength={240} value={htmlForm.subtitle} onChange={(event) => setHtmlForm({ ...htmlForm, subtitle: event.target.value })} /></label>
            <CurrencyMultiSelect context="HTML 报价币种" value={htmlForm.currencies} options={quoteCurrencies} onChange={(currencies) => setHtmlForm({ ...htmlForm, currencies })} />
            <p className="rounded-lg border border-[#d9cdc4] bg-white/70 px-3 py-2 text-[10px] leading-4 text-slate-500">可同时输出 USD、JPY 及其他已配置币种。每个产品只显示自身有值的所选币种，空值不显示，也不会用汇率换算或回退到其他市场价格。</p>
            <label><span className="label">报价备注</span><textarea className="input min-h-24 resize-y py-2" maxLength={1000} value={htmlForm.note} onChange={(event) => setHtmlForm({ ...htmlForm, note: event.target.value })} placeholder="价格有效期、交期、贸易条款等；留空则使用标准说明" /></label>
            <div className="rounded-xl bg-[#985d49] p-4 text-white shadow-sm">
              <p className="text-[10px] font-black uppercase tracking-[.2em] text-white/65">Selected collection</p>
              <div className="mt-2 flex items-end justify-between"><strong className="text-3xl font-black">{selectedHtmlProducts.length}</strong><span className="pb-1 text-xs text-white/75">/ {products.length} 个产品</span></div>
            </div>
            <Button className="w-full bg-[#201d1a] hover:bg-[#352f2a]" type="submit" disabled={htmlSubmitting || !selectedHtmlProducts.length}>
              {htmlSubmitting ? <><LoaderCircle className="size-4 animate-spin" /> 正在固化资料与图片…</> : <><FileCode2 className="size-4" /> 生成并下载 HTML</>}
            </Button>
            <p className="text-[11px] leading-5 text-slate-500">仅输出内置模板明确绑定的客户字段；supplier_cost、purchase_price、margin、supplier 等内部字段不会进入文件。</p>
          </div>
          <div className="p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div><p className="text-sm font-bold text-slate-900">选择产品</p><p className="mt-1 text-xs text-slate-500">已默认选中当前导入的全部有效产品，取消勾选即可排除</p></div>
              <div className="flex gap-2"><Button variant="secondary" onClick={() => setSelectedHtmlProducts(products.map((item) => item.id))}>全选</Button><Button variant="ghost" onClick={() => setSelectedHtmlProducts([])}>清空</Button></div>
            </div>
            {products.length ? <div className="grid max-h-[500px] grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 2xl:grid-cols-3">
              {products.map((product) => {
                const checked = selectedHtmlProducts.includes(product.id);
                return <label key={product.id} className={`group flex cursor-pointer items-center gap-3 rounded-xl border p-2.5 transition ${checked ? "border-[#b77c66] bg-white shadow-sm" : "border-slate-200 bg-white/45 opacity-65 hover:opacity-100"}`}>
                  <input className="size-4 accent-[#985d49]" type="checkbox" checked={checked} onChange={() => setSelectedHtmlProducts((current) => current.includes(product.id) ? current.filter((item) => item !== product.id) : [...current, product.id])} />
                  <ProtectedImage src={product.primary_image_url} alt={product.product_name} className="size-14 shrink-0 rounded-lg bg-[#f2ede5]" />
                  <span className="min-w-0"><strong className="block truncate text-xs text-slate-900">{product.product_name}</strong><span className="mt-1 block text-[10px] font-semibold tracking-wide text-slate-400">{product.sku} · {product.image_count} 图</span><span className="mt-1 block text-[11px] font-black text-[#985d49]">{productQuotes(product, htmlForm.currencies)}</span></span>
                </label>;
              })}
            </div> : <EmptyState icon={<FileCode2 className="size-5" />} title="没有可选产品" description="先导入或创建有效产品，再生成 HTML 报价单。" />}
          </div>
        </form>
      </Card>

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
            <CurrencyMultiSelect context="文件报价币种" value={form.currencies} options={quoteCurrencies} onChange={(currencies) => setForm({ ...form, currencies })} />
            <Button className="w-full" type="submit" disabled={submitting || !readyTemplates.length || (mode === "selection" && !selectedProducts.length)}>{submitting ? <><LoaderCircle className="size-4 animate-spin" /> 正在冻结快照并生成…</> : <><Play className="size-4" /> 创建并生成文件</>}</Button>
          </form>
        </Card>

        <Card>
          <CardHeader title="生成记录" description="历史任务固定引用创建时的快照，产品后续变化不会影响追溯" />
          {tasks.length ? <div className="divide-y divide-slate-100">{tasks.map((task) => <div key={task.id} className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-bold text-slate-900">{task.name}</p><Badge tone={task.status === "completed" ? "green" : task.status === "failed" ? "red" : "blue"}>{task.status === "completed" ? <CheckCircle2 className="mr-1 size-3" /> : task.status === "failed" ? <XCircle className="mr-1 size-3" /> : <LoaderCircle className="mr-1 size-3" />}{statusLabel[task.status]}</Badge><Badge>{task.output_type.toUpperCase()}</Badge><Badge tone="purple">{(task.quote_currencies?.length ? task.quote_currencies : [task.quote_currency || "USD"]).join(" / ")}</Badge></div><p className="mt-2 text-xs text-slate-500">{task.customer_name} · {task.product_set_name || "临时选择"} · {task.product_count} 个产品</p><p className="mt-1 text-[11px] text-slate-400">{task.template_name} v{task.template_version_number} · {new Date(task.created_at).toLocaleString("zh-CN")}</p>{task.error_message ? <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{task.error_message}</p> : null}</div>{task.download_url ? <Button variant="secondary" onClick={() => download(task)}><Download className="size-4" /> 下载文件</Button> : null}</div></div>)}</div> : <EmptyState icon={<FileOutput className="size-5" />} title="还没有生成任务" description="完成客户、产品组合和模板映射后即可生成第一个文件。" />}
        </Card>
      </div>
    </div>
  );
}
