"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  Users,
  Briefcase,
  Activity,
  ShieldAlert,
  UserSearch,
} from "lucide-react";
import { useAdminOrgDossier, useImpersonateOrg } from "@/lib/hooks";

const HEALTH_COLOR = (score: number) =>
  score >= 70 ? "text-green-600" : score >= 40 ? "text-amber-600" : "text-red-600";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  pending_approval: "bg-amber-100 text-amber-700",
  suspended: "bg-red-100 text-red-700",
  rejected: "bg-gray-100 text-gray-600",
};

export default function OrgDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: org, isLoading, error } = useAdminOrgDossier(id);
  const impersonate = useImpersonateOrg();
  const [reason, setReason] = useState("");
  const [showImpersonateModal, setShowImpersonateModal] = useState(false);
  const [impersonateSuccess, setImpersonateSuccess] = useState<string | null>(null);

  const handleImpersonate = async () => {
    if (!reason.trim()) return;
    try {
      const res = await impersonate.mutateAsync({ orgId: id, reason });
      // Store the impersonation token so the user can switch contexts
      if (typeof window !== "undefined") {
        localStorage.setItem("paths-impersonation-token", res.access_token);
        localStorage.setItem("paths-impersonation-session", res.impersonation_session_id);
        localStorage.setItem("paths-impersonation-target", res.target_user_email);
      }
      setImpersonateSuccess(
        `Impersonating ${res.target_user_email} @ ${res.target_org ?? "org"}. Token valid for 15 min.`,
      );
      setShowImpersonateModal(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Impersonation failed");
    }
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-10 text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }
  if (error || !org) {
    return (
      <div className="mx-auto max-w-5xl px-8 py-10 text-sm text-destructive">
        Failed to load org.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/admin/organizations"
            className="rounded-lg border border-border/50 p-1.5 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="font-heading text-2xl font-bold">{org.name}</h1>
            <p className="text-xs text-muted-foreground">
              /{org.slug} · {org.industry ?? "No industry"} ·{" "}
              {org.contact_email ?? "No email"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              STATUS_BADGE[org.status] ?? "bg-gray-100 text-gray-600"
            }`}
          >
            {org.status}
          </span>
          <button
            onClick={() => setShowImpersonateModal(true)}
            className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600"
          >
            <UserSearch className="h-3.5 w-3.5" />
            Impersonate
          </button>
        </div>
      </div>

      {impersonateSuccess && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          ⚠️ {impersonateSuccess}
        </div>
      )}

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
            <Activity className="h-3.5 w-3.5 text-primary" /> Health Score
          </div>
          <p className={`text-3xl font-bold ${HEALTH_COLOR(org.health_score)}`}>
            {org.health_score}
            <span className="text-base font-normal text-muted-foreground">/100</span>
          </p>
        </div>
        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
            <Users className="h-3.5 w-3.5 text-primary" /> Members
          </div>
          <p className="text-3xl font-bold">{org.members.length}</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
            <Briefcase className="h-3.5 w-3.5 text-primary" /> Plan
          </div>
          <p className="text-2xl font-bold capitalize">
            {org.subscription?.plan ?? "Free"}
          </p>
          {org.subscription && (
            <p className="text-xs text-muted-foreground">
              {org.subscription.status} · {org.subscription.billing_cycle}
            </p>
          )}
        </div>
      </div>

      {/* Members table */}
      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        <div className="border-b border-border/40 p-5">
          <h2 className="font-heading text-lg font-semibold">Members</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20 text-xs font-semibold uppercase text-muted-foreground">
                <th className="px-5 py-3 text-left">Name / Email</th>
                <th className="px-5 py-3 text-left">Role</th>
                <th className="px-5 py-3 text-left">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {org.members.map((m) => (
                <tr key={m.user_id} className="hover:bg-muted/10">
                  <td className="px-5 py-3">
                    <p className="font-medium">{m.full_name}</p>
                    <p className="text-xs text-muted-foreground">{m.email}</p>
                  </td>
                  <td className="px-5 py-3">
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {m.role_code}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {m.is_active ? (
                      <span className="text-green-600 text-xs font-semibold">Active</span>
                    ) : (
                      <span className="text-red-500 text-xs font-semibold">Inactive</span>
                    )}
                  </td>
                </tr>
              ))}
              {org.members.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-5 py-6 text-center text-muted-foreground">
                    No members
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recent jobs */}
      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        <div className="border-b border-border/40 p-5">
          <h2 className="font-heading text-lg font-semibold">Recent Jobs</h2>
        </div>
        <div className="divide-y divide-border/20">
          {org.recent_jobs.map((j) => (
            <div key={j.id} className="flex items-center justify-between px-5 py-3">
              <p className="text-sm font-medium">{j.title}</p>
              <div className="flex items-center gap-3">
                <span className="rounded-full border border-border/40 px-2 py-0.5 text-xs text-muted-foreground capitalize">
                  {j.status}
                </span>
                <span className="text-xs text-muted-foreground">
                  {j.created_at ? new Date(j.created_at).toLocaleDateString() : "—"}
                </span>
              </div>
            </div>
          ))}
          {org.recent_jobs.length === 0 && (
            <p className="px-5 py-6 text-center text-sm text-muted-foreground">No jobs</p>
          )}
        </div>
      </div>

      {/* Impersonate Modal */}
      {showImpersonateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="mb-1 font-heading text-lg font-bold text-destructive">
              Impersonate Organization
            </h3>
            <p className="mb-4 text-xs text-muted-foreground">
              You will receive a 15-minute read-scoped token as the first member of{" "}
              <strong>{org.name}</strong>. Every impersonation is audited.
            </p>
            <textarea
              rows={3}
              placeholder="Reason for impersonation (required)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded-lg border border-border/50 p-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowImpersonateModal(false)}
                className="rounded-lg border border-border/50 px-4 py-2 text-sm hover:bg-muted/30"
              >
                Cancel
              </button>
              <button
                onClick={handleImpersonate}
                disabled={!reason.trim() || impersonate.isPending}
                className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
              >
                {impersonate.isPending ? "Starting…" : "Start impersonation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
