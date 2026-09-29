import {
  Boxes,
  Building2,
  DatabaseZap,
  FileOutput,
  Images,
  Import,
  LayoutDashboard,
  Layers3,
  LogOut,
  Menu,
  PackageSearch,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Settings2,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthProvider";
import { cn } from "../lib/utils";

const mainNavigation = [
  { label: "业务概览", icon: LayoutDashboard, to: "/dashboard" },
  { label: "产品资料", icon: PackageSearch, to: "/products" },
  { label: "产品组合", icon: Layers3, to: "/product-sets" },
  { label: "客户管理", icon: Building2, to: "/customers" },
  { label: "数据导入", icon: Import, to: "/imports" },
  { label: "图片库", icon: Images, to: "/images" },
  { label: "字段管理", icon: DatabaseZap, to: "/fields" },
  { label: "模板中心", icon: Settings2, to: "/templates" },
  { label: "生成中心", icon: FileOutput, to: "/generation" },
];

const roleLabel = { owner: "租户所有者", admin: "管理员", member: "业务成员" };
const sidebarStorageKey = "productflow.sidebar.collapsed";

function Navigation({
  isPlatformAdmin,
  onNavigate,
  collapsed = false,
}: {
  isPlatformAdmin: boolean;
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  return (
    <nav
      className={cn("flex-1 overflow-y-auto py-5", collapsed ? "px-2" : "px-3")}
      aria-label="主导航"
    >
      {collapsed ? (
        <div className="mx-3 mb-3 h-px bg-slate-200" aria-hidden="true" />
      ) : (
        <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[1.2px] text-slate-400">
          工作台
        </p>
      )}
      {mainNavigation.map(({ label, icon: Icon, to }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          aria-label={collapsed ? label : undefined}
          title={collapsed ? label : undefined}
          className={({ isActive }) =>
            cn(
              "mb-1 flex min-h-11 items-center rounded-xl text-[13px] font-semibold transition-colors",
              collapsed ? "justify-center px-1" : "gap-3 px-3",
              isActive
                ? "bg-blue-50 text-[#1a365d]"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
            )
          }
        >
          <span className="grid size-8 place-items-center rounded-lg bg-white/70 ring-1 ring-slate-200/70">
            <Icon aria-hidden="true" className="size-4" />
          </span>
          {collapsed ? null : <span>{label}</span>}
        </NavLink>
      ))}

      {isPlatformAdmin ? (
        <>
          {collapsed ? (
            <div className="mx-3 mb-3 mt-5 h-px bg-violet-200" aria-hidden="true" />
          ) : (
            <p className="mt-6 px-3 pb-2 text-[10px] font-bold uppercase tracking-[1.2px] text-slate-400">
              平台管理
            </p>
          )}
          <NavLink
            to="/admin"
            onClick={onNavigate}
            aria-label={collapsed ? "系统后台" : undefined}
            title={collapsed ? "系统后台" : undefined}
            className={({ isActive }) =>
              cn(
                "mb-1 flex min-h-11 items-center rounded-xl text-[13px] font-semibold transition-colors",
                collapsed ? "justify-center px-1" : "gap-3 px-3",
                isActive
                  ? "bg-violet-50 text-violet-800"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
              )
            }
          >
            <span className="grid size-8 place-items-center rounded-lg bg-white/70 ring-1 ring-violet-200/70">
              <ShieldCheck aria-hidden="true" className="size-4" />
            </span>
            {collapsed ? null : <span>系统后台</span>}
          </NavLink>
        </>
      ) : null}

    </nav>
  );
}

export function AppLayout() {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => window.localStorage.getItem(sidebarStorageKey) === "true",
  );

  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => {
    window.localStorage.setItem(sidebarStorageKey, String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  function renderUserPanel(collapsed = false) {
    return (
      <div
        className={cn(
          "border-t border-slate-200 bg-slate-50/70",
          collapsed ? "px-2 py-3" : "p-4",
        )}
      >
        <div className={cn("flex items-center", collapsed ? "flex-col gap-2" : "gap-3")}>
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#1a365d] text-xs font-bold text-white">
            {session?.user.username.slice(0, 1).toUpperCase()}
          </span>
          {collapsed ? null : (
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold text-slate-900">{session?.user.username}</p>
              <p className="truncate text-[11px] text-slate-500">
                {session?.user.is_platform_admin
                  ? "平台管理员"
                  : session
                    ? roleLabel[session.user.role]
                    : ""}
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={handleLogout}
            aria-label="退出登录"
            className="grid size-9 place-items-center rounded-lg text-slate-500 hover:bg-white hover:text-slate-900"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "min-h-screen md:grid md:transition-[grid-template-columns] md:duration-200",
        sidebarCollapsed
          ? "md:grid-cols-[80px_minmax(0,1fr)]"
          : "md:grid-cols-[236px_minmax(0,1fr)]",
      )}
    >
      <aside className="sticky top-0 z-40 hidden h-screen flex-col border-r border-slate-200 bg-white md:flex">
        <div
          className={cn(
            "relative flex h-[76px] items-center border-b border-slate-100",
            sidebarCollapsed ? "justify-center px-3" : "gap-3 px-5",
          )}
        >
          <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-[#2c5aa0] to-[#1a365d] text-white shadow-sm">
            <Boxes aria-hidden="true" className="size-5" />
          </span>
          {sidebarCollapsed ? null : (
            <div className="min-w-0">
              <p className="font-extrabold tracking-tight text-[#1a365d]">ProductFlow</p>
              <p className="truncate text-[10px] uppercase tracking-wide text-slate-400">
                Product Operations
              </p>
            </div>
          )}
          <button
            type="button"
            onClick={() => setSidebarCollapsed((current) => !current)}
            aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            title={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            className="absolute -right-3 top-1/2 z-10 grid size-7 -translate-y-1/2 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition-colors hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen aria-hidden="true" className="size-3.5" />
            ) : (
              <PanelLeftClose aria-hidden="true" className="size-3.5" />
            )}
          </button>
        </div>
        <Navigation
          isPlatformAdmin={Boolean(session?.user.is_platform_admin)}
          collapsed={sidebarCollapsed}
        />
        {renderUserPanel(sidebarCollapsed)}
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-[68px] items-center justify-between gap-3 border-b border-slate-200/90 bg-white/95 px-4 shadow-[0_6px_24px_rgba(15,23,42,0.035)] backdrop-blur-xl sm:px-6 md:h-[76px] md:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              className="grid size-10 place-items-center rounded-xl text-slate-700 hover:bg-slate-100 md:hidden"
              aria-label="打开导航菜单"
            >
              <Menu className="size-5" />
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-slate-900">{session?.tenant.name}</p>
              <p className="truncate text-[11px] text-slate-500">
                安全工作空间 · 数据按企业隔离
              </p>
            </div>
          </div>
          <span className="hidden rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold text-emerald-700 sm:inline-flex">
            数据隔离已启用
          </span>
        </header>

        <main className="px-4 py-6 pb-24 sm:px-6 md:px-8 md:py-8 md:pb-10">
          <div className="mx-auto max-w-[1440px]">
            <Outlet />
          </div>
        </main>
      </div>

      {menuOpen ? (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            type="button"
            aria-label="关闭导航菜单"
            className="absolute inset-0 h-full w-full bg-slate-950/45 backdrop-blur-[2px]"
            onClick={() => setMenuOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-[min(86vw,340px)] flex-col bg-white shadow-2xl">
            <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4">
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-[#2c5aa0] to-[#1a365d] text-white">
                  <Boxes className="size-4" />
                </span>
                <span className="font-extrabold text-[#1a365d]">ProductFlow</span>
              </div>
              <button
                type="button"
                onClick={() => setMenuOpen(false)}
                className="grid size-10 place-items-center rounded-xl text-slate-500 hover:bg-slate-100"
                aria-label="关闭导航菜单"
              >
                <X className="size-5" />
              </button>
            </div>
            <Navigation
              isPlatformAdmin={Boolean(session?.user.is_platform_admin)}
              onNavigate={() => setMenuOpen(false)}
            />
            {renderUserPanel()}
          </aside>
        </div>
      ) : null}

      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-8px_30px_rgba(15,23,42,0.08)] backdrop-blur-xl md:hidden"
        style={{
          gridTemplateColumns: `repeat(${mainNavigation.length + (session?.user.is_platform_admin ? 1 : 0)}, minmax(0, 1fr))`,
        }}
      >
        {[
          ...mainNavigation,
          ...(session?.user.is_platform_admin
            ? [{ label: "系统后台", icon: ShieldCheck, to: "/admin" }]
            : []),
        ].map(({ label, icon: Icon, to }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "relative flex min-h-16 flex-col items-center justify-center gap-1 px-1 text-[10px] font-semibold",
                isActive ? "text-[#1a365d]" : "text-slate-500",
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive ? (
                  <span className="absolute top-0 h-0.5 w-8 rounded-full bg-[#1a365d]" />
                ) : null}
                <Icon className="size-4" />
                <span>{label.replace("管理", "")}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
