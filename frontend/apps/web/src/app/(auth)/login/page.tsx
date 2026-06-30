"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, ArrowRight, Loader2, ShieldCheck, Brain, Users } from "lucide-react";
import { BrandLogo } from "@/components/layout/brand-logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "Password must be at least 6 characters"),
});
type LoginForm = z.infer<typeof loginSchema>;

const features = [
  { icon: Brain, label: "15 AI Agents", sub: "Evidence-driven scoring & ranking" },
  { icon: ShieldCheck, label: "Bias Guardrails", sub: "Anonymization before evaluation" },
  { icon: Users, label: "HITL Approvals", sub: "AI proposes, humans decide" },
];

function LoginForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const { login, isLoading } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);

  // Accept both ?next= (middleware convention) and ?redirectTo= (our intent flow)
  const redirectAfterLogin =
    searchParams.get("next") ?? searchParams.get("redirectTo") ?? null;

  const {
    register, handleSubmit, formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    await login(data.email, data.password);
    const u = useAuthStore.getState().user;

    // 1. Platform admin → /admin. This overrides any ?next=/redirectTo so a
    //    forged redirect can't land them in a non-admin context.
    if (u?.isPlatformAdmin || u?.accountType === "platform_admin") {
      router.push("/admin");
      return;
    }

    // 2. Org member with non-active org status → pending or rejected screen.
    if (u?.accountType === "organization_member") {
      if (u.organizationStatus === "pending_approval") {
        router.push("/pending-approval");
        return;
      }
      if (u.organizationStatus === "rejected" || u.organizationStatus === "suspended") {
        router.push("/rejected");
        return;
      }
    }

    // 3. Honour any pending redirect (e.g. from Apply button or protected route)
    if (redirectAfterLogin) {
      router.push(redirectAfterLogin);
      return;
    }
    if (u?.accountType === "candidate" || u?.role === "candidate") {
      router.push("/candidate/dashboard");
      return;
    }
    router.push("/dashboard");
  };

  return (
    <div className="flex min-h-screen w-full">
      {/* Left — Brand panel */}
      <div className="relative hidden w-[520px] shrink-0 flex-col justify-between overflow-hidden bg-navy-950 p-12 lg:flex">
        {/* Background gradient orbs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-primary/10 blur-[100px]" />
          <div className="absolute -bottom-20 right-0 h-80 w-80 rounded-full bg-teal-glow/8 blur-[80px]" />
          <div className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/5 blur-[60px]" />
        </div>

        {/* Logo */}
        <div className="relative flex items-center">
          <BrandLogo className="h-16 w-auto max-w-[220px]" />
        </div>

        {/* Hero text */}
        <div className="relative space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <h1 className="font-heading text-4xl font-bold leading-tight tracking-tight text-foreground">
              Hire with evidence,<br />
              <span className="gradient-text">not guesswork.</span>
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
              A multi-agent AI system that scores, ranks, and explains every
              hiring decision — traceable to real evidence.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="space-y-3"
          >
            {features.map((f) => (
              <div key={f.label} className="flex items-center gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/8 ring-1 ring-primary/15">
                  <f.icon className="h-3.5 w-3.5 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{f.label}</p>
                  <p className="text-xs text-muted-foreground">{f.sub}</p>
                </div>
              </div>
            ))}
          </motion.div>
        </div>

        {/* Bottom quote */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="relative text-xs text-muted-foreground/60"
        >
          PATHS enforces Egypt PDPL · EU AI Act · EEOC compliance by design.
        </motion.p>
      </div>

      {/* Right — Login form */}
      <div className="flex flex-1 items-center justify-center bg-background p-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <div className="mb-8 flex items-center lg:hidden">
            <BrandLogo className="h-11 w-auto max-w-[160px]" />
          </div>

          <div className="mb-8 space-y-1.5">
            <h2 className="font-heading text-2xl font-bold tracking-tight">Sign in</h2>
            <p className="text-sm text-muted-foreground">Enter your credentials to access your workspace.</p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-medium">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="ahmed@techcorp.io"
                autoComplete="email"
                autoFocus
                {...register("email")}
                className={cn("h-10", errors.email && "border-destructive focus-visible:ring-destructive/30")}
              />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-sm font-medium">Password</Label>
                <button type="button" className="text-xs text-primary hover:underline">Forgot password?</button>
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  {...register("password")}
                  className={cn("h-10 pr-10", errors.password && "border-destructive focus-visible:ring-destructive/30")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>

            <Button type="submit" className="w-full h-10 gap-2 font-semibold" disabled={isLoading}>
              {isLoading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Signing in…</>
              ) : (
                <>Sign in <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>

          {/* Demo hint */}
          <div className="mt-6 rounded-lg border border-border/40 bg-muted/30 p-3">
            <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">Demo credentials</p>
            <p className="text-xs text-muted-foreground">
              Email: <span className="font-mono text-foreground/80">ahmed@techcorp.io</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Password: <span className="font-mono text-foreground/80">any text</span>
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
