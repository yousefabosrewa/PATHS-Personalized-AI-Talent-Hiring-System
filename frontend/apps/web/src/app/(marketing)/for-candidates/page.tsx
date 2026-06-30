"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Upload, Brain, Shield, BarChart3, Globe, Bell,
  CheckCircle2, ChevronDown, ArrowRight, Star,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { cn } from "@/lib/utils/cn";

const benefits = [
  {
    icon: Upload,
    title: "Upload CV once, apply everywhere",
    desc: "Upload your CV and PATHS extracts every skill, role, and credential automatically. One profile reaches multiple companies — no re-entering data.",
    color: "text-primary bg-primary/10 border-primary/20",
  },
  {
    icon: Brain,
    title: "Evidence-based scoring",
    desc: "AI scores your fit for each role using real evidence from your profile. You can see exactly which skills earned which points — no guesswork.",
    color: "text-teal-400 bg-teal-500/10 border-teal-500/20",
  },
  {
    icon: Shield,
    title: "Anonymous, fair screening",
    desc: "During initial screening your name, photo, and personal details are hidden. Recruiters evaluate your skills, not your background.",
    color: "text-violet-400 bg-violet-500/10 border-violet-500/20",
  },
  {
    icon: BarChart3,
    title: "Transparent match scores",
    desc: "See a detailed breakdown of how you scored — skills match, experience relevance, and role fit — all backed by traceable evidence.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
  {
    icon: Globe,
    title: "Apply to global opportunities",
    desc: "Reach companies across the MENA region and beyond. Your profile travels — you don't have to fill in forms for every application.",
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  },
  {
    icon: Bell,
    title: "Know your application status",
    desc: "Track every application in real time. See which stage you're in, when a decision is made, and why — no more ghosting.",
    color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
  },
];

const steps = [
  { label: "Sign up", desc: "Create an account in 30 seconds" },
  { label: "Upload CV", desc: "PDF or DOCX — AI extracts everything" },
  { label: "Add links", desc: "LinkedIn, GitHub, portfolio" },
  { label: "Set preferences", desc: "Role, location, work mode, salary" },
  { label: "Go live", desc: "Your profile is discoverable by companies" },
];

const faqs = [
  {
    q: "Is PATHS free for candidates?",
    a: "Yes. Candidates always use PATHS for free. Companies pay for access to the talent pool and hiring tools.",
  },
  {
    q: "Who can see my personal information?",
    a: "During screening, recruiters see only anonymized data — your skills, experience, and scores. Your full profile (name, email, phone) is only revealed if you consent and a recruiter requests de-anonymization, which requires explicit approval.",
  },
  {
    q: "What happens to my CV data?",
    a: "Your data is stored securely and used only for matching you to relevant roles. You can delete your profile at any time. We comply with Egypt PDPL and GDPR data protection laws.",
  },
  {
    q: "Can I apply to multiple jobs with the same profile?",
    a: "Yes — that's the whole point. One profile, multiple opportunities. Update it once and it's reflected everywhere.",
  },
  {
    q: "What if I'm not actively looking?",
    a: "You can set your profile to 'passive' mode. Companies can still find you, but you won't appear in urgent shortlists unless you accept an outreach invitation.",
  },
];

function FAQ({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="glass rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-6 py-4 text-left"
      >
        <span className="text-[14px] font-semibold text-foreground">{q}</span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-border/40 px-6 pb-5 pt-4">
          <p className="text-[13px] leading-relaxed text-muted-foreground">{a}</p>
        </div>
      )}
    </div>
  );
}

export default function ForCandidatesPage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-20 pt-16 text-center">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-teal-glow/8 blur-[100px]" />
        </div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative mx-auto max-w-3xl">
          <Badge variant="outline" className="mb-4 border-teal-500/25 bg-teal-500/8 text-teal-400">For Candidates</Badge>
          <h1 className="font-heading text-5xl font-bold tracking-tight text-foreground">
            Your profile. Your story.
            <br />
            <span className="gradient-text">Fairly evaluated.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            Build one powerful profile and let PATHS match you to the right opportunities — where your skills matter more than your name.
          </p>
          <Button className="mt-8 gap-2 glow-blue" size="lg" asChild>
            <Link href="/candidate-signup">Create Free Profile <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        </motion.div>
      </section>

      {/* Benefits */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {benefits.map((b, i) => (
              <motion.div key={b.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.06 }} className="glass gradient-border rounded-2xl p-6">
                <div className={cn("mb-4 flex h-11 w-11 items-center justify-center rounded-xl border", b.color)}>
                  <b.icon className="h-5 w-5" />
                </div>
                <h3 className="font-heading text-[15px] font-semibold text-foreground">{b.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{b.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How to get started */}
      <section className="bg-navy-900/40 px-6 py-20">
        <div className="mx-auto max-w-3xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mb-12 text-center">
            <h2 className="font-heading text-3xl font-bold text-foreground">Get started in 5 minutes</h2>
          </motion.div>
          <div className="space-y-3">
            {steps.map((step, i) => (
              <motion.div key={step.label} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.07 }} className="glass flex items-center gap-5 rounded-xl px-6 py-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[13px] font-bold text-primary ring-1 ring-primary/25">
                  {i + 1}
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-foreground">{step.label}</p>
                  <p className="text-[12px] text-muted-foreground">{step.desc}</p>
                </div>
                {i < steps.length - 1 && <CheckCircle2 className="ml-auto h-4 w-4 text-emerald-400/50 shrink-0" />}
                {i === steps.length - 1 && <Star className="ml-auto h-4 w-4 text-amber-400 shrink-0" />}
              </motion.div>
            ))}
          </div>
          <div className="mt-8 text-center">
            <Button className="gap-2 glow-blue" size="lg" asChild>
              <Link href="/candidate-signup">Start Now — It&apos;s Free <ArrowRight className="h-4 w-4" /></Link>
            </Button>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-2xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mb-10 text-center">
            <h2 className="font-heading text-3xl font-bold text-foreground">Frequently asked</h2>
          </motion.div>
          <div className="space-y-3">
            {faqs.map((faq) => <FAQ key={faq.q} {...faq} />)}
          </div>
        </div>
      </section>
    </div>
  );
}
