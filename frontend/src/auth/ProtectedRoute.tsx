import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function ProtectedRoute() {
  const { session, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return (
      <main className="grid min-h-screen place-items-center text-sm text-slate-500">
        正在验证登录状态…
      </main>
    );
  }
  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
