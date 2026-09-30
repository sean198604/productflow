import { Images, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ProtectedImage } from "../components/ProtectedImage";
import { useGlobalError } from "../components/errors/GlobalErrorProvider";
import { Badge, Card, EmptyState, PageHeader } from "../components/ui/primitives";
import { apiRequest } from "../lib/api";
import type { ProductImage } from "../types/catalog";

const imageTypeLabel = {
  main: "产品图",
  white_background: "白底图",
  lifestyle: "场景图",
  detail: "细节图",
  packaging: "包装图",
  certificate: "证书",
  other: "其他",
};

export function ImageLibraryPage() {
  const { reportError } = useGlobalError();
  const [images, setImages] = useState<ProductImage[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    apiRequest<{ items: ProductImage[] }>(`/product-images${filter ? `?image_type=${filter}` : ""}`)
      .then((payload) => setImages(payload.items))
      .catch(() => reportError("图片库加载失败。"))
      .finally(() => setLoading(false));
  }, [filter, reportError]);
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Product Assets"
        title="产品图片库"
        description="查看自动生成的透明 PNG、图片类型、文件指纹以及产品关联。原始文件始终保留。"
        actions={
          <select
            className="input w-40"
            aria-label="图片类型"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="">全部类型</option>
            {Object.entries(imageTypeLabel).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        }
      />
      {loading ? (
        <Card className="p-12 text-center text-sm text-slate-500">正在加载图片…</Card>
      ) : images.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {images.map((image) => (
            <Link
              key={image.id}
              to={`/products/${image.product_id}`}
              className={`card group overflow-hidden transition ${
                image.is_primary
                  ? "border-amber-400 ring-2 ring-amber-200 shadow-md shadow-amber-100"
                  : ""
              }`}
            >
              <div className="relative bg-[linear-gradient(45deg,#f1f5f9_25%,transparent_25%),linear-gradient(-45deg,#f1f5f9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#f1f5f9_75%),linear-gradient(-45deg,transparent_75%,#f1f5f9_75%)] bg-[length:16px_16px]">
                <ProtectedImage
                  src={image.processed_content_url ?? image.content_url}
                  alt={image.original_filename}
                  className="aspect-[4/3] w-full bg-white"
                />
                <div className="absolute left-3 top-3">
                  <Badge tone="slate">{imageTypeLabel[image.image_type]}</Badge>
                </div>
                {image.is_primary ? (
                  <span className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-1 text-[11px] font-black text-amber-950 shadow-md">
                    <Star className="size-3.5 fill-current" aria-hidden="true" /> 主图
                  </span>
                ) : null}
                {image.processed_content_url ? (
                  <span className="absolute bottom-3 left-3 rounded-full bg-emerald-600 px-2 py-1 text-[10px] font-bold text-white">
                    {image.background_removed ? "已去白底" : "附件 PNG"}
                  </span>
                ) : null}
              </div>
              <div className="p-4">
                <h2 className="truncate text-sm font-bold text-slate-900">{image.product_name}</h2>
                <p className="mt-1 font-mono text-[11px] text-slate-500">{image.product_sku}</p>
                <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-[10px] text-slate-400">
                  <span>{image.width} × {image.height}</span>
                  <span>{(image.size_bytes / 1024).toFixed(1)} KB</span>
                </div>
                <p className="mt-2 truncate text-[10px] text-slate-400" title={image.sha256}>
                  SHA256 · {image.sha256.slice(0, 16)}…
                </p>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={<Images className="size-5" />}
            title="图片库还是空的"
            description="进入产品详情页上传图片，系统会记录完整文件元数据。"
          />
        </Card>
      )}
    </div>
  );
}
