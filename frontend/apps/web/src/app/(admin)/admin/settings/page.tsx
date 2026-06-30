"use client";

import { useEffect, useState } from "react";
import { Save, Settings } from "lucide-react";
import { useAdminPlatformSettings, useUpdatePlatformSettings } from "@/lib/hooks";

export default function AdminSettingsPage() {
  const { data: settings, isLoading } = useAdminPlatformSettings();
  const update = useUpdatePlatformSettings();

  const [form, setForm] = useState({
    display_name: "",
    support_email: "",
    legal_company_name: "",
    maintenance_mode: false,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (settings) {
      setForm({
        display_name: settings.display_name ?? "",
        support_email: settings.support_email ?? "",
        legal_company_name: settings.legal_company_name ?? "",
        maintenance_mode: settings.maintenance_mode ?? false,
      });
    }
  }, [settings]);

  const handleSave = async () => {
    try {
      await update.mutateAsync(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save");
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-8 py-10 space-y-8">
      <div className="flex items-center gap-3">
        <Settings className="h-7 w-7 text-primary" />
        <div>
          <h1 className="font-heading text-3xl font-bold">Platform Settings</h1>
          <p className="text-sm text-muted-foreground">
            Singleton configuration for the PATHS platform.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-8 text-center text-sm text-muted-foreground">
          Loading…
        </div>
      ) : (
        <div className="rounded-xl border border-border/50 bg-white p-6 shadow-sm space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-semibold">
              Platform Display Name
            </label>
            <input
              value={form.display_name}
              onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))}
              className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-semibold">
              Support Email
            </label>
            <input
              type="email"
              value={form.support_email}
              onChange={(e) => setForm((p) => ({ ...p, support_email: e.target.value }))}
              className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-semibold">
              Legal Company Name
            </label>
            <input
              value={form.legal_company_name}
              onChange={(e) =>
                setForm((p) => ({ ...p, legal_company_name: e.target.value }))
              }
              className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/10 p-4">
            <div>
              <p className="text-sm font-semibold text-foreground">Maintenance Mode</p>
              <p className="text-xs text-muted-foreground">
                When enabled, all non-admin requests return 503.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={form.maintenance_mode}
              onClick={() =>
                setForm((p) => ({ ...p, maintenance_mode: !p.maintenance_mode }))
              }
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                form.maintenance_mode ? "bg-red-500" : "bg-gray-200"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
                  form.maintenance_mode ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {form.maintenance_mode && (
            <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              ⚠️ Maintenance mode is <strong>ON</strong>. All org users will see a 503 error.
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            {saved && (
              <span className="text-sm font-semibold text-green-600">
                ✓ Settings saved
              </span>
            )}
            <div className="ml-auto">
              <button
                onClick={handleSave}
                disabled={update.isPending}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {update.isPending ? "Saving…" : "Save settings"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Audit log shortcut */}
      <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-heading text-lg font-semibold">Impersonation Audit Log</h2>
        <p className="text-sm text-muted-foreground">
          All impersonation sessions are recorded. View the full audit trail in the{" "}
          <a href="/admin/audit" className="font-medium text-primary hover:underline">
            Audit Log
          </a>{" "}
          — filter by action prefix <code className="rounded bg-muted px-1">platform.impersonate</code>.
        </p>
      </div>
    </div>
  );
}
