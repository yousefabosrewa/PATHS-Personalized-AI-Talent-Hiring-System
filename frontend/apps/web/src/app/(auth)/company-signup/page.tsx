"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye, EyeOff, ArrowRight, Loader2, Building2, Shield, Users, CheckCircle2,
} from "lucide-react";
import { BrandLogo } from "@/components/layout/brand-logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { registerOrganizationApi } from "@/lib/api/auth.api";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";

function slugifyOrganizationSlug(input: string): string {
  const s = input
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return s || "company";
}

const INDUSTRIES = [
  "Technology",
  "Financial Services",
  "Healthcare",
  "Manufacturing",
  "Retail & E-commerce",
  "Education",
  "Professional Services",
  "Government & Public Sector",
  "Energy & Utilities",
  "Other",
];

const COMPANY_SIZES = [
  "1–10",
  "11–50",
  "51–200",
  "201–500",
  "501–1,000",
  "1,000+",
];

const COMPANY_TYPES = [
  "Startup",
  "Private Company (LLC / Ltd)",
  "Public Company (PLC)",
  "Corporation / Enterprise",
  "Sole Proprietorship",
  "Partnership",
  "Non-profit / NGO",
  "Government / Public Sector",
  "Educational Institution",
  "Agency / Consultancy",
  "Freelance / Self-employed",
  "Other",
];

