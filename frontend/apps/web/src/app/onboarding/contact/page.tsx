"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft, ArrowRight, Loader2, Mail, Plus, X, ShieldCheck, Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";

const schema = z.object({
  phone:           z.string().optional(),
  locationCity:    z.string().min(1, "City is required"),
  locationCountry: z.string().min(1, "Country is required"),
  locationText:    z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ContactPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();
  const primaryEmail = useAuthStore((s) => s.user?.email) ?? draft.email ?? "";

  // "Other email addresses" — managed as a dynamic list (always show ≥1 input).
  const [otherEmails, setOtherEmails] = useState<string[]>(
    draft.otherEmails && draft.otherEmails.length > 0 ? [...draft.otherEmails] : [""],
  );
  const [emailError, setEmailError] = useState<string | null>(null);

  const setEmailAt = (i: number, v: string) =>
    setOtherEmails((arr) => arr.map((e, idx) => (idx === i ? v : e)));
  const addEmail = () => setOtherEmails((arr) => [...arr, ""]);
  const removeEmail = (i: number) =>
    setOtherEmails((arr) => (arr.length <= 1 ? [""] : arr.filter((_, idx) => idx !== i)));

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      phone:           draft.phone           ?? "",
      locationCity:    draft.locationCity    ?? "",
      locationCountry: draft.locationCountry ?? "",
      locationText:    draft.locationText    ?? "",
    },
  });

  const city    = watch("locationCity");
  const country = watch("locationCountry");

  const onSubmit = async (data: FormValues) => {
    // Clean + validate the additional emails.
    const cleaned: string[] = [];
    const seen = new Set<string>();
    for (const raw of otherEmails) {
      const e = raw.trim().toLowerCase();
      if (!e) continue;
      if (!EMAIL_RE.test(e)) {
        setEmailError(`"${raw.trim()}" is not a valid email address.`);
        return;
      }
      if (e === primaryEmail.trim().toLowerCase()) {
        setEmailError("That's already your primary email — add a different one.");
        return;
      }
      if (seen.has(e)) continue;
      seen.add(e);
      cleaned.push(e);
    }
    setEmailError(null);

    const locationText = [data.locationCity, data.locationCountry].filter(Boolean).join(", ");
    updateDraft({ ...data, otherEmails: cleaned, locationText });
    markStepComplete("contact");
    await saveDraft();
    router.push("/onboarding/skills");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 3 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Contact Information</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          How can recruiters reach you? Your location is required.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Primary email — read-only, comes from sign-up */}
        <div className="space-y-1.5">
          <Label className="text-sm font-medium">Primary email</Label>
          <div className="flex h-11 items-center gap-2 rounded-md border border-border bg-muted/30 px-3">
            <Mail className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate text-sm text-foreground">{primaryEmail || "—"}</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              <Lock className="h-3 w-3" /> used to sign in
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground/60">
            This is the email you signed up with. It stays your main address.
          </p>
        </div>

        {/* Other email addresses — additional, optional, multiple */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">
            Other email addresses <span className="text-muted-foreground/60">(optional)</span>
          </Label>
          <div className="space-y-2">
            {otherEmails.map((val, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                  <Input
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    placeholder="you@another-domain.com"
                    value={val}
                    onChange={(e) => setEmailAt(i, e.target.value)}
                    className="h-11 pl-10"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removeEmail(i)}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="Remove"
                  aria-label="Remove email"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          {emailError && <p className="text-xs text-destructive">{emailError}</p>}
          <button
            type="button"
            onClick={addEmail}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" /> Add another email
          </button>

          {/* Why we ask — communication + GitHub/LinkedIn verification */}
          <div className="mt-2 flex items-start gap-2 rounded-lg border border-primary/15 bg-primary/5 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              Add any other emails you use — including the ones linked to your{" "}
              <span className="font-medium text-foreground">GitHub</span> and{" "}
              <span className="font-medium text-foreground">LinkedIn</span>. We use them to reach
              you and to confirm those profiles really belong to you.
            </p>
          </div>
        </div>

        {/* Phone */}
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
            className="h-11"
          />
        </div>

        {/* City + Country */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="locationCity" className="text-sm font-medium">City</Label>
            <Input
              id="locationCity"
              placeholder="Cairo"
              {...register("locationCity")}
              className={cn("h-11", errors.locationCity && "border-destructive")}
            />
            {errors.locationCity && <p className="text-xs text-destructive">{errors.locationCity.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="locationCountry" className="text-sm font-medium">Country</Label>
            <Input
              id="locationCountry"
              placeholder="Egypt"
              {...register("locationCountry")}
              className={cn("h-11", errors.locationCountry && "border-destructive")}
            />
            {errors.locationCountry && <p className="text-xs text-destructive">{errors.locationCountry.message}</p>}
          </div>
        </div>

        {(city || country) && (
          <p className="text-[12px] text-muted-foreground">
            Your location will appear as: <span className="font-medium text-foreground">{[city, country].filter(Boolean).join(", ")}</span>
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/basic-info")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button type="submit" className="gap-2 glow-blue" disabled={isSubmitting}>
            {isSubmitting ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
            ) : (
              <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>
            )}
          </Button>
        </div>
      </form>
    </motion.div>
  );
}
