"use client";

/**
 * SkillEvidencePanel
 *
 * Renders per-skill evidence (CV / GitHub / LinkedIn) on a candidate's
 * profile. Each skill row shows a 0-100 aggregate score and a click-to-
 * expand breakdown listing the three sources, their sub-scores, the
 * verifying snippets and the agent's one-line reasoning.
 *
 * A "Refresh skill evidence" button at the top runs the MCP-style
 * evidence tools on every skill (slow — the LLM is called per skill).
 *
 * Profile-URL editor lets the recruiter paste the candidate's LinkedIn
 * and GitHub URLs when they weren't extracted from the CV — without
 * those URLs the GitHub / LinkedIn tools return ``url_missing``.
 */

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2, Sparkles, ChevronDown, ChevronUp, ExternalLink,
  Code2 as Github, FileText, AlertCircle, Pencil, Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";
import {
  useSkillEvidence,
  useRefreshSkillEvidence,
  useCandidateProfileUrls,
  useSetCandidateProfileUrls,
} from "@/lib/hooks";
import type { SkillEvidenceItem, SkillEvidenceSource } from "@/lib/api";

// ── Per-source presentation ─────────────────────────────────────────────────

// Candidate.md §4/§6 — the rubric is CV + GitHub only (LinkedIn removed).
const SOURCE_CONFIG: Record<
  string,
  { label: string; icon: typeof FileText; tone: string }
> = {
  cv:       { label: "CV",       icon: FileText,  tone: "text-amber-300"   },
  github:   { label: "GitHub",   icon: Github,    tone: "text-foreground"  },
};

// Translates the per-source status enum into a human sentence so the UI
// never says "missing" without explaining who needs to fix it.
const STATUS_HINTS: Record<string, string> = {
  available:       "Evidence collected.",
  not_run:         "Hasn't been collected yet for this candidate.",
  not_configured:  "Missing because this source has not been configured for the deployment yet.",
  url_missing:     "Missing because the candidate has no URL on file for this source. Paste one in the editor above.",
  blocked:         "Source was reachable but blocked the request — public scraping limits. A real MCP server would unblock this.",
  error:           "Source returned an error this run. Try Refresh again, or check the URL is reachable.",
  no_match:        "Source was reachable but did not mention this skill.",
};

function scoreTone(score: number | null | undefined): string {
  if (score == null) return "border-muted/40 text-muted-foreground";
  if (score >= 75) return "border-emerald-500/40 text-emerald-300";
  if (score >= 50) return "border-amber-500/40 text-amber-300";
  return "border-rose-500/40 text-rose-300";
}

