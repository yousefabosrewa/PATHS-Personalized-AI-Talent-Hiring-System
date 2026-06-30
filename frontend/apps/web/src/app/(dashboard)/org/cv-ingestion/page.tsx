// fix2.md §9: the standalone CV Processing surface was folded into the
// Candidates → Sources CSV upload flow.  Server-side redirect keeps any
// existing bookmark working.

import { redirect } from "next/navigation";

export default function CvProcessingLegacyRedirect() {
  redirect("/candidates/sources");
}
