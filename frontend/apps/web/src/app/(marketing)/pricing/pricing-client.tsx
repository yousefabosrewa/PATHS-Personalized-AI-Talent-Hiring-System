"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  ChevronRight,
  Loader2,
  MessageSquare,
  Sparkles,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { usePublicPlans, useUpgradePlan } from "@/lib/hooks";

// ── Types ──────────────────────────────────────────────────────────────────

interface Plan {
  id: string;
  name: string;
  code: string;
  price_monthly_cents: number;
  price_annual_cents: number;
  currency: string;
  limits: Record<string, number>;
  features: string[];
}

// ── Static fallback plans (shown while API loads or on error) ──────────────

const FALLBACK_PLANS: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    code: "starter",
    price_monthly_cents: 4900,
    price_annual_cents: 49000,
    currency: "USD",
    limits: { jobs_active: 5, cvs_per_month: 100, seats: 3 },
    features: ["cv_ingestion", "screening", "interview_intelligence"],
  },
  {
    id: "growth",
    name: "Growth",
    code: "growth",
    price_monthly_cents: 14900,
    price_annual_cents: 149000,
    currency: "USD",
    limits: { jobs_active: 25, cvs_per_month: 500, seats: 10 },
    features: [
      "cv_ingestion",
      "screening",
      "interview_intelligence",
      "sourcing",
      "outreach",
      "bias_reports",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    code: "enterprise",
    price_monthly_cents: 49900,
    price_annual_cents: 499000,
    currency: "USD",
    limits: { jobs_active: -1, cvs_per_month: -1, seats: -1 },
    features: [
      "cv_ingestion",
      "screening",
      "interview_intelligence",
      "sourcing",
      "outreach",
      "bias_reports",
      "custom_rubrics",
      "sso",
      "audit_export",
    ],
  },
];

// ── Feature labels ────────────────────────────────────────────────────────

const FEATURE_LABELS: Record<string, string> = {
  cv_ingestion: "CV Ingestion & Parsing",
  screening: "AI Screening Agent",
  interview_intelligence: "Interview Intelligence",
  sourcing: "Candidate Sourcing",
  outreach: "Automated Outreach",
  bias_reports: "Bias & Fairness Reports",
  custom_rubrics: "Custom Scoring Rubrics",
  sso: "SSO / SAML",
  audit_export: "Audit Log Export",
};

// ── Plan icons ────────────────────────────────────────────────────────────

const PLAN_ICONS: Record<string, React.ReactNode> = {
  starter: <Zap className="h-5 w-5 text-blue-500" />,
  growth: <Sparkles className="h-5 w-5 text-violet-500" />,
  enterprise: <MessageSquare className="h-5 w-5 text-amber-500" />,
};

const PLAN_ACCENT: Record<string, string> = {
  starter: "border-blue-500/30",
  growth: "border-violet-500 ring-2 ring-violet-500/20",
  enterprise: "border-amber-500/30",
};

// ── Helpers ───────────────────────────────────────────────────────────────

function fmt(cents: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

function limitLabel(key: string, val: number) {
  if (val === -1) return "Unlimited";
  const labels: Record<string, string> = {
    jobs_active: `${val} active jobs`,
    cvs_per_month: `${val} CVs / month`,
    seats: `${val} seats`,
    agent_runs_per_hour: `${val} agent runs / hr`,
  };
  return labels[key] ?? `${val}`;
}

// ── PricingCard ───────────────────────────────────────────────────────────

function PricingCard({
  plan,
  annual,
  orgId,
}: {
  plan: Plan;
  annual: boolean;
  orgId: string | null;
}) {
  const router = useRouter();
  const price = annual ? plan.price_annual_cents / 12 : plan.price_monthly_cents;
  const isPopular = plan.code === "growth";
  const isEnterprise = plan.code === "enterprise";

  const { mutateAsync: upgrade, isPending } = useUpgradePlan(orgId ?? "");

  async function handleChoose() {
    if (!orgId) {
      router.push("/company-signup");
      return;
    }
    if (isEnterprise) {
      window.location.href = "mailto:sales@paths.app?subject=Enterprise+Enquiry";
      return;
    }
    try {
      await upgrade({ planCode: plan.code, billingCycle: annual ? "annual" : "monthly" });
    } catch {
      toast.error("Billing unavailable — please try again or contact support.");
    }
  }

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-2xl border bg-card p-6 gap-5 transition-shadow hover:shadow-lg",
        PLAN_ACCENT[plan.code] ?? "border-border",
      )}
    >
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge className="bg-violet-600 text-white text-[10px] px-3 py-0.5">
            Most Popular
          </Badge>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted/40">
          {PLAN_ICONS[plan.code] ?? <Zap className="h-5 w-5" />}
        </div>
        <div>
          <p className="font-bold text-base">{plan.name}</p>
          <p className="text-xs text-muted-foreground capitalize">{plan.code}</p>
        </div>
      </div>

      {/* Price */}
      <div>
        {isEnterprise ? (
          <p className="text-3xl font-bold">Custom</p>
        ) : (
          <>
            <span className="text-3xl font-bold">{fmt(price, plan.currency)}</span>
            <span className="text-sm text-muted-foreground"> / mo</span>
            {annual && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">
                Save {fmt(plan.price_monthly_cents * 12 - plan.price_annual_cents, plan.currency)} / yr
              </p>
            )}
          </>
        )}
      </div>

      <Separator />

      {/* Limits */}
      <div className="space-y-1.5">
        {Object.entries(plan.limits).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs text-muted-foreground">
            <Check className="h-3 w-3 text-primary shrink-0" />
            {limitLabel(k, v)}
          </div>
        ))}
      </div>

      {/* Features */}
      <div className="space-y-1.5 flex-1">
        {plan.features.map((f) => (
          <div key={f} className="flex items-center gap-2 text-xs">
            <Check className="h-3 w-3 text-primary shrink-0" />
            {FEATURE_LABELS[f] ?? f.replace(/_/g, " ")}
          </div>
        ))}
      </div>

      {/* CTA */}
      <Button
        className={cn("w-full gap-1.5", isPopular && "bg-violet-600 hover:bg-violet-700")}
        onClick={handleChoose}
        disabled={isPending}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isEnterprise ? (
          <>
            Contact Sales <ChevronRight className="h-4 w-4" />
          </>
        ) : (
          <>
            Get Started <ChevronRight className="h-4 w-4" />
          </>
        )}
      </Button>
    </div>
  );
}

