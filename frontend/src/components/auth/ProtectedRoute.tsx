/**
 * ProtectedRoute
 *
 * Wraps private routes. Redirects unauthenticated users to /auth/login
 * while preserving the original path so they can be sent back after login.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthLoading, useIsAuthenticated } from "@/store/authStore";

export default function ProtectedRoute() {
  const isAuthenticated = useIsAuthenticated();
  const isLoading = useAuthLoading();
  const location = useLocation();

  // Wait for the store to finish bootstrapping from localStorage
  if (isLoading) {
    return (
      <div className="route-loading" role="status" aria-label="Loading…">
        <div className="route-loading__spinner" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={`/auth/login?redirect=${encodeURIComponent(location.pathname)}`}
        replace
      />
    );
  }

  return <Outlet />;
}