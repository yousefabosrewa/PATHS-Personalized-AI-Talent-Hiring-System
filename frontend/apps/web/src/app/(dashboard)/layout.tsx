"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shell } from "@/components/layout/shell";
import { useAuthStore } from "@/lib/stores/auth.store";
import { AgentRunsListener } from "@/components/features/agents/AgentRunsListener";
import { ImpersonationBanner } from "@/components/layout/ImpersonationBanner";
import { AssistantWidget } from "@/components/assistant/AssistantWidget";

/**
 * Dashboard route group — gating rules:
 *
 *  1. Must be signed in.
 *  2. Platform admins → /admin (their workspace).
 *  3. Candidates → /candidate/dashboard.
 *  4. Org members whose organisation is NOT in `active` status are routed
 *     to /pending-approval or /rejected. They must never see live dashboard
 *     pages because every backend API will reject them with 403 anyway.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, _hasHydrated, user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.push("/login?next=/dashboard");
      return;
    }
    if (user?.isPlatformAdmin || user?.accountType === "platform_admin") {
      router.replace("/admin");
      return;
    }
    const isCandidate =
      user?.accountType === "candidate" || user?.role === "candidate";
    if (isCandidate) {
      router.replace("/candidate/dashboard");
      return;
    }
    if (user?.accountType === "organization_member") {
      if (user.organizationStatus === "pending_approval") {
        router.replace("/pending-approval");
        return;
      }
      if (user.organizationStatus === "rejected" || user.organizationStatus === "suspended") {
        router.replace("/rejected");
        return;
      }
    }
  }, [_hasHydrated, isAuthenticated, user, router]);

  if (!_hasHydrated || !isAuthenticated) return null;
  if (user?.isPlatformAdmin || user?.accountType === "platform_admin") return null;
  const isCandidateUser =
    user?.accountType === "candidate" || user?.role === "candidate";
  if (isCandidateUser) return null;
  if (
    user?.accountType === "organization_member" &&
    user.organizationStatus &&
    user.organizationStatus !== "active"
  ) {
    return null;
  }

  // Source the org from the auth store. The legacy `paths_org` localStorage key
  // was never written, so reading it always yielded "" and the AgentRunsListener
  // below never mounted. `user` is guaranteed populated here — the component
  // returns null until `_hasHydrated` is true (see the gate above).
  const orgId = user?.orgId ?? "";

  return (
    <Shell>
      <ImpersonationBanner />
      {orgId && <AgentRunsListener orgId={orgId} />}
      {children}
      <AssistantWidget />
    </Shell>
  );
}
