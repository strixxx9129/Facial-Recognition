/**
 * Global auth state via Zustand.
 *
 * Responsibilities:
 *  - Store user + tokens in memory (tokens also persisted to localStorage)
 *  - Expose login / register / logout / refreshUser actions
 *  - Bootstrap state from localStorage on app load
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";

import {
  AuthApiError,
  _clearTokens,
  _loadStoredTokens,
  _storeTokens,
  authApi,
} from "@/api/client";
import type { AuthState, AuthTokens, LoginIn, RegisterIn, UserOut } from "@/types/auth";

// ─── Store shape ─────────────────────────────────────────────────────────────

interface AuthActions {
  /** Bootstrap from persisted tokens; silently no-ops if nothing stored. */
  initialize: () => Promise<void>;

  register: (payload: RegisterIn) => Promise<void>;
  login: (payload: LoginIn) => Promise<void>;
  logout: () => Promise<void>;

  /** Re-fetch /auth/me and update user in store. */
  refreshUser: () => Promise<void>;

  /** Called after a successful OAuth redirect (Google/Apple). */
  handleOAuthCallback: (accessToken: string, refreshToken: string, expiresIn: number) => Promise<void>;

  _setLoading: (v: boolean) => void;
  _setError: (msg: string | null) => void;
}

interface AuthStore extends AuthState {
  error: string | null;
  actions: AuthActions;
}

// ─── Store ───────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthStore>()(
  devtools(
    (set, get) => ({
      // ── State ──────────────────────────────────────────────────────────────
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: true, // true until initialize() resolves
      error: null,

      // ── Actions ────────────────────────────────────────────────────────────
      actions: {
        _setLoading: (v) => set({ isLoading: v }),
        _setError: (msg) => set({ error: msg }),

        initialize: async () => {
          const stored = _loadStoredTokens();
          if (!stored) {
            set({ isLoading: false });
            return;
          }

          // Token might still be valid — try /auth/me
          try {
            const user = await authApi.me();
            set({
              user,
              tokens: stored,
              isAuthenticated: true,
              isLoading: false,
            });
          } catch {
            // Refresh token rotation will have been attempted inside the client.
            // If it also fails we arrive here — clear everything.
            _clearTokens();
            set({ isLoading: false });
          }
        },

        register: async (payload) => {
          set({ isLoading: true, error: null });
          try {
            const res = await authApi.register(payload);
            _storeTokens(res.access_token, res.refresh_token, res.expires_in);
            set({
              user: res.user,
              tokens: _buildTokens(res.access_token, res.refresh_token, res.expires_in),
              isAuthenticated: true,
              isLoading: false,
            });
          } catch (err) {
            set({ isLoading: false, error: _extractMessage(err) });
            throw err; // allow form-level handling
          }
        },

        login: async (payload) => {
          set({ isLoading: true, error: null });
          try {
            const res = await authApi.login(payload);
            _storeTokens(res.access_token, res.refresh_token, res.expires_in);
            set({
              user: res.user,
              tokens: _buildTokens(res.access_token, res.refresh_token, res.expires_in),
              isAuthenticated: true,
              isLoading: false,
            });
          } catch (err) {
            set({ isLoading: false, error: _extractMessage(err) });
            throw err;
          }
        },

        logout: async () => {
          const { tokens } = get();
          if (tokens?.refreshToken) {
            try {
              await authApi.logout({ refresh_token: tokens.refreshToken });
            } catch {
              // Best-effort — always clear local state
            }
          }
          _clearTokens();
          set({ user: null, tokens: null, isAuthenticated: false, error: null });
        },

        refreshUser: async () => {
          try {
            const user = await authApi.me();
            set({ user });
          } catch {
            // Silently ignore — token refresh is handled in the client
          }
        },

        handleOAuthCallback: async (accessToken, refreshToken, expiresIn) => {
          set({ isLoading: true, error: null });
          try {
            _storeTokens(accessToken, refreshToken, expiresIn);
            const user = await authApi.me();
            set({
              user,
              tokens: _buildTokens(accessToken, refreshToken, expiresIn),
              isAuthenticated: true,
              isLoading: false,
            });
          } catch (err) {
            _clearTokens();
            set({ isLoading: false, error: _extractMessage(err) });
            throw err;
          }
        },
      },
    }),
    { name: "auth-store" },
  ),
);

// ─── Selectors ────────────────────────────────────────────────────────────────

export const useUser = () => useAuthStore((s) => s.user);
export const useIsAuthenticated = () => useAuthStore((s) => s.isAuthenticated);
export const useAuthLoading = () => useAuthStore((s) => s.isLoading);
export const useAuthError = () => useAuthStore((s) => s.error);
export const useAuthActions = () => useAuthStore((s) => s.actions);

// ─── Helpers ─────────────────────────────────────────────────────────────────

function _buildTokens(
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
): AuthTokens {
  return { accessToken, refreshToken, expiresAt: Date.now() + expiresIn * 1000 };
}

function _extractMessage(err: unknown): string {
  if (err instanceof AuthApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}