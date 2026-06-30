"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, Loader2, Globe, Link2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { cn } from "@/lib/utils/cn";

const urlOrEmpty = z
  .string()
  .optional()
  .refine((v) => !v || /^https?:\/\/.+/.test(v), { message: "Must start with https://" });

const schema = z.object({
  linkedin:  urlOrEmpty,
  github:    urlOrEmpty,
  portfolio: urlOrEmpty,
  website:   urlOrEmpty,
  twitter:   urlOrEmpty,
});

type FormValues = z.infer<typeof schema>;

const fields: { key: keyof FormValues; label: string; placeholder: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "linkedin",  label: "LinkedIn",          placeholder: "https://linkedin.com/in/your-profile", Icon: ExternalLink },
  { key: "github",    label: "GitHub",            placeholder: "https://github.com/yourusername",       Icon: ExternalLink },
  { key: "portfolio", label: "Portfolio",         placeholder: "https://yourportfolio.com",             Icon: Globe     },
  { key: "website",   label: "Personal Website",  placeholder: "https://yourwebsite.com",               Icon: Globe     },
  { key: "twitter",   label: "Twitter / X",       placeholder: "https://x.com/yourhandle",              Icon: Link2     },
];

export default function LinksPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      linkedin:  draft.links?.linkedin  ?? "",
      github:    draft.links?.github    ?? "",
      portfolio: draft.links?.portfolio ?? "",
      website:   draft.links?.website   ?? "",
      twitter:   draft.links?.twitter   ?? "",
    },
  });

  const onSubmit = async (data: FormValues) => {
    const links = Object.fromEntries(
      Object.entries(data).filter(([, v]) => v && v.length > 0)
    );
    updateDraft({ links });
    markStepComplete("links");
    await saveDraft();
    router.push("/onboarding/preferences");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 7 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Professional Links</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Add links to your online presence. All fields are optional — add what&apos;s relevant.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
        {fields.map(({ key, label, placeholder, Icon }) => (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={key} className="text-sm font-medium">{label}</Label>
            <div className="relative">
              <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">
                <Icon className="h-4 w-4" />
              </div>
              <Input
                id={key}
                type="url"
                placeholder={placeholder}
                {...register(key)}
                className={cn("h-11 pl-10", errors[key] && "border-destructive")}
              />
            </div>
            {errors[key] && <p className="text-xs text-destructive">{errors[key]?.message}</p>}
          </div>
        ))}

        <p className="text-[11px] text-muted-foreground/60 pt-1">
          GitHub and portfolio links help our AI agents verify your skills with evidence from real projects.
        </p>
        <p className="text-[11px] text-muted-foreground/60">
          To confirm these GitHub &amp; LinkedIn profiles are yours, make sure the emails on those
          accounts are listed under <span className="font-medium text-foreground">Other email addresses</span> in
          the Contact step.
        </p>

        <div className="flex items-center justify-between pt-4">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/education")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button type="submit" className="gap-2 glow-blue" disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>}
          </Button>
        </div>
      </form>
    </motion.div>
  );
}
