import { Boxes, Loader2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/ui/button";
import { ApiError } from "../lib/api";
import { cn } from "../lib/utils";

type Mode = "login" | "register";

export function LoginPage() {
  const { session, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("login");
  const [tenantName, setTenantName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (session) return <Navigate to="/dashboard" replace />;

  function switchMode(nextMode: Mode) {
    setMode(nextMode);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致。");
      return;
    }
    setIsSubmitting(true);
    try {
      if (mode === "login") {
        await login({ identifier, password });
      } else {
        await register({ tenantName, username, email, password });
      }
      const destination = (location.state as { from?: string } | null)?.from ?? "/dashboard";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : mode === "login"
            ? "登录失败，请稍后重试。"
            : "注册失败，请稍后重试。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const registering = mode === "register";

  return (
    <main className="grid min-h-screen place-items-center px-5 py-12">
      <section
        className={cn(
          "relative w-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-7 shadow-[0_24px_70px_rgba(15,23,42,0.12)] sm:p-9",
          registering ? "max-w-lg" : "max-w-md",
        )}
      >
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#1a365d] via-blue-500 to-violet-600" />
        <div className="text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-gradient-to-br from-[#2c5aa0] to-[#1a365d] text-white shadow-[0_8px_20px_rgba(26,54,93,0.25)]">
            <Boxes aria-hidden="true" className="size-6" />
          </span>
          <h1 className="mt-5 text-2xl font-extrabold tracking-tight text-[#1a365d]">ProductFlow</h1>
          <p className="mt-1 text-sm text-slate-500">产品资料 · 报价文件生成平台</p>
        </div>

        <div className="mt-7 grid grid-cols-2 rounded-xl bg-slate-100 p-1" aria-label="账号入口">
          {(["login", "register"] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => switchMode(item)}
              className={cn(
                "h-9 rounded-lg text-sm font-bold transition-all",
                mode === item
                  ? "bg-white text-[#1a365d] shadow-sm ring-1 ring-slate-200"
                  : "text-slate-500 hover:text-slate-800",
              )}
            >
              {item === "login" ? "登录" : "注册企业账号"}
            </button>
          ))}
        </div>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          {registering ? (
            <label className="block">
              <span className="label">企业名称</span>
              <input
                required
                autoComplete="organization"
                placeholder="例如 Acme Trading"
                value={tenantName}
                onChange={(event) => setTenantName(event.target.value)}
                className="input h-11 bg-[#fcfdff]"
              />
            </label>
          ) : null}
          {registering ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="label">管理员用户名</span>
                <input
                  required
                  autoComplete="username"
                  minLength={3}
                  value={username}
                  onChange={(event) => setUsername(event.target.value.toLowerCase())}
                  className="input h-11 bg-[#fcfdff]"
                />
              </label>
              <label className="block">
                <span className="label">管理员邮箱</span>
                <input
                  required
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="input h-11 bg-[#fcfdff]"
                />
              </label>
            </div>
          ) : (
            <label className="block">
              <span className="label">邮箱或用户名</span>
              <input
                required
                autoComplete="username"
                placeholder="name@company.com"
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                className="input h-11 bg-[#fcfdff]"
              />
            </label>
          )}
          <div className={cn(registering && "grid gap-4 sm:grid-cols-2")}>
            <label className="block">
              <span className="label">密码</span>
              <input
                required
                type="password"
                minLength={12}
                autoComplete={registering ? "new-password" : "current-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="input h-11 bg-[#fcfdff]"
              />
            </label>
            {registering ? (
              <label className="block">
                <span className="label">确认密码</span>
                <input
                  required
                  type="password"
                  minLength={12}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className="input h-11 bg-[#fcfdff]"
                />
              </label>
            ) : null}
          </div>
          {error ? (
            <p role="alert" className="rounded-xl bg-red-50 px-3.5 py-3 text-sm text-red-700">
              {error}
            </p>
          ) : null}
          <Button type="submit" disabled={isSubmitting} className="h-11 w-full text-sm">
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null}
            {isSubmitting
              ? registering
                ? "正在创建企业账号…"
                : "正在登录…"
              : registering
                ? "创建企业账号"
                : "登 录"}
          </Button>
        </form>
        <div className="mt-6 border-t border-slate-100 pt-5 text-center text-[11px] leading-5 text-slate-400">
          产品与内部成本数据按租户隔离，仅限授权账号访问。
          <br />
          {registering
            ? "注册账号将成为该企业的租户所有者。"
            : "没有账号？可切换到注册创建独立企业空间。"}
        </div>
      </section>
    </main>
  );
}
