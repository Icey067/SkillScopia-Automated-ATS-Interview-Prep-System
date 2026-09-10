import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [access, setAccess] = useState(() => localStorage.getItem("access") || "");
  const [refresh, setRefresh] = useState(() => localStorage.getItem("refresh") || "");
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  function storeTokens(pair) {
    setAccess(pair.access_token);
    setRefresh(pair.refresh_token);
    localStorage.setItem("access", pair.access_token);
    localStorage.setItem("refresh", pair.refresh_token);
  }

  function logout() {
    if (refresh) {
      api("/auth/logout", { method: "POST", body: { refresh_token: refresh } }).catch(() => {});
    }
    setAccess("");
    setRefresh("");
    setUser(null);
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
  }

  useEffect(() => {
    if (!access) {
      setUser(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchUser() {
      try {
        const me = await api("/auth/me", { token: access });
        if (!cancelled) setUser(me);
      } catch {
        if (!refresh) {
          if (!cancelled) logout();
          return;
        }
        try {
          const pair = await api("/auth/refresh", { method: "POST", body: { refresh_token: refresh } });
          storeTokens(pair);
          const me = await api("/auth/me", { token: pair.access_token });
          if (!cancelled) setUser(me);
        } catch {
          if (!cancelled) logout();
        }
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
