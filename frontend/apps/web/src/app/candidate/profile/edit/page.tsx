"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowLeft, Save, Loader2, CheckCircle2, Plus, X, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCandidateProfile, useUpdateCandidateProfile } from "@/lib/hooks";
import { createEmptyCandidateProfile } from "@/lib/candidate/portal-profile";
import type { CareerLevel } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";

type Tab = "basic" | "contact" | "skills" | "experience" | "education" | "links" | "preferences";

const TABS: { key: Tab; label: string }[] = [
  { key: "basic",       label: "Basic Info"  },
  { key: "contact",     label: "Contact"     },
  { key: "skills",      label: "Skills"      },
  { key: "experience",  label: "Experience"  },
  { key: "education",   label: "Education"   },
  { key: "links",       label: "Links"       },
  { key: "preferences", label: "Preferences" },
];

const JOB_TYPES = ["full_time", "part_time", "contract", "freelance", "internship"] as const;
const WORKPLACE_TYPES = ["remote", "hybrid", "onsite"] as const;

type ExperienceRow = {
  id: string;
  companyName: string;
  title: string;
  startDate: string;
  endDate: string;
  isCurrent: boolean;
  description: string;
};
type EducationRow = {
  id: string;
  institution: string;
  degree: string;
  fieldOfStudy: string;
  startYear: string;
  endYear: string;
  isOngoing: boolean;
};

function newId(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `tmp-${Math.random().toString(36).slice(2)}`;
}

const textareaCls =
  "flex w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const selectCls =
  "h-11 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

