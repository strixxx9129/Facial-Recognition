/**
 * OAuthCallback
 *
 * The backend redirects here after a successful Google / Apple OAuth flow
 * with tokens in the URL:
 *
 *   /auth/callback?access_token=...&refresh_token=...&expires_in=900&provider=google
 *
 * This page extracts the tokens, hydrates the store, then navigates home.
 * On error it redirects to /auth/login with an error message.
 */

import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuthActions } from "@/store/authStore";

export default function OAuthCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { handleOAuthCallback } = useAuthActions();
  const ran = useRef(false); // StrictMode guard

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    const expiresIn = Number(params.get("expires_in") ?? 900);
    const error = params.get("error");

    if (error) {
      navigate(`/auth/login?error=${encodeURIComponent(error)}`, { replace: true });
      return;
    }

    if (!accessToken || !refreshToken) {
      navigate("/auth/login?error=missing_tokens", { replace: true });
      return;
    }

    handleOAuthCallback(accessToken, refreshToken, expiresIn)
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => navigate("/auth/login?error=oauth_failed", { replace: true }));
  }, []);

  return (
    <div className="oauth-callback">
      <div className="oauth-callback__spinner" aria-label="Completing sign in…" />
      <p className="oauth-callback__label">Completing sign in…</p>
    </div>
  );
}