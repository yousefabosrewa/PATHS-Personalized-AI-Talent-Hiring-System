"use client";

import { motion } from "framer-motion";
import {
  Database, Loader2, RefreshCw, CheckCircle2, XCircle,
  Clock, AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useJobImportStatus, useRunJobImport } from "@/lib/hooks";

export default function JobIngestionPage() {
  const { data: status, isLoading, isError, refetch } = useJobImportStatus();
  const runImport = useRunJobImport();

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 max-w-4xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
            <Database className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Job Ingestion
            </h1>
            <p className="text-sm text-muted-foreground">
              Automated job import pipeline — fetches and processes job listings from external sources.
            </p>
          </div>
        </div>
        <Button
          size="sm"
          onClick={() => runImport.mutateAsync({})}
          disabled={runImport.isPending}
          className="text-xs shrink-0"
        >
          {runImport.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
          )}
          Run Import
        </Button>
      </motion.div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading job ingestion status…
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="glass rounded-xl p-6 border border-red-500/20 space-y-2">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-4 w-4" />
            <p className="text-sm font-medium">Could not load job ingestion status.</p>
          </div>
          <p className="text-xs text-muted-foreground">The import status endpoint may be unavailable.</p>
          <Button size="sm" variant="ghost" onClick={() => refetch()} className="text-xs">
            Retry
          </Button>
        </div>
      )}

      {/* Status cards */}
      {!isLoading && !isError && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="glass rounded-xl p-5 space-y-2"
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Last Run
              </p>
              <p className="text-sm text-foreground">
                {status?.last_run_at
                  ? new Date(status.last_run_at).toLocaleString()
                  : "Never run"}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
              className="glass rounded-xl p-5 space-y-2"
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Last Outcome
              </p>
              <div className="flex items-center gap-2">
                {status?.last_success === true && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                )}
                {status?.last_success === false && (
                  <XCircle className="h-4 w-4 text-red-400" />
                )}
                {status?.last_success === null && (
                  <Clock className="h-4 w-4 text-muted-foreground" />
                )}
                <p className="text-sm text-foreground">
                  {status?.last_success === true ? "Success" :
                   status?.last_success === false ? "Failed" :
                   "No data"}
                </p>
              </div>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.11 }}
              className="glass rounded-xl p-5 space-y-2"
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Jobs Inserted
              </p>
              <p className="text-2xl font-bold text-foreground tabular-nums">
                {status?.last_inserted_count ?? 0}
              </p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.14 }}
              className="glass rounded-xl p-5 space-y-2"
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Last Error
              </p>
              <p className="text-sm text-red-400 break-words">
                {status?.last_error || "None"}
              </p>
            </motion.div>
          </div>

          {/* Info card */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.17 }}
            className="glass rounded-xl p-6 space-y-3"
          >
            <h2 className="text-sm font-semibold text-foreground">About Job Ingestion</h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              The job ingestion agent periodically fetches job listings from configured external sources
              and processes them into the platform. The pipeline handles deduplication, skill extraction,
              and vector embedding for semantic search. Imported jobs appear in the Jobs section once processed.
            </p>
            <p className="text-xs text-muted-foreground">
              If the last run shows an error, verify that external API credentials and rate limits are configured correctly.
            </p>
          </motion.div>
        </>
      )}
    </div>
  );
}
