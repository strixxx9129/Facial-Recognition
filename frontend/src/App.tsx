/**
 * App.tsx — root component.
 *
 * Initialises auth state from localStorage on mount, then renders routes.
 */

import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import AuthPage from "@/pages/auth/AuthPage";
import OAuthCallback from "@/pages/auth/OAuthCallback";
import { useAuthActions } from "@/store/authStore";

// Lazy-load protected pages (code split)
import { lazy, Suspense } from "react";
const Dashboard = lazy(() => import("@/pages/Dashboard"));

export default function App() {
  const { initialize } = useAuthActions();

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <BrowserRouter>
      <Routes>
        {/* ── Public ─────────────────────────────────────────────── */}
        <Route path="/auth/login" element={<AuthPage />} />
        <Route path="/auth/register" element={<AuthPage />} />

        {/* OAuth redirect landing — receives tokens in query params */}
        <Route path="/auth/callback" element={<OAuthCallback />} />

        {/* ── Protected ──────────────────────────────────────────── */}
        <Route element={<ProtectedRoute />}>
          <Route
            path="/dashboard"
            element={
              <Suspense fallback={<div className="route-loading"><div className="route-loading__spinner" /></div>}>
                <Dashboard />
              </Suspense>
            }
          />
        </Route>

        {/* ── Fallback ───────────────────────────────────────────── */}
        <Route path="*" element={<AuthPage />} />
      </Routes>
    </BrowserRouter>
  );
}