"use client";

/**
 * Candidates → Find Talent sub-tab.
 *
 * Sources outbound candidates live from LinkedIn for the recruiter's query
 * and ranks them against a target job (best fit first), with an Import action.
 * When "All sources" is selected, database candidates are folded in and
 * ranked alongside the LinkedIn finds.
 */

import { CandidatesTabBar } from "@/components/features/candidates/CandidatesTabBar";
import { FindTalentPanel } from "@/components/outreach/find-talent-panel";

export default function CandidatesFindTalentPage() {
  return (
    <div className="flex h-full flex-col">
      {/* Top bar (mirrors the Candidates pipeline header) */}
      <div className="border-b border-border/50 bg-background/60 backdrop-blur-sm px-6 py-4">
        <div className="mb-3">
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Candidates
          </h1>
          <p className="text-sm text-muted-foreground">
            Find Talent — source outbound candidates from LinkedIn for your
            search and let the agent rank them against a target job.
          </p>
        </div>
        <CandidatesTabBar />
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto w-full max-w-5xl">
          <FindTalentPanel />
        </div>
      </div>
    </div>
  );
}
