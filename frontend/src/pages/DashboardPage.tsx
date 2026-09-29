import {
  Activity,
  ArrowRight,
  DatabaseZap,
  Images,
  PackageCheck,
  PackageSearch,
  Plus,
  Server,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Button } from "../components/ui/button";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "../components/ui/primitives";
import { apiRequest } from "../lib/api";
import type { Product } from "../types/catalog";

type HealthPayload = {
  status: "ok" | "error";
  service: string;
  version: string;
  dependencies: Record<string, { status: "ok" | "error"; message: string | null }>;
};

type ProductStats = {
  total: number;
  active: number;
  draft: number;
  archived: number;
  with_images: number;
  field_count: number;
};

export function DashboardPage() {
  const { reportError } = useGlobalError();
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [stats, setStats] = useState<ProductStats | null>(null);
  const [recentProducts, setRecentProducts] = useState<Product[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([
      apiRequest<HealthPayload>("/health"),
      apiRequest<ProductStats>("/products/stats"),
      apiRequest<{ items: Product[] }>("/products?page_size=5"),
    ])
      .then(([healthPayload, statsPayload, productsPayload]) => {
        if (!active) return;
        setHealth(healthPayload);
        setStats(statsPayload);
        setRecentProducts(productsPayload.items);
      })
      .catch(() => {
        if (active) reportError("无法加载业务概览，请检查服务状态后重试。")
      });
    return () => {
      active = false;
    };
  }, [reportError]);

  const statCards = [
    { label: "产品总数", value: stats?.total ?? "—", hint: "当前租户产品", icon: PackageSearch, tone: "blue" },
    { label: "有效产品", value: stats?.active ?? "—", hint: `${stats?.draft ?? 0} 个草稿`, icon: PackageCheck, tone: "green" },
    { label: "已配图片", value: stats?.with_images ?? "—", hint: "至少一张产品图", icon: Images, tone: "purple" },
    { label: "字段定义", value: stats?.field_count ?? "—", hint: "标准与自定义字段", icon: DatabaseZap, tone: "amber" },
  ] as const;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Overview"
        title="业务概览"
        description="统一管理产品资料、字段与图片，为后续客户模板和报价文件生成准备可信数据。"
        actions={
          <Link to="/products">
            <Button>
              <Plus className="size-4" /> 新建产品
            </Button>
          </Link>
        }
      />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4" aria-label="产品指标">
        {statCards.map(({ label, value, hint, icon: Icon, tone }) => (
          <Card key={label} className="p-4 sm:p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-slate-500">{label}</p>
                <p className="mt-2 text-2xl font-extrabold tabular-nums tracking-tight text-slate-950 sm:text-3xl">
                  {value}
                </p>
              </div>
              <span
                className={`grid size-9 place-items-center rounded-xl ${
                  tone === "green"
                    ? "bg-emerald-50 text-emerald-600"
                    : tone === "purple"
                      ? "bg-violet-50 text-violet-600"
                      : tone === "amber"
                        ? "bg-amber-50 text-amber-600"
                        : "bg-blue-50 text-blue-600"
                }`}
              >
                <Icon className="size-4" />
              </span>
            </div>
            <p className="mt-3 text-[11px] text-slate-400">{hint}</p>
          </Card>
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.7fr)]">
        <Card>
          <CardHeader
            title="最近更新的产品"
            description="按最后更新时间排序"
            actions={
              <Link to="/products" className="flex items-center gap-1 text-xs font-semibold text-[#1a365d]">
                查看全部 <ArrowRight className="size-3.5" />
              </Link>
            }
          />
          {recentProducts.length ? (
            <div className="divide-y divide-slate-100">
              {recentProducts.map((product) => (
                <Link
                  key={product.id}
                  to={`/products/${product.id}`}
                  className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-slate-50/70"
                >
                  <ProtectedImage
                    src={product.primary_image_url}
                    alt={product.product_name}
                    className="size-12 shrink-0 rounded-lg border border-slate-200"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-bold text-slate-900">{product.product_name}</span>
                      <Badge tone={product.status === "active" ? "green" : "amber"}>
                        {product.status === "active" ? "有效" : "草稿"}
                      </Badge>
                    </div>
                    <p className="mt-1 truncate text-xs text-slate-500">
                      {product.sku} · {product.category ?? "未分类"} · {product.image_count} 张图片
                    </p>
                  </div>
                  <ArrowRight className="size-4 shrink-0 text-slate-300" />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<PackageSearch className="size-5" />}
              title="产品库还是空的"
              description="创建第一个产品，随后可以维护字段和图片。"
              action={
                <Link to="/products">
                  <Button>创建产品</Button>
                </Link>
              }
            />
          )}
        </Card>

        <Card>
          <CardHeader title="系统状态" description="基础服务实时检查" />
          <div className="space-y-3 p-5">
            {[
              { label: "Backend API", ok: health?.status === "ok", icon: Server },
              { label: "PostgreSQL", ok: health?.dependencies.postgres?.status === "ok", icon: DatabaseZap },
              { label: "Redis", ok: health?.dependencies.redis?.status === "ok", icon: Activity },
            ].map(({ label, ok, icon: Icon }) => (
              <div key={label} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                <span className="grid size-8 place-items-center rounded-lg bg-white text-slate-500 shadow-sm">
                  <Icon className="size-4" />
                </span>
                <span className="flex-1 text-xs font-semibold text-slate-700">{label}</span>
                <span className={`size-2 rounded-full ${ok ? "bg-emerald-500" : "bg-slate-300"}`} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
