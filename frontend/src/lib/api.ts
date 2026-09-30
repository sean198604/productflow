import { getAccessToken } from "../auth/tokenStorage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const DEFAULT_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiRequestOptions = RequestInit & {
  timeoutMs?: number;
};

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );

  try {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    const accessToken = getAccessToken();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    const requestUrl = path.startsWith("/api/v1/") ? path : `${API_BASE_URL}${path}`;
    const response = await fetch(requestUrl, {
      ...options,
      signal: controller.signal,
      headers,
    });

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { message?: string; request_id?: string }
        | null;
      const fallbackMessage =
        response.status === 413
          ? "上传文件过大，请选择 50 MB 以内的文件。"
          : `Request failed with status ${response.status}`;
      throw new ApiError(
        payload?.message ?? fallbackMessage,
        response.status,
        payload?.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
      );
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试。", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function apiBlob(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Blob> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers({ Accept: "image/*" });
    const accessToken = getAccessToken();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    const response = await fetch(`${path}`, { headers, signal: controller.signal });
    if (!response.ok) throw new ApiError("图片加载失败。", response.status);
    return await response.blob();
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function apiDownload(
  path: string,
  options: ApiRequestOptions = {},
): Promise<{ blob: Blob; filename: string | null }> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  try {
    const headers = new Headers(options.headers);
    headers.set("Accept", "text/html,application/octet-stream");
    const accessToken = getAccessToken();
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    const requestUrl = path.startsWith("/api/v1/") ? path : `${API_BASE_URL}${path}`;
    const response = await fetch(requestUrl, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as
        | { message?: string; request_id?: string }
        | null;
      throw new ApiError(
        payload?.message ?? `Request failed with status ${response.status}`,
        response.status,
        payload?.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
      );
    }
    const disposition = response.headers.get("Content-Disposition");
    const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? null;
    return { blob: await response.blob(), filename };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("生成超时，请减少产品数量后重试。", 408);
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}
