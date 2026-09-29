const ACCESS_TOKEN_KEY = "productflow.access_token";

export function getAccessToken(): string | null {
  return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function storeAccessToken(token: string): void {
  window.sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}