const schema = z
  .object({
    full_name: z.string().min(2, "Full name is required"),
    work_email: z.string().email("Enter a valid work email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string(),
    company_name: z.string().min(2, "Company name is required"),
    organization_slug: z
      .string()
      .min(2, "Slug must be at least 2 characters")
      .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase letters, numbers, and single hyphens only"),
    company_type: z.string().min(1, "Select a company type"),
    company_type_other: z.string().optional(),
    company_website: z.string().optional(),
    job_title: z.string().min(1, "Job title is required"),
    company_size: z.string().min(1, "Select company size"),
    industry: z.string().min(1, "Select an industry"),
    phone: z.string().optional(),
    accept_terms: z
      .boolean()
      .refine((v) => v === true, { message: "You must accept the Terms and Conditions" }),
    confirm_authorized: z
      .boolean()
      .refine((v) => v === true, {
        message: "You must confirm you are authorized to register this company",
      }),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  })
  .refine(
    (d) => d.company_type !== "Other" || Boolean(d.company_type_other?.trim()),
    { message: "Please specify your company type", path: ["company_type_other"] },
  );

type FormValues = z.infer<typeof schema>;

const perks = [
  { icon: Building2, label: "Organization workspace", sub: "Full hiring OS for your team" },
  { icon: Shield, label: "Compliance built in", sub: "PDPL, EEOC, and EU AI Act guardrails" },
  { icon: Users, label: "Human-in-the-loop", sub: "AI proposes; your team decides" },
  { icon: CheckCircle2, label: "org_admin access", sub: "You start with the highest org permission" },
];

export default function CompanySignupPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successPhase, setSuccessPhase] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      organization_slug: "",
      accept_terms: false,
      confirm_authorized: false,
    },
  });

  const companyName = watch("company_name");
  const companyType = watch("company_type");

  useEffect(() => {
    if (!companyName?.trim()) return;
    const slug = getValues("organization_slug");
    if (slug) return;
    setValue("organization_slug", slugifyOrganizationSlug(companyName), { shouldValidate: true });
  }, [companyName, setValue, getValues]);

  const onSubmit = async (data: FormValues) => {
    setIsLoading(true);
    setError(null);
    const website = data.company_website?.trim() || undefined;
    const companyType =
      data.company_type === "Other"
        ? (data.company_type_other?.trim() || "Other")
        : data.company_type;
    const basePayload = {
      organization_name: data.company_name.trim(),
      industry: data.industry,
      organization_email: data.work_email.trim(),
      company_website: website,
      company_size: data.company_size,
      company_type: companyType,
      first_admin_full_name: data.full_name.trim(),
      first_admin_email: data.work_email.trim(),
      first_admin_password: data.password,
      first_admin_job_title: data.job_title.trim(),
      first_admin_phone: data.phone?.trim() || undefined,
      accept_terms: true,
      confirm_authorized: true,
    };

    let slug = data.organization_slug.trim();
    let lastErr: Error | null = null;

    for (let attempt = 0; attempt < 6; attempt++) {
      try {
        await registerOrganizationApi({
          ...basePayload,
          organization_slug: slug,
        });
        lastErr = null;
        break;
      } catch (e) {
        lastErr = e instanceof Error ? e : new Error("Registration failed");
        const msg = lastErr.message.toLowerCase();
        if (msg.includes("slug") && attempt < 5) {
          slug = `${slugifyOrganizationSlug(data.company_name)}-${Math.random().toString(36).slice(2, 6)}`;
          continue;
        }
        setError(lastErr.message);
        setIsLoading(false);
        return;
      }
    }

    if (lastErr) {
      setError(lastErr.message);
      setIsLoading(false);
      return;
    }

    try {
      setSuccessPhase(true);
      await login(data.work_email.trim(), data.password);
      // New companies always start in PENDING_APPROVAL — route to the
      // pending screen so the user knows their request is being reviewed.
      router.replace("/pending-approval");
    } catch (e) {
      setSuccessPhase(false);
      setError(
        e instanceof Error
          ? e.message
          : "Account created but sign-in failed. Please sign in manually.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full">
      <div className="relative hidden w-[480px] shrink-0 flex-col justify-between overflow-hidden bg-navy-950 p-12 lg:flex">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-32 -top-32 h-80 w-80 rounded-full bg-primary/10 blur-[100px]" />
          <div className="absolute -bottom-20 right-0 h-72 w-72 rounded-full bg-teal-glow/8 blur-[80px]" />
        </div>

        <div className="relative">
          <Link href="/" className="flex items-center gap-3">
            <BrandLogo className="h-16 w-auto max-w-[200px]" />
            <span className="border-l border-border/40 pl-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              For Companies
            </span>
          </Link>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="relative space-y-8"
        >
          <div>
            <h1 className="font-heading text-4xl font-bold leading-tight text-foreground">
              Hire with evidence,
              <br />
              <span className="gradient-text">not guesswork.</span>
            </h1>
            <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
              Create your organization on PATHS. You will be assigned the organization admin role for
              your team.
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
          <Link href="/for-companies" className="text-primary hover:underline">← Back to For Companies</Link>
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-navy-950 lg:bg-gradient-to-b lg:from-navy-950 lg:to-background">
        <div className="mx-auto w-full max-w-lg flex-1 px-5 py-10 sm:px-8 sm:py-14">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <BrandLogo className="h-11 w-auto max-w-[150px]" />
            <span className="border-l border-border/40 pl-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Company signup
            </span>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border bg-card p-6 shadow-lg sm:p-8"
          >
            <div className="mb-6 space-y-1">
              <h2 className="font-heading text-2xl font-bold tracking-tight text-foreground">
                Create company account
              </h2>
              <p className="text-sm text-muted-foreground">
                All fields marked required must be completed. You will be able to sign in immediately
                after registration.
              </p>
            </div>

            {successPhase && (
              <div className="mb-4 flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="font-medium text-emerald-100">Company account created successfully.</p>
                  <p className="mt-1 text-xs text-emerald-200/80">Signing you in…</p>
                </div>
              </div>
            )}

            {error && (
              <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="full_name" className="text-sm font-medium">Full name</Label>
                  <Input
                    id="full_name"
                    autoComplete="name"
                    placeholder="Your name"
                    {...register("full_name")}
                    className={cn("h-10 rounded-xl border-border bg-input", errors.full_name && "border-destructive")}
                  />
                  {errors.full_name && (
                    <p className="text-xs text-destructive">{errors.full_name.message}</p>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="work_email" className="text-sm font-medium">Work email</Label>
                  <Input
                    id="work_email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    {...register("work_email")}
                    className={cn("h-10 rounded-xl border-border bg-input", errors.work_email && "border-destructive")}
                  />
                  {errors.work_email && (
                    <p className="text-xs text-destructive">{errors.work_email.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password" className="text-sm font-medium">Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      {...register("password")}
                      className={cn("h-10 rounded-xl border-border bg-input pr-10", errors.password && "border-destructive")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.password && (
                    <p className="text-xs text-destructive">{errors.password.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="confirm_password" className="text-sm font-medium">Confirm password</Label>
                  <div className="relative">
                    <Input
                      id="confirm_password"
                      type={showConfirm ? "text" : "password"}
                      autoComplete="new-password"
                      {...register("confirm_password")}
                      className={cn("h-10 rounded-xl border-border bg-input pr-10", errors.confirm_password && "border-destructive")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  {errors.confirm_password && (
                    <p className="text-xs text-destructive">{errors.confirm_password.message}</p>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="company_name" className="text-sm font-medium">Company name</Label>
                  <Input
                    id="company_name"
                    autoComplete="organization"
                    placeholder="Acme Inc."
                    {...register("company_name")}
                    className={cn("h-10 rounded-xl border-border bg-input", errors.company_name && "border-destructive")}
                  />
                  {errors.company_name && (
                    <p className="text-xs text-destructive">{errors.company_name.message}</p>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="organization_slug" className="text-sm font-medium">
                    Company URL slug
                  </Label>
                  <Input
                    id="organization_slug"
                    placeholder="acme-inc"
                    {...register("organization_slug")}
                    className={cn("h-10 rounded-xl border-border bg-input font-mono text-sm", errors.organization_slug && "border-destructive")}
                  />
                  <p className="text-[11px] text-muted-foreground">Lowercase identifier for your workspace. Auto-filled from the company name; you can edit it.</p>
                  {errors.organization_slug && (
                    <p className="text-xs text-destructive">{errors.organization_slug.message}</p>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="company_type" className="text-sm font-medium">Company type</Label>
                  <select
                    id="company_type"
                    {...register("company_type")}
                    className={cn(
                      "flex h-10 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground",
                      errors.company_type && "border-destructive",
                    )}
                  >
                    <option value="">Select…</option>
                    {COMPANY_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                  {errors.company_type && (
                    <p className="text-xs text-destructive">{errors.company_type.message}</p>
                  )}

                  {/* "Other" → let them type their own company type */}
                  {companyType === "Other" && (
                    <div className="pt-1">
                      <Input
                        id="company_type_other"
                        autoFocus
                        placeholder="Type your company type"
                        {...register("company_type_other")}
                        className={cn(
                          "h-10 rounded-xl border-border bg-input",
                          errors.company_type_other && "border-destructive",
                        )}
                      />
                      {errors.company_type_other && (
                        <p className="mt-1 text-xs text-destructive">{errors.company_type_other.message}</p>
                      )}
                    </div>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="company_website" className="text-sm font-medium">
                    Company website <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="company_website"
                    type="url"
                    placeholder="https://company.com"
                    {...register("company_website")}
                    className="h-10 rounded-xl border-border bg-input"
                  />
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="job_title" className="text-sm font-medium">Your role at the company</Label>
                  <Input
                    id="job_title"
                    placeholder="e.g. Head of Talent"
                    {...register("job_title")}
                    className={cn("h-10 rounded-xl border-border bg-input", errors.job_title && "border-destructive")}
                  />
                  {errors.job_title && (
                    <p className="text-xs text-destructive">{errors.job_title.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="company_size" className="text-sm font-medium">Company size</Label>
                  <select
                    id="company_size"
                    {...register("company_size")}
                    className={cn(
                      "flex h-10 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground",
                      errors.company_size && "border-destructive",
                    )}
                  >
                    <option value="">Select…</option>
                    {COMPANY_SIZES.map((s) => (
                      <option key={s} value={s}>{s} employees</option>
                    ))}
                  </select>
                  {errors.company_size && (
                    <p className="text-xs text-destructive">{errors.company_size.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="industry" className="text-sm font-medium">Industry</Label>
                  <select
                    id="industry"
                    {...register("industry")}
                    className={cn(
                      "flex h-10 w-full rounded-xl border border-border bg-input px-3 text-sm text-foreground",
                      errors.industry && "border-destructive",
                    )}
                  >
                    <option value="">Select…</option>
                    {INDUSTRIES.map((i) => (
                      <option key={i} value={i}>{i}</option>
                    ))}
                  </select>
                  {errors.industry && (
                    <p className="text-xs text-destructive">{errors.industry.message}</p>
                  )}
                </div>

                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="phone" className="text-sm font-medium">
                    Phone <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="phone"
                    type="tel"
                    autoComplete="tel"
                    {...register("phone")}
                    className="h-10 rounded-xl border-border bg-input"
                  />
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <div className="flex items-start gap-2.5">
                  <input
                    id="confirm_authorized"
                    type="checkbox"
                    {...register("confirm_authorized", {
                      setValueAs: (v) => v === true,
                    })}
                    className="mt-1 h-4 w-4 rounded border-border accent-primary"
                  />
                  <label htmlFor="confirm_authorized" className="text-xs leading-relaxed text-muted-foreground">
                    I confirm that I am authorized to create an account for this company and use PATHS
                    services on its behalf.
                  </label>
                </div>
                {errors.confirm_authorized && (
                  <p className="text-xs text-destructive">{errors.confirm_authorized.message}</p>
                )}

                <div className="flex items-start gap-2.5">
                  <input
                    id="accept_terms"
                    type="checkbox"
                    {...register("accept_terms")}
                    className="mt-1 h-4 w-4 rounded border-border accent-primary"
                  />
                  <label htmlFor="accept_terms" className="text-xs leading-relaxed text-muted-foreground">
                    I agree to the{" "}
                    <Link href="#" className="text-primary hover:underline">Terms of Service</Link>
                    {" "}and{" "}
                    <Link href="#" className="text-primary hover:underline">Privacy Policy</Link>
                    .
                  </label>
                </div>
                {errors.accept_terms && (
                  <p className="text-xs text-destructive">{errors.accept_terms.message}</p>
                )}
              </div>

              <Button
                type="submit"
                className="h-11 w-full gap-2 rounded-xl font-semibold glow-blue"
                disabled={isLoading}
              >
                {isLoading ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Please wait…</>
                ) : (
                  <>Create company account <ArrowRight className="h-4 w-4" /></>
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
    </div>
  );
}
