"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Contact, Loader2, AlertCircle, Mail, Phone, Link2, Code, Globe,
  ChevronDown, ChevronUp, Sparkles, CheckCircle2, XCircle, ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useInterviewContactCandidates, useEnrichCandidate } from "@/lib/hooks";
import type { ContactFinderCandidate } from "@/lib/api";

// ── Per-channel presentation ────────────────────────────────────────────────

const CHANNELS: { key: keyof ContactFinderCandidate; label: string; icon: typeof Mail; isLink?: boolean }[] = [
  { key: "email", label: "Email", icon: Mail },
  { key: "phone", label: "Phone", icon: Phone },
  { key: "linkedin", label: "LinkedIn", icon: Link2, isLink: true },
  { key: "github", label: "GitHub", icon: Code, isLink: true },
  { key: "portfolio", label: "Portfolio", icon: Globe, isLink: true },
];

function ChannelRow({
  label,
  icon: Icon,
  value,
  isLink,
}: {
  label: string;
  icon: typeof Mail;
  value: string | null;
  isLink?: boolean;
}) {
  const has = Boolean(value);
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border/40 bg-muted/15 px-3 py-2">
      <div className="flex items-center gap-2 min-w-0">
        <Icon className={cn("h-3.5 w-3.5 shrink-0", has ? "text-primary" : "text-muted-foreground/50")} />
        <span className="text-[12px] font-medium text-foreground shrink-0">{label}</span>
      </div>
      {has ? (
        isLink ? (
          <a
            href={value!.startsWith("http") ? value! : `https://${value}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[12px] text-primary hover:underline truncate max-w-[260px]"
          >
            {value!.replace(/^https?:\/\//, "")}
            <ExternalLink className="h-3 w-3 shrink-0" />
          </a>
        ) : (
          <span className="text-[12px] text-foreground font-mono truncate max-w-[260px]">{value}</span>
        )
      ) : (
        <Badge variant="outline" className="text-[10px] border-amber-500/40 text-amber-400 shrink-0">
          Missing
        </Badge>
      )}
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: ContactFinderCandidate }) {
  const [open, setOpen] = useState(false);
  const enrich = useEnrichCandidate();
  const missingCount = candidate.missing.length;

  const onEnrich = async () => {
    try {
      const res = await enrich.mutateAsync(candidate.candidate_id);
      if (res.found.length > 0) {
        toast.success(`Found: ${res.found.join(", ")}.`);
      } else {
        toast.message(res.notes[0] ?? "No new contact details found.");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Enrichment failed.");
    }
  };

  return (
    <motion.div layout className="glass rounded-xl overflow-hidden">
      <div className="flex items-center justify-between gap-3 p-4">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-3 text-left min-w-0"
        >
          {open ? (
            <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <div className="min-w-0">
            <p className="font-semibold text-sm text-foreground truncate">{candidate.name}</p>
            <p className="text-[12px] text-muted-foreground truncate">
              {candidate.current_title || "In interview process"}
            </p>
          </div>
        </button>
        <div className="flex items-center gap-2 shrink-0">
          {candidate.complete ? (
            <Badge variant="outline" className="text-[10px] border-emerald-500/40 bg-emerald-500/10 text-emerald-300 gap-1">
              <CheckCircle2 className="h-3 w-3" /> Complete
            </Badge>
          ) : (
            <Badge variant="outline" className="text-[10px] border-amber-500/40 bg-amber-500/10 text-amber-300 gap-1">
              <AlertCircle className="h-3 w-3" /> {missingCount} missing
            </Badge>
          )}
          {!candidate.complete && (
            <Button
              size="sm"
              className="gap-1.5 text-xs"
              onClick={onEnrich}
              disabled={enrich.isPending}
              title="Search available sources (GitHub, LinkedIn) using the data already on file"
            >
              {enrich.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Enrich
            </Button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-2">
              {CHANNELS.map((ch) => (
                <ChannelRow
                  key={ch.key}
                  label={ch.label}
                  icon={ch.icon}
                  value={candidate[ch.key] as string | null}
                  isLink={ch.isLink}
                />
              ))}
              {candidate.socials.map((s, i) => (
                <ChannelRow key={`social-${i}`} label={s.type} icon={Globe} value={s.value} isLink />
              ))}
              {enrich.data && enrich.variables === candidate.candidate_id && (
                <div className="rounded-lg border border-border/40 bg-muted/10 p-2.5 text-[11px] text-muted-foreground space-y-1">
                  {enrich.data.found.length > 0 && (
                    <p className="text-emerald-400">Found: {enrich.data.found.join(", ")}</p>
                  )}
                  {enrich.data.notes.map((n, i) => (
                    <p key={i}>{n}</p>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ContactFinderPage() {
  const { data: candidates = [], isLoading, isError, refetch } = useInterviewContactCandidates();

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-4xl">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <Contact className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Contact Finder
          </h1>
          <p className="text-sm text-muted-foreground">
            Candidates in the interview process and their reach-out details. If a
            channel is missing, click <strong>Enrich</strong> to search public
            sources from the data already on file.
          </p>
        </div>
      </motion.div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin text-primary" /> Loading interview candidates…
        </div>
      ) : isError ? (
        <div className="glass gradient-border rounded-2xl p-6 flex flex-col items-center gap-3 text-center">
          <XCircle className="h-8 w-8 text-red-400" />
          <p className="text-sm font-medium text-foreground">Failed to load candidates.</p>
          <Button size="sm" variant="secondary" onClick={() => refetch()}>Retry</Button>
        </div>
      ) : candidates.length === 0 ? (
        <div className="glass gradient-border rounded-2xl p-8 text-center max-w-lg mx-auto">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <Contact className="h-6 w-6 text-primary" />
          </div>
          <p className="text-sm font-medium text-foreground">No candidates in the interview process yet.</p>
          <p className="text-xs text-muted-foreground mt-1">
            Schedule an interview from the Interviews tab, and the candidate will
            appear here for contact lookup.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {candidates.length} candidate{candidates.length === 1 ? "" : "s"} ·{" "}
            {candidates.filter((c) => !c.complete).length} with missing contact info
          </p>
          {candidates.map((c) => (
            <CandidateCard key={c.candidate_id} candidate={c} />
          ))}
        </div>
      )}
    </div>
  );
}
