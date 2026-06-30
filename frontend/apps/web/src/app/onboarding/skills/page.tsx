"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight, Plus, X, Loader2, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useOnboardingStore } from "@/lib/stores/onboarding.store";
import type { ProfileSkill } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";

const POPULAR_SKILLS = [
  "Python", "JavaScript", "TypeScript", "React", "Node.js", "SQL", "PostgreSQL",
  "Docker", "AWS", "Git", "REST APIs", "GraphQL", "Machine Learning", "Data Analysis",
  "Figma", "Product Management", "Agile / Scrum", "Communication", "Leadership",
];

const proficiencyLevels: { value: ProfileSkill["proficiency"]; label: string; color: string }[] = [
  { value: "beginner",     label: "Beginner",     color: "border-slate-500/40 bg-slate-500/10 text-slate-400"    },
  { value: "intermediate", label: "Intermediate", color: "border-primary/40 bg-primary/10 text-primary"           },
  { value: "advanced",     label: "Advanced",     color: "border-violet-500/40 bg-violet-500/10 text-violet-400"  },
  { value: "expert",       label: "Expert",       color: "border-amber-500/40 bg-amber-500/10 text-amber-400"     },
];

const categoryForSkill = (name: string): ProfileSkill["category"] => {
  const tech = ["python","javascript","typescript","react","node","sql","postgres","docker","aws","git","graphql","api","machine learning","data"];
  if (tech.some((t) => name.toLowerCase().includes(t))) return "technical";
  return "other";
};

export default function SkillsPage() {
  const router = useRouter();
  const { draft, updateDraft, markStepComplete, saveDraft } = useOnboardingStore();

  const [skills, setSkills] = useState<ProfileSkill[]>(draft.skills ?? []);
  const [query, setQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const filteredSuggestions = POPULAR_SKILLS.filter(
    (s) =>
      s.toLowerCase().includes(query.toLowerCase()) &&
      !skills.find((sk) => sk.name.toLowerCase() === s.toLowerCase())
  );

  const addSkill = (name: string) => {
    if (skills.find((s) => s.name.toLowerCase() === name.toLowerCase())) return;
    setSkills((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        name,
        category: categoryForSkill(name),
        proficiency: "intermediate",
      },
    ]);
    setQuery("");
  };

  const removeSkill = (id: string) => setSkills((prev) => prev.filter((s) => s.id !== id));

  const setProficiency = (id: string, proficiency: ProfileSkill["proficiency"]) =>
    setSkills((prev) => prev.map((s) => (s.id === id ? { ...s, proficiency } : s)));

  const onSubmit = async () => {
    setIsSubmitting(true);
    updateDraft({ skills });
    markStepComplete("skills");
    await saveDraft();
    router.push("/onboarding/experience");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mx-auto max-w-2xl px-6 py-10"
    >
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-primary">Step 4 of 9</p>
        <h1 className="mt-1 font-heading text-3xl font-bold text-foreground">Skills</h1>
        <p className="mt-2 text-sm text-muted-foreground">Add your skills and set your proficiency level for each.</p>
      </div>

      <div className="space-y-6">
        {/* Search / add */}
        <div className="space-y-2">
          <Label className="text-sm font-medium">Search or type a skill</Label>
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="e.g. Python, React, Project Management…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && query.trim()) {
                  e.preventDefault();
                  addSkill(query.trim());
                }
              }}
              className="h-11 pl-10 pr-4"
            />
          </div>

          {/* Suggestions dropdown */}
          {query && filteredSuggestions.length > 0 && (
            <div className="glass rounded-xl border border-border/60 p-2 space-y-0.5">
              {filteredSuggestions.slice(0, 8).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => addSkill(s)}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" /> {s}
                </button>
              ))}
              {!filteredSuggestions.find((s) => s.toLowerCase() === query.toLowerCase()) && (
                <button
                  type="button"
                  onClick={() => addSkill(query.trim())}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-primary hover:bg-primary/10 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" /> Add &quot;{query.trim()}&quot;
                </button>
              )}
            </div>
          )}
        </div>

        {/* Popular skills */}
        {!query && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground/50">Popular Skills</p>
            <div className="flex flex-wrap gap-2">
              {POPULAR_SKILLS.filter((s) => !skills.find((sk) => sk.name === s)).slice(0, 12).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => addSkill(s)}
                  className="flex items-center gap-1 rounded-full border border-border/50 px-3 py-1 text-xs text-muted-foreground hover:border-primary/40 hover:text-primary transition-colors"
                >
                  <Plus className="h-3 w-3" /> {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Added skills */}
        {skills.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground/50">
              Your Skills ({skills.length})
            </p>
            <AnimatePresence>
              {skills.map((skill) => (
                <motion.div
                  key={skill.id}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="glass rounded-xl p-3.5 flex items-center gap-3"
                >
                  <span className="flex-1 text-sm font-medium text-foreground">{skill.name}</span>
                  <div className="flex items-center gap-1">
                    {proficiencyLevels.map((p) => (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => setProficiency(skill.id, p.value)}
                        className={cn(
                          "rounded-full border px-2.5 py-0.5 text-[10px] font-medium transition-all",
                          skill.proficiency === p.value ? p.color : "border-border/40 text-muted-foreground/60 hover:border-border"
                        )}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => removeSkill(skill.id)}
                    className="text-muted-foreground/40 hover:text-destructive transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}

        {skills.length === 0 && (
          <div className="rounded-xl border border-dashed border-border/40 py-8 text-center">
            <p className="text-sm text-muted-foreground">No skills added yet. Search above or pick from popular skills.</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          <Button type="button" variant="ghost" className="gap-2" onClick={() => router.push("/onboarding/contact")}>
            <ArrowLeft className="h-4 w-4" /> Back
          </Button>
          <Button
            type="button"
            className="gap-2 glow-blue"
            disabled={isSubmitting || skills.length === 0}
            onClick={onSubmit}
          >
            {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</> : <>Save &amp; Continue <ArrowRight className="h-4 w-4" /></>}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
