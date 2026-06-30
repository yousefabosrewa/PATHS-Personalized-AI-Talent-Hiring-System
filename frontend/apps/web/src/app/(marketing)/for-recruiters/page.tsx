import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ForRecruitersPage() {
  return (
    <div className="min-h-screen">
      <section className="px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
                Recruiters
              </p>
              <h1 className="mt-3 font-heading text-3xl font-bold tracking-tight sm:text-4xl">
                Efficiency-first hiring workflows
              </h1>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                PATHS is structured around the work recruiters repeat every week: triage, evidence
                review, stakeholder alignment, and decision documentation — with AI acceleration
                where it actually helps.
              </p>
              <div className="mt-8 flex flex-wrap gap-2">
                <Link href="/register/org">
                  <Button className="!px-6">Create organization workspace</Button>
                </Link>
                <Link href="/login">
                  <Button variant="ghost" className="!px-6">
                    Sign in
                  </Button>
                </Link>
              </div>
            </div>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            <div className="glass gradient-border rounded-2xl p-6">
              <h2 className="font-heading text-base font-semibold">Shortlist velocity</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Move from job spec to ranked candidates with a reviewable artifact.
              </p>
            </div>
            <div className="glass gradient-border rounded-2xl p-6">
              <h2 className="font-heading text-base font-semibold">Interview intelligence</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Operational tools for availability and structured summaries.
              </p>
            </div>
            <div className="glass gradient-border rounded-2xl p-6">
              <h2 className="font-heading text-base font-semibold">Decision support</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Generate explainable packets tied to real application context.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