function SkillSourceRow({ src }: { src: SkillEvidenceSource }) {
  const cfg = SOURCE_CONFIG[src.source] ?? {
    label: src.source.toUpperCase(),
    icon: FileText,
    tone: "text-muted-foreground",
  };
  const SrcIcon = cfg.icon;
  const hint = STATUS_HINTS[src.status] ?? "";
  // Candidate.md §6 — each source contributes up to its weight (50). Show the
  // contribution out of that cap, e.g. "42 / 50". Missing source → "0 / 50".
  const cap = src.weight > 0 ? Math.round(src.weight) : 50;
  const contribution =
    src.score == null ? 0 : Math.round(((src.score as number) * src.weight) / 100);
  return (
    <div className="rounded-lg border border-border/40 bg-muted/15 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <SrcIcon className={cn("h-3.5 w-3.5", cfg.tone)} />
          <span className="text-[12px] font-semibold text-foreground">{cfg.label}</span>
          <span className="text-[10px] text-muted-foreground">
            {src.score == null ? "Found: No" : "Found: Yes"}
          </span>
        </div>
        <Badge variant="outline" className={cn("text-[10px]", scoreTone(src.score))}>
          {contribution} / {cap}
        </Badge>
      </div>
      {src.reasoning && (
        <p className="text-[11px] text-foreground/80 leading-snug">{src.reasoning}</p>
      )}
      {src.score == null && hint && (
        <p className="text-[10px] text-muted-foreground italic">{hint}</p>
      )}
      {src.snippets.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            {src.snippets.length} verifying snippet{src.snippets.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 space-y-1 list-disc list-inside text-foreground/80">
            {src.snippets.slice(0, 6).map((s, i) => (
              <li key={i}>
                {s.text}
                {s.source_url && (
                  <a
                    href={s.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-1 inline-flex items-center text-primary hover:underline"
                  >
                    <ExternalLink className="h-2.5 w-2.5 ml-0.5" />
                  </a>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {src.fallback && (
        <p className="text-[10px] text-amber-300 italic">
          Score from deterministic fallback — LLM was unavailable.
        </p>
      )}
    </div>
  );
}


function SkillRow({ item }: { item: SkillEvidenceItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-border/40 bg-muted/10">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/20 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-semibold text-foreground">{item.skill}</span>
            {/* The "confidence low/medium/high" badge was removed per request —
                the aggregate score is the headline; confidence is still
                stored server-side and surfaced inside the per-source
                breakdown if a recruiter expands the row. */}
            {item.last_refreshed_at && (
              <span className="text-[10px] text-muted-foreground">
                refreshed {new Date(item.last_refreshed_at).toLocaleDateString()}
              </span>
            )}
          </div>
          <div className="mt-2 h-1.5 w-full rounded-full bg-muted/40 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${item.aggregate_score}%` }}
              transition={{ duration: 0.7, ease: "easeOut" }}
              className={cn(
                "h-full rounded-full",
                item.aggregate_score >= 75
                  ? "bg-emerald-500"
                  : item.aggregate_score >= 50
                  ? "bg-amber-500"
                  : "bg-rose-500",
              )}
            />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-heading text-base font-bold text-foreground">{item.aggregate_score}</span>
          <span className="text-[10px] text-muted-foreground">/ 100</span>
          {open ? (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-2">
              {item.sources.map((s) => (
                <SkillSourceRow key={s.source} src={s} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


function ProfileUrlEditor({ candidateId }: { candidateId: string }) {
  const { data: urls } = useCandidateProfileUrls(candidateId);
  const setUrls = useSetCandidateProfileUrls();
  const [editing, setEditing] = useState(false);
  const [github, setGithub] = useState("");

  // Initialise draft from persisted value whenever the editor opens.
  useEffect(() => {
    if (!editing && urls) {
      setGithub(urls.github ?? "");
    }
  }, [urls, editing]);

  const save = () => {
    // Only GitHub feeds the rubric now (Candidate.md §4); LinkedIn is left
    // untouched server-side.
    setUrls.mutate(
      {
        candidateId,
        github: github.trim() || null,
      },
      { onSuccess: () => setEditing(false) },
    );
  };

  if (!editing) {
    return (
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground flex-wrap">
        <span className="inline-flex items-center gap-1.5">
          <Github className="h-3 w-3" />
          {urls?.github ? (
            <a href={urls.github} target="_blank" rel="noreferrer" className="text-primary hover:underline">
              {urls.github.replace(/^https?:\/\//, "")}
            </a>
          ) : (
            <span className="italic">no GitHub URL on file</span>
          )}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 px-2 gap-1 text-[11px]"
          onClick={() => setEditing(true)}
        >
          <Pencil className="h-3 w-3" />
          Edit
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/40 bg-muted/15 p-3 space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        GitHub URL (the verification agent reads this)
      </p>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Github className="h-3.5 w-3.5 shrink-0" />
          <Input
            placeholder="https://github.com/<username>"
            value={github}
            onChange={(e) => setGithub(e.target.value)}
            className="h-8 text-[12px]"
          />
        </div>
      </div>
      <div className="flex items-center gap-2 pt-1">
        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-[11px]"
          onClick={() => setEditing(false)}
        >
          Cancel
        </Button>
        <Button
          size="sm"
          className="h-7 gap-1 text-[11px]"
          onClick={save}
          disabled={setUrls.isPending}
        >
          {setUrls.isPending
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <Check className="h-3 w-3" />}
          Save
        </Button>
      </div>
    </div>
  );
}


export function SkillEvidencePanel({ candidateId }: { candidateId: string }) {
  const evidence = useSkillEvidence(candidateId);
  const refresh = useRefreshSkillEvidence();

  const items = evidence.data?.items ?? [];
  const hasAnyEvidence = items.length > 0;

  return (
    <div className="glass rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="font-heading text-sm font-semibold text-foreground">
            Skill Evidence
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Per-skill score: 50% CV evidence + 50% GitHub verification (0-100).
            Click any skill to see the per-source breakdown.
          </p>
        </div>
        <Button
          size="sm"
          variant={hasAnyEvidence ? "outline" : "default"}
          className="gap-1.5 text-xs"
          onClick={() => refresh.mutate({ candidateId })}
          disabled={refresh.isPending}
          title="Re-run the CV / GitHub / LinkedIn tools and re-score every skill"
        >
          {refresh.isPending
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <Sparkles className="h-3 w-3" />}
          {hasAnyEvidence ? "Refresh skill evidence" : "Collect skill evidence"}
        </Button>
      </div>

      <ProfileUrlEditor candidateId={candidateId} />

      {refresh.isError && (
        <div className="flex items-center gap-2 text-[12px] text-rose-300">
          <AlertCircle className="h-3.5 w-3.5" />
          {(refresh.error as Error | undefined)?.message ?? "Refresh failed."}
        </div>
      )}

      {evidence.isLoading ? (
        <div className="flex items-center gap-2 py-6 text-[12px] text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading evidence…
        </div>
      ) : !hasAnyEvidence ? (
        <p className="text-[12px] text-muted-foreground italic">
          No skill evidence collected yet. Click <strong>Collect skill evidence</strong>{" "}
          to run the agent — this can take up to a minute per skill while the
          LLM scores each source.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <SkillRow key={item.skill} item={item} />
          ))}
        </div>
      )}

      {refresh.isPending && hasAnyEvidence && (
        <p className="text-[11px] text-muted-foreground italic">
          Refreshing evidence — the agent calls each source per skill, so this
          can take a while. The page won't freeze; you can keep navigating.
        </p>
      )}
    </div>
  );
}
