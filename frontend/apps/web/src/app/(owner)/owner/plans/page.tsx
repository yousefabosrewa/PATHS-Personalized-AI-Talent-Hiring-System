"use client";

import { useState } from "react";
import { Plus, Pencil, Check, X } from "lucide-react";
import { useOwnerPlans, useUpsertPlan } from "@/lib/hooks";
import type { OwnerPlan } from "@/lib/api/owner.api";

type PlanForm = Omit<OwnerPlan, "id"> & { id?: string };

const EMPTY_FORM: PlanForm = {
  name: "",
  code: "",
  price_monthly_cents: 0,
  price_annual_cents: 0,
  currency: "USD",
  limits: {},
  features: [],
  is_public: true,
};

function PlanCard({
  plan,
  onEdit,
}: {
  plan: OwnerPlan;
  onEdit: (plan: OwnerPlan) => void;
}) {
  return (
    <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="font-heading text-lg font-bold capitalize">{plan.name}</p>
          <code className="text-xs text-muted-foreground">{plan.code}</code>
        </div>
        <button
          onClick={() => onEdit(plan)}
          className="rounded-lg border border-border/50 p-1.5 text-muted-foreground hover:text-foreground"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Monthly</p>
          <p className="font-semibold">${(plan.price_monthly_cents / 100).toFixed(0)}/mo</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Annual</p>
          <p className="font-semibold">${(plan.price_annual_cents / 100).toFixed(0)}/yr</p>
        </div>
      </div>
      {plan.features.length > 0 && (
        <ul className="space-y-1">
          {plan.features.slice(0, 4).map((f, i) => (
            <li key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Check className="h-3 w-3 text-green-500 shrink-0" />
              {f}
            </li>
          ))}
          {plan.features.length > 4 && (
            <li className="text-xs text-muted-foreground pl-4.5">
              +{plan.features.length - 4} more
            </li>
          )}
        </ul>
      )}
      {!plan.is_public && (
        <span className="mt-3 inline-block rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
          Hidden from pricing page
        </span>
      )}
    </div>
  );
}

export default function OwnerPlansPage() {
  const { data: plans = [], isLoading } = useOwnerPlans();
  const upsert = useUpsertPlan();
  const [editForm, setEditForm] = useState<PlanForm | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<PlanForm>({ ...EMPTY_FORM });
  const [featInput, setFeatInput] = useState("");

  const handleSave = async (form: PlanForm) => {
    try {
      await upsert.mutateAsync(form);
      setEditForm(null);
      setShowCreate(false);
      setCreateForm({ ...EMPTY_FORM });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save plan");
    }
  };

  function PlanEditor({
    form,
    onChange,
    onSave,
    onCancel,
  }: {
    form: PlanForm;
    onChange: (f: PlanForm) => void;
    onSave: () => void;
    onCancel: () => void;
  }) {
    const [feat, setFeat] = useState(featInput);
    return (
      <div className="rounded-xl border border-primary/30 bg-white p-5 shadow-md space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-semibold">Name</label>
            <input
              value={form.name}
              onChange={(e) => onChange({ ...form, name: e.target.value })}
              className="mt-1 w-full rounded-lg border border-border/50 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="text-xs font-semibold">Code</label>
            <input
              value={form.code}
              onChange={(e) => onChange({ ...form, code: e.target.value })}
              className="mt-1 w-full rounded-lg border border-border/50 px-2 py-1.5 text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="text-xs font-semibold">Monthly (cents)</label>
            <input
              type="number"
              value={form.price_monthly_cents}
              onChange={(e) => onChange({ ...form, price_monthly_cents: Number(e.target.value) })}
              className="mt-1 w-full rounded-lg border border-border/50 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="text-xs font-semibold">Annual (cents)</label>
            <input
              type="number"
              value={form.price_annual_cents}
              onChange={(e) => onChange({ ...form, price_annual_cents: Number(e.target.value) })}
              className="mt-1 w-full rounded-lg border border-border/50 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold">Features (one per line)</label>
          <textarea
            rows={3}
            value={form.features.join("\n")}
            onChange={(e) =>
              onChange({
                ...form,
                features: e.target.value.split("\n").filter(Boolean),
              })
            }
            className="mt-1 w-full rounded-lg border border-border/50 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_public"
            checked={form.is_public}
            onChange={(e) => onChange({ ...form, is_public: e.target.checked })}
          />
          <label htmlFor="is_public" className="text-sm">
            Show on public pricing page
          </label>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-lg border border-border/50 px-3 py-1.5 text-sm hover:bg-muted/30"
          >
            <X className="inline h-3.5 w-3.5 mr-1" /> Cancel
          </button>
          <button
            onClick={onSave}
            disabled={upsert.isPending}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
          >
            <Check className="inline h-3.5 w-3.5 mr-1" /> Save
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Plans Editor</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Changes propagate immediately to the public pricing page.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> New plan
        </button>
      </div>

      {showCreate && (
        <PlanEditor
          form={createForm}
          onChange={setCreateForm}
          onSave={() => handleSave(createForm)}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) =>
            editForm?.id === plan.id ? (
              <PlanEditor
                key={plan.id}
                form={editForm}
                onChange={(f) => setEditForm(f)}
                onSave={() => handleSave(editForm)}
                onCancel={() => setEditForm(null)}
              />
            ) : (
              <PlanCard
                key={plan.id}
                plan={plan}
                onEdit={(p) => setEditForm({ ...p })}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}
