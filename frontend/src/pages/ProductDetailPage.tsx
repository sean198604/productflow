import { ArrowLeft, CheckCircle2, ChevronLeft, ChevronRight, Download, ImagePlus, LockKeyhole, PanelRightClose, PanelRightOpen, Save, Search, ShieldCheck, Star, Trash2 } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { DeleteConfirmationModal } from "../components/ui/DeleteConfirmationModal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, PageHeader } from "../components/ui/primitives";
import { ApiError, apiDownload, apiRequest } from "../lib/api";
import type { FieldDefinition, Product, ProductDictionary, ProductImage } from "../types/catalog";

type EditableValue = string | number | boolean | string[] | null;
type ProductList = { items: Product[]; total: number; page: number; page_size: number };
type ProductForm = Pick<Product, "sku" | "product_name" | "description" | "category" | "brand" | "status"> & {
  custom_fields: Record<string, EditableValue>;
};

const imageTypeLabel = {
  main: "产品图",
  white_background: "白底图",
  lifestyle: "场景图",
  detail: "细节图",
  packaging: "包装图",
  certificate: "证书",
  other: "其他",
};

export function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { reportError } = useGlobalError();
  const [product, setProduct] = useState<Product | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [productTotal, setProductTotal] = useState(0);
  const [productSearch, setProductSearch] = useState("");
  const [productListCollapsed, setProductListCollapsed] = useState(false);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [images, setImages] = useState<ProductImage[]>([]);
  const [dictionaries, setDictionaries] = useState<ProductDictionary[]>([]);
  const [form, setForm] = useState<ProductForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  const load = useCallback(() => {
    if (!productId) return;
    setSaveMessage(null);
    setShowDelete(false);
    Promise.all([
      apiRequest<Product>(`/products/${productId}`),
      apiRequest<{ items: FieldDefinition[] }>("/field-definitions"),
      apiRequest<{ items: ProductImage[] }>(`/products/${productId}/images`),
      apiRequest<{ items: ProductDictionary[] }>("/product-dictionaries"),
      apiRequest<ProductList>("/products?page=1&page_size=100"),
    ])
      .then(([productPayload, fieldPayload, imagePayload, dictionaryPayload, productListPayload]) => {
        setProduct(productPayload);
        setFields(fieldPayload.items);
        setImages(imagePayload.items);
        setDictionaries(dictionaryPayload.items);
        setProductTotal(productListPayload.total);
        setProducts(productListPayload.items.some((item) => item.id === productPayload.id)
          ? productListPayload.items
          : [productPayload, ...productListPayload.items]);
        setForm({
          sku: productPayload.sku,
          product_name: productPayload.product_name,
          description: productPayload.description,
          category: productPayload.category,
          brand: productPayload.brand,
          status: productPayload.status,
          custom_fields: productPayload.custom_fields,
        });
      })
      .catch(() => reportError("产品资料加载失败。"));
  }, [productId, reportError]);

  useEffect(() => load(), [load]);
  useEffect(() => {
    if (!saveMessage) return;
    const timeout = window.setTimeout(() => setSaveMessage(null), 2500);
    return () => window.clearTimeout(timeout);
  }, [saveMessage]);

  const editableFields = useMemo(() => fields.filter((field) => !field.is_core && field.status === "active"), [fields]);
  const customerFields = editableFields.filter((field) => field.scope === "customer");
  const internalFields = editableFields.filter((field) => field.scope === "internal");

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form || !productId) return;
    setSaving(true);
    setSaveMessage(null);
    try {
      const saved = await apiRequest<Product>(`/products/${productId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setProduct(saved);
      setProducts((current) => current.map((item) => item.id === saved.id ? saved : item));
      setSaveMessage("资料已保存");
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "产品保存失败。")
    } finally {
      setSaving(false);
    }
  }

  function setCustomField(code: string, value: EditableValue) {
    setForm((current) =>
      current
        ? { ...current, custom_fields: { ...current.custom_fields, [code]: value } }
        : current,
    );
  }

  if (!form || !product) {
    return <div className="py-20 text-center text-sm text-slate-500">正在加载产品资料…</div>;
  }

  const currentIndex = products.findIndex((item) => item.id === product.id);
  const previousProduct = currentIndex > 0 ? products[currentIndex - 1] : null;
  const nextProduct = currentIndex >= 0 && currentIndex < products.length - 1 ? products[currentIndex + 1] : null;
  const visibleProducts = products.filter((item) => {
    const term = productSearch.trim().toLocaleLowerCase();
    return !term || item.sku.toLocaleLowerCase().includes(term) || item.product_name.toLocaleLowerCase().includes(term);
  });

  return (
    <div className={productListCollapsed ? "xl:pr-[68px]" : "xl:pr-[340px]"}>
      <div className="min-w-0 space-y-6">
        <Link to="/products" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900">
          <ArrowLeft className="size-3.5" /> 返回产品列表
        </Link>
        <PageHeader
          eyebrow={`Product · ${product.sku}`}
          title={product.product_name}
          description="维护客户可见资料、内部经营字段以及产品图片。内部字段不会进入客户模板上下文。"
          actions={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="flex items-center gap-2" role="group" aria-label="产品资料翻页">
                <Button variant="secondary" disabled={!previousProduct} onClick={() => previousProduct && navigate(`/products/${previousProduct.id}`)}>
                  <ChevronLeft className="size-4" /> 上一个
                </Button>
                <Button variant="secondary" disabled={!nextProduct} onClick={() => nextProduct && navigate(`/products/${nextProduct.id}`)}>
                  下一个 <ChevronRight className="size-4" />
                </Button>
              </div>
              <Button variant="danger" onClick={() => setShowDelete(true)}>
                <Trash2 className="size-4" /> 删除产品
              </Button>
              <Button type="submit" form="product-form" disabled={saving}>
                <Save className="size-4" /> {saving ? "保存中…" : "保存资料"}
              </Button>
            </div>
          }
        />

        <form id="product-form" onSubmit={save} className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(300px,0.8fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader title="核心资料" description="用于检索、去重和产品识别" />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="label">SKU *</span><input className="input" required value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></label>
              <label><span className="label">状态</span><select className="input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as Product["status"] })}><option value="active">有效</option><option value="draft">草稿</option><option value="archived">已归档</option></select></label>
              <label className="sm:col-span-2"><span className="label">产品名称 *</span><input className="input" required value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} /></label>
              <DictionaryInput label="分类" listId="product-detail-categories" items={dictionaries.filter((item) => item.kind === "category")} value={form.category} onChange={(value) => setForm({ ...form, category: value })} />
              <DictionaryInput label="品牌" listId="product-detail-brands" items={dictionaries.filter((item) => item.kind === "brand")} value={form.brand} onChange={(value) => setForm({ ...form, brand: value })} />
              <label className="sm:col-span-2"><span className="label">产品描述</span><textarea className="textarea" value={form.description ?? ""} onChange={(event) => setForm({ ...form, description: event.target.value || null })} /></label>
            </div>
          </Card>

          <Card>
            <CardHeader title="客户报价字段" description="可由未来的客户输出模板显式绑定" actions={<Badge tone="blue">Customer fields</Badge>} />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              {customerFields.map((field) => (
                <FieldInput key={field.id} field={field} value={form.custom_fields[field.code] ?? null} onChange={(value) => setCustomField(field.code, value)} />
              ))}
            </div>
          </Card>

          <Card className="border-amber-200/80">
            <CardHeader title="内部字段" description="成本、供应商和利润数据永远不会默认输出" actions={<Badge tone="amber"><LockKeyhole className="mr-1 size-3" /> Internal only</Badge>} />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              {internalFields.map((field) => (
                <FieldInput key={field.id} field={field} value={form.custom_fields[field.code] ?? null} onChange={(value) => setCustomField(field.code, value)} />
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <ProductImages productId={product.id} images={images} onChanged={load} />
          <Card className="p-5">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-600"><ShieldCheck className="size-4" /></span>
              <div>
                <h3 className="text-sm font-bold text-slate-900">数据边界</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">所有字段值和图片都带 tenant_id，并由 PostgreSQL RLS 强制隔离。图片内容接口同样需要当前租户的有效令牌。</p>
              </div>
            </div>
          </Card>
        </div>
        </form>
      </div>

      <ProductDirectoryPanel
        collapsed={productListCollapsed}
        onCollapsedChange={setProductListCollapsed}
        currentProduct={product}
        products={products}
        visibleProducts={visibleProducts}
        productTotal={productTotal}
        currentIndex={currentIndex}
        search={productSearch}
        onSearchChange={setProductSearch}
      />

      {showDelete ? (
        <DeleteConfirmationModal
          title={`删除产品 ${product.sku}`}
          description="产品资料、自定义字段、图片关联以及其在产品组合中的成员关系都会被删除。已用于历史生成任务的产品会受到保护，系统将拒绝删除。"
          confirmLabel="永久删除产品"
          onClose={() => setShowDelete(false)}
          onConfirm={async () => {
            await apiRequest<void>(`/products/${product.id}`, { method: "DELETE" });
            navigate("/products", { replace: true });
          }}
        />
      ) : null}
      {saveMessage ? (
        <div
          role="status"
          aria-live="polite"
          className="fixed left-1/2 top-24 z-50 flex -translate-x-1/2 items-center gap-2 rounded-xl border border-emerald-200 bg-white px-4 py-3 text-sm font-bold text-emerald-700 shadow-xl shadow-emerald-950/10"
        >
          <CheckCircle2 className="size-4" aria-hidden="true" />
          {saveMessage}
        </div>
      ) : null}
    </div>
  );
}

function ProductDirectoryPanel({
  collapsed,
  onCollapsedChange,
  currentProduct,
  products,
  visibleProducts,
  productTotal,
  currentIndex,
  search,
  onSearchChange,
}: {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  currentProduct: Product;
  products: Product[];
  visibleProducts: Product[];
  productTotal: number;
  currentIndex: number;
  search: string;
  onSearchChange: (value: string) => void;
}) {
  return (
    <aside
      className={`mt-5 min-w-0 xl:fixed xl:right-0 xl:top-[76px] xl:z-20 xl:mt-0 xl:h-[calc(100vh-76px)] ${collapsed ? "xl:w-12" : "xl:w-[320px]"}`}
      aria-label="产品快速列表"
      data-testid="product-directory-panel"
    >
      {collapsed ? (
        <Card className="flex min-h-20 overflow-hidden xl:h-full xl:rounded-none xl:border-y-0 xl:border-r-0 xl:shadow-none">
          <button
            type="button"
            aria-label="展开产品列表"
            title="展开产品列表"
            onClick={() => onCollapsedChange(false)}
            className="flex w-full flex-row items-center justify-center gap-2 text-slate-500 transition hover:bg-slate-50 hover:text-[#1a365d] xl:flex-col"
          >
            <PanelRightOpen className="size-4" />
            <span className="text-[10px] font-bold tracking-wider xl:[writing-mode:vertical-rl]">产品列表</span>
          </button>
        </Card>
      ) : (
        <Card className="flex max-h-[560px] flex-col overflow-hidden xl:h-full xl:max-h-none xl:rounded-none xl:border-y-0 xl:border-r-0 xl:shadow-none">
          <div className="flex shrink-0 items-start justify-between gap-3 border-b border-slate-100 px-4 py-4">
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-slate-900">产品列表</h2>
              <p className="mt-1 truncate text-xs text-slate-500">
                {currentIndex >= 0 ? `当前第 ${currentIndex + 1} 个，共 ${productTotal || products.length} 个` : `共 ${productTotal || products.length} 个`}
              </p>
            </div>
            <button
              type="button"
              aria-label="向右收缩产品列表"
              title="向右收缩"
              onClick={() => onCollapsedChange(true)}
              className="grid size-8 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
            >
              <PanelRightClose className="size-4" />
            </button>
          </div>

          <div className="shrink-0 border-b border-slate-100 p-3">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <input className="input pl-9" aria-label="在产品列表中查询" placeholder="查询 SKU 或产品名称" value={search} onChange={(event) => onSearchChange(event.target.value)} />
            </label>
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain p-3" data-testid="product-directory-scroll">
            {visibleProducts.map((item) => {
              const selected = item.id === currentProduct.id;
              return (
                <Link
                  key={item.id}
                  to={`/products/${item.id}`}
                  aria-current={selected ? "page" : undefined}
                  className={`flex min-w-0 items-center gap-3 rounded-xl border p-2.5 transition ${selected ? "border-[#1a365d] bg-blue-50 shadow-sm" : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"}`}
                >
                  <ProtectedImage src={item.primary_image_url} alt={item.product_name} className="size-11 shrink-0 rounded-lg border border-slate-200" />
                  <span className="min-w-0"><strong className="block truncate text-xs text-slate-900">{item.product_name}</strong><span className="mt-1 block truncate font-mono text-[10px] text-slate-500">{item.sku}</span></span>
                </Link>
              );
            })}
            {!visibleProducts.length ? <p className="py-8 text-center text-xs text-slate-400">没有匹配的产品。</p> : null}
          </div>

          {productTotal > products.length ? <p className="shrink-0 border-t border-amber-100 bg-amber-50 px-3 py-2 text-[10px] leading-4 text-amber-700">快速列表显示最近 {products.length} 个产品；完整查询请返回产品资料。</p> : null}
        </Card>
      )}
    </aside>
  );
}

