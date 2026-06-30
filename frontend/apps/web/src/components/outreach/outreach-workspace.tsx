"use client";

/**
 * Unified candidate search workspace (org Matching page).
 *
 * Natural-language semantic search across every candidate source — each
 * result row shows where the candidate came from. The standalone candidate
 * sourcing flow now lives under Candidates → Find Talent.
 */

import { SemanticSearchPanel } from "@/components/outreach/semantic-search-panel";

export function OutreachSearchWorkspace() {
  return <SemanticSearchPanel />;
}
