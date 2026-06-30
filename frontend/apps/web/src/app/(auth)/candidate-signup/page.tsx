"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye, EyeOff, ArrowRight, Loader2, Shield, Brain, Users, CheckCircle2,
} from "lucide-react";
import { BrandLogo } from "@/components/layout/brand-logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { candidatePortalApi } from "@/lib/api/candidate-portal.api";
import { useAuthStore } from "@/lib/stores/auth.store";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { cn } from "@/lib/utils/cn";

const schema = z
  .object({
    full_name: z.string().min(2, "Full name must be at least 2 characters"),
    email: z.string().email("Enter a valid email address"),
    phone: z.string().optional(),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
    agreed: z.literal(true, { error: () => ({ message: "You must agree to the terms" }) }),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type SignupForm = z.infer<typeof schema>;

const perks = [
  { icon: Brain,        label: "AI-matched to jobs",       sub: "Smart matching based on your real skills" },
  { icon: Shield,       label: "Anonymous screening",      sub: "Evaluated on merit, not identity" },
  { icon: Users,        label: "Human final decisions",    sub: "Always reviewed by a real person" },
  { icon: CheckCircle2, label: "Transparent scores",       sub: "See exactly why you ranked where you did" },
];

function CandidateSignupForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const login        = useAuthStore((s) => s.login);

  // Preserve the job/page the candidate was trying to reach before signup
  const redirectTo = searchParams.get("redirectTo") ?? null;

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm]   = useState(false);
  const [isLoading, setIsLoading]       = useState(false);
  const [error, setError]               = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupForm>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: SignupForm) => {
    setIsLoading(true);
    setError(null);
    try {
      await candidatePortalApi.signup({
        full_name: data.full_name,
        email:     data.email,
        password:  data.password,
        phone:     data.phone || undefined,
      });
      await login(data.email, data.password);

      // A brand-new account always starts onboarding clean. Without this, a
      // previous/abandoned session's in-memory draft (basic info, contact,
      // even a phantom uploaded CV) would leak into this fresh sign-up.
      useOnboardingStore.getState().reset();

      // Pass the intent through onboarding so it's preserved after completion.
      // CV upload is the first step — it auto-fills the rest of the profile.
      const onboardingUrl = redirectTo
        ? `/onboarding/cv-upload?redirectTo=${encodeURIComponent(redirectTo)}`
        : "/onboarding/cv-upload";
      router.push(onboardingUrl);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full">
      {/* Left — brand panel */}
      <div className="relative hidden w-[500px] shrink-0 flex-col justify-between overflow-hidden bg-navy-950 p-12 lg:flex">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-32 -top-32 h-80 w-80 rounded-full bg-primary/10 blur-[100px]" />
          <div className="absolute -bottom-20 right-0 h-72 w-72 rounded-full bg-teal-glow/8 blur-[80px]" />
        </div>

        <div className="relative">
          <Link href="/" className="flex items-center">
            <BrandLogo className="h-16 w-auto max-w-[220px]" />
          </Link>
        </div>

        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="relative space-y-8">
          <div>
            <h1 className="font-heading text-4xl font-bold leading-tight text-foreground">
              Your skills,<br />
              <span className="gradient-text">fairly evaluated.</span>
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
              Build one profile. Get matched to multiple roles. Know exactly where you stand — with evidence.
            </p>
          </div>

          <div className="space-y-4">
            {perks.map((p) => (
              <div key={p.label} className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/8 ring-1 ring-primary/15">
                  <p.icon className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{p.label}</p>
                  <p className="text-xs text-muted-foreground">{p.sub}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <p className="relative text-xs text-muted-foreground/50">
          Free for candidates · Egypt PDPL compliant · Data never sold
        </p>
      </div>

      {/* Right — signup form */}
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

          <div className="mb-7 space-y-1.5">
            <h2 className="font-heading text-2xl font-bold tracking-tight">Create your profile</h2>
            <p className="text-sm text-muted-foreground">Free for candidates. No credit card required.</p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Full name */}
            <div className="space-y-1.5">
              <Label htmlFor="full_name" className="text-sm font-medium">Full Name</Label>
              <Input
                id="full_name"
                placeholder="Your full name"
                autoComplete="name"
                autoFocus
                {...register("full_name")}
                className={cn("h-10", errors.full_name && "border-destructive")}
              />
              {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-sm font-medium">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="sara@example.com"
                autoComplete="email"
                {...register("email")}
                className={cn("h-10", errors.email && "border-destructive")}
              />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>

            {/* Phone (optional) */}
            <div className="space-y-1.5">
              <Label htmlFor="phone" className="text-sm font-medium">
                Phone <span className="text-muted-foreground/60">(optional)</span>
              </Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+20 100 000 0000"
                autoComplete="tel"
                {...register("phone")}
                className="h-10"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-sm font-medium">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Min 8 characters"
                  autoComplete="new-password"
                  {...register("password")}
                  className={cn("h-10 pr-10", errors.password && "border-destructive")}
                />
                <button type="button" onClick={() => setShowPassword((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground">
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>

            {/* Confirm password */}
            <div className="space-y-1.5">
              <Label htmlFor="confirm_password" className="text-sm font-medium">Confirm Password</Label>
              <div className="relative">
                <Input
                  id="confirm_password"
                  type={showConfirm ? "text" : "password"}
                  placeholder="Re-enter password"
                  autoComplete="new-password"
                  {...register("confirm_password")}
                  className={cn("h-10 pr-10", errors.confirm_password && "border-destructive")}
                />
                <button type="button" onClick={() => setShowConfirm((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/60 hover:text-muted-foreground">
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirm_password && <p className="text-xs text-destructive">{errors.confirm_password.message}</p>}
            </div>

            {/* Terms */}
            <div className="flex items-start gap-2.5">
              <input
                id="agreed"
                type="checkbox"
                {...register("agreed")}
                className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
              />
              <label htmlFor="agreed" className="text-xs text-muted-foreground leading-relaxed">
                I agree to the{" "}
                <Link href="#" className="text-primary hover:underline">Terms of Service</Link>
                {" "}and{" "}
                <Link href="#" className="text-primary hover:underline">Privacy Policy</Link>
              </label>
            </div>
            {errors.agreed && <p className="text-xs text-destructive">{errors.agreed.message}</p>}

            <Button type="submit" className="w-full h-10 gap-2 font-semibold glow-blue" disabled={isLoading}>
              {isLoading ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Creating profile…</>
              ) : (
                <>Create Profile <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

export default function CandidateSignupPage() {
  return (
    <Suspense>
      <CandidateSignupForm />
    </Suspense>
  );
}
