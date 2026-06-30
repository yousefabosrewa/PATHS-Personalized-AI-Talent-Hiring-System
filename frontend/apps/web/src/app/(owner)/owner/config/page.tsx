"use client";

import { useEffect, useState } from "react";
import { Save, Settings2 } from "lucide-react";
import { useOwnerPlatformConfig, useUpdateOwnerPlatformConfig } from "@/lib/hooks";

export default function OwnerConfigPage() {
  const { data: config, isLoading } = useOwnerPlatformConfig();
  const update = useUpdateOwnerPlatformConfig();

  const [form, setForm] = useState({
    display_name: "",
    support_email: "",
    legal_company_name: "",
    maintenance_mode: false,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (config) {
      setForm({
        display_name: config.display_name ?? "",
        support_email: config.support_email ?? "",
        legal_company_name: config.legal_company_name ?? "",
        maintenance_mode: config.maintenance_mode ?? false,
      });
    }
  }, [config]);

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
        <Settings2 className="h-7 w-7 text-primary" />
        <div>
          <h1 className="font-heading text-3xl font-bold">Platform Config</h1>
          <p className="text-sm text-muted-foreground">
            Global platform identity and operational settings.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-border/40 bg-muted/20 p-8 text-center text-sm text-muted-foreground">
          Loading…
        </div>
      ) : (
        <div className="rounded-xl border border-border/50 bg-white p-6 shadow-sm space-y-5">
          {[
            { key: "display_name", label: "Platform Display Name", type: "text" },
            { key: "support_email", label: "Support Email", type: "email" },
            { key: "legal_company_name", label: "Legal Company Name", type: "text" },
          ].map((field) => (
            <div key={field.key}>
              <label className="mb-1.5 block text-sm font-semibold">{field.label}</label>
              <input
                type={field.type}
                value={form[field.key as keyof typeof form] as string}
                onChange={(e) =>
                  setForm((p) => ({ ...p, [field.key]: e.target.value }))
                }
                className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          ))}

          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/10 p-4">
            <div>
              <p className="text-sm font-semibold">Maintenance Mode</p>
              <p className="text-xs text-muted-foreground">
                Block all org users with a 503 response.
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
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                  form.maintenance_mode ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {form.maintenance_mode && (
            <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700">
              ⚠️ Maintenance mode is <strong>ON</strong>.
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            {saved && (
              <span className="text-sm font-semibold text-green-600">✓ Saved</span>
            )}
            <div className="ml-auto">
              <button
                onClick={handleSave}
                disabled={update.isPending}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {update.isPending ? "Saving…" : "Save config"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
