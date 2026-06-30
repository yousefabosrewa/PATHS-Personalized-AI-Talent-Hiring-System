"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Upload, Brain, Shield, Users, CheckCircle2, Zap,
  FileText, BarChart3, Eye, Lock, ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const phases = [
  {
    number: "01",
    title: "Create your profile",
    subtitle: "Upload once. We do the rest.",
    icon: Upload,
    color: "text-primary border-primary/20 bg-primary/10",
    points: [
      "Upload your CV (PDF or DOCX) — AI extracts your full work history, skills, and education",
      "Add your LinkedIn, GitHub, and portfolio links for richer evidence",
      "Complete short onboarding steps to confirm and enrich extracted data",
      "Set your job preferences: role type, location, salary range, remote/hybrid",
      "Your profile is saved and reusable across multiple job opportunities",
    ],
  },
  {
    number: "02",
    title: "AI extracts & organizes",
    subtitle: "Evidence over inference.",
    icon: Brain,
    color: "text-teal-400 border-teal-500/20 bg-teal-500/10",
    points: [
      "CV parsing agent extracts every skill, role, achievement, and credential",
      "Each extracted fact becomes an 'evidence item' — traceable to source text",
      "Skills are normalized and categorized (technical, soft, tools, languages)",
      "GitHub and portfolio links are analyzed for additional technical evidence",
      "All evidence is stored with confidence scores — nothing is fabricated",
    ],
  },
  {
    number: "03",
    title: "Smart job matching",
    subtitle: "15 agents, one transparent score.",
    icon: BarChart3,
    color: "text-violet-400 border-violet-500/20 bg-violet-500/10",
    points: [
      "15 specialized AI agents score your profile against each job's requirements",
      "Skills match, experience fit, education level, and culture signals are all weighted",
      "Every score is backed by evidence — you see exactly which skills earned which points",
      "Vector similarity finds candidates who match conceptually, not just by keyword",
      "Scores are deterministic and auditable — no black-box decisions",
    ],
  },
  {
    number: "04",
    title: "Fair, anonymous screening",
    subtitle: "Your skills speak. Not your name.",
    icon: Shield,
    color: "text-amber-400 border-amber-500/20 bg-amber-500/10",
    points: [
      "Recruiters see skills, experience, and scores — not name, photo, or personal details",
      "Anonymized view hides: full name, email, phone, exact address, nationality",
      "Bias flags automatically detect and surface potential discrimination risks",
      "De-anonymization requires explicit recruiter request + HITL approval",
      "Full audit trail maintained for every view, decision, and de-anon request",
    ],
  },
  {
    number: "05",
    title: "Human makes the final call",
    subtitle: "AI proposes. Humans decide.",
    icon: Users,
    color: "text-emerald-400 border-emerald-500/20 bg-emerald-500/10",
    points: [
      "Every shortlist is reviewed by a human recruiter before candidates are contacted",
      "Human-in-the-loop approvals required for outreach, shortlisting, and final offers",
      "Recruiters see AI rationale alongside their own judgment",
      "Candidates are never automatically rejected — a human always reviews edge cases",
      "Decision packets include evidence, scores, and bias check results",
    ],
  },
];

const principles = [
  { icon: Eye,       title: "Transparent",  desc: "Every score is backed by evidence. No opaque AI decisions." },
  { icon: Lock,      title: "Private",       desc: "Candidate PII is protected by anonymization until consent." },
  { icon: CheckCircle2, title: "Compliant", desc: "Egypt PDPL, EU AI Act, and EEOC guidelines enforced by design." },
  { icon: Zap,       title: "Fast",          desc: "From CV upload to ranked shortlist in minutes, not weeks." },
  { icon: FileText,  title: "Auditable",     desc: "Full audit log of every hiring action — exportable on demand." },
  { icon: Users,     title: "Human-first",  desc: "AI assists. Humans own every decision that affects people." },
];

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-20 pt-16 text-center">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-primary/6 blur-[100px]" />
        </div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative mx-auto max-w-3xl">
          <Badge variant="outline" className="mb-4 border-primary/25 bg-primary/8 text-primary">How PATHS Works</Badge>
          <h1 className="font-heading text-5xl font-bold tracking-tight text-foreground">
            Fair hiring, step by step
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            Every phase is designed to reduce bias, increase transparency, and keep humans in control — from first CV upload to final hire.
          </p>
        </motion.div>
      </section>

      {/* Phases */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-4xl space-y-8">
          {phases.map((phase, i) => (
            <motion.div
              key={phase.number}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: i * 0.05 }}
              className="glass gradient-border rounded-2xl p-8"
            >
              <div className="flex items-start gap-6">
                <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border ${phase.color}`}>
                  <phase.icon className="h-6 w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="font-mono text-xs font-bold text-muted-foreground/50">{phase.number}</span>
                    <h2 className="font-heading text-xl font-bold text-foreground">{phase.title}</h2>
                    <span className="text-[12px] text-muted-foreground">— {phase.subtitle}</span>
                  </div>
                  <ul className="mt-5 space-y-2.5">
                    {phase.points.map((pt) => (
                      <li key={pt} className="flex items-start gap-2.5 text-[13px] text-muted-foreground">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                        {pt}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Principles */}
      <section className="bg-navy-900/40 px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mb-12 text-center">
            <h2 className="font-heading text-3xl font-bold text-foreground">Built on six principles</h2>
          </motion.div>
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-3">
            {principles.map((p, i) => (
              <motion.div key={p.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }} className="glass rounded-xl p-5">
                <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                  <p.icon className="h-4 w-4 text-primary" />
                </div>
                <p className="font-semibold text-[14px] text-foreground">{p.title}</p>
                <p className="mt-1 text-[12px] text-muted-foreground">{p.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-20 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mx-auto max-w-xl">
          <h2 className="font-heading text-3xl font-bold text-foreground">Ready to experience it?</h2>
          <p className="mt-4 text-muted-foreground">Create your candidate profile in minutes. No fees. No BS.</p>
          <Button className="mt-8 gap-2 glow-blue" size="lg" asChild>
            <Link href="/candidate-signup">Create Your Profile <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        </motion.div>
      </section>
    </div>
  );
}
