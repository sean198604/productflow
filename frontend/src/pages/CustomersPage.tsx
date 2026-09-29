import { Building2, Plus, Upload } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "../auth/AuthProvider";
import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Modal } from "../components/ui/Modal";
import { Button } from "../components/ui/button";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui/primitives";
import { ApiError, apiRequest } from "../lib/api";
import type { Customer } from "../types/generation";
import type { OutputTemplate } from "../types/templates";

type CustomerList = { items: Customer[]; total: number };
type TemplateList = { items: OutputTemplate[]; total: number };

const statusLabel = { active: "有效", inactive: "停用", archived: "已归档" };

export function CustomersPage() {
  const { session } = useAuth();
  const { reportError } = useGlobalError();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [templates, setTemplates] = useState<OutputTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const canManage = session?.user.role === "owner" || session?.user.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [customerPayload, templatePayload] = await Promise.all([
        apiRequest<CustomerList>("/customers"),
        apiRequest<TemplateList>("/output-templates"),
      ]);
      setCustomers(customerPayload.items);
      setTemplates(templatePayload.items);
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "客户资料加载失败。");
    } finally {
      setLoading(false);
    }
  }, [reportError]);

  useEffect(() => { load(); }, [load]);

  async function uploadLogo(customerId: string, file: File | undefined) {
    if (!file) return;
    const form = new FormData();
    form.append("logo", file);
    try {
      await apiRequest<Customer>(`/customers/${customerId}/logo`, {
        method: "POST",
        body: form,
        timeoutMs: 60_000,
      });
      load();
    } catch (caught) {
      reportError(caught instanceof ApiError ? caught.message : "客户 Logo 上传失败。");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Customers"
        title="客户管理"
        description="维护客户身份、输出偏好和默认 PPTX/XLSX 模板。Tenant 与 Customer 相互独立。"
        actions={canManage ? <Button onClick={() => setShowCreate(true)}><Plus className="size-4" /> 新建客户</Button> : undefined}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="p-4"><p className="text-xs text-slate-500">客户总数</p><p className="mt-2 text-2xl font-black text-slate-950">{customers.length}</p></Card>
        <Card className="p-4"><p className="text-xs text-slate-500">有效客户</p><p className="mt-2 text-2xl font-black text-emerald-700">{customers.filter((item) => item.status === "active").length}</p></Card>
        <Card className="p-4"><p className="text-xs text-slate-500">已绑定默认模板</p><p className="mt-2 text-2xl font-black text-blue-700">{customers.filter((item) => item.default_ppt_template_id || item.default_xlsx_template_id).length}</p></Card>
      </div>

      <div className="table-shell">
        {loading ? <div className="p-12 text-center text-sm text-slate-500">正在加载客户…</div> : customers.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead className="bg-slate-50/80"><tr className="border-b border-slate-200 text-[11px] font-bold uppercase tracking-wide text-slate-500"><th className="px-5 py-3">客户</th><th className="px-4 py-3">区域设置</th><th className="px-4 py-3">默认模板</th><th className="px-4 py-3">状态</th><th className="px-5 py-3 text-right">Logo</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {customers.map((customer) => (
                  <tr key={customer.id} className="hover:bg-slate-50/70">
                    <td className="px-5 py-4"><div className="flex items-center gap-3">{customer.logo_url ? <ProtectedImage src={customer.logo_url} alt={customer.name} className="size-11 rounded-lg border border-slate-200 bg-white object-contain" /> : <span className="grid size-11 place-items-center rounded-lg bg-blue-50 text-blue-700"><Building2 className="size-5" /></span>}<div><p className="text-sm font-bold text-slate-900">{customer.name}</p><p className="mt-0.5 font-mono text-[11px] text-slate-500">{customer.code}</p></div></div></td>
                    <td className="px-4 py-4 text-xs text-slate-600"><p>{customer.settings.currency} · {customer.settings.locale}</p><p className="mt-0.5 text-slate-400">{customer.settings.timezone}</p></td>
                    <td className="px-4 py-4 text-xs text-slate-600"><p>PPTX：{customer.default_ppt_template_id ? "已绑定" : "未设置"}</p><p className="mt-0.5">XLSX：{customer.default_xlsx_template_id ? "已绑定" : "未设置"}</p></td>
                    <td className="px-4 py-4"><Badge tone={customer.status === "active" ? "green" : "slate"}>{statusLabel[customer.status]}</Badge></td>
                    <td className="px-5 py-4 text-right">{canManage ? <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"><Upload className="size-3.5" /> 上传<input className="hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { uploadLogo(customer.id, event.target.files?.[0]); event.target.value = ""; }} /></label> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={<Building2 className="size-5" />} title="尚未建立客户" description="创建客户后即可设置默认模板并生成可追溯的报价文件。" action={canManage ? <Button onClick={() => setShowCreate(true)}>创建第一个客户</Button> : undefined} />}
      </div>

      {showCreate ? <CreateCustomerModal templates={templates} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} /> : null}
    </div>
  );
}

function CreateCustomerModal({ templates, onClose, onCreated }: { templates: OutputTemplate[]; onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name: "", code: "", status: "active", currency: "USD", locale: "en-US", timezone: "Asia/Shanghai", default_ppt_template_id: "", default_xlsx_template_id: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiRequest<Customer>("/customers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: form.name, code: form.code, status: form.status, default_ppt_template_id: form.default_ppt_template_id || null, default_xlsx_template_id: form.default_xlsx_template_id || null, settings: { currency: form.currency, locale: form.locale, timezone: form.timezone, settings: {} } }) });
      onCreated();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "客户创建失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return <Modal title="新建客户" description="客户可以拥有独立的区域设置和默认输出模板。" onClose={onClose}><form className="space-y-4 p-5" onSubmit={submit}><div className="grid gap-4 sm:grid-cols-2"><label><span className="label">客户名称 *</span><input className="input" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label><span className="label">客户代码 *</span><input className="input" required pattern="[A-Za-z0-9][A-Za-z0-9._-]*" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="CUSTOMER-A" /></label></div><div className="grid gap-4 sm:grid-cols-3"><label><span className="label">币种</span><input className="input" value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label><label><span className="label">语言区域</span><input className="input" value={form.locale} onChange={(event) => setForm({ ...form, locale: event.target.value })} /></label><label><span className="label">时区</span><input className="input" value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} /></label></div><div className="grid gap-4 sm:grid-cols-2"><label><span className="label">默认 PPTX 模板</span><select className="input" value={form.default_ppt_template_id} onChange={(event) => setForm({ ...form, default_ppt_template_id: event.target.value })}><option value="">不设置</option>{templates.filter((item) => item.output_type === "pptx" && item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span className="label">默认 XLSX 模板</span><select className="input" value={form.default_xlsx_template_id} onChange={(event) => setForm({ ...form, default_xlsx_template_id: event.target.value })}><option value="">不设置</option>{templates.filter((item) => item.output_type === "xlsx" && item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>{error ? <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}<div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button variant="secondary" onClick={onClose}>取消</Button><Button type="submit" disabled={submitting}>{submitting ? "正在创建…" : "创建客户"}</Button></div></form></Modal>;
}
