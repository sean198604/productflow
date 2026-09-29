import { DatabaseZap, LockKeyhole, Plus } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { useAuth } from "../auth/AuthProvider";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { FieldDefinition, FieldDataType } from "../types/catalog";

const typeLabel: Record<FieldDataType, string> = { text: "文本", number: "数字", money: "金额", date: "日期", boolean: "布尔", select: "下拉", multi_select: "多选", image: "图片" };

export function FieldDefinitionsPage() {
  const { session } = useAuth();
  const { reportError } = useGlobalError();
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const load = () => apiRequest<{ items: FieldDefinition[] }>("/field-definitions").then((payload) => setFields(payload.items)).catch(() => reportError("字段定义加载失败。"));
  useEffect(() => { load(); }, []);
  const canManage = session?.user.role === "owner" || session?.user.role === "admin";
  const customer = fields.filter((field) => field.scope === "customer");
  const internal = fields.filter((field) => field.scope === "internal");
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Data Dictionary" title="字段管理" description="定义产品资料的数据类型与输出边界。客户字段和内部字段在此明确隔离。" actions={canManage ? <Button onClick={() => setShowCreate(true)}><Plus className="size-4" /> 新建字段</Button> : undefined} />
      <FieldTable title="客户报价字段" description="模板可以显式绑定这些字段；仍不会默认全部输出" fields={customer} />
      <FieldTable title="内部字段" description="成本、供应商与经营数据；客户模板禁止引用" fields={internal} internal />
      {!fields.length ? <Card><EmptyState icon={<DatabaseZap className="size-5" />} title="暂无字段定义" description="创建字段后即可在产品资料中录入对应值。" /></Card> : null}
      {showCreate ? <CreateFieldModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} /> : null}
    </div>
  );
}

function FieldTable({ title, description, fields, internal = false }: { title: string; description: string; fields: FieldDefinition[]; internal?: boolean }) {
  return <Card className={internal ? "border-amber-200/80" : undefined}><CardHeader title={title} description={description} actions={internal ? <Badge tone="amber"><LockKeyhole className="mr-1 size-3" /> Internal only</Badge> : <Badge tone="blue">Customer fields</Badge>} /><div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left"><thead className="bg-slate-50/80 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">字段</th><th className="px-4 py-3">代码</th><th className="px-4 py-3">类型</th><th className="px-4 py-3">来源</th><th className="px-5 py-3 text-right">必填</th></tr></thead><tbody className="divide-y divide-slate-100">{fields.map((field) => <tr key={field.id}><td className="px-5 py-3 text-sm font-semibold text-slate-900">{field.label}</td><td className="px-4 py-3 font-mono text-xs text-slate-500">{field.code}</td><td className="px-4 py-3"><Badge tone="slate">{typeLabel[field.data_type]}</Badge></td><td className="px-4 py-3"><Badge tone={field.is_system ? "blue" : "purple"}>{field.is_system ? "系统" : "自定义"}</Badge></td><td className="px-5 py-3 text-right text-xs text-slate-500">{field.is_required ? "是" : "否"}</td></tr>)}</tbody></table></div></Card>;
}

function CreateFieldModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ code: "", label: "", data_type: "text", scope: "customer", choices: "" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setSubmitting(true); setError(null);
    try { await apiRequest("/field-definitions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: form.code, label: form.label, data_type: form.data_type, scope: form.scope, options: form.choices ? { choices: form.choices.split(",").map((item) => item.trim()).filter(Boolean) } : {} }) }); onCreated(); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "字段创建失败。"); }
    finally { setSubmitting(false); }
  }
  const needsChoices = form.data_type === "select" || form.data_type === "multi_select";
  return <Modal title="新建自定义字段" description="字段代码创建后不可修改，避免破坏历史映射。" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}><div className="grid gap-4 sm:grid-cols-2"><label><span className="label">字段名称 *</span><input required className="input" value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} /></label><label><span className="label">字段代码 *</span><input required className="input" placeholder="例如 ip_rating" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} /></label><label><span className="label">数据类型</span><select className="input" value={form.data_type} onChange={(event) => setForm({ ...form, data_type: event.target.value })}>{Object.entries(typeLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label><span className="label">字段边界</span><select className="input" value={form.scope} onChange={(event) => setForm({ ...form, scope: event.target.value })}><option value="customer">客户报价字段</option><option value="internal">内部字段</option></select></label></div>{needsChoices ? <label><span className="label">可选值</span><input className="input" placeholder="多个值用逗号分隔" value={form.choices} onChange={(event) => setForm({ ...form, choices: event.target.value })} /></label> : null}{error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}<div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={submitting}>{submitting ? "创建中…" : "创建字段"}</Button></div></form></Modal>;
}
