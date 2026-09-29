import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileCheck2,
  FileSpreadsheet,
  History,
  ImageIcon,
  Layers3,
  LoaderCircle,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  WandSparkles,
} from "lucide-react";
import {
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import { cn } from "../lib/utils";
import type { FieldDefinition } from "../types/catalog";
import type {
  ImportFieldMapping,
  ImportImageCandidate,
  ImportJob,
  ImportMappingConfig,
  ImportTemplate,
  ImportTransform,
} from "../types/imports";

type View = "home" | "mapping" | "preview" | "result";
type DuplicateStrategy = "overwrite" | "update_non_empty" | "skip";

const transforms: Array<{ value: ImportTransform; label: string }> = [
  { value: "trim", label: "去除首尾空格" },
  { value: "text", label: "文本" },
  { value: "uppercase", label: "转大写" },
  { value: "lowercase", label: "转小写" },
  { value: "decimal", label: "小数" },
  { value: "integer", label: "整数" },
  { value: "boolean", label: "布尔值" },
  { value: "date", label: "日期" },
  { value: "normalize_dimension", label: "规格标准化" },
];

const imageTypeLabels: Record<ImportImageCandidate["image_type"], string> = {
  main: "产品图",
  white_background: "白底图",
  lifestyle: "场景图",
  detail: "细节图",
  packaging: "包装图",
  certificate: "证书",
  other: "其他",
};

const statusLabels: Record<ImportJob["status"], string> = {
  analyzing: "分析中",
  analyzed: "待映射",
  preview_ready: "待确认",
  importing: "导入中",
  completed: "已完成",
  failed: "失败",
};

function statusTone(status: ImportJob["status"]): "blue" | "green" | "amber" | "red" | "slate" {
  if (status === "completed") return "green";
  if (status === "failed") return "red";
  if (status === "preview_ready") return "amber";
  if (status === "analyzed" || status === "analyzing" || status === "importing") return "blue";
  return "slate";
}

function emptyFieldMapping(source = "", target = ""): ImportFieldMapping {
  return {
    source,
    target,
    transform: "trim",
    default_value: null,
    required: target === "sku" || target === "product_name",
    validation: {},
    formatter: null,
  };
}

function firstProductRow(
  job: ImportJob,
  sheetName: string,
  mappings: ImportFieldMapping[],
  headerRow: number,
) {
  const sheet = job.analysis.sheets.find((item) => item.name === sheetName);
  const skuColumn = mappings.find((item) => item.target === "sku")?.source;
  const nameColumn = mappings.find((item) => item.target === "product_name")?.source;
  if (!sheet || !skuColumn || !nameColumn) return headerRow + 1;
  const row = sheet.sample_rows.find((item) => {
    if (item.row <= headerRow) return false;
    const sku = item.cells[skuColumn];
    const name = item.cells[nameColumn];
    return sku != null && String(sku).trim() !== "" && name != null && String(name).trim() !== "";
  });
  return row?.row ?? headerRow + 1;
}

export function suggestedMapping(job: ImportJob, fields: FieldDefinition[]): ImportMappingConfig {
  const activeCodes = new Set(fields.filter((field) => field.status === "active").map((field) => field.code));
  const firstSheet = job.analysis.sheets[0];
  const suggestions: ImportFieldMapping[] = (firstSheet?.suggested_mapping ?? [])
    .filter((item) => activeCodes.has(item.target))
    .map((item) => ({
      ...emptyFieldMapping(item.source, item.target),
      transform: item.transform,
      required: item.required,
    }));

  for (const target of ["sku", "product_name"]) {
    if (!suggestions.some((item) => item.target === target)) {
      const fallback = firstSheet?.headers.find((header) => {
        const label = String(header.value ?? "").toLowerCase();
        return target === "sku"
          ? label.includes("sku") || label.includes("货号") || label.includes("item no")
          : label.includes("description") || label.includes("name") || label.includes("品名");
      });
      suggestions.push(emptyFieldMapping(fallback?.column ?? "", target));
    }
  }

  const headerRow = 1;
  return {
    version: "1.0",
    // Select only the primary product sheet by default. Auxiliary sheets such
    // as image indexes often repeat every SKU and must be explicitly opted in.
    sheet_names: firstSheet ? [firstSheet.name] : [],
    header_row: headerRow,
    data_start_row: firstSheet
      ? firstProductRow(job, firstSheet.name, suggestions, headerRow)
      : headerRow + 1,
    fields: suggestions,
  };
}

function apiMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

const MAX_EXCEL_UPLOAD_BYTES = 50 * 1024 * 1024;

export function ImportsPage() {
  const { session } = useAuth();
  const { reportError } = useGlobalError();
  const [view, setView] = useState<View>("home");
  const [templates, setTemplates] = useState<ImportTemplate[]>([]);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<ImportMappingConfig | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);
  const canManageTemplates = session?.user.role === "owner" || session?.user.role === "admin";

  const loadOverview = useCallback(async () => {
    try {
      const [templatePayload, fieldPayload, jobPayload] = await Promise.all([
        apiRequest<{ items: ImportTemplate[] }>("/import-templates"),
        apiRequest<{ items: FieldDefinition[] }>("/field-definitions"),
        apiRequest<{ items: ImportJob[] }>("/import-jobs"),
      ]);
      setTemplates(templatePayload.items);
      setFields(fieldPayload.items);
      setJobs(jobPayload.items);
    } catch {
      reportError("导入中心数据加载失败，请稍后重试。");
    }
  }, [reportError]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  function reset() {
    setView("home");
    setJob(null);
    setMapping(null);
    setSelectedTemplateId("");
    setFile(null);
    setLocalError(null);
    void loadOverview();
  }

  async function analyzeFile() {
    if (!file) {
      setLocalError("请先选择一个 XLSX 文件。");
      return;
    }
    if (file.size > MAX_EXCEL_UPLOAD_BYTES) {
      setLocalError("Excel 文件不能超过 50 MB。");
      return;
    }
    setBusy(true);
    setLocalError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const analyzed = await apiRequest<ImportJob>("/import-jobs/analyze", {
        method: "POST",
        body,
        timeoutMs: 120_000,
      });
      setJob(analyzed);
      setMapping(suggestedMapping(analyzed, fields));
      setSelectedTemplateId("");
      setView("mapping");
    } catch (error) {
      setLocalError(apiMessage(error, "Excel 文件分析失败。"));
    } finally {
      setBusy(false);
    }
  }

  async function openJob(item: ImportJob) {
    setBusy(true);
    setLocalError(null);
    try {
      const detailed = await apiRequest<ImportJob>(`/import-jobs/${item.id}`, {
        timeoutMs: 60_000,
      });
      setJob(detailed);
      setMapping(detailed.mapping_snapshot ?? suggestedMapping(detailed, fields));
      setSelectedTemplateId(detailed.import_template_id ?? "");
      setView(
        detailed.status === "completed"
          ? "result"
          : detailed.status === "preview_ready"
            ? "preview"
            : "mapping",
      );
    } catch (error) {
      reportError(apiMessage(error, "导入任务加载失败。"));
    } finally {
      setBusy(false);
    }
  }

  function applyTemplate(templateId: string) {
    setSelectedTemplateId(templateId);
    const template = templates.find((item) => item.id === templateId);
    if (template) setMapping(template.mapping_config);
  }

  function validateMapping(config: ImportMappingConfig): string | null {
    if (!config.sheet_names?.length) return "请至少选择一个工作表。";
    if (!config.fields.length) return "请至少配置一个字段映射。";
    if (config.data_start_row <= config.header_row) return "数据起始行必须位于表头行之后。";
    if (config.fields.some((item) => !item.source || !item.target)) return "每一行映射都必须选择来源列和目标字段。";
    const targets = config.fields.map((item) => item.target);
    if (new Set(targets).size !== targets.length) return "同一个目标字段只能映射一次。";
    if (!targets.includes("sku") || !targets.includes("product_name")) return "SKU 和产品名称是必需映射。";
    return null;
  }

  async function createPreview() {
    if (!job || !mapping) return;
    const validationError = validateMapping(mapping);
    if (validationError) {
      setLocalError(validationError);
      return;
    }
    setBusy(true);
    setLocalError(null);
    try {
      const payload = selectedTemplateId
        ? { import_template_id: selectedTemplateId }
        : { mapping_config: mapping };
      const preview = await apiRequest<ImportJob>(`/import-jobs/${job.id}/preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        timeoutMs: 120_000,
      });
      setJob(preview);
      setMapping(preview.mapping_snapshot);
      setView("preview");
      void loadOverview();
    } catch (error) {
      setLocalError(apiMessage(error, "导入预览生成失败。"));
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport(strategy: DuplicateStrategy) {
    if (!job) return;
    setBusy(true);
    setLocalError(null);
    try {
      const completed = await apiRequest<ImportJob>(`/import-jobs/${job.id}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duplicate_strategy: strategy }),
        timeoutMs: 180_000,
      });
      setJob(completed);
      setView("result");
      void loadOverview();
    } catch (error) {
      setLocalError(apiMessage(error, "确认导入失败。"));
    } finally {
      setBusy(false);
    }
  }

  async function updateImage(
    candidate: ImportImageCandidate,
    payload: { matched_sku: string | null; image_type: string; is_primary: boolean },
  ) {
    const updated = await apiRequest<ImportImageCandidate>(
      `/import-image-candidates/${candidate.id}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    setJob((current) =>
      current
        ? { ...current, images: current.images.map((item) => (item.id === updated.id ? updated : item)) }
        : current,
    );
  }

  async function saveTemplate(name: string, description: string) {
    if (!mapping) return;
    const validationError = validateMapping(mapping);
    if (validationError) throw new Error(validationError);
    const created = await apiRequest<ImportTemplate>("/import-templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: description || null, mapping_config: mapping }),
    });
    setTemplates((current) => [created, ...current]);
    setSelectedTemplateId(created.id);
    setShowSaveTemplate(false);
  }

  const activeStep = view === "home" ? 1 : view === "mapping" ? 2 : view === "preview" ? 3 : 4;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Import Center"
        title="Excel 数据导入"
        description="分析供应商工作簿，确认字段与图片匹配后，再将资料写入产品库。"
        actions={
          view !== "home" ? (
            <Button variant="secondary" onClick={reset} disabled={busy}>
              <ArrowLeft className="size-4" /> 返回导入中心
            </Button>
          ) : undefined
        }
      />

      <ImportStepper activeStep={activeStep} />

      {localError ? (
        <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>{localError}</span>
        </div>
      ) : null}

      {view === "home" ? (
        <ImportHome
          file={file}
          jobs={jobs}
          templates={templates}
          busy={busy}
          onFile={setFile}
          onAnalyze={analyzeFile}
          onOpenJob={openJob}
        />
      ) : null}

      {view === "mapping" && job && mapping ? (
        <MappingStage
          job={job}
          mapping={mapping}
          fields={fields}
          templates={templates.filter((item) => item.status === "active")}
          selectedTemplateId={selectedTemplateId}
          busy={busy}
          canSaveTemplate={canManageTemplates}
          onMappingChange={(next) => {
            setMapping(next);
            setSelectedTemplateId("");
          }}
          onTemplateChange={applyTemplate}
          onSaveTemplate={() => setShowSaveTemplate(true)}
          onPreview={createPreview}
        />
      ) : null}

      {view === "preview" && job ? (
        <PreviewStage
          job={job}
          busy={busy}
          onBack={() => setView("mapping")}
          onImageUpdate={updateImage}
          onConfirm={confirmImport}
        />
      ) : null}

      {view === "result" && job ? <ResultStage job={job} onReset={reset} /> : null}

      {showSaveTemplate && mapping ? (
        <SaveTemplateModal
          onClose={() => setShowSaveTemplate(false)}
          onSave={saveTemplate}
        />
      ) : null}
    </div>
  );
}

function ImportStepper({ activeStep }: { activeStep: number }) {
  const steps = [
    { label: "上传文件", icon: UploadCloud },
    { label: "字段映射", icon: Layers3 },
    { label: "预览确认", icon: ShieldCheck },
    { label: "导入完成", icon: CheckCircle2 },
  ];
  return (
    <Card className="overflow-hidden">
      <ol className="grid grid-cols-4" aria-label="导入步骤">
        {steps.map(({ label, icon: Icon }, index) => {
          const step = index + 1;
          const done = step < activeStep;
          const active = step === activeStep;
          return (
            <li
              key={label}
              className={cn(
                "relative flex min-h-16 items-center justify-center gap-2 border-r border-slate-100 px-2 text-center text-[11px] font-semibold last:border-r-0 sm:min-h-[72px] sm:text-xs",
                active ? "bg-blue-50/80 text-[#1a365d]" : done ? "text-emerald-700" : "text-slate-400",
              )}
            >
              {active ? <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#1a365d]" /> : null}
              <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg", active ? "bg-[#1a365d] text-white" : done ? "bg-emerald-50" : "bg-slate-100")}>
                {done ? <Check className="size-3.5" /> : <Icon className="size-3.5" />}
              </span>
              <span className="hidden sm:inline">{label}</span>
              <span className="sm:hidden">{step}</span>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function ImportHome({
  file,
  jobs,
  templates,
  busy,
  onFile,
  onAnalyze,
  onOpenJob,
}: {
  file: File | null;
  jobs: ImportJob[];
  templates: ImportTemplate[];
  busy: boolean;
  onFile: (file: File | null) => void;
  onAnalyze: () => void;
  onOpenJob: (job: ImportJob) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function pickFile(candidate: File | undefined) {
    if (candidate) onFile(candidate);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(300px,0.65fr)]">
      <div className="space-y-5">
        <Card className="p-5 sm:p-7">
          <div
            className={cn(
              "flex min-h-[280px] flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
              dragging ? "border-[#2c5aa0] bg-blue-50" : "border-slate-200 bg-slate-50/55",
            )}
            onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              pickFile(event.dataTransfer.files[0]);
            }}
          >
            <span className="grid size-16 place-items-center rounded-2xl bg-white text-[#2c5aa0] shadow-sm ring-1 ring-slate-200">
              <FileSpreadsheet className="size-7" />
            </span>
            <h2 className="mt-5 text-lg font-extrabold text-slate-950">
              {file ? file.name : "上传供应商 Excel"}
            </h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
              {file
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB · 等待安全分析`
                : "拖放 XLSX 文件到这里，或从电脑中选择。系统会先分析字段、图片与工作表，不会立即写入产品库。"}
            </p>
            <input
              ref={inputRef}
              type="file"
              className="sr-only"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event: ChangeEvent<HTMLInputElement>) => pickFile(event.target.files?.[0])}
            />
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Button variant="secondary" onClick={() => inputRef.current?.click()} disabled={busy}>
                <UploadCloud className="size-4" /> {file ? "更换文件" : "选择 XLSX 文件"}
              </Button>
              <Button onClick={onAnalyze} disabled={!file || busy}>
                {busy ? <LoaderCircle className="size-4 animate-spin" /> : <WandSparkles className="size-4" />}
                {busy ? "正在分析…" : "开始分析"}
              </Button>
            </div>
          </div>
          <div className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-3">
            <SafetyHint icon={<FileCheck2 className="size-4" />} title="仅支持 XLSX" text="拒绝宏和受保护文件" />
            <SafetyHint icon={<ImageIcon className="size-4" />} title="图片指纹" text="记录 SHA256 与锚点" />
            <SafetyHint icon={<ShieldCheck className="size-4" />} title="确认后写入" text="低置信度绝不自动归属" />
          </div>
        </Card>

        <Card>
          <CardHeader title="最近导入任务" description="可继续待映射或待确认的任务" actions={<Badge tone="slate">{jobs.length} 个任务</Badge>} />
          {jobs.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                <thead className="bg-slate-50/80 text-[11px] font-bold uppercase tracking-wide text-slate-500">
                  <tr><th className="px-5 py-3">文件</th><th className="px-4 py-3">状态</th><th className="px-4 py-3">数据行</th><th className="px-4 py-3">更新时间</th><th className="px-5 py-3 text-right">操作</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {jobs.slice(0, 12).map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-3.5"><p className="max-w-xs truncate text-sm font-bold text-slate-900">{item.source_filename}</p><p className="mt-0.5 font-mono text-[10px] text-slate-400">{item.source_sha256.slice(0, 16)}…</p></td>
                      <td className="px-4 py-3.5"><Badge tone={statusTone(item.status)}>{statusLabels[item.status]}</Badge></td>
                      <td className="px-4 py-3.5 text-xs tabular-nums text-slate-600">{item.total_rows || "—"}</td>
                      <td className="px-4 py-3.5 text-xs text-slate-500">{new Date(item.updated_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
                      <td className="px-5 py-3.5 text-right"><button type="button" onClick={() => onOpenJob(item)} className="text-xs font-semibold text-[#1a365d] hover:underline">{item.status === "completed" ? "查看结果" : "继续任务"}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon={<History className="size-5" />} title="暂无导入记录" description="完成一次工作簿分析后，任务会显示在这里。" />
          )}
        </Card>
      </div>

      <Card className="self-start">
        <CardHeader title="导入模板" description="复用已验证的列映射" actions={<Badge tone="blue">{templates.filter((item) => item.status === "active").length} 个有效</Badge>} />
        {templates.length ? (
          <div className="divide-y divide-slate-100">
            {templates.slice(0, 8).map((template) => (
              <div key={template.id} className="px-5 py-4">
                <div className="flex items-center justify-between gap-3"><h3 className="truncate text-sm font-bold text-slate-900">{template.name}</h3><Badge tone={template.status === "active" ? "green" : "slate"}>{template.status === "active" ? "有效" : "已归档"}</Badge></div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{template.description || `${template.mapping_config.fields.length} 个字段映射`}</p>
                <p className="mt-2 text-[10px] text-slate-400">{template.mapping_config.sheet_names?.join("、") || "全部工作表"}</p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState icon={<Layers3 className="size-5" />} title="暂无导入模板" description="分析文件并确认字段映射后，可将配置保存为模板。" />
        )}
      </Card>
    </div>
  );
}

function SafetyHint({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return <div className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2.5"><span className="text-[#2c5aa0]">{icon}</span><span><strong className="block text-slate-700">{title}</strong><span className="text-[10px] text-slate-400">{text}</span></span></div>;
}

function MappingStage({
  job,
  mapping,
  fields,
  templates,
  selectedTemplateId,
  busy,
  canSaveTemplate,
  onMappingChange,
  onTemplateChange,
  onSaveTemplate,
  onPreview,
}: {
  job: ImportJob;
  mapping: ImportMappingConfig;
  fields: FieldDefinition[];
  templates: ImportTemplate[];
  selectedTemplateId: string;
  busy: boolean;
  canSaveTemplate: boolean;
  onMappingChange: (mapping: ImportMappingConfig) => void;
  onTemplateChange: (id: string) => void;
  onSaveTemplate: () => void;
  onPreview: () => void;
}) {
  const selectedSheets = mapping.sheet_names ?? [];
  const primarySheet = job.analysis.sheets.find((sheet) => selectedSheets.includes(sheet.name)) ?? job.analysis.sheets[0];
  const targetFields = fields.filter((field) => field.status === "active");

  function updateField(index: number, patch: Partial<ImportFieldMapping>) {
    onMappingChange({
      ...mapping,
      fields: mapping.fields.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item),
    });
  }

  function addField() {
    const usedTargets = new Set(mapping.fields.map((item) => item.target));
    const usedSources = new Set(mapping.fields.map((item) => item.source));
    const target = targetFields.find((field) => !usedTargets.has(field.code))?.code ?? "";
    const source = primarySheet?.headers.find((header) => !usedSources.has(header.column))?.column ?? "";
    onMappingChange({ ...mapping, fields: [...mapping.fields, emptyFieldMapping(source, target)] });
  }

  function toggleSheet(sheetName: string) {
    const current = mapping.sheet_names ?? [];
    onMappingChange({
      ...mapping,
      sheet_names: current.includes(sheetName)
        ? current.filter((item) => item !== sheetName)
        : [...current, sheetName],
    });
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title={job.source_filename}
          description={`检测到 ${job.analysis.sheets.length} 个工作表、${job.images.length} 张图片；请选择要导入的工作表并校准字段。`}
          actions={<Badge tone="blue"><Sparkles className="mr-1 size-3" /> 已智能建议</Badge>}
        />
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div>
            <p className="label">工作表</p>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {job.analysis.sheets.map((sheet) => (
                <label key={sheet.name} className={cn("flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-3", selectedSheets.includes(sheet.name) ? "border-blue-200 bg-blue-50/70" : "border-slate-200 bg-white")}>
                  <input type="checkbox" checked={selectedSheets.includes(sheet.name)} onChange={() => toggleSheet(sheet.name)} className="size-4 accent-[#1a365d]" />
                  <span className="min-w-0"><span className="block truncate text-xs font-bold text-slate-800">{sheet.name}</span><span className="text-[10px] text-slate-400">{Math.max(0, sheet.max_row - mapping.header_row)} 行 · {sheet.images.length} 图</span></span>
                </label>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <label><span className="label">应用已有模板</span><select className="input" value={selectedTemplateId} onChange={(event) => onTemplateChange(event.target.value)}><option value="">智能建议 / 自定义</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>
            <div className="grid grid-cols-2 gap-2">
              <label><span className="label">表头行</span><input className="input" type="number" min={1} value={mapping.header_row} onChange={(event) => onMappingChange({ ...mapping, header_row: Number(event.target.value) })} /></label>
              <label><span className="label">数据起始行</span><input className="input" type="number" min={2} value={mapping.data_start_row} onChange={(event) => onMappingChange({ ...mapping, data_start_row: Number(event.target.value) })} /></label>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="字段映射"
          description="来源列经过转换和验证后写入目标字段。SKU 与产品名称必须存在。"
          actions={<Button variant="secondary" onClick={addField}><Plus className="size-4" /> 添加字段</Button>}
        />
        <div className="space-y-3 p-4 sm:p-5">
          {mapping.fields.map((item, index) => (
            <div key={`${index}-${item.target}`} className="rounded-xl border border-slate-200 bg-slate-50/45 p-3">
              <div className="grid items-end gap-3 md:grid-cols-[minmax(160px,1fr)_24px_minmax(170px,1fr)_minmax(150px,0.8fr)_auto]">
                <label><span className="label">来源列</span><select className="input" value={item.source} onChange={(event) => updateField(index, { source: event.target.value })}><option value="">选择 Excel 列</option>{primarySheet?.headers.map((header) => <option key={header.column} value={header.column}>{header.column} · {String(header.value)}</option>)}</select></label>
                <ArrowRight className="mb-3 hidden size-4 text-slate-300 md:block" />
                <label><span className="label">目标字段</span><select className="input" value={item.target} onChange={(event) => updateField(index, { target: event.target.value, required: event.target.value === "sku" || event.target.value === "product_name" ? true : item.required })}><option value="">选择产品字段</option>{targetFields.map((field) => <option key={field.id} value={field.code}>{field.label} · {field.code}{field.scope === "internal" ? "（内部）" : ""}</option>)}</select></label>
                <label><span className="label">转换</span><select className="input" value={item.transform ?? "text"} onChange={(event) => updateField(index, { transform: event.target.value as ImportTransform })}>{transforms.map((transform) => <option key={transform.value} value={transform.value}>{transform.label}</option>)}</select></label>
                <div className="flex h-10 items-center justify-end gap-1"><label className="flex h-10 items-center gap-2 px-2 text-xs font-semibold text-slate-600"><input type="checkbox" checked={item.required} disabled={item.target === "sku" || item.target === "product_name"} onChange={(event) => updateField(index, { required: event.target.checked })} className="size-4 accent-[#1a365d]" /> 必填</label><button type="button" aria-label="删除映射" disabled={item.target === "sku" || item.target === "product_name"} onClick={() => onMappingChange({ ...mapping, fields: mapping.fields.filter((_, itemIndex) => itemIndex !== index) })} className="grid size-9 place-items-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"><Trash2 className="size-4" /></button></div>
              </div>
              <details className="mt-3 border-t border-slate-100 pt-3">
                <summary className="cursor-pointer text-[11px] font-semibold text-slate-500">高级规则：默认值、格式化与验证</summary>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <label><span className="label">默认值</span><input className="input" value={item.default_value == null ? "" : String(item.default_value)} onChange={(event) => updateField(index, { default_value: event.target.value || null })} /></label>
                  <label><span className="label">Formatter</span><input className="input" placeholder="例如 currency" value={item.formatter ?? ""} onChange={(event) => updateField(index, { formatter: event.target.value || null })} /></label>
                  <label><span className="label">最小值 / 长度</span><input className="input" type="number" value={typeof item.validation.min === "number" ? item.validation.min : ""} onChange={(event) => updateField(index, { validation: { ...item.validation, min: event.target.value ? Number(event.target.value) : null } })} /></label>
                  <label><span className="label">匹配规则</span><input className="input" placeholder="正则表达式" value={typeof item.validation.pattern === "string" ? item.validation.pattern : ""} onChange={(event) => updateField(index, { validation: { ...item.validation, pattern: event.target.value || null } })} /></label>
                </div>
              </details>
            </div>
          ))}
        </div>
        <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:justify-end">
          {canSaveTemplate ? <Button variant="secondary" onClick={onSaveTemplate}><Save className="size-4" /> 保存为模板</Button> : null}
          <Button onClick={onPreview} disabled={busy}>{busy ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}{busy ? "正在生成预览…" : "生成导入预览"}</Button>
        </div>
      </Card>
    </div>
  );
}

function PreviewStage({
  job,
  busy,
  onBack,
  onImageUpdate,
  onConfirm,
}: {
  job: ImportJob;
  busy: boolean;
  onBack: () => void;
  onImageUpdate: (candidate: ImportImageCandidate, payload: { matched_sku: string | null; image_type: string; is_primary: boolean }) => Promise<void>;
  onConfirm: (strategy: DuplicateStrategy) => void;
}) {
  const [tab, setTab] = useState<"rows" | "images">("rows");
  const [strategy, setStrategy] = useState<DuplicateStrategy>("update_non_empty");
  const unmatched = job.images.filter((image) => image.status !== "matched").length;
  return (
    <div className="space-y-5">
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="识别数据行" value={job.total_rows} hint="全部工作表合计" tone="blue" />
        <MetricCard label="有效行" value={job.valid_rows} hint="可创建或更新" tone="green" />
        <MetricCard label="冲突 / 错误" value={job.conflict_rows} hint="按重复策略处理" tone={job.conflict_rows ? "amber" : "slate"} />
        <MetricCard label="未匹配图片" value={unmatched} hint="不会自动导入" tone={unmatched ? "amber" : "green"} />
      </section>

      <Card>
        <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
            <TabButton active={tab === "rows"} onClick={() => setTab("rows")}>数据预览 <span className="tabular-nums">{job.rows.length}</span></TabButton>
            <TabButton active={tab === "images"} onClick={() => setTab("images")}>图片匹配 <span className="tabular-nums">{job.images.length}</span></TabButton>
          </div>
          <p className="text-[11px] text-slate-500">文件指纹：<span className="font-mono">{job.source_sha256.slice(0, 20)}…</span></p>
        </div>
        {tab === "rows" ? <RowsPreview rows={job.rows} /> : <ImagesPreview images={job.images} rows={job.rows} onUpdate={onImageUpdate} />}
      </Card>

      <Card>
        <CardHeader title="重复 SKU 处理策略" description="必须明确选择；系统不会静默覆盖已有产品。" />
        <div className="grid gap-3 p-5 md:grid-cols-3">
          <StrategyOption selected={strategy === "update_non_empty"} title="仅补充非空字段" description="推荐：保留已有非空值，用 Excel 的非空字段补充产品资料。" onClick={() => setStrategy("update_non_empty")} />
          <StrategyOption selected={strategy === "overwrite"} title="按映射覆盖" description="Excel 空值也会清空已映射的可选字段，请谨慎使用。" onClick={() => setStrategy("overwrite")} />
          <StrategyOption selected={strategy === "skip"} title="跳过已有 SKU" description="只创建新产品，已有产品及其数据保持不变。" onClick={() => setStrategy("skip")} />
        </div>
        {unmatched ? <div className="mx-5 mb-4 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertTriangle className="mt-0.5 size-4 shrink-0" />仍有 {unmatched} 张图片未可靠匹配。它们会保留在任务中，但不会自动归属产品。</div> : null}
        <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:justify-between">
          <Button variant="secondary" onClick={onBack} disabled={busy}><ArrowLeft className="size-4" /> 返回调整映射</Button>
          <Button onClick={() => onConfirm(strategy)} disabled={busy}>{busy ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}{busy ? "正在导入…" : "确认并写入产品库"}</Button>
        </div>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, hint, tone }: { label: string; value: number; hint: string; tone: "blue" | "green" | "amber" | "slate" }) {
  const color = tone === "green" ? "text-emerald-600" : tone === "amber" ? "text-amber-600" : tone === "blue" ? "text-blue-600" : "text-slate-600";
  return <Card className="p-4"><p className="text-xs font-semibold text-slate-500">{label}</p><p className={cn("mt-2 text-2xl font-extrabold tabular-nums", color)}>{value}</p><p className="mt-1 text-[10px] text-slate-400">{hint}</p></Card>;
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return <button type="button" onClick={onClick} className={cn("rounded-md px-3 py-2 text-xs font-semibold transition-colors", active ? "bg-white text-[#1a365d] shadow-sm" : "text-slate-500 hover:text-slate-800")}>{children}</button>;
}

function RowsPreview({ rows }: { rows: ImportJob["rows"] }) {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row.mapped_data))));
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const pageRows = rows.slice((page - 1) * pageSize, page * pageSize);
  useEffect(() => setPage(1), [rows]);
  if (!rows.length) return <EmptyState icon={<FileSpreadsheet className="size-5" />} title="没有可预览的数据行" description="请返回检查工作表和字段映射。" />;
  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left">
          <thead className="bg-slate-50/80 text-[11px] font-bold uppercase tracking-wide text-slate-500"><tr><th className="sticky left-0 z-10 bg-slate-50 px-4 py-3">来源</th><th className="px-4 py-3">状态</th>{columns.map((column) => <th key={column} className="px-4 py-3">{column}</th>)}<th className="px-4 py-3">问题</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {pageRows.map((row) => <tr key={row.id} className={row.errors.length ? "bg-red-50/35" : "hover:bg-slate-50/60"}><td className="sticky left-0 bg-white px-4 py-3 font-mono text-[10px] text-slate-500">{row.source_sheet}!{row.source_row}</td><td className="px-4 py-3"><Badge tone={row.errors.length ? "red" : row.action === "conflict" ? "amber" : "green"}>{row.errors.length ? "错误" : row.action === "conflict" ? "已有 SKU" : "新建"}</Badge></td>{columns.map((column) => <td key={column} className="max-w-[240px] truncate px-4 py-3 text-xs text-slate-700" title={String(row.mapped_data[column] ?? "")}>{String(row.mapped_data[column] ?? "—")}</td>)}<td className="max-w-xs px-4 py-3 text-[11px] text-red-600">{row.errors.map(String).join("；") || "—"}</td></tr>)}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3"><p className="text-xs text-slate-500">显示 {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, rows.length)}，共 {rows.length} 行</p><div className="flex items-center gap-2"><Button variant="secondary" className="size-9 px-0" disabled={page === 1} onClick={() => setPage((current) => current - 1)}><ChevronLeft className="size-4" /></Button><span className="text-xs font-semibold text-slate-600">{page} / {totalPages}</span><Button variant="secondary" className="size-9 px-0" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)}><ChevronRight className="size-4" /></Button></div></div>
    </>
  );
}

function ImagesPreview({ images, rows, onUpdate }: { images: ImportImageCandidate[]; rows: ImportJob["rows"]; onUpdate: (candidate: ImportImageCandidate, payload: { matched_sku: string | null; image_type: string; is_primary: boolean }) => Promise<void> }) {
  const [page, setPage] = useState(1);
  const pageSize = 12;
  const skus = Array.from(new Set(rows.filter((row) => !row.errors.length).map((row) => String(row.mapped_data.sku ?? "")).filter(Boolean)));
  const totalPages = Math.max(1, Math.ceil(images.length / pageSize));
  const pageImages = images.slice((page - 1) * pageSize, page * pageSize);
  useEffect(() => setPage(1), [images.length]);
  if (!images.length) return <EmptyState icon={<ImageIcon className="size-5" />} title="工作簿中没有图片" description="可以继续导入产品字段，稍后在产品详情页上传图片。" />;
  return <><div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">{pageImages.map((image) => <ImageMatchCard key={image.id} image={image} skus={skus} onUpdate={onUpdate} />)}</div><div className="flex items-center justify-between border-t border-slate-100 px-5 py-3"><p className="text-xs text-slate-500">显示 {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, images.length)}，共 {images.length} 张</p><div className="flex items-center gap-2"><Button variant="secondary" className="size-9 px-0" disabled={page === 1} onClick={() => setPage((current) => current - 1)}><ChevronLeft className="size-4" /></Button><span className="text-xs font-semibold text-slate-600">{page} / {totalPages}</span><Button variant="secondary" className="size-9 px-0" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)}><ChevronRight className="size-4" /></Button></div></div></>;
}

function ImageMatchCard({ image, skus, onUpdate }: { image: ImportImageCandidate; skus: string[]; onUpdate: (candidate: ImportImageCandidate, payload: { matched_sku: string | null; image_type: string; is_primary: boolean }) => Promise<void> }) {
  const [sku, setSku] = useState(image.matched_sku ?? "");
  const [imageType, setImageType] = useState(image.image_type);
  const [isPrimary, setIsPrimary] = useState(image.is_primary);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setSaving(true); setError(null); setSaved(false);
    try { await onUpdate(image, { matched_sku: sku || null, image_type: imageType, is_primary: isPrimary }); setSaved(true); window.setTimeout(() => setSaved(false), 1600); }
    catch (caught) { setError(apiMessage(caught, "图片匹配保存失败。")); }
    finally { setSaving(false); }
  }
  const reliable = image.status === "matched";
  return (
    <article className={cn("overflow-hidden rounded-xl border bg-white", reliable ? "border-emerald-200" : "border-amber-200")}>
      <div className="relative"><ProtectedImage src={image.content_url} alt={image.original_filename} className="aspect-[4/3] w-full bg-white" /><div className="absolute left-3 top-3 flex gap-1"><Badge tone={reliable ? "green" : "amber"}>{reliable ? "已匹配" : "待确认"}</Badge><Badge tone="slate">{Math.round(image.match_confidence * 100)}%</Badge></div></div>
      <div className="space-y-3 p-3.5">
        <div><p className="truncate text-xs font-bold text-slate-800" title={image.original_filename}>{image.original_filename}</p><p className="mt-1 text-[10px] text-slate-400">{image.source_sheet}!R{image.source_row}C{image.source_column} · {image.width ?? "?"}×{image.height ?? "?"}</p></div>
        <label><span className="label">匹配产品 SKU</span><select className="input" value={sku} onChange={(event) => setSku(event.target.value)}><option value="">保持未匹配</option>{skus.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <div className="grid grid-cols-[1fr_auto] gap-2"><label><span className="label">图片类型</span><select className="input" value={imageType} onChange={(event) => setImageType(event.target.value as ImportImageCandidate["image_type"])}>{Object.entries(imageTypeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="flex items-end pb-2.5"><span className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-600"><input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} className="size-4 accent-[#1a365d]" /> 主图</span></label></div>
        <div className="flex items-center justify-between border-t border-slate-100 pt-3"><span className="text-[10px] text-slate-400">{image.match_method} · {image.match_source}</span><button type="button" onClick={save} disabled={saving} className="flex items-center gap-1 text-xs font-semibold text-[#1a365d] disabled:opacity-50">{saving ? <LoaderCircle className="size-3.5 animate-spin" /> : saved ? <Check className="size-3.5 text-emerald-600" /> : <Save className="size-3.5" />}{saving ? "保存中" : saved ? "已保存" : "保存"}</button></div>
        {error ? <p className="text-[11px] text-red-600">{error}</p> : null}
      </div>
    </article>
  );
}

function StrategyOption({ selected, title, description, onClick }: { selected: boolean; title: string; description: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={cn("rounded-xl border p-4 text-left transition-colors", selected ? "border-blue-300 bg-blue-50/70 ring-2 ring-blue-100" : "border-slate-200 hover:bg-slate-50")}><span className="flex items-center gap-2 text-sm font-bold text-slate-900"><span className={cn("grid size-5 place-items-center rounded-full border", selected ? "border-[#1a365d] bg-[#1a365d] text-white" : "border-slate-300")}>{selected ? <Check className="size-3" /> : null}</span>{title}</span><span className="mt-2 block pl-7 text-xs leading-5 text-slate-500">{description}</span></button>;
}

function ResultStage({ job, onReset }: { job: ImportJob; onReset: () => void }) {
  const importedImages = job.images.filter((image) => image.status === "imported").length;
  const unmatchedImages = job.images.filter((image) => image.status === "unmatched").length;
  return (
    <Card className="overflow-hidden">
      <div className="bg-gradient-to-br from-[#1a365d] to-[#2c5aa0] px-6 py-10 text-center text-white sm:px-10">
        <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/20"><CheckCircle2 className="size-8" /></span>
        <h2 className="mt-5 text-2xl font-extrabold">导入任务已完成</h2>
        <p className="mt-2 text-sm text-blue-100">{job.source_filename} 已按确认的映射和重复策略写入产品库。</p>
      </div>
      <div className="grid gap-px bg-slate-100 sm:grid-cols-4">
        <ResultMetric label="成功写入" value={job.imported_rows} />
        <ResultMetric label="跳过产品" value={job.skipped_rows} />
        <ResultMetric label="冲突 / 失败" value={job.conflict_rows} />
        <ResultMetric label="导入图片" value={importedImages} />
      </div>
      <div className="p-5 sm:p-6">
        {unmatchedImages ? <div className="mb-5 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800"><AlertTriangle className="mt-0.5 size-4 shrink-0" /><span>{unmatchedImages} 张低置信度图片仍为 unmatched，未自动归属任何产品。其指纹和来源位置已保留在导入任务中。</span></div> : null}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center"><Link to="/products"><Button><FileCheck2 className="size-4" /> 查看产品库</Button></Link><Button variant="secondary" onClick={onReset}><RefreshCw className="size-4" /> 开始新的导入</Button></div>
      </div>
    </Card>
  );
}

function ResultMetric({ label, value }: { label: string; value: number }) {
  return <div className="bg-white px-5 py-5 text-center"><p className="text-2xl font-extrabold tabular-nums text-slate-950">{value}</p><p className="mt-1 text-[11px] text-slate-500">{label}</p></div>;
}

function SaveTemplateModal({ onClose, onSave }: { onClose: () => void; onSave: (name: string, description: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(null);
    try { await onSave(name.trim(), description.trim()); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "模板保存失败。"); }
    finally { setSaving(false); }
  }
  return <Modal title="保存导入模板" description="以后上传同结构的工作簿时可直接复用当前映射。" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}><label><span className="label">模板名称 *</span><input className="input" required maxLength={200} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如 Germany Outdoor 供应商表" /></label><label><span className="label">说明</span><textarea className="textarea" maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="记录供应商、版本或适用场景" /></label>{error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}<div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={saving || !name.trim()}>{saving ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}{saving ? "保存中…" : "保存模板"}</Button></div></form></Modal>;
}
