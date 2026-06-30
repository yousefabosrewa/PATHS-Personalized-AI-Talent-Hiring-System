"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  Zap, User, Phone, GraduationCap, Briefcase,
  Code2, Upload, Link2, Settings, CheckCircle2, CheckCircle,
} from "lucide-react";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { ONBOARDING_STEPS } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";
import { useAuthStore } from "@/lib/stores/auth.store";

const stepIcons = {
  "basic-info":  User,
  "contact":     Phone,
  "education":   GraduationCap,
  "experience":  Briefcase,
  "skills":      Code2,
  "cv-upload":   Upload,
  "links":       Link2,
  "preferences": Settings,
  "review":      CheckCircle2,
};

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, _hasHydrated, user } = useAuthStore();
  const { completedSteps, lastSavedAt } = useOnboardingStore();

  const isCandidateSession =
    user?.accountType === "candidate" || user?.role === "candidate";

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!isCandidateSession) {
      router.replace("/dashboard");
    }
  }, [_hasHydrated, isAuthenticated, isCandidateSession, router]);

  const currentIndex = ONBOARDING_STEPS.findIndex((s) => pathname.includes(s.key));
  const progressPct = currentIndex >= 0 ? Math.round(((currentIndex) / ONBOARDING_STEPS.length) * 100) : 0;

  if (!_hasHydrated || !isAuthenticated || !isCandidateSession) {
    return null;
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-72 shrink-0 flex-col border-r border-border/40 bg-navy-950 lg:flex">
        {/* Logo */}
        <div className="flex items-center gap-2.5 border-b border-border/40 p-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/15 ring-1 ring-primary/30">
              <Zap className="h-4 w-4 text-primary" />
            </div>
            <div>
              <p className="font-heading text-sm font-bold text-foreground">PATHS</p>
              <p className="text-[10px] text-muted-foreground">Candidate Onboarding</p>
            </div>
          </Link>
        </div>

        {/* Steps */}
        <div className="flex-1 overflow-y-auto p-4">
          <p className="mb-4 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/50">
            Your Profile Steps
          </p>
          <div className="space-y-1">
            {ONBOARDING_STEPS.map((step, i) => {
              const Icon = stepIcons[step.key] ?? User;
              const isCompleted = completedSteps.has(step.key);
              const isCurrent = pathname.includes(step.key);
              const isReachable = i === 0 || completedSteps.has(ONBOARDING_STEPS[i - 1].key) || isCompleted;

              return (
                <div key={step.key} className="relative">
                  {/* Connector line */}
                  {i < ONBOARDING_STEPS.length - 1 && (
                    <div className={cn(
                      "absolute left-[22px] top-10 h-6 w-px",
                      isCompleted ? "bg-primary/40" : "bg-border/40"
                    )} />
                  )}

                  <Link
                    href={isReachable ? `/onboarding/${step.key}` : "#"}
                    className={cn(
                      "flex items-start gap-3 rounded-xl px-3 py-2.5 transition-all",
                      isCurrent && "bg-primary/10",
                      !isCurrent && isReachable && "hover:bg-muted/30",
                      !isReachable && "opacity-40 cursor-not-allowed pointer-events-none"
                    )}
                  >
                    <div className={cn(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ring-1",
                      isCompleted && "bg-primary/20 ring-primary/40 text-primary",
                      isCurrent && !isCompleted && "bg-primary/15 ring-primary/30 text-primary",
                      !isCurrent && !isCompleted && "bg-muted/30 ring-border/50 text-muted-foreground"
                    )}>
                      {isCompleted ? <CheckCircle className="h-3.5 w-3.5" /> : <Icon className="h-3.5 w-3.5" />}
                    </div>
                    <div className="min-w-0">
                      <p className={cn(
                        "text-[13px] font-medium",
                        isCurrent ? "text-primary" : isCompleted ? "text-foreground" : "text-muted-foreground"
                      )}>
                        {step.label}
                      </p>
                      <p className="text-[11px] text-muted-foreground/60 truncate">{step.description}</p>
                    </div>
                  </Link>
                </div>
              );
            })}
          </div>
        </div>

        {/* Save indicator */}
        {lastSavedAt && (
          <div className="border-t border-border/40 p-4">
            <p className="text-[11px] text-muted-foreground/60">
              Progress saved · {new Date(lastSavedAt).toLocaleTimeString()}
            </p>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        {/* Mobile top bar */}
        <div className="flex items-center justify-between border-b border-border/40 bg-background/80 px-4 py-3 lg:hidden">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15">
              <Zap className="h-3.5 w-3.5 text-primary" />
            </div>
            <span className="font-heading text-sm font-bold">PATHS</span>
          </Link>
          <div className="text-right">
            <p className="text-[11px] font-medium text-muted-foreground">
              Step {Math.max(currentIndex + 1, 1)} of {ONBOARDING_STEPS.length}
            </p>
            <p className="text-[10px] text-muted-foreground/60">
              {currentIndex >= 0 ? ONBOARDING_STEPS[currentIndex].label : ""}
            </p>
          </div>
        </div>

        {/* Mobile progress bar */}
        <div className="h-1 w-full bg-muted/30 lg:hidden">
          <div
            className="h-full bg-primary transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
