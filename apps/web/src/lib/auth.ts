const TOKEN_KEY = "thirdy_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  // Notify same-tab listeners (StorageEvent only fires cross-tab)
  window.dispatchEvent(new StorageEvent("storage", { key: TOKEN_KEY, newValue: token }));
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
