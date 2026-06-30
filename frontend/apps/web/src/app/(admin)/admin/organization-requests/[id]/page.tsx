"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, CheckCircle2, Loader2, ShieldCheck, XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { platformAdminApi, type AdminOrgRequestDetail } from "@/lib/api/platform-admin.api";
import { cn } from "@/lib/utils/cn";

function StatusBadge({ status }: { status: AdminOrgRequestDetail["status"] }) {
  const map = {
    pending:  "border-amber-300/70 bg-amber-50 text-amber-700",
    approved: "border-emerald-300/70 bg-emerald-50 text-emerald-700",
    rejected: "border-rose-300/70 bg-rose-50 text-rose-700",
  } as const;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold capitalize", map[status])}>
      {status}
    </span>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/70">{label}</p>
      <p className="mt-1 text-sm text-foreground">{value || <span className="text-muted-foreground">—</span>}</p>
    </div>
  );
}

export default function OrgRequestDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [req, setReq] = useState<AdminOrgRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!id) return;
    let mounted = true;
    (async () => {
      try {
        const data = await platformAdminApi.getRequest(id);
        if (mounted) setReq(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [id]);

  const onApprove = async () => {
    if (!id) return;
    setBusy("approve");
    setError(null);
    try {
      const updated = await platformAdminApi.approveRequest(id);
      setReq(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setBusy(null);
    }
  };

  const onReject = async () => {
    if (!id) return;
    if (reason.trim().length < 3) {
      setError("Reason must be at least 3 characters");
      return;
    }
    setBusy("reject");
    setError(null);
    try {
      const updated = await platformAdminApi.rejectRequest(id, reason.trim());
      setReq(updated);
      setShowRejectForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rejection failed");
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return <div className="p-10 text-sm text-muted-foreground">Loading…</div>;
  }
  if (!req) {
    return (
      <div className="p-10 text-sm text-destructive">
        {error ?? "Request not found"}
      </div>
    );
  }

  const isPending = req.status === "pending";

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <button
        type="button"
        onClick={() => router.back()}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to requests
      </button>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-3">
            <h1 className="font-heading text-3xl font-bold">{req.organization_name}</h1>
            <StatusBadge status={req.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            Submitted {new Date(req.submitted_at).toLocaleString()}
            {req.reviewed_at && ` · Reviewed ${new Date(req.reviewed_at).toLocaleString()}`}
          </p>
        </div>
        {isPending && !showRejectForm && (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              className="border-rose-300 text-rose-600 hover:bg-rose-50"
              onClick={() => setShowRejectForm(true)}
              disabled={busy !== null}
            >
              <XCircle className="mr-1.5 h-4 w-4" />
              Reject
            </Button>
            <Button
              type="button"
              onClick={onApprove}
              disabled={busy !== null}
            >
              {busy === "approve" ? (
                <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Approving…</>
              ) : (
                <><CheckCircle2 className="mr-1.5 h-4 w-4" /> Approve</>
              )}
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {showRejectForm && (
        <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50/40 p-5">
          <h3 className="font-heading text-base font-semibold text-rose-800">Reject request</h3>
          <p className="mt-1 text-sm text-rose-700/80">
            The requester will see this reason on their next sign-in.
          </p>
          <textarea
            rows={4}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason for rejection (required, min 3 chars)…"
            className="mt-3 w-full rounded-md border border-rose-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
          />
          <div className="mt-3 flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => { setShowRejectForm(false); setReason(""); }}
              disabled={busy !== null}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-rose-600 text-white hover:bg-rose-700"
              onClick={onReject}
              disabled={busy !== null || reason.trim().length < 3}
            >
              {busy === "reject" ? (
                <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Rejecting…</>
              ) : (
                "Confirm rejection"
              )}
            </Button>
          </div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-heading text-sm font-semibold uppercase tracking-wide text-muted-foreground">Company</h3>
          <div className="space-y-3">
            <Field label="Name" value={req.organization_name} />
            <Field label="Slug" value={req.organization_slug} />
            <Field label="Industry" value={req.organization_industry} />
            <Field label="Contact Email" value={req.organization_contact_email} />
          </div>
        </div>

        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
          <h3 className="mb-4 font-heading text-sm font-semibold uppercase tracking-wide text-muted-foreground">Requester</h3>
          <div className="space-y-3">
            <Field label="Name" value={req.requester_name} />
            <Field label="Email" value={req.requester_email} />
            <Field label="Title / Role" value={req.contact_role} />
            <Field label="Phone" value={req.contact_phone} />
          </div>
        </div>

        {req.status === "rejected" && req.rejection_reason && (
          <div className="md:col-span-2 rounded-xl border border-rose-200 bg-rose-50/40 p-5">
            <h3 className="mb-2 flex items-center gap-2 font-heading text-sm font-semibold text-rose-800">
              <XCircle className="h-4 w-4" />
              Rejection reason
            </h3>
            <p className="text-sm text-rose-700">{req.rejection_reason}</p>
          </div>
        )}

        {req.status === "approved" && (
          <div className="md:col-span-2 rounded-xl border border-emerald-200 bg-emerald-50/40 p-5">
            <h3 className="mb-2 flex items-center gap-2 font-heading text-sm font-semibold text-emerald-800">
              <ShieldCheck className="h-4 w-4" />
              Approved
            </h3>
            <p className="text-sm text-emerald-700">
              The organisation is now active and the requester can sign in to their workspace.{" "}
              <Link href="/admin/organizations" className="underline">View all organisations</Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
