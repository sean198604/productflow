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

    const response = await fetch(`${API_BASE_URL}${path}`, {
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
