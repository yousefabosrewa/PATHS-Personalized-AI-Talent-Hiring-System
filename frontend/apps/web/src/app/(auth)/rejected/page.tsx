"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LogOut, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/stores/auth.store";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export default function RejectedPage() {
  const router = useRouter();
  const { user, isAuthenticated, _hasHydrated, logout, token } = useAuthStore() as {
    user: ReturnType<typeof useAuthStore.getState>["user"];
    isAuthenticated: boolean;
    _hasHydrated: boolean;
    logout: () => void;
    token: string | null;
  };
  const [reason, setReason] = useState<string | null>(null);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (user?.organizationStatus === "active") {
      router.replace("/dashboard");
      return;
    }
    if (user?.organizationStatus === "pending_approval") {
      router.replace("/pending-approval");
      return;
    }
    // Try to fetch the rejection reason from /auth/me — the backend
    // populates it on the org row.
    if (!token) return;
    fetch(`${BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data?.organization?.status === "rejected") {
          // The detail isn't returned by /me (privacy-by-default). Show a
          // generic message and let the user contact support.
          setReason(null);
        }
      })
      .catch(() => { /* ignore */ });
  }, [_hasHydrated, isAuthenticated, user, token, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-lg rounded-2xl border border-rose-200 bg-white p-10 text-center shadow-lg">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-rose-50 ring-1 ring-rose-200">
          <ShieldAlert className="h-6 w-6 text-rose-600" />
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Your company access request was not approved
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          A platform administrator reviewed your request and decided not to
          grant access at this time.
        </p>
        {user?.orgName && (
          <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50/50 p-4 text-left">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-rose-700">
              Rejected request
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">{user.orgName}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
        )}
        {reason && (
          <p className="mt-4 rounded-md border border-rose-200 bg-rose-50/40 p-3 text-sm text-rose-700">
            <strong>Reason:</strong> {reason}
          </p>
        )}
        <div className="mt-7 flex justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-border bg-white px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/40"
          >
            Back to homepage
          </Link>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
          >
            <LogOut className="mr-1.5 h-4 w-4" />
            Sign out
          </Button>
        </div>
      </div>
    </div>
  );
}
