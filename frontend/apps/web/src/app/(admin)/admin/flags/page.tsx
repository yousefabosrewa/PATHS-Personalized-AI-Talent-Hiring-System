"use client";

import { useState } from "react";
import { Flag, Plus, ChevronDown, ChevronUp } from "lucide-react";
import {
  useAdminFeatureFlags,
  useToggleFeatureFlag,
  useCreateFeatureFlag,
} from "@/lib/hooks";
import type { AdminFeatureFlag } from "@/lib/api/platform-admin.api";

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${
        checked ? "bg-green-500" : "bg-gray-200"
      } disabled:cursor-not-allowed disabled:opacity-50`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

function FlagRow({ flag }: { flag: AdminFeatureFlag }) {
  const [expanded, setExpanded] = useState(false);
  const toggle = useToggleFeatureFlag();

  return (
    <div className="border-b border-border/30 last:border-0">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <code className="text-sm font-mono font-semibold text-foreground">{flag.code}</code>
            {flag.overrides.length > 0 && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                {flag.overrides.length} override{flag.overrides.length > 1 ? "s" : ""}
              </span>
            )}
          </div>
          {flag.description && (
            <p className="mt-0.5 text-xs text-muted-foreground">{flag.description}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ToggleSwitch
            checked={flag.enabled}
            onChange={(v) => toggle.mutate({ id: flag.id, enabled: v })}
            disabled={toggle.isPending}
          />
          {flag.overrides.length > 0 && (
            <button
              onClick={() => setExpanded((p) => !p)}
              className="text-muted-foreground hover:text-foreground"
            >
              {expanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {expanded && flag.overrides.length > 0 && (
        <div className="mx-5 mb-3 rounded-lg border border-border/40 bg-muted/10 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase text-muted-foreground">
            Per-org overrides
          </p>
          <div className="space-y-1">
            {flag.overrides.map((o) => (
              <div
                key={o.org_id}
                className="flex items-center justify-between text-xs"
              >
                <code className="font-mono text-muted-foreground">{o.org_id}</code>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    o.enabled
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-600"
                  }`}
                >
                  {o.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminFlagsPage() {
  const { data: flags = [], isLoading } = useAdminFeatureFlags();
  const createFlag = useCreateFeatureFlag();
  const [showCreate, setShowCreate] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const handleCreate = async () => {
    if (!newCode.trim()) return;
    try {
      await createFlag.mutateAsync({
        code: newCode.trim().toLowerCase().replace(/\s+/g, "_"),
        description: newDesc.trim() || undefined,
        enabled: false,
      });
      setNewCode("");
      setNewDesc("");
      setShowCreate(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create flag");
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-8 py-10 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Feature Flags</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Toggle features globally or per-organisation.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((p) => !p)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> New flag
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm space-y-3">
          <h3 className="font-semibold">Create Feature Flag</h3>
          <input
            placeholder="flag_code (snake_case)"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
            className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            placeholder="Description (optional)"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-border/50 px-3 py-1.5 text-sm hover:bg-muted/30"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!newCode.trim() || createFlag.isPending}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
            >
              Create
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : flags.length === 0 ? (
          <div className="flex flex-col items-center p-10 text-muted-foreground">
            <Flag className="mb-3 h-8 w-8 opacity-30" />
            <p className="text-sm">No feature flags yet.</p>
          </div>
        ) : (
          flags.map((f) => <FlagRow key={f.id} flag={f} />)
        )}
      </div>
    </div>
  );
}
