import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileSpreadsheet,
  FileType2,
  LockKeyhole,
  Save,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { DeleteConfirmationModal } from "../components/ui/DeleteConfirmationModal";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { FieldDefinition } from "../types/catalog";
import type {
  OutputTemplateBinding,
  OutputTemplateDetail,
  OutputTemplateVersion,
  TemplateObject,
} from "../types/templates";

const imageSources = [
  ["image.main", "主图"],
  ["image.white_background", "白底图"],
  ["image.lifestyle", "场景图"],
  ["image.detail", "细节图"],
  ["image.packaging", "包装图"],
  ["image.other", "其他图片"],
  ["customer.logo", "客户 Logo"],
] as const;

const customerTextSources = [
  ["customer.name", "客户名称"],
  ["customer.code", "客户代码"],
] as const;

const objectTypeLabel: Record<string, string> = {
  slide: "幻灯片",
  sheet: "工作表",
  text: "文本框",
  image: "图片",
  table: "表格",
  cell: "单元格",
  merged_cell: "合并单元格",
  chart: "图表",
  smartart: "SmartArt",
  group: "组合图形",
  shape: "普通图形",
  connector: "连接线",
};

const formatterLabel = {
  text: "文本",
  number: "数字",
  integer: "整数",
  currency: "货币",
  percent: "百分比",
  date: "日期",
};

function defaultFormatter(field: FieldDefinition | undefined): OutputTemplateBinding["formatter"] {
  if (!field) return "text";
  if (field.data_type === "money") return "currency";
  if (field.data_type === "number") return "number";
  if (field.data_type === "date") return "date";
  return "text";
}

function objectName(object: TemplateObject) {
  if (object.shape_name) return object.shape_name;
  if (object.cell) return `${object.sheet_name} · ${object.cell}`;
  return object.container;
}

export function TemplateDetailPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const { reportError } = useGlobalError();
  const [template, setTemplate] = useState<OutputTemplateDetail | null>(null);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [bindings, setBindings] = useState<OutputTemplateBinding[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [showVersionUpload, setShowVersionUpload] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const canManage = session?.user.role === "owner" || session?.user.role === "admin";

  const load = useCallback(async () => {
    if (!templateId) return;
    try {
      const [templatePayload, fieldPayload] = await Promise.all([
        apiRequest<OutputTemplateDetail>(`/output-templates/${templateId}`),
        apiRequest<{ items: FieldDefinition[] }>("/field-definitions"),
      ]);
      setTemplate(templatePayload);
      setFields(fieldPayload.items);
      setSelectedVersionId((current) => current || templatePayload.current_version.id);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "模板详情加载失败。");
    }
  }, [reportError, templateId]);

  useEffect(() => { load(); }, [load]);

  const selectedVersion = useMemo(
    () => template?.versions.find((item) => item.id === selectedVersionId) ?? template?.current_version,
    [selectedVersionId, template],
  );

  useEffect(() => {
    setBindings(selectedVersion?.mapping_config.bindings ?? []);
    setSavedMessage(null);
  }, [selectedVersion?.id]);

  const customerFields = fields.filter(
    (field) => field.scope === "customer" && field.status === "active",
  );
  const internalFieldCount = fields.filter((field) => field.scope === "internal").length;

  function changeSource(object: TemplateObject, source: string) {
    setSavedMessage(null);
    setBindings((current) => {
      const withoutObject = current.filter((item) => item.object_key !== object.object_key);
      if (!source) return withoutObject;
      const isImage = source.startsWith("image.") || source === "customer.logo";
      const field = customerFields.find((item) => item.code === source);
      return [
        ...withoutObject,
        {
          object_key: object.object_key,
          source,
          visible: true,
          label: null,
          formatter: isImage ? null : defaultFormatter(field),
          default_value: null,
          fallback: isImage
            ? ["image.white_background", "image.lifestyle", "unmatched_placeholder"]
            : [],
          transform: null,
          fit: isImage ? "contain" : null,
          position: isImage ? "center" : null,
          product_slot: 1,
          allow_formula: false,
        },
      ];
    });
  }

  function updateBinding(objectKey: string, values: Partial<OutputTemplateBinding>) {
    setSavedMessage(null);
    setBindings((current) =>
      current.map((item) => item.object_key === objectKey ? { ...item, ...values } : item),
    );
  }

  async function saveMapping() {
    if (!selectedVersion) return;
    setSaving(true);
    setSavedMessage(null);
    try {
      const saved = await apiRequest<OutputTemplateVersion>(
        `/output-templates/versions/${selectedVersion.id}/mapping`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            version: "1.0",
            template_sha256: selectedVersion.template_sha256,
            bindings,
          }),
        },
      );
      setTemplate((current) => current ? {
        ...current,
        current_version: current.current_version.id === saved.id ? saved : current.current_version,
        versions: current.versions.map((item) => item.id === saved.id ? saved : item),
      } : current);
      setSavedMessage(bindings.length ? "字段映射已验证" : "已清空字段映射");
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "字段映射保存失败。");
    } finally {
      setSaving(false);
    }
  }

  if (!template || !selectedVersion) {
    return <div className="py-20 text-center text-sm text-slate-500">正在加载模板详情…</div>;
  }

  const report = selectedVersion.validation_report;
  const mappingByObject = new Map(bindings.map((binding) => [binding.object_key, binding]));

  return (
    <div className="space-y-6">
      <Link to="/templates" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-3.5" /> 返回模板中心
      </Link>
      <PageHeader
        eyebrow={`${template.output_type.toUpperCase()} Output Template`}
        title={template.name}
        description={template.description || "查看模板验证结果并为支持的对象绑定客户输出字段。"}
        actions={canManage ? <div className="flex items-center gap-2"><Button variant="danger" onClick={() => setShowDelete(true)}><Trash2 className="size-4" /> 删除模板</Button><Button variant="secondary" onClick={() => setShowVersionUpload(true)}><Upload className="size-4" /> 上传新版本</Button></div> : undefined}
      />

      {report.template_changed ? (
        <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div><p className="font-bold">模板文件发生变化，请重新验证字段映射。</p><p className="mt-1 text-xs text-amber-700">新版本使用新的 SHA256 指纹，旧版本 Mapping 不会被静默复用。</p></div>
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <InfoCard label="当前查看版本" value={`v${selectedVersion.version_number}`} icon={template.output_type === "pptx" ? <FileType2 className="size-4" /> : <FileSpreadsheet className="size-4" />} />
        <InfoCard label="模板对象" value={report.object_count} />
        <InfoCard label="可参数化" value={report.parameterizable_count} tone="green" />
        <InfoCard label="暂不支持" value={report.unsupported_count} tone={report.unsupported_count ? "amber" : "slate"} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader
            title="模板对象与字段映射"
            description="只有这里明确绑定的客户字段才会进入未来的输出上下文。"
            actions={canManage ? <div className="flex items-center gap-2">{savedMessage ? <span className="text-xs font-semibold text-emerald-600">{savedMessage}</span> : null}<Button onClick={saveMapping} disabled={saving}><Save className="size-4" /> {saving ? "保存中…" : "保存并验证"}</Button></div> : <Badge tone="slate">只读</Badge>}
          />
          <div className="divide-y divide-slate-100">
            {report.objects.map((object) => (
              <TemplateObjectRow
                key={object.object_key}
                object={object}
                binding={mappingByObject.get(object.object_key)}
                customerFields={customerFields}
                canManage={canManage}
                onSourceChange={(source) => changeSource(object, source)}
                onBindingChange={(values) => updateBinding(object.object_key, values)}
              />
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title="模板版本" description="Mapping 始终绑定到具体文件指纹" />
            <div className="space-y-3 p-4">
              <label><span className="label">查看版本</span><select className="input" value={selectedVersion.id} onChange={(event) => setSelectedVersionId(event.target.value)}>{template.versions.map((version) => <option key={version.id} value={version.id}>v{version.version_number} · {version.status === "ready" ? "映射已验证" : "待配置"}</option>)}</select></label>
              <div className="rounded-lg bg-slate-50 p-3 text-[11px] leading-5 text-slate-500"><p className="truncate font-semibold text-slate-700">{selectedVersion.original_filename}</p><p className="mt-1 break-all font-mono">SHA256 · {selectedVersion.template_sha256}</p></div>
            </div>
          </Card>

          <Card className="border-amber-200/80">
            <CardHeader title="输出安全边界" actions={<LockKeyhole className="size-4 text-amber-600" />} />
            <div className="space-y-3 p-4 text-xs leading-5 text-slate-600">
              <p>本租户共有 <strong>{internalFieldCount}</strong> 个内部字段。它们不会出现在映射选项中，后端也会拒绝相关请求。</p>
              <p>未绑定字段不会默认输出。图片必须选择明确来源，并保存 fallback 顺序。</p>
            </div>
          </Card>

          <Card>
            <CardHeader title="验证范围" description="第一版支持范围" />
            <div className="p-4">
              <div className="flex flex-wrap gap-2">{report.capabilities.map((item) => <Badge key={item} tone="green"><CheckCircle2 className="mr-1 size-3" />{item}</Badge>)}</div>
              {report.unsupported_capabilities.length ? <div className="mt-3 flex flex-wrap gap-2">{report.unsupported_capabilities.map((item) => <Badge key={item} tone="slate"><XCircle className="mr-1 size-3" />{item}</Badge>)}</div> : null}
              {report.warnings.map((warning) => <p key={warning} className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">{warning}</p>)}
            </div>
          </Card>
        </div>
      </div>

      {showVersionUpload ? (
        <UploadVersionModal
          outputType={template.output_type}
          onClose={() => setShowVersionUpload(false)}
          onCreated={(updated) => {
            setTemplate(updated);
            setSelectedVersionId(updated.current_version.id);
            setShowVersionUpload(false);
          }}
          templateId={template.id}
        />
      ) : null}

      {showDelete ? (
        <DeleteConfirmationModal
          title={`删除模板 ${template.name}`}
          description="模板记录、全部版本和字段映射都会被删除，同时解除客户默认模板绑定。已用于历史生成任务的模板会受到保护，系统将拒绝删除。"
          confirmLabel="永久删除模板"
          onClose={() => setShowDelete(false)}
          onConfirm={async () => {
            await apiRequest<void>(`/output-templates/${template.id}`, { method: "DELETE" });
            navigate("/templates", { replace: true });
          }}
        />
      ) : null}
    </div>
  );
}

function InfoCard({ label, value, icon, tone = "slate" }: { label: string; value: string | number; icon?: React.ReactNode; tone?: "slate" | "green" | "amber" }) {
  const textTone = { slate: "text-slate-950", green: "text-emerald-700", amber: "text-amber-700" }[tone];
  return <Card className="p-4"><div className="flex items-center gap-2 text-xs text-slate-500">{icon}{label}</div><p className={`mt-2 text-2xl font-black ${textTone}`}>{value}</p></Card>;
}

function TemplateObjectRow({ object, binding, customerFields, canManage, onSourceChange, onBindingChange }: { object: TemplateObject; binding?: OutputTemplateBinding; customerFields: FieldDefinition[]; canManage: boolean; onSourceChange: (source: string) => void; onBindingChange: (values: Partial<OutputTemplateBinding>) => void }) {
  const isImage = object.object_type === "image";
  return (
    <div className={`p-5 ${object.supported ? "" : "bg-slate-50/70"}`}>
      <div className="grid gap-4 lg:grid-cols-[minmax(220px,0.8fr)_minmax(280px,1.2fr)]">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><Badge tone={object.supported ? "blue" : "slate"}>{objectTypeLabel[object.object_type] || object.object_type}</Badge><span className="truncate text-xs font-bold text-slate-800">{objectName(object)}</span></div>
          <p className="mt-2 truncate text-[11px] text-slate-400">{object.container}{object.shape_id ? ` · Shape ${object.shape_id}` : ""}</p>
          {object.preview !== null && object.preview !== "" ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{String(object.preview)}</p> : null}
          {!object.supported ? <p className="mt-2 text-xs font-semibold text-slate-500">{object.reason}</p> : null}
        </div>
        {object.supported ? (
          <div className="space-y-3">
            <label><span className="label">绑定来源</span><select className="input" disabled={!canManage} value={binding?.source ?? ""} onChange={(event) => onSourceChange(event.target.value)}><option value="">不输出此对象</option>{isImage ? <optgroup label="图片来源">{imageSources.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</optgroup> : <><optgroup label="客户资料">{customerTextSources.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</optgroup><optgroup label="客户报价字段">{customerFields.map((field) => <option key={field.id} value={field.code}>{field.label} · {field.code}</option>)}</optgroup></>}</select></label>
            {binding ? (
              <div className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50/70 p-3 sm:grid-cols-2">
                {!binding.source.startsWith("customer.") ? <label><span className="label">产品槽位</span><input className="input" disabled={!canManage} type="number" min="1" max="1000" value={binding.product_slot ?? 1} onChange={(event) => onBindingChange({ product_slot: Math.max(1, Number(event.target.value) || 1) })} /><span className="mt-1 block text-[10px] text-slate-400">按生成任务中的产品排序，从 1 开始</span></label> : null}
                {isImage ? (
                  <>
                    <label><span className="label">图片适配</span><select className="input" disabled={!canManage} value={binding.fit ?? "contain"} onChange={(event) => onBindingChange({ fit: event.target.value as OutputTemplateBinding["fit"] })}><option value="contain">完整显示 contain</option><option value="cover">填满裁切 cover</option><option value="stretch">拉伸 stretch</option></select></label>
                    <label><span className="label">图片位置</span><select className="input" disabled={!canManage} value={binding.position ?? "center"} onChange={(event) => onBindingChange({ position: event.target.value as OutputTemplateBinding["position"] })}><option value="center">居中</option><option value="top">顶部</option><option value="right">右侧</option><option value="bottom">底部</option><option value="left">左侧</option></select></label>
                    <label className="sm:col-span-2"><span className="label">Fallback 顺序</span><input className="input" disabled={!canManage} value={binding.fallback.join(", ")} onChange={(event) => onBindingChange({ fallback: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) })} /></label>
                  </>
                ) : (
                  <>
                    <label><span className="label">输出标签</span><input className="input" disabled={!canManage} value={binding.label ?? ""} onChange={(event) => onBindingChange({ label: event.target.value || null })} placeholder="沿用模板原标签" /></label>
                    <label><span className="label">格式化</span><select className="input" disabled={!canManage} value={binding.formatter ?? "text"} onChange={(event) => onBindingChange({ formatter: event.target.value as OutputTemplateBinding["formatter"] })}>{Object.entries(formatterLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                    <label><span className="label">默认值</span><input className="input" disabled={!canManage} value={String(binding.default_value ?? "")} onChange={(event) => onBindingChange({ default_value: event.target.value || null })} /></label>
                    <label><span className="label">转换</span><select className="input" disabled={!canManage} value={binding.transform ?? ""} onChange={(event) => onBindingChange({ transform: event.target.value ? event.target.value as OutputTemplateBinding["transform"] : null })}><option value="">不转换</option><option value="trim">去除首尾空格</option><option value="uppercase">转大写</option><option value="lowercase">转小写</option><option value="normalize_dimension">标准化尺寸</option></select></label>
                    {object.object_key.startsWith("xlsx:") ? <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 sm:col-span-2"><input type="checkbox" disabled={!canManage} checked={binding.allow_formula ?? false} onChange={(event) => onBindingChange({ allow_formula: event.target.checked })} /> 明确允许公式输入（默认关闭）</label> : null}
                  </>
                )}
                <label className="flex items-center gap-2 text-xs font-semibold text-slate-600 sm:col-span-2"><input type="checkbox" disabled={!canManage} checked={binding.visible} onChange={(event) => onBindingChange({ visible: event.target.checked })} /> 输出此对象</label>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex items-center rounded-lg border border-dashed border-slate-300 px-4 py-3 text-xs text-slate-500">该对象会保留在原模板中，但当前版本不会参数化修改。</div>
        )}
      </div>
    </div>
  );
}

function UploadVersionModal({ templateId, outputType, onClose, onCreated }: { templateId: string; outputType: "pptx" | "xlsx"; onClose: () => void; onCreated: (template: OutputTemplateDetail) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const updated = await apiRequest<OutputTemplateDetail>(`/output-templates/${templateId}/versions`, { method: "POST", body: form, timeoutMs: 60_000 });
      onCreated(updated);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "模板版本上传失败。");
    } finally {
      setSubmitting(false);
    }
  }
  return <Modal title="上传模板新版本" description="新文件会生成独立指纹，旧 Mapping 不会自动沿用。" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}><label><span className="label">{outputType.toUpperCase()} 文件 *</span><input className="input py-2" required type="file" accept={`.${outputType}`} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label><div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">文件 SHA256 变化后，系统将提示重新验证字段映射。</div>{error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}<div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={!file || submitting}>{submitting ? "验证中…" : "上传新版本"}</Button></div></form></Modal>;
}
