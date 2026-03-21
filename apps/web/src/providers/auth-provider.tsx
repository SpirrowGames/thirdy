"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { UserRead } from "@/types/api";
import { clearToken, getToken } from "@/lib/auth";
import { api } from "@/lib/api-client";

interface AuthContextValue {
  user: UserRead | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const verifyToken = useCallback(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    api
      .get<UserRead>("/auth/me")
      .then(setUser)
      .catch(() => {
        clearToken();
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    verifyToken();
  }, [verifyToken]);

  // Re-verify when localStorage token changes (e.g. set by /auth/callback)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "thirdy_token") {
        verifyToken();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [verifyToken]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  return useContext(AuthContext);
}
