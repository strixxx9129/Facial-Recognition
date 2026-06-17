/**
 * Typed API client for the FastAPI backend.
 * Handles:
 *  - Base URL injection
 *  - Bearer token attachment
 *  - Automatic silent token refresh on 401
 *  - Normalised ApiError throwing
 */

import type {
  ApiError,
  AuthResponseOut,
  LoginIn,
  LogoutIn,
  RegisterIn,
  TokenRefreshOut,
  UserOut,
} from "@/types/auth";

// ─── Constants ───────────────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_PREFIX = "/api/v1";

// Keys used in localStorage (keep in sync with useAuthStore)
const ACCESS_TOKEN_KEY = "em_access_token";
const REFRESH_TOKEN_KEY = "em_refresh_token";
const EXPIRES_AT_KEY = "em_expires_at";

// ─── Error helper ────────────────────────────────────────────────────────────

export class AuthApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "AuthApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseError(res: Response): Promise<never> {
  let detail = "An unexpected error occurred.";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) {
      // FastAPI validation errors: [{loc, msg, type}]
      detail = body.detail.map((e: { msg: string }) => e.msg).join(", ");
    }
  } catch {
    detail = res.statusText || detail;
  }
  throw new AuthApiError(res.status, detail);
}

// ─── Core fetch wrapper ──────────────────────────────────────────────────────

let _refreshPromise: Promise<TokenRefreshOut> | null = null;

async function request<T>(
  path: string,
  options: RequestInit = {},
  withAuth = false,
  _retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (withAuth) {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE_URL}${API_PREFIX}${path}`, {
    ...options,
    headers,
  });

  // ── Silent refresh on 401 ────────────────────────────────────────────────
  if (res.status === 401 && withAuth && _retry) {
    const rawRefresh = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!rawRefresh) throw new AuthApiError(401, "Session expired. Please log in again.");

    // Deduplicate concurrent refresh calls
    if (!_refreshPromise) {
      _refreshPromise = authApi.refresh({ refresh_token: rawRefresh }).finally(
        () => { _refreshPromise = null; },
      );
    }

    try {
      const refreshed = await _refreshPromise;
      _storeTokens(refreshed.access_token, refreshed.refresh_token, refreshed.expires_in);
      // Retry the original request once with the new token
      return request<T>(path, options, true, false);
    } catch {
      _clearTokens();
      throw new AuthApiError(401, "Session expired. Please log in again.");
    }
  }

  if (!res.ok) await parseError(res);

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Token persistence helpers (used internally + by useAuthStore) ──────────

export function _storeTokens(
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  localStorage.setItem(EXPIRES_AT_KEY, String(Date.now() + expiresIn * 1000));
}

export function _clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
}

export function _loadStoredTokens() {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  const expiresAt = Number(localStorage.getItem(EXPIRES_AT_KEY) ?? 0);
  if (!accessToken || !refreshToken) return null;
  return { accessToken, refreshToken, expiresAt };
}

// ─── Auth API ────────────────────────────────────────────────────────────────

export const authApi = {
  /** POST /auth/register */
  register(body: RegisterIn): Promise<AuthResponseOut> {
    return request<AuthResponseOut>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** POST /auth/login */
  login(body: LoginIn): Promise<AuthResponseOut> {
    return request<AuthResponseOut>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** POST /auth/refresh */
  refresh(body: { refresh_token: string }): Promise<TokenRefreshOut> {
    return request<TokenRefreshOut>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** POST /auth/logout — requires auth */
  logout(body: LogoutIn): Promise<void> {
    return request<void>(
      "/auth/logout",
      { method: "POST", body: JSON.stringify(body) },
      true,
    );
  },

  /** GET /auth/me — requires auth */
  me(): Promise<UserOut> {
    return request<UserOut>("/auth/me", {}, true);
  },

  /**
   * Google OAuth: redirect browser to backend initiation endpoint.
   * The backend handles the full redirect to accounts.google.com.
   */
  initiateGoogle(): void {
    window.location.href = `${BASE_URL}${API_PREFIX}/auth/google`;
  },

  /**
   * Apple Sign In: redirect browser to backend initiation endpoint.
   * Apple sends a POST back to the backend callback so no token
   * handling is needed here — the backend redirects to the frontend
   * with tokens in the URL hash or query params.
   */
  initiateApple(): void {
    window.location.href = `${BASE_URL}${API_PREFIX}/auth/apple`;
  },
};