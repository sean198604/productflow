import { ImageIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { apiBlob } from "../lib/api";
import { cn } from "../lib/utils";

export function ProtectedImage({
  src,
  alt,
  className,
}: {
  src: string | null;
  alt: string;
  className?: string;
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    setObjectUrl(null);
    if (!src) return;
    let active = true;
    let url: string | null = null;
    apiBlob(src)
      .then((blob) => {
        if (!active) return;
        url = URL.createObjectURL(blob);
        setObjectUrl(url);
      })
      .catch(() => setObjectUrl(null));
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);

  if (!objectUrl) {
    return (
      <div
        className={cn(
          "grid place-items-center bg-gradient-to-br from-slate-50 to-slate-100 text-slate-300",
          className,
        )}
        aria-label={alt}
      >
        <ImageIcon className="size-5" aria-hidden="true" />
      </div>
    );
  }
  return <img src={objectUrl} alt={alt} className={cn("object-contain", className)} />;
}
