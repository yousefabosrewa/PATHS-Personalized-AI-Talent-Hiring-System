"use client";

/**
 * Candidate Duplicate Review (fix2_1.md Feature 2).
 *
 * Lives inside the Candidates step/tab. Lists exact-identity duplicate groups
 * (same normalized name + email + phone) and merges each group into one
 * canonical profile while preserving history.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import {
  Users, Loader2, GitMerge, ChevronDown, ChevronRight,
  AlertTriangle, RefreshCw,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils/cn";
import { CandidatesTabBar } from "@/components/features/candidates/CandidatesTabBar";

interface DuplicateCandidate {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  source: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface DuplicateGroup {
  group_id: string;
  normalized_name: string;
  normalized_email: string;
  normalized_phone: string;
  candidate_count: number;
  candidate_ids: string[];
  candidates: DuplicateCandidate[];
  last_updated: string | null;
}

interface DuplicateGroupList {
  total: number;
  groups: DuplicateGroup[];
}

interface MergeResult {
  merged: boolean;
  group_id: string;
  canonical_candidate_id: string;
  merged_candidate_ids: string[];
  merged_count: number;
}

export default function CandidateDuplicatesPage() {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [confirmGroup, setConfirmGroup] = useState<DuplicateGroup | null>(null);
  const [mergingId, setMergingId] = useState<string | null>(null);

  const dupQuery = useQuery({
    queryKey: ["candidate-duplicates"],
    queryFn: () => api.get<DuplicateGroupList>("/api/v1/candidates/duplicates"),
    staleTime: 15_000,
  });

  const mergeMutation = useMutation({
    mutationFn: (groupId: string) =>
      api.post<MergeResult>(
        `/api/v1/candidates/duplicates/${encodeURIComponent(groupId)}/merge`,
        {},
      ),
  });

  function toggle(groupId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  }

  async function doMerge(group: DuplicateGroup) {
    setMergingId(group.group_id);
    try {
      const res = await mergeMutation.mutateAsync(group.group_id);
      toast.success(
        `Merged ${res.merged_count} duplicate${res.merged_count === 1 ? "" : "s"} into one profile.`,
      );
      qc.invalidateQueries({ queryKey: ["candidate-duplicates"] });
      qc.invalidateQueries({ queryKey: ["applications"] });
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Merge failed. No changes were made.",
      );
    } finally {
      setMergingId(null);
      setConfirmGroup(null);
    }
  }

  const groups = dupQuery.data?.groups ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="flex items-center justify-between gap-4 mb-3">
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Candidates
            </h1>
            <p className="text-sm text-muted-foreground">
              Duplicate Candidates — review candidates that appear multiple times
              with the same name, email, and phone number.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5"
            onClick={() => dupQuery.refetch()}
            disabled={dupQuery.isFetching}
          >
            {dupQuery.isFetching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Rescan
          </Button>
        </div>
        <CandidatesTabBar />
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-4xl">
        <p className="text-xs text-muted-foreground">
          Merge exact duplicates into one profile while preserving candidate
          history. Detection rule: same normalized name + email + phone.
        </p>

        {dupQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Scanning for duplicates…
          </div>
        ) : dupQuery.isError ? (
          <p className="text-sm text-red-400">Failed to load duplicate groups.</p>
        ) : groups.length === 0 ? (
          <div className="glass rounded-xl p-8 text-center text-sm text-muted-foreground">
            No exact duplicates found. Candidates with the same name, email, and
            phone number will appear here for review.
          </div>
        ) : (
          groups.map((g) => {
            const isOpen = expanded.has(g.group_id);
            return (
              <motion.div
                key={g.group_id}
                layout
                className="glass rounded-xl overflow-hidden"
              >
                <div className="flex items-center justify-between gap-3 p-4">
                  <button
                    type="button"
                    onClick={() => toggle(g.group_id)}
                    className="flex items-center gap-3 text-left min-w-0"
                  >
                    {isOpen ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-semibold text-sm text-foreground truncate">
                          {g.candidates[0]?.name || g.normalized_name}
                        </p>
                        <Badge
                          variant="outline"
                          className="border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px]"
                        >
                          {g.candidate_count} duplicates
                        </Badge>
                      </div>
                      <p className="text-[12px] text-muted-foreground truncate">
                        {g.normalized_email}
                        {g.normalized_phone ? ` · ${g.normalized_phone}` : ""}
                      </p>
                    </div>
                  </button>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => toggle(g.group_id)}
                    >
                      {isOpen ? "Hide" : "View duplicates"}
                    </Button>
                    <Button
                      size="sm"
                      className="gap-1.5"
                      onClick={() => setConfirmGroup(g)}
                      disabled={mergingId === g.group_id}
                    >
                      {mergingId === g.group_id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <GitMerge className="h-3.5 w-3.5" />
                      )}
                      Merge all
                    </Button>
                  </div>
                </div>

                {isOpen && (
                  <div className="border-t border-border/40 divide-y divide-border/30">
                    {g.candidates.map((c, idx) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between gap-3 px-4 py-3"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-sm text-foreground">{c.name}</p>
                            {idx === 0 && (
                              <Badge
                                variant="outline"
                                className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]"
                              >
                                Oldest
                              </Badge>
                            )}
                            {c.source && (
                              <Badge variant="outline" className="text-[10px]">
                                {c.source}
                              </Badge>
                            )}
                          </div>
                          <p className="text-[11px] text-muted-foreground truncate">
                            {c.email || "—"}
                            {c.phone ? ` · ${c.phone}` : ""}
                          </p>
                        </div>
                        <span className="font-mono text-[10px] text-muted-foreground/70 shrink-0">
                          {c.id.slice(0, 8)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            );
          })
        )}
      </div>

      <Dialog
        open={confirmGroup !== null}
        onOpenChange={(open) => !open && setConfirmGroup(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              Merge duplicate candidates
            </DialogTitle>
            <DialogDescription>
              This will merge candidates with the same name, email, and phone
              number into one profile. All candidate history will be preserved
              where possible. This action should not affect unrelated candidates.
            </DialogDescription>
          </DialogHeader>
          {confirmGroup && (
            <div className="rounded-lg border border-border/50 bg-muted/20 p-3 text-sm">
              <p className="font-semibold text-foreground">
                {confirmGroup.candidates[0]?.name || confirmGroup.normalized_name}
              </p>
              <p className="text-[12px] text-muted-foreground">
                {confirmGroup.normalized_email} ·{" "}
                {confirmGroup.candidate_count} records will be merged into one.
              </p>
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setConfirmGroup(null)}>
              Cancel
            </Button>
            <Button
              className="gap-1.5"
              onClick={() => confirmGroup && doMerge(confirmGroup)}
              disabled={mergingId !== null}
            >
              {mergingId !== null ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <GitMerge className="h-3.5 w-3.5" />
              )}
              Confirm merge
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
