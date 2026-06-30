"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ListTree, Loader2 } from "lucide-react";
import { useMatchingRun, useMatchingShortlist } from "@/lib/hooks";

export default function OrgRunPage() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;

  const {
    data: run,
    isLoading: runLoading,
    isError: runError,
  } = useMatchingRun(runId);

  const {
    data: shortlistData,
    isLoading: shortlistLoading,
  } = useMatchingShortlist(runId);

  const shortlist = shortlistData?.shortlist;

  if (!runId) {
    return (
      <div className="h-full overflow-y-auto p-6">
        <p className="text-sm text-muted-foreground">Invalid run.</p>
      </div>
    );
  }

  if (runLoading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading run details…
      </div>
    );
  }

  const hasError = runError || (!runLoading && !run);

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
          Matching run
        </h1>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{runId}</p>
      </div>

      {hasError && (
        <div className="glass rounded-xl p-6 text-sm text-red-400">
          Could not load matching run. It may not exist or you may not have access.
        </div>
      )}

      {run && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass gradient-border rounded-2xl p-6 space-y-4"
        >
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Run summary
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="glass rounded-xl p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
              <p className="mt-1 text-sm text-foreground">
                {run.status ?? (shortlist ? "completed" : "unknown")}
              </p>
            </div>
            <div className="glass rounded-xl p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Job ID</p>
              <p className="mt-1 truncate text-sm text-foreground font-mono text-xs">
                {run.job_id ?? "n/a"}
              </p>
            </div>
          </div>
        </motion.div>
      )}

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="glass gradient-border rounded-2xl p-6 space-y-4"
      >
        <div className="flex items-center gap-2 text-muted-foreground">
          <ListTree className="h-4 w-4" />
          <h2 className="text-xs font-semibold uppercase tracking-wider">Anonymised shortlist</h2>
        </div>

        {shortlistLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading shortlist…
          </div>
        )}

        {!shortlistLoading && (!shortlist || shortlist.length === 0) && (
          <div className="glass rounded-xl p-6 text-sm text-muted-foreground text-center">
            No shortlist entries yet. Try another search with broader skills or a larger Top-K value.
          </div>
        )}

        {shortlist && shortlist.length > 0 && (
          <div className="space-y-3">
            {shortlist.map((item, index) => (
              <div
                key={item.candidate_id ?? index}
                className="glass rounded-xl p-4 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Candidate {item.rank ?? index + 1}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {item.candidate_name ?? "Anonymous"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-lg font-bold text-primary">
                    {item.score != null ? item.score.toFixed(0) : "—"}
                  </p>
                  <p className="text-[10px] text-muted-foreground">score</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      <p className="text-center text-sm text-muted-foreground">
        <Link href="/org/matching" className="text-primary hover:underline">
          New search
        </Link>
      </p>
    </div>
  );
}
