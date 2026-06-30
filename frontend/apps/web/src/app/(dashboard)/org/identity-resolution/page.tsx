// fix2.md §6: Duplicate Candidates moved into Candidates → Sources →
// Review Duplicates.  Server-side redirect for legacy deep links.

import { redirect } from "next/navigation";

export default function DuplicateCandidatesLegacyRedirect() {
  redirect("/candidates/sources");
}
