// fix2.md §2: the standalone /candidate-sources route was consolidated
// into /candidates → Sources tab.  Server-side redirect so old bookmarks
// and deep links don't 404.

import { redirect } from "next/navigation";

export default function CandidateSourcesLegacyRedirect() {
  redirect("/candidates/sources");
}
