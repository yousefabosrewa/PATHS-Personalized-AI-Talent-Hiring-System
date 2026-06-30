"use client";

import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { platformAdminApi, type AdminAuditRow } from "@/lib/api/platform-admin.api";

export default function AdminAuditPage() {
  const [rows, setRows] = useState<AdminAuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const data = await platformAdminApi.listAudit({ limit: 200 });
        if (mounted) setRows(data);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <div className="mb-8 flex items-center gap-3">
        <ShieldCheck className="h-6 w-6 text-primary" />
        <div>
          <h1 className="font-heading text-3xl font-bold">Audit log</h1>
          <p className="mt-1 text-sm text-muted-foreground">Every platform-level event, newest first.</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        {loading ? (
          <p className="p-6 text-sm text-muted-foreground">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">No audit events yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/40 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3">When</th>
                <th className="px-5 py-3">Action</th>
                <th className="px-5 py-3">Entity</th>
                <th className="px-5 py-3">Actor</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/30 last:border-0 hover:bg-muted/20">
                  <td className="px-5 py-3 whitespace-nowrap text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    <code className="rounded bg-muted/40 px-2 py-0.5 text-[11px] text-foreground">{r.action}</code>
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {r.entity_type}
                    {r.entity_id ? ` · ${r.entity_id.slice(0, 8)}…` : ""}
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">
                    {r.actor_user_id ? `${r.actor_user_id.slice(0, 8)}…` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
