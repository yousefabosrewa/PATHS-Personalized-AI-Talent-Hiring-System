"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Clock4, LogOut, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/stores/auth.store";

export default function PendingApprovalPage() {
  const router = useRouter();
  const { user, isAuthenticated, _hasHydrated, logout } = useAuthStore();

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    // If their org is already active, route them onward.
    if (user?.organizationStatus === "active") {
      router.replace("/dashboard");
    }
    if (user?.organizationStatus === "rejected") {
      router.replace("/rejected");
    }
  }, [_hasHydrated, isAuthenticated, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-lg rounded-2xl border border-border/50 bg-white p-10 text-center shadow-lg">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-amber-50 ring-1 ring-amber-200">
          <Clock4 className="h-6 w-6 text-amber-600" />
        </div>
        <h1 className="font-heading text-2xl font-bold text-foreground">
          Your company account is pending approval
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          A platform admin is reviewing your access request. You will be able
          to sign in to your company workspace once it has been approved.
        </p>
        {user?.orgName && (
          <div className="mt-6 rounded-lg border border-border/40 bg-muted/30 p-4 text-left">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Your request
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">{user.orgName}</p>
            <p className="text-xs text-muted-foreground">{user.email}</p>
          </div>
        )}
        <div className="mt-7 flex items-center justify-center gap-3 text-xs text-muted-foreground">
          <Mail className="h-3.5 w-3.5" />
          We will email you when the decision is made.
        </div>
        <div className="mt-6 flex justify-center gap-3">
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