function FieldInput({ field, value, onChange }: { field: FieldDefinition; value: EditableValue; onChange: (value: EditableValue) => void }) {
  const label = <span className="label">{field.label}{field.is_required ? " *" : ""}<span className="ml-1 font-normal text-slate-400">{field.code}</span></span>;
  if (field.data_type === "boolean") return <label className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 sm:self-end"> <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /> <span className="text-sm font-semibold text-slate-700">{field.label}</span></label>;
  if (field.data_type === "select") return <label>{label}<select className="input" value={String(value ?? "")} onChange={(event) => onChange(event.target.value || null)}><option value="">未设置</option>{field.options.choices?.map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select></label>;
  if (field.data_type === "multi_select") return <label>{label}<input className="input" placeholder="多个值用逗号分隔" value={Array.isArray(value) ? value.join(", ") : ""} onChange={(event) => onChange(event.target.value ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean) : null)} /></label>;
  return <label>{label}<input className="input" type={field.data_type === "date" ? "date" : field.data_type === "number" || field.data_type === "money" ? "number" : "text"} step={field.data_type === "money" ? "0.01" : "any"} value={typeof value === "string" || typeof value === "number" ? value : ""} onChange={(event) => onChange(event.target.value || null)} /></label>;
}

function DictionaryInput({ label, listId, items, value, onChange }: { label: string; listId: string; items: ProductDictionary[]; value: string | null; onChange: (value: string | null) => void }) {
  return (
    <label>
      <span className="label">{label}</span>
      <input className="input" list={listId} value={value ?? ""} onChange={(event) => onChange(event.target.value || null)} placeholder={`选择或输入新${label}`} />
      <datalist id={listId}>{items.map((item) => <option key={item.id} value={item.name} />)}</datalist>
      <span className="mt-1 block text-[10px] text-slate-400">可直接修改；新名称保存后自动加入字典。</span>
    </label>
  );
}

