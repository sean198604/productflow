import { ArrowLeft, ImagePlus, LockKeyhole, Save, ShieldCheck, Star, Trash2 } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { DeleteConfirmationModal } from "../components/ui/DeleteConfirmationModal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { FieldDefinition, Product, ProductImage } from "../types/catalog";

type EditableValue = string | number | boolean | string[] | null;
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
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [images, setImages] = useState<ProductImage[]>([]);
  const [form, setForm] = useState<ProductForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  const load = useCallback(() => {
    if (!productId) return;
    Promise.all([
      apiRequest<Product>(`/products/${productId}`),
      apiRequest<{ items: FieldDefinition[] }>("/field-definitions"),
      apiRequest<{ items: ProductImage[] }>(`/products/${productId}/images`),
    ])
      .then(([productPayload, fieldPayload, imagePayload]) => {
        setProduct(productPayload);
        setFields(fieldPayload.items);
        setImages(imagePayload.items);
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

  return (
    <div className="space-y-6">
      <Link to="/products" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-3.5" /> 返回产品列表
      </Link>
      <PageHeader
        eyebrow={`Product · ${product.sku}`}
        title={product.product_name}
        description="维护客户可见资料、内部经营字段以及产品图片。内部字段不会进入客户模板上下文。"
        actions={
          <div className="flex items-center gap-2">
            {saveMessage ? <span className="text-xs font-semibold text-emerald-600">{saveMessage}</span> : null}
            <Button variant="danger" onClick={() => setShowDelete(true)}>
              <Trash2 className="size-4" /> 删除产品
            </Button>
            <Button type="submit" form="product-form" disabled={saving}>
              <Save className="size-4" /> {saving ? "保存中…" : "保存资料"}
            </Button>
          </div>
        }
      />

      <form id="product-form" onSubmit={save} className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.8fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader title="核心资料" description="用于检索、去重和产品识别" />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="label">SKU *</span><input className="input" required value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></label>
              <label><span className="label">状态</span><select className="input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as Product["status"] })}><option value="active">有效</option><option value="draft">草稿</option><option value="archived">已归档</option></select></label>
              <label className="sm:col-span-2"><span className="label">产品名称 *</span><input className="input" required value={form.product_name} onChange={(event) => setForm({ ...form, product_name: event.target.value })} /></label>
              <label><span className="label">分类</span><input className="input" value={form.category ?? ""} onChange={(event) => setForm({ ...form, category: event.target.value || null })} /></label>
              <label><span className="label">品牌</span><input className="input" value={form.brand ?? ""} onChange={(event) => setForm({ ...form, brand: event.target.value || null })} /></label>
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
    </div>
  );
}

function FieldInput({ field, value, onChange }: { field: FieldDefinition; value: EditableValue; onChange: (value: EditableValue) => void }) {
  const label = <span className="label">{field.label}{field.is_required ? " *" : ""}<span className="ml-1 font-normal text-slate-400">{field.code}</span></span>;
  if (field.data_type === "boolean") return <label className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 sm:self-end"> <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /> <span className="text-sm font-semibold text-slate-700">{field.label}</span></label>;
  if (field.data_type === "select") return <label>{label}<select className="input" value={String(value ?? "")} onChange={(event) => onChange(event.target.value || null)}><option value="">未设置</option>{field.options.choices?.map((choice) => <option key={choice} value={choice}>{choice}</option>)}</select></label>;
  if (field.data_type === "multi_select") return <label>{label}<input className="input" placeholder="多个值用逗号分隔" value={Array.isArray(value) ? value.join(", ") : ""} onChange={(event) => onChange(event.target.value ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean) : null)} /></label>;
  return <label>{label}<input className="input" type={field.data_type === "date" ? "date" : field.data_type === "number" || field.data_type === "money" ? "number" : "text"} step={field.data_type === "money" ? "0.01" : "any"} value={typeof value === "string" || typeof value === "number" ? value : ""} onChange={(event) => onChange(event.target.value || null)} /></label>;
}

function ProductImages({ productId, images, onChanged }: { productId: string; images: ProductImage[]; onChanged: () => void }) {
  const { reportError } = useGlobalError();
  const [uploading, setUploading] = useState(false);
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
  return (
    <Card>
      <CardHeader title="产品图片" description={`${images.length} 张 · SHA256 去重`} actions={<label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-lg bg-[#1a365d] px-3 text-xs font-semibold text-white"><ImagePlus className="size-4" />{uploading ? "上传中…" : "上传图片"}<input className="hidden" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp" disabled={uploading} onChange={upload} /></label>} />
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
            <div className="relative">
              <ProtectedImage
                src={image.content_url}
                alt={image.original_filename}
                className="aspect-square w-full bg-white"
              />
              {image.is_primary ? (
                <span className="absolute left-2.5 top-2.5 inline-flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-1 text-[11px] font-black text-amber-950 shadow-md">
                  <Star className="size-3.5 fill-current" aria-hidden="true" /> 主图
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
            </div>
          </div>
        ))}
        {!images.length ? <div className="col-span-2 py-8 text-center text-xs text-slate-400">暂无图片，上传后第一张会自动成为主图。</div> : null}
      </div>
    </Card>
  );
}
