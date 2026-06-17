// ─── Request payloads ────────────────────────────────────────────────────────

export interface RegisterIn {
  email: string;
  password: string;
  display_name?: string;
}

export interface LoginIn {
  email: string;
  password: string;
}

export interface RefreshIn {
  refresh_token: string;
}

export interface LogoutIn {
  refresh_token: string;
}

// ─── Response payloads ───────────────────────────────────────────────────────

export interface UserOut {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface AuthResponseOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserOut;
}

export interface TokenRefreshOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ─── Internal auth state ─────────────────────────────────────────────────────

export type AuthProvider = "email" | "google" | "apple";

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // Unix ms timestamp
}

export interface AuthState {
  user: UserOut | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// ─── Form states ─────────────────────────────────────────────────────────────

export type AuthMode = "login" | "register";

export interface FieldError {
  field: string;
  message: string;
}

export interface ApiError {
  detail: string | FieldError[];
  status: number;
}