import {
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  FileType2,
  Layers3,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { DeleteConfirmationModal } from "../components/ui/DeleteConfirmationModal";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { ImportTemplate } from "../types/imports";
import type { OutputTemplate, OutputTemplateDetail } from "../types/templates";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
type PendingDelete = { kind: "output" | "import"; id: string; name: string };

function fileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function TemplateCenterPage() {
  const { session } = useAuth();
  const { reportError } = useGlobalError();
  const [templates, setTemplates] = useState<OutputTemplate[]>([]);
  const [importTemplates, setImportTemplates] = useState<ImportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const canManage = session?.user.role === "owner" || session?.user.role === "admin";

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiRequest<{ items: OutputTemplate[]; total: number }>("/output-templates"),
      apiRequest<{ items: ImportTemplate[]; total: number }>("/import-templates"),
    ])
      .then(([outputPayload, importPayload]) => {
        setTemplates(outputPayload.items);
        setImportTemplates(importPayload.items);
      })
      .catch((caught) =>
        reportError(caught instanceof ApiError ? caught.message : "模板列表加载失败。"),
      )
      .finally(() => setLoading(false));
  }, [reportError]);

  useEffect(() => load(), [load]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Output Templates"
        title="模板中心"
        description="上传 PPTX 或 XLSX 模板，验证可参数化对象并建立显式字段映射。第一版不提供在线 PowerPoint 编辑器。"
        actions={canManage ? (
          <Button onClick={() => setShowUpload(true)}>
            <Plus className="size-4" /> 上传模板
          </Button>
        ) : undefined}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="输出模板" value={templates.length} icon={<Layers3 className="size-4" />} />
        <SummaryCard label="导入模板" value={importTemplates.length} icon={<FileSpreadsheet className="size-4" />} />
        <SummaryCard
          label="映射已验证"
          value={templates.filter((item) => item.current_version.status === "ready").length}
          icon={<CheckCircle2 className="size-4" />}
          tone="green"
        />
        <SummaryCard
          label="待配置"
          value={templates.filter((item) => item.current_version.status === "needs_mapping").length}
          icon={<AlertTriangle className="size-4" />}
          tone="amber"
        />
      </div>

      {loading ? (
        <Card className="p-12 text-center text-sm text-slate-500">正在加载模板…</Card>
      ) : templates.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {templates.map((template) => {
            const version = template.current_version;
            const report = version.validation_report;
            return (
              <article
                key={template.id}
                className="card group overflow-hidden transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
              >
                <Link to={`/templates/${template.id}`} className="block">
                  <div className="flex items-start gap-4 p-5">
                    <span className={`grid size-12 shrink-0 place-items-center rounded-xl ${template.output_type === "pptx" ? "bg-orange-50 text-orange-700" : "bg-emerald-50 text-emerald-700"}`}>
                      {template.output_type === "pptx" ? <FileType2 className="size-5" /> : <FileSpreadsheet className="size-5" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h2 className="truncate text-sm font-extrabold text-slate-950">{template.name}</h2>
                          <p className="mt-1 truncate text-xs text-slate-500">{template.description || version.original_filename}</p>
                        </div>
                        <Badge tone={version.status === "ready" ? "green" : "amber"}>
                          {version.status === "ready" ? "映射已验证" : "待配置映射"}
                        </Badge>
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 px-3 py-3 text-center">
                        <Metric value={`v${version.version_number}`} label="当前版本" />
                        <Metric value={report.parameterizable_count} label="可参数化" />
                        <Metric value={report.unsupported_count} label="暂不支持" />
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[10px] text-slate-400">
                        <span>{version.original_filename}</span>
                        <span>{fileSize(version.size_bytes)}</span>
                      </div>
                    </div>
                  </div>
                </Link>
                {canManage ? (
                  <div className="flex justify-end border-t border-slate-100 px-4 py-2.5">
                    <Button variant="ghost" className="h-8 px-2.5 text-red-600 hover:bg-red-50 hover:text-red-700" onClick={() => setPendingDelete({ kind: "output", id: template.id, name: template.name })}>
                      <Trash2 className="size-3.5" /> 删除模板
                    </Button>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Upload className="size-5" />}
            title="还没有输出模板"
            description="上传现有 PPTX 或 XLSX 文件，系统会先验证对象和模板边界，再开放字段映射。"
            action={canManage ? <Button onClick={() => setShowUpload(true)}>上传第一个模板</Button> : undefined}
          />
        </Card>
      )}

      <Card>
        <CardHeader
          title="Excel 导入模板"
          description="复用供应商工作簿的字段映射；编辑与实际应用仍在数据导入工作台完成。"
          actions={<Link to="/imports" className="text-xs font-bold text-[#1a365d] hover:underline">打开数据导入</Link>}
        />
        {importTemplates.length ? (
          <div className="grid gap-px bg-slate-100 sm:grid-cols-2 xl:grid-cols-3">
            {importTemplates.map((template) => (
              <article key={template.id} className="bg-white p-4 transition hover:bg-slate-50">
                <div className="flex items-center justify-between gap-3"><Link to="/imports" className="min-w-0"><h3 className="truncate text-sm font-bold text-slate-900">{template.name}</h3></Link><Badge tone={template.status === "active" ? "green" : "slate"}>{template.status === "active" ? "有效" : "已归档"}</Badge></div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">{template.description || `${template.mapping_config.fields.length} 个字段映射`}</p>
                <div className="mt-3 flex items-center justify-between gap-3"><p className="text-[10px] text-slate-400">{template.mapping_config.sheet_names?.join("、") || "全部工作表"}</p>{canManage ? <button type="button" aria-label={`删除导入模板 ${template.name}`} onClick={() => setPendingDelete({ kind: "import", id: template.id, name: template.name })} className="grid size-8 place-items-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-600"><Trash2 className="size-4" /></button> : null}</div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState icon={<FileSpreadsheet className="size-5" />} title="暂无导入模板" description="在数据导入工作台确认字段映射后，可以保存为可复用模板。" />
        )}
      </Card>

      {showUpload ? (
        <UploadTemplateModal
          onClose={() => setShowUpload(false)}
          onCreated={(created) => {
            setShowUpload(false);
            setTemplates((current) => [created, ...current]);
          }}
        />
      ) : null}

      {pendingDelete ? (
        <DeleteConfirmationModal
          title={`删除${pendingDelete.kind === "output" ? "输出" : "导入"}模板 ${pendingDelete.name}`}
          description={pendingDelete.kind === "output" ? "模板记录、全部版本和字段映射都会被删除，并解除客户默认模板绑定。已用于历史生成任务的模板会受到保护。" : "该导入映射模板会被永久删除；历史导入任务已保存映射快照，不会受影响。"}
          confirmLabel="永久删除模板"
          onClose={() => setPendingDelete(null)}
          onConfirm={async () => {
            const endpoint = pendingDelete.kind === "output"
              ? `/output-templates/${pendingDelete.id}`
              : `/import-templates/${pendingDelete.id}`;
            await apiRequest<void>(endpoint, { method: "DELETE" });
            if (pendingDelete.kind === "output") {
              setTemplates((current) => current.filter((item) => item.id !== pendingDelete.id));
            } else {
              setImportTemplates((current) => current.filter((item) => item.id !== pendingDelete.id));
            }
            setPendingDelete(null);
          }}
        />
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value, icon, tone = "blue" }: { label: string; value: number; icon: React.ReactNode; tone?: "blue" | "green" | "amber" }) {
  const style = { blue: "bg-blue-50 text-blue-700", green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700" }[tone];
  return <Card className="flex items-center gap-3 p-4"><span className={`grid size-9 place-items-center rounded-lg ${style}`}>{icon}</span><div><p className="text-xl font-black text-slate-950">{value}</p><p className="text-xs text-slate-500">{label}</p></div></Card>;
}

function Metric({ value, label }: { value: string | number; label: string }) {
  return <div><p className="text-sm font-extrabold text-slate-800">{value}</p><p className="mt-0.5 text-[10px] text-slate-400">{label}</p></div>;
}

function UploadTemplateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (template: OutputTemplateDetail) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setError("模板文件不能超过 50 MB。");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("name", name.trim());
      form.append("description", description.trim());
      form.append("file", file);
      const created = await apiRequest<OutputTemplateDetail>("/output-templates", {
        method: "POST",
        body: form,
        timeoutMs: 60_000,
      });
      onCreated(created);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "模板上传失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="上传输出模板" description="系统会读取模板结构，但不会修改原始文件。" onClose={onClose}>
      <form className="space-y-4 p-5" onSubmit={submit}>
        <label><span className="label">模板名称 *</span><input className="input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如 Customer A 产品报价" /></label>
        <label><span className="label">说明</span><textarea className="textarea" maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="记录客户、使用场景或设计版本" /></label>
        <label><span className="label">PPTX / XLSX 文件 *</span><input className="input py-2" required type="file" accept=".pptx,.xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-800">上传后将执行 Template Validation，并明确列出可参数化对象和暂不支持对象。</div>
        {error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={submitting || !name.trim() || !file}>{submitting ? "解析中…" : "上传并验证"}</Button></div>
      </form>
    </Modal>
  );
}
