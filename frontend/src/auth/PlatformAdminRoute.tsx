import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function PlatformAdminRoute() {
  const { session } = useAuth();
  if (!session?.user.is_platform_admin) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Outlet />;
}