// ── FAQ ───────────────────────────────────────────────────────────────────

const FAQ = [
  {
    q: "Is there a free trial?",
    a: "Yes — all paid plans start with a 14-day free trial. No credit card required to start.",
  },
  {
    q: "Can I change plans?",
    a: "Absolutely. You can upgrade or downgrade at any time from your Billing page. Changes take effect immediately, with prorated billing.",
  },
  {
    q: "What happens when I hit a limit?",
    a: "PATHS returns a 402 response for resource-creating actions that exceed your plan limits. Upgrade instantly to unblock.",
  },
  {
    q: "Do you offer annual discounts?",
    a: "Yes — switching to annual billing saves ~2 months compared to monthly pricing.",
  },
  {
    q: "Is my data safe?",
    a: "PATHS is GDPR-compliant. All data is encrypted at rest and in transit. You can export or delete your data at any time.",
  },
];

function FaqSection() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="max-w-2xl mx-auto space-y-2">
      {FAQ.map((item, i) => (
        <div key={i} className="rounded-xl border border-border bg-card overflow-hidden">
          <button
            className="w-full text-left px-5 py-4 flex items-center justify-between text-sm font-medium"
            onClick={() => setOpen(open === i ? null : i)}
          >
            {item.q}
            <ChevronRight
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform",
                open === i && "rotate-90",
              )}
            />
          </button>
          {open === i && (
            <div className="px-5 pb-4 text-xs text-muted-foreground leading-relaxed">
              {item.a}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Page (client) ───────────────────────────────────────────────────────────
// NOTE: this is a Client Component (useState/hooks/toast). Route metadata lives
// in the sibling server `page.tsx`, because Next.js forbids exporting
// `metadata` from a "use client" module.

export default function PricingPage() {
  const [annual, setAnnual] = useState(false);

  // Pull orgId from storage for logged-in users
  const orgId =
    typeof window !== "undefined" ? localStorage.getItem("paths_org") : null;

  const { data: plans, isLoading } = usePublicPlans();
  const displayPlans: Plan[] = (plans as Plan[] | undefined) ?? FALLBACK_PLANS;

  return (
    <div className="flex flex-col items-center gap-16 px-4 py-20">
      {/* Hero */}
      <div className="text-center space-y-4 max-w-2xl">
        <Badge variant="outline" className="text-xs">Pricing</Badge>
        <h1 className="text-4xl font-bold tracking-tight">
          Simple, transparent pricing
        </h1>
        <p className="text-muted-foreground">
          One platform. Every tool your hiring team needs.
          Start free, scale when you&apos;re ready.
        </p>

        {/* Monthly / Annual toggle */}
        <div className="flex items-center justify-center gap-3 pt-2">
          <span className={cn("text-sm", !annual && "font-semibold")}>Monthly</span>
          <button
            onClick={() => setAnnual((v) => !v)}
            className={cn(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
              annual ? "bg-primary" : "bg-muted",
            )}
            role="switch"
            aria-checked={annual}
          >
            <span
              className={cn(
                "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
                annual ? "translate-x-5" : "translate-x-0",
              )}
            />
          </button>
          <span className={cn("text-sm flex items-center gap-1", annual && "font-semibold")}>
            Annual
            <Badge variant="outline" className="text-[10px] text-green-600 border-green-500/30 ml-1">
              Save 15%
            </Badge>
          </span>
        </div>
      </div>

      {/* Plans grid */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading plans…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full">
          {displayPlans.map((plan) => (
            <PricingCard key={plan.id} plan={plan} annual={annual} orgId={orgId} />
          ))}
        </div>
      )}

      {/* Trust strip */}
      <div className="flex flex-wrap justify-center gap-8 text-xs text-muted-foreground">
        <span>✓ 14-day free trial</span>
        <span>✓ No credit card required</span>
        <span>✓ Cancel any time</span>
        <span>✓ GDPR compliant</span>
      </div>

      <Separator className="max-w-4xl w-full" />

      {/* FAQ */}
      <div className="w-full max-w-4xl space-y-6">
        <h2 className="text-2xl font-bold text-center">Frequently Asked Questions</h2>
        <FaqSection />
      </div>
    </div>
  );
}
