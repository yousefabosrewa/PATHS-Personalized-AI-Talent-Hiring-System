"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Upload, FileText, X, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import { candidatePortalApi } from "@/lib/api";
import { cn } from "@/lib/utils/cn";
import type {
  OnboardingDraft,
  ProfileEducation,
  ProfileExperience,
  ProfileSkill,
} from "@/types/candidate-profile.types";

const ACCEPTED = [".pdf", ".doc", ".docx"];
const MAX_MB = 10;

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function inferSkillCategory(name: string): ProfileSkill["category"] {
  const lower = name.toLowerCase();
  if (
    ["python", "javascript", "typescript", "react", "node", "sql", "docker", "aws", "git", "java", "c++", "kubernetes", "ml", "ai"]
      .some((token) => lower.includes(token))
  ) {
    return "technical";
  }
  return "other";
}

function parseYear(value: string | null | undefined): number | null {
  if (!value) return null;
  const m = value.match(/(19|20)\d{2}/);
  return m ? Number(m[0]) : null;
}

type ExtractSummary = { skills: number; experiences: number; education: number; basics: boolean };

export default function CVUploadPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [uploadedDoc, setUploadedDoc] = useState(draft.cvDocument ?? null);
  const [summary, setSummary] = useState<ExtractSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFile = useCallback(async (f: File) => {
    setError(null);
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File too large. Max size is ${MAX_MB} MB.`);
      return;
    }
    setFile(f);
    setUploadState("uploading");

    try {
      const result = await candidatePortalApi.extractMyCV(f);

      // ── Map the extracted data onto the onboarding draft ──
      const patch: Partial<OnboardingDraft> = {};
      if (result.full_name) patch.fullName = result.full_name;
      if (result.current_title) patch.currentTitle = result.current_title;
      if (result.summary) patch.summary = result.summary;
      if (typeof result.years_experience === "number") patch.yearsExperience = result.years_experience;
      if (result.phone) patch.phone = result.phone;
      if (result.location) patch.locationText = result.location;
      // The extracted email becomes an "other" email — the primary stays the
      // sign-up email. The backend drops it on submit if it equals the primary.
      if (result.email) patch.otherEmails = [result.email];

      const skills: ProfileSkill[] = (result.skills ?? [])
        .map((name) => name.trim())
        .filter(Boolean)
        .map((name) => ({
          id: crypto.randomUUID(),
          name,
          category: inferSkillCategory(name),
          proficiency: "intermediate" as const,
        }));
      if (skills.length) patch.skills = skills;

      const experiences: ProfileExperience[] = (result.experiences ?? [])
        .filter((e) => (e.company_name && e.company_name !== "—") || (e.title && e.title !== "—"))
        .map((e) => ({
          id: crypto.randomUUID(),
          companyName: e.company_name ?? "",
          title: e.title ?? "",
          location: "",
          startDate: e.start_date ?? "",
          endDate: e.end_date ?? null,
          isCurrent: !e.end_date,
          description: e.description ?? "",
          achievements: [],
        }));
      if (experiences.length) patch.experiences = experiences;

      const education: ProfileEducation[] = (result.education ?? [])
        .filter((e) => (e.institution && e.institution !== "—") || e.degree)
        .map((e) => ({
          id: crypto.randomUUID(),
          institution: e.institution ?? "",
          degree: e.degree ?? "",
          fieldOfStudy: e.field_of_study ?? "",
          startYear: parseYear(e.start_date),
          endYear: parseYear(e.end_date),
          isOngoing: !e.end_date,
          gpa: "",
          description: "",
        }));
      if (education.length) patch.education = education;

      const doc = {
        id: result.document_id ?? crypto.randomUUID(),
        fileName: f.name,
        fileSize: f.size,
        mimeType: f.type,
        uploadedAt: new Date().toISOString(),
        status: "processed" as const,
      };
      patch.cvDocument = doc;

      updateDraft(patch);
      setUploadedDoc(doc);
      setSummary({
        skills: skills.length,
        experiences: experiences.length,
        education: education.length,
        basics: Boolean(result.full_name || result.summary || result.current_title),
      });
      setUploadState("done");
    } catch (e) {
      setUploadState("error");
      setError(e instanceof Error ? e.message : "CV upload failed.");
    }
  }, [updateDraft]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const clearFile = () => {
    setFile(null);
    setUploadedDoc(null);
    setSummary(null);
    setUploadState("idle");
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const onContinue = async () => {
    setIsSubmitting(true);
    markStepComplete("cv-upload");
    await saveDraft();
    router.push("/onboarding/basic-info");
  };

  const canContinue = uploadState === "done" || !!draft.cvDocument;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 1 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Upload Your CV</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Start here — we read your CV and automatically fill in your basic info, contact, skills,
          experience and education. You&apos;ll review everything in the next steps.
        </p>
      </div>

      <div className="space-y-6">
        {/* Drop zone */}
        {uploadState !== "done" && (
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            onClick={() => uploadState !== "uploading" && inputRef.current?.click()}
            className={cn(
              "relative flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 text-center transition-all",
              isDragging
                ? "border-primary/60 bg-primary/5"
                : "border-border/50 hover:border-primary/40 hover:bg-muted/10",
              uploadState === "uploading" && "pointer-events-none opacity-60",
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPTED.join(",")}
              className="sr-only"
              onChange={onFileChange}
            />
            <div className={cn(
              "flex h-16 w-16 items-center justify-center rounded-2xl transition-colors",
              isDragging ? "bg-primary/15" : "bg-muted/30",
            )}>
              <Upload className={cn("h-7 w-7", isDragging ? "text-primary" : "text-muted-foreground")} />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                {isDragging ? "Drop it here" : "Drag & drop your CV here"}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">or click to browse — PDF, DOC, DOCX · Max {MAX_MB} MB</p>
            </div>
          </div>
        )}

        {/* Uploading / extracting */}
        {uploadState === "uploading" && file && (
          <div className="glass rounded-xl p-4 flex items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
              <p className="text-xs text-muted-foreground">{formatBytes(file.size)} · Reading your CV &amp; extracting details…</p>
            </div>
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
          </div>
        )}

        {/* Done — show what was extracted */}
        {uploadState === "done" && uploadedDoc && (
          <div className="glass gradient-border rounded-xl p-4 space-y-3">
            <div className="flex items-center gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{uploadedDoc.fileName}</p>
                <p className="text-xs text-muted-foreground">Saved to your documents · {formatBytes(uploadedDoc.fileSize)}</p>
              </div>
              <button type="button" onClick={clearFile} className="text-muted-foreground/50 hover:text-destructive transition-colors">
                <X className="h-4 w-4" />
              </button>
            </div>
            {summary && (
              <div className="flex flex-wrap items-center gap-2 border-t border-border/40 pt-3">
                <span className="flex items-center gap-1 text-[11px] font-medium text-primary">
                  <Sparkles className="h-3.5 w-3.5" /> Auto-filled:
                </span>
                {summary.basics && <Chip>Basic info</Chip>}
                {summary.skills > 0 && <Chip>{summary.skills} skills</Chip>}
                {summary.experiences > 0 && <Chip>{summary.experiences} experience{summary.experiences > 1 ? "s" : ""}</Chip>}
                {summary.education > 0 && <Chip>{summary.education} education</Chip>}
                {!summary.basics && summary.skills === 0 && summary.experiences === 0 && summary.education === 0 && (
                  <span className="text-[11px] text-muted-foreground">Couldn&apos;t auto-read much — you can fill it in next.</span>
                )}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground/70">Review and edit everything in the next steps before submitting.</p>
          </div>
        )}

        {/* Prior upload from draft */}
        {uploadState === "idle" && draft.cvDocument && (
          <div className="glass rounded-xl p-4 flex items-center gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
              <FileText className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{draft.cvDocument.fileName}</p>
              <p className="text-xs text-muted-foreground">Previously uploaded · {formatBytes(draft.cvDocument.fileSize)}</p>
            </div>
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive">{error}</p>
        )}

        <p className="text-[11px] text-muted-foreground/60">
          Your CV is stored securely. It is only used to pre-fill your profile and match you to roles. It is never shared without your consent.
        </p>

        {/* Actions — CV upload is the first step, so there is no Back. */}
        <div className="flex items-center justify-end pt-2">
          <div className="flex items-center gap-3">
            {!canContinue && (
              <button
                type="button"
                className="text-xs text-muted-foreground hover:text-foreground underline"
                onClick={onContinue}
              >
                Skip &amp; fill in manually
              </button>
            )}
            <Button
              type="button"
              className="gap-2 glow-blue"
              disabled={isSubmitting || uploadState === "uploading"}
              onClick={onContinue}
            >
              {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <>Review my profile <ArrowRight className="h-4 w-4" /></>}
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/5 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
      {children}
    </span>
  );
}