function ProductImages({ productId, images, onChanged }: { productId: string; images: ProductImage[]; onChanged: () => void }) {
  const { reportError } = useGlobalError();
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProductImage | null>(null);
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("image", file);
    form.append("image_type", "other");
    setUploading(true);
    try {
      await apiRequest(`/products/${productId}/images`, { method: "POST", body: form });
      onChanged();
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "图片上传失败。")
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }
  async function setPrimary(image: ProductImage) {
    try {
      await apiRequest(`/product-images/${image.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_primary: true }),
      });
      onChanged();
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "主图设置失败。");
    }
  }
  async function downloadProcessed(image: ProductImage) {
    if (!image.processed_content_url) return;
    try {
      const { blob, filename } = await apiDownload(image.processed_content_url);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename ?? `${image.product_sku}-transparent.png`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "透明 PNG 下载失败。");
    }
  }
  return (
    <Card>
      <CardHeader title="产品图片" description={`${images.length} 张 · 原图保留并自动生成透明 PNG`} actions={<label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg bg-[#1a365d] px-3 text-xs font-semibold text-white"><ImagePlus className="size-4" />{uploading ? "处理中…" : "上传图片"}<input className="hidden" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp" disabled={uploading} onChange={upload} /></label>} />
      <div className="grid grid-cols-2 gap-3 p-4">
        {images.map((image) => (
          <div
            key={image.id}
            className={`group overflow-hidden rounded-xl border bg-slate-50 transition ${
              image.is_primary
                ? "border-amber-400 ring-2 ring-amber-200 shadow-md shadow-amber-100"
                : "border-slate-200 hover:border-slate-300"
            }`}
          >
            <div className="relative bg-[linear-gradient(45deg,#f1f5f9_25%,transparent_25%),linear-gradient(-45deg,#f1f5f9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f1f5f9_75%),linear-gradient(-45deg,transparent_75%,#f1f5f9_75%)] bg-[length:16px_16px]">
              <ProtectedImage
                src={image.processed_content_url ?? image.content_url}
                alt={image.original_filename}
                className="aspect-square w-full bg-white"
              />
              {image.is_primary ? (
                <span className="absolute left-2.5 top-2.5 inline-flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-1 text-[11px] font-black text-amber-950 shadow-md">
                  <Star className="size-3.5 fill-current" aria-hidden="true" /> 主图
                </span>
              ) : null}
              {image.processed_content_url ? (
                <span className="absolute bottom-2.5 left-2.5 rounded-full bg-emerald-600 px-2 py-1 text-[10px] font-bold text-white shadow-sm">
                  {image.background_removed ? "已去白底" : "透明 PNG"}
                </span>
              ) : null}
            </div>
            <div className="p-2.5">
              <div className="flex items-center justify-between gap-2">
                <Badge tone="slate">{imageTypeLabel[image.image_type]}</Badge>
                {image.is_primary ? (
                  <span className="text-[10px] font-bold text-amber-700">当前主图</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setPrimary(image)}
                    className="rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-800 transition hover:bg-amber-100"
                  >
                    设为主图
                  </button>
                )}
              </div>
              <p className="mt-2 truncate text-[10px] text-slate-400" title={image.original_filename}>
                {image.original_filename}
              </p>
              <div className="mt-2 flex items-center justify-between gap-2">
                {image.processed_content_url ? (
                  <button type="button" onClick={() => downloadProcessed(image)} className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 hover:text-emerald-900">
                    <Download className="size-3" /> 下载附件 PNG
                  </button>
                ) : <span />}
                <button
                  type="button"
                  aria-label={`删除图片 ${image.original_filename}`}
                  title="删除图片"
                  onClick={() => setDeleteTarget(image)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-bold text-red-600 transition hover:bg-red-50 hover:text-red-800"
                >
                  <Trash2 className="size-3" /> 删除
                </button>
              </div>
            </div>
          </div>
        ))}
        {!images.length ? <div className="col-span-2 py-8 text-center text-xs text-slate-400">暂无图片，上传后第一张会自动成为主图。</div> : null}
      </div>
      {deleteTarget ? (
        <DeleteConfirmationModal
          title={`删除图片 ${deleteTarget.original_filename}`}
          description={deleteTarget.is_primary && images.length > 1
            ? "该图片是当前主图。删除后系统会自动将下一张图片设为主图，产品资料和其他图片不受影响。"
            : "图片将从当前产品资料中移除，产品资料和其他图片不受影响。"}
          confirmLabel="永久删除图片"
          onClose={() => setDeleteTarget(null)}
          onConfirm={async () => {
            await apiRequest<void>(`/product-images/${deleteTarget.id}`, { method: "DELETE" });
            setDeleteTarget(null);
            onChanged();
          }}
        />
      ) : null}
    </Card>
  );
}
