"use client";

/**
 * Outreach workspace.
 *
 * Lives at /org/matching for back-compat; also surfaced as the
 * Candidates → Outreach sub-tab. One unified search covers every candidate
 * source (All / Database / Outbound / Imported CSV) and each result shows
 * its source. Identities stay anonymized — only an alias + agent
 * explanation are returned.
 */

import { motion } from "framer-motion";
import { Telescope } from "lucide-react";
import { OutreachSearchWorkspace } from "@/components/outreach/outreach-workspace";

export default function OutreachWorkspacePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-6 space-y-6">
        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
            <Telescope className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
              Outreach
            </h1>
            <p className="text-sm text-muted-foreground">
              Search every candidate source in one place — database, outbound and
              imported pools. PATHS returns an anonymized shortlist with an
              agent-generated explanation and the source for each candidate.
            </p>
          </div>
        </motion.header>

        <OutreachSearchWorkspace />
      </div>
    </div>
  );
}