// ── Reusable add/remove string-list editor (skills, desired roles) ──────────
function StringListEditor({
  label,
  placeholder,
  hint,
  items,
  onChange,
}: {
  label: string;
  placeholder: string;
  hint?: string;
  items: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    if (items.some((i) => i.toLowerCase() === v.toLowerCase())) {
      setDraft("");
      return;
    }
    onChange([...items, v]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">{label}</Label>
      <div className="flex gap-2">
        <Input
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          className="h-10"
        />
        <Button type="button" variant="outline" size="sm" className="shrink-0 gap-1" onClick={add}>
          <Plus className="h-3.5 w-3.5" /> Add
        </Button>
      </div>
      {items.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {items.map((item) => (
            <span
              key={item}
              className="flex items-center gap-1 rounded-full border border-border/50 bg-muted/30 px-2.5 py-1 text-xs"
            >
              {item}
              <button
                type="button"
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="text-muted-foreground/60 hover:text-destructive"
                aria-label={`Remove ${item}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {hint && <p className="text-[11px] text-muted-foreground/60">{hint}</p>}
    </div>
  );
}

export default function EditProfilePage() {
  const { data: profile = createEmptyCandidateProfile() } = useCandidateProfile();
  const updateProfile = useUpdateCandidateProfile();
  const [tab, setTab] = useState<Tab>("basic");
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [form, setForm] = useState({
    fullName: "",
    currentTitle: "",
    summary: "",
    careerLevel: "mid" as CareerLevel,
    yearsExperience: 0,
    email: "",
    phone: "",
    location: "",
    linkedin: "",
    github: "",
    portfolio: "",
    website: "",
  });
  const [skills, setSkills] = useState<string[]>([]);
  const [experiences, setExperiences] = useState<ExperienceRow[]>([]);
  const [education, setEducation] = useState<EducationRow[]>([]);
  const [jobTypes, setJobTypes] = useState<string[]>([]);
  const [workplaceTypes, setWorkplaceTypes] = useState<string[]>([]);
  const [desiredRoles, setDesiredRoles] = useState<string[]>([]);

  // Hydrate every section from the loaded profile.
  useEffect(() => {
    if (!profile.id) return;
    setForm({
      fullName: profile.fullName,
      currentTitle: profile.currentTitle,
      summary: profile.summary,
      careerLevel: profile.careerLevel,
      yearsExperience: profile.yearsExperience,
      email: profile.email,
      phone: profile.phone ?? "",
      location: profile.locationText ?? "",
      linkedin: profile.links.linkedin ?? "",
      github: profile.links.github ?? "",
      portfolio: profile.links.portfolio ?? "",
      website: profile.links.website ?? "",
    });
    setSkills(profile.skills.map((s) => s.name));
    setExperiences(
      profile.experiences.map((x) => ({
        id: x.id || newId(),
        companyName: x.companyName,
        title: x.title,
        startDate: x.startDate ?? "",
        endDate: x.endDate ?? "",
        isCurrent: x.isCurrent,
        description: x.description ?? "",
      })),
    );
    setEducation(
      profile.education.map((e) => ({
        id: e.id || newId(),
        institution: e.institution,
        degree: e.degree,
        fieldOfStudy: e.fieldOfStudy,
        startYear: e.startYear != null ? String(e.startYear) : "",
        endYear: e.endYear != null ? String(e.endYear) : "",
        isOngoing: e.isOngoing,
      })),
    );
    setJobTypes(profile.preferences.jobTypes);
    setWorkplaceTypes(profile.preferences.workplaceTypes);
    setDesiredRoles(profile.preferences.desiredRoles);
  }, [profile]);

  const update = (key: keyof typeof form, value: string | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  // ── Experience helpers ────────────────────────────────────────────────────
  const addExperience = () =>
    setExperiences((p) => [
      ...p,
      { id: newId(), companyName: "", title: "", startDate: "", endDate: "", isCurrent: false, description: "" },
    ]);
  const patchExperience = (id: string, patch: Partial<ExperienceRow>) =>
    setExperiences((p) => p.map((x) => (x.id === id ? { ...x, ...patch } : x)));
  const removeExperience = (id: string) =>
    setExperiences((p) => p.filter((x) => x.id !== id));

  // ── Education helpers ─────────────────────────────────────────────────────
  const addEducation = () =>
    setEducation((p) => [
      ...p,
      { id: newId(), institution: "", degree: "", fieldOfStudy: "", startYear: "", endYear: "", isOngoing: false },
    ]);
  const patchEducation = (id: string, patch: Partial<EducationRow>) =>
    setEducation((p) => p.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  const removeEducation = (id: string) =>
    setEducation((p) => p.filter((e) => e.id !== id));

  const handleSave = async () => {
    if (!profile.id) {
      toast.error("Profile still loading — please wait a moment and try again.");
      return;
    }
    setIsSaving(true);
    try {
      // Links — preserve twitter / "other" links not editable on this form.
      const links: { link_type: string; url: string; label?: string }[] = [];
      for (const [type, url] of [
        ["linkedin", form.linkedin],
        ["github", form.github],
        ["portfolio", form.portfolio],
        ["website", form.website],
      ] as const) {
        if (url.trim()) links.push({ link_type: type, url: url.trim() });
      }
      if (profile.links.twitter?.trim()) {
        links.push({ link_type: "twitter", url: profile.links.twitter.trim() });
      }
      for (const other of profile.links.other ?? []) {
        if (other.url?.trim()) {
          links.push({ link_type: "other", url: other.url.trim(), label: other.label });
        }
      }

      await updateProfile.mutateAsync({
        full_name: form.fullName.trim(),
        current_title: form.currentTitle.trim(),
        summary: form.summary.trim(),
        location: form.location.trim(),
        phone: form.phone.trim() || undefined,
        years_experience: Number(form.yearsExperience) || 0,
        career_level: form.careerLevel,
        links,
        skills: skills.map((s) => s.trim()).filter(Boolean),
        open_to_job_types: jobTypes,
        open_to_workplace_settings: workplaceTypes,
        desired_job_titles: desiredRoles,
        education: education
          .filter((e) => e.institution.trim())
          .map((e) => ({
            institution: e.institution.trim(),
            degree: e.degree.trim() || undefined,
            field_of_study: e.fieldOfStudy.trim() || undefined,
            start_date: e.startYear.trim() || undefined,
            end_date: e.isOngoing ? undefined : e.endYear.trim() || undefined,
          })),
        experiences: experiences
          .filter((x) => x.companyName.trim() && x.title.trim())
          .map((x) => ({
            company_name: x.companyName.trim(),
            title: x.title.trim(),
            start_date: x.startDate.trim() || undefined,
            end_date: x.isCurrent ? undefined : x.endDate.trim() || undefined,
            description: x.description.trim() || undefined,
          })),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      toast.success("Profile saved");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save profile. Please try again.",
      );
    }
    setIsSaving(false);
  };

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 flex items-center gap-4"
        >
          <Link
            href="/candidate/profile"
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </Link>
          <div className="flex-1">
            <h1 className="font-heading text-2xl font-bold text-foreground">Edit Profile</h1>
          </div>
          <Button className="gap-2 glow-blue" disabled={isSaving} onClick={handleSave}>
            {isSaving ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
            ) : saved ? (
              <><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Saved</>
            ) : (
              <><Save className="h-4 w-4" /> Save Changes</>
            )}
          </Button>
        </motion.div>

        {/* Tabs */}
        <div className="mb-6 flex flex-wrap gap-1 rounded-xl bg-muted/20 p-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "rounded-lg px-3 py-2 text-xs font-semibold transition-all",
                tab === t.key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        <motion.div key={tab} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }}>
          {/* ── Basic Info ───────────────────────────────────────────────── */}
          {tab === "basic" && (
            <div className="space-y-5">
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">Full Name</Label>
                <Input value={form.fullName} onChange={(e) => update("fullName", e.target.value)} className="h-11" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">Current Title</Label>
                <Input value={form.currentTitle} onChange={(e) => update("currentTitle", e.target.value)} className="h-11" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">Career Level</Label>
                  <select
                    value={form.careerLevel}
                    onChange={(e) => update("careerLevel", e.target.value)}
                    className={selectCls}
                  >
                    {["junior", "mid", "senior", "lead", "manager", "director", "executive"].map((l) => (
                      <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">Years of Experience</Label>
                  <Input
                    type="number"
                    min={0}
                    max={50}
                    value={form.yearsExperience}
                    onChange={(e) => update("yearsExperience", Number(e.target.value))}
                    className="h-11"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">Professional Summary</Label>
                <textarea
                  rows={5}
                  value={form.summary}
                  onChange={(e) => update("summary", e.target.value)}
                  className={cn(textareaCls, "min-h-[120px]")}
                />
              </div>
            </div>
          )}

          {/* ── Contact ──────────────────────────────────────────────────── */}
          {tab === "contact" && (
            <div className="space-y-5">
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">
                  Email Address <span className="text-muted-foreground/60">(read-only)</span>
                </Label>
                <Input type="email" value={form.email} disabled className="h-11" />
                <p className="text-[11px] text-muted-foreground/60">
                  Your email is linked to your account and can&apos;t be changed here.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">
                  Phone <span className="text-muted-foreground/60">(optional)</span>
                </Label>
                <Input type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)} className="h-11" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-medium">Location</Label>
                <Input
                  value={form.location}
                  onChange={(e) => update("location", e.target.value)}
                  placeholder="e.g. Cairo, Egypt"
                  className="h-11"
                />
              </div>
            </div>
          )}

          {/* ── Skills ───────────────────────────────────────────────────── */}
          {tab === "skills" && (
            <div className="space-y-5">
              <StringListEditor
                label="Skills"
                placeholder="e.g. Python, FastAPI, PostgreSQL…"
                hint="Skills power your Learning Hub recommendations and job match scores."
                items={skills}
                onChange={setSkills}
              />
            </div>
          )}

          {/* ── Experience ───────────────────────────────────────────────── */}
          {tab === "experience" && (
            <div className="space-y-4">
              {experiences.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No experience added yet. Add your work history below.
                </p>
              )}
              {experiences.map((exp) => (
                <div key={exp.id} className="rounded-xl border border-border/50 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Experience
                    </p>
                    <button
                      type="button"
                      onClick={() => removeExperience(exp.id)}
                      className="text-muted-foreground/50 hover:text-destructive"
                      aria-label="Remove experience"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Job Title</Label>
                      <Input value={exp.title} onChange={(e) => patchExperience(exp.id, { title: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Company</Label>
                      <Input value={exp.companyName} onChange={(e) => patchExperience(exp.id, { companyName: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Start (YYYY-MM)</Label>
                      <Input value={exp.startDate} placeholder="2022-01" onChange={(e) => patchExperience(exp.id, { startDate: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">End (YYYY-MM)</Label>
                      <Input
                        value={exp.endDate}
                        placeholder="2024-06"
                        disabled={exp.isCurrent}
                        onChange={(e) => patchExperience(exp.id, { endDate: e.target.value })}
                        className="h-10"
                      />
                    </div>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={exp.isCurrent}
                      onChange={(e) => patchExperience(exp.id, { isCurrent: e.target.checked })}
                      className="accent-primary"
                    />
                    I currently work here
                  </label>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Description</Label>
                    <textarea
                      rows={3}
                      value={exp.description}
                      onChange={(e) => patchExperience(exp.id, { description: e.target.value })}
                      className={textareaCls}
                    />
                  </div>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" className="gap-1.5" onClick={addExperience}>
                <Plus className="h-3.5 w-3.5" /> Add Experience
              </Button>
            </div>
          )}

          {/* ── Education ────────────────────────────────────────────────── */}
          {tab === "education" && (
            <div className="space-y-4">
              {education.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No education added yet. Add your degrees below.
                </p>
              )}
              {education.map((edu) => (
                <div key={edu.id} className="rounded-xl border border-border/50 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Education
                    </p>
                    <button
                      type="button"
                      onClick={() => removeEducation(edu.id)}
                      className="text-muted-foreground/50 hover:text-destructive"
                      aria-label="Remove education"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Institution / University</Label>
                    <Input value={edu.institution} onChange={(e) => patchEducation(edu.id, { institution: e.target.value })} className="h-10" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Degree</Label>
                      <Input value={edu.degree} placeholder="B.Sc." onChange={(e) => patchEducation(edu.id, { degree: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Field of Study</Label>
                      <Input value={edu.fieldOfStudy} placeholder="Computer Science" onChange={(e) => patchEducation(edu.id, { fieldOfStudy: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Start Year</Label>
                      <Input value={edu.startYear} placeholder="2019" onChange={(e) => patchEducation(edu.id, { startYear: e.target.value })} className="h-10" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">End Year</Label>
                      <Input
                        value={edu.endYear}
                        placeholder="2023"
                        disabled={edu.isOngoing}
                        onChange={(e) => patchEducation(edu.id, { endYear: e.target.value })}
                        className="h-10"
                      />
                    </div>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={edu.isOngoing}
                      onChange={(e) => patchEducation(edu.id, { isOngoing: e.target.checked })}
                      className="accent-primary"
                    />
                    Currently studying here
                  </label>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" className="gap-1.5" onClick={addEducation}>
                <Plus className="h-3.5 w-3.5" /> Add Education
              </Button>
            </div>
          )}

          {/* ── Links ────────────────────────────────────────────────────── */}
          {tab === "links" && (
            <div className="space-y-5">
              {[
                { key: "linkedin",  label: "LinkedIn",         placeholder: "https://linkedin.com/in/…" },
                { key: "github",    label: "GitHub",           placeholder: "https://github.com/…" },
                { key: "portfolio", label: "Portfolio",        placeholder: "https://yourportfolio.com" },
                { key: "website",   label: "Personal Website", placeholder: "https://yoursite.com" },
              ].map(({ key, label, placeholder }) => (
                <div key={key} className="space-y-1.5">
                  <Label className="text-sm font-medium">{label}</Label>
                  <Input
                    type="url"
                    placeholder={placeholder}
                    value={form[key as keyof typeof form] as string}
                    onChange={(e) => update(key as keyof typeof form, e.target.value)}
                    className="h-11"
                  />
                </div>
              ))}
            </div>
          )}

          {/* ── Preferences ──────────────────────────────────────────────── */}
          {tab === "preferences" && (
            <div className="space-y-6">
              <div className="space-y-2">
                <Label className="text-sm font-medium">Preferred Job Types</Label>
                <div className="flex flex-wrap gap-2">
                  {JOB_TYPES.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() =>
                        setJobTypes((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]))
                      }
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
                        jobTypes.includes(t)
                          ? "border-primary/40 bg-primary/10 text-primary"
                          : "border-border/50 text-muted-foreground hover:bg-muted/30",
                      )}
                    >
                      {t.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-sm font-medium">Preferred Workplace</Label>
                <div className="flex flex-wrap gap-2">
                  {WORKPLACE_TYPES.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() =>
                        setWorkplaceTypes((p) => (p.includes(t) ? p.filter((x) => x !== t) : [...p, t]))
                      }
                      className={cn(
                        "rounded-full border px-3 py-1 text-xs capitalize transition-colors",
                        workplaceTypes.includes(t)
                          ? "border-primary/40 bg-primary/10 text-primary"
                          : "border-border/50 text-muted-foreground hover:bg-muted/30",
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <StringListEditor
                label="Desired Roles"
                placeholder="e.g. Backend Engineer…"
                hint="The roles you want next — used for job matching and Learning Hub paths."
                items={desiredRoles}
                onChange={setDesiredRoles}
              />
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
