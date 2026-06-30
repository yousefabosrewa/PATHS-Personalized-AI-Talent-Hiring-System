// fix6.md — the recruiter "Sourcing" tab was renamed to "Source Candidate".
// This page exists only to keep deep links working; the real page lives at
// /source-candidate.

import { redirect } from "next/navigation";

export default function SourcingRedirectPage() {
  redirect("/source-candidate");
}
