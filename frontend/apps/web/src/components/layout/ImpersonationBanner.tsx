"use client";

/**
 * ImpersonationBanner — PATHS-159
 *
 * Renders a persistent red banner when the current session has the
 * `impersonating: true` claim in its JWT. Shows who is being impersonated
 * and provides an "Exit" button that clears the impersonation token.
 */

import { useEffect, useState } from "react";
import { ShieldAlert, X } from "lucide-react";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

export function ImpersonationBanner() {
  const [target, setTarget] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const impToken = localStorage.getItem("paths-impersonation-token");
    if (!impToken) return;

    const payload = decodeJwtPayload(impToken);
    if (!payload || !payload.impersonating) {
      localStorage.removeItem("paths-impersonation-token");
      return;
    }

    // Check expiry
    const exp = payload.exp as number | undefined;
    if (exp && exp * 1000 < Date.now()) {
      localStorage.removeItem("paths-impersonation-token");
      localStorage.removeItem("paths-impersonation-session");
      localStorage.removeItem("paths-impersonation-target");
      return;
    }

    setTarget(localStorage.getItem("paths-impersonation-target") ?? (payload.sub as string));
    setSessionId(localStorage.getItem("paths-impersonation-session"));
  }, []);

  const exitImpersonation = () => {
    localStorage.removeItem("paths-impersonation-token");
    localStorage.removeItem("paths-impersonation-session");
    localStorage.removeItem("paths-impersonation-target");
    setTarget(null);
    setSessionId(null);
  };

  if (!target) return null;

  return (
    <div className="sticky top-0 z-50 flex items-center justify-between gap-4 bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-md">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        <span>
          You are impersonating <strong>{target}</strong>.
          {sessionId && (
            <span className="ml-2 font-mono text-red-200 text-xs">{sessionId.slice(0, 8)}</span>
          )}
          {" "}This session expires in 15 minutes.
        </span>
      </div>
      <button
        onClick={exitImpersonation}
        className="flex items-center gap-1 rounded-md border border-white/30 bg-white/10 px-3 py-1 text-xs font-semibold hover:bg-white/20"
      >
        <X className="h-3 w-3" /> Exit impersonation
      </button>
    </div>
  );
}
