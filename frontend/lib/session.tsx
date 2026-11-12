"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type Me } from "./api";

interface SessionValue {
  me: Me;
  refresh: () => Promise<void>;
  setMe: (me: Me) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

/** Loads the signed-in user and current organisation; sends visitors who are not signed in to the login page. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [failed, setFailed] = useState("");

  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("auth/me/"));
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        router.replace(`/login/?next=${encodeURIComponent(window.location.pathname)}`);
      } else {
        setFailed(error instanceof Error ? error.message : "Could not load your account.");
      }
    }
  }, [router]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (failed) return <p className="p-8 text-red-700">{failed}</p>;
  if (!me) return <p className="p-8 text-muted">Loading your workspace…</p>;
  return <SessionContext.Provider value={{ me, refresh, setMe }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

export function can(me: Me, role: "admin" | "owner"): boolean {
  const rank = { member: 1, admin: 2, owner: 3 } as const;
  return rank[me.organization.role] >= rank[role];
}
