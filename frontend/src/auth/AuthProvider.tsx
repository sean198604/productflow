import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiRequest } from "../lib/api";
import { clearAccessToken, getAccessToken, storeAccessToken } from "./tokenStorage";

export type UserRole = "owner" | "admin" | "member";

export type Session = {
  user: {
    id: string;
    tenant_id: string;
    username: string;
    email: string;
    role: UserRole;
    is_platform_admin: boolean;
    status: string;
  };
  tenant: {
    id: string;
    name: string;
    slug: string;
  };
};

type LoginCredentials = {
  identifier: string;
  password: string;
};

export type RegisterCredentials = {
  tenantName: string;
  username: string;
  email: string;
  password: string;
};

type LoginResponse = Session & {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

type AuthContextValue = {
  session: Session | null;
  isInitializing: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isInitializing, setIsInitializing] = useState(() => getAccessToken() !== null);

  useEffect(() => {
    if (getAccessToken() === null) {
      setIsInitializing(false);
      return;
    }

    let active = true;
    apiRequest<Session>("/auth/me")
      .then((currentSession) => {
        if (active) setSession(currentSession);
      })
      .catch(() => {
        clearAccessToken();
        if (active) setSession(null);
      })
      .finally(() => {
        if (active) setIsInitializing(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const response = await apiRequest<LoginResponse>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        identifier: credentials.identifier.trim().toLowerCase(),
        password: credentials.password,
      }),
    });
    storeAccessToken(response.access_token);
    setSession({ user: response.user, tenant: response.tenant });
  }, []);

  const register = useCallback(async (credentials: RegisterCredentials) => {
    const response = await apiRequest<LoginResponse>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant_name: credentials.tenantName.trim(),
        username: credentials.username.trim().toLowerCase(),
        email: credentials.email.trim().toLowerCase(),
        password: credentials.password,
      }),
    });
    storeAccessToken(response.access_token);
    setSession({ user: response.user, tenant: response.tenant });
  }, []);

  const logout = useCallback(() => {
    clearAccessToken();
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ session, isInitializing, login, register, logout }),
    [isInitializing, login, logout, register, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
