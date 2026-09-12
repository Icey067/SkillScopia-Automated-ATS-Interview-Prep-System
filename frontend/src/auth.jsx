import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [access, setAccess] = useState(() => localStorage.getItem("access") || "dev-test-token");
  const [refresh, setRefresh] = useState(() => localStorage.getItem("refresh") || "dev-test-token");
  const [user, setUser] = useState({ id: 1, email: "tester@example.com" });
  const [loading, setLoading] = useState(false);

  function storeTokens(pair) {
    setAccess(pair.access_token);
    setRefresh(pair.refresh_token);
    localStorage.setItem("access", pair.access_token);
    localStorage.setItem("refresh", pair.refresh_token);
  }

  function logout() {
    setAccess("dev-test-token");
    setRefresh("dev-test-token");
    setUser({ id: 1, email: "tester@example.com" });
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
  }

  useEffect(() => {
    let cancelled = false;

    async function fetchUser() {
      try {
        const me = await api("/auth/me", { token: access });
        if (!cancelled && me) setUser(me);
      } catch {
        // Testing mode: silently keep test user
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchUser();

    return () => {
      cancelled = true;
    };
  }, [access, refresh]);

  const value = useMemo(
    () => ({ access, refresh, user, storeTokens, logout, loading }),
    [access, refresh, user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
