"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Brain, Shield, Users, CheckCircle2, BarChart3,
  FileText, Zap, ArrowRight, Star, Lock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";

const pillars = [
  {
    icon: Brain,
    title: "15 Specialized AI Agents",
    desc: "Each agent is purpose-built: CV parsing, skill matching, vector similarity, scoring, rationale generation, bias detection, and more. They work in concert — not as a black box.",
    color: "text-primary bg-primary/10 border-primary/20",
  },
  {
    icon: Shield,
    title: "Bias Reduction by Design",
    desc: "Candidates are anonymized before evaluation. Recruiters see skills, experience, and scores — not names, photos, or personal details. Bias flags surface automatically.",
    color: "text-teal-400 bg-teal-500/10 border-teal-500/20",
  },
  {
    icon: Users,
    title: "Human-in-the-Loop",
    desc: "AI proposes. Humans decide. Every shortlist, outreach, and final offer requires explicit human approval. No candidate is auto-rejected by an algorithm.",
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  },
];

const features = [
  { icon: Zap,       title: "10× faster screening",          desc: "From CV upload to ranked shortlist in minutes." },
  { icon: BarChart3, title: "Evidence-based scoring",         desc: "Every score references specific CV claims or skills." },
  { icon: Lock,      title: "Audit-ready decisions",          desc: "Full log of every view, decision, and approval." },
  { icon: FileText,  title: "Transparent rationale",          desc: "AI explains exactly why each candidate ranked where they did." },
  { icon: Shield,    title: "Compliance by default",          desc: "Egypt PDPL, EEOC, and EU AI Act baked in — not bolted on." },
  { icon: Users,     title: "Collaborative review",           desc: "Invite hiring managers, interviewers, and HR to review together." },
];

const tiers = [
  {
    name: "Starter",
    price: "Free",
    period: "",
    desc: "For small teams trying PATHS for the first time.",
    features: ["5 active jobs", "Up to 50 candidates/mo", "Basic AI scoring", "Email support"],
    cta: "Get Started",
    href: "/candidate-signup",
    highlight: false,
  },
  {
    name: "Growth",
    price: "$299",
    period: "/mo",
    desc: "For growing teams with active hiring pipelines.",
    features: ["Unlimited jobs", "Unlimited candidates", "Full 15-agent AI suite", "Bias guardrails", "HITL approvals", "Priority support"],
    cta: "Create Company Account",
    href: "/company-signup",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    desc: "For large orgs with compliance and integration needs.",
    features: ["Everything in Growth", "SSO / SAML", "ATS integration", "Custom scoring rubrics", "Dedicated CSM", "SLA guarantee"],
    cta: "Contact Sales",
    href: "/company-signup",
    highlight: false,
  },
];

export default function ForCompaniesPage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-20 pt-16 text-center">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-primary/6 blur-[100px]" />
        </div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative mx-auto max-w-3xl">
          <Badge variant="outline" className="mb-4 border-primary/25 bg-primary/8 text-primary">For Companies</Badge>
          <h1 className="font-heading text-5xl font-bold tracking-tight text-foreground">
            Hire with evidence,
            <br />
            <span className="gradient-text">not guesswork.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-muted-foreground">
            PATHS gives your hiring team an AI-powered edge — faster screening, fairer decisions, and a full audit trail for every hire.
          </p>
          <Button className="mt-8 gap-2 glow-blue" size="lg" asChild>
            <Link href="/company-signup">Create Company Account <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        </motion.div>
      </section>

      {/* Three pillars */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {pillars.map((p, i) => (
              <motion.div key={p.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="glass gradient-border rounded-2xl p-7">
                <div className={cn("mb-5 flex h-12 w-12 items-center justify-center rounded-xl border", p.color)}>
                  <p.icon className="h-6 w-6" />
                </div>
                <h3 className="font-heading text-lg font-bold text-foreground">{p.title}</h3>
                <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">{p.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="bg-navy-900/40 px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mb-12 text-center">
            <h2 className="font-heading text-3xl font-bold text-foreground">Everything your team needs</h2>
          </motion.div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f, i) => (
              <motion.div key={f.title} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.05 }} className="glass flex items-start gap-4 rounded-xl p-5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <f.icon className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-[13px] font-semibold text-foreground">{f.title}</p>
                  <p className="mt-1 text-[12px] text-muted-foreground">{f.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mb-12 text-center">
            <h2 className="font-heading text-3xl font-bold text-foreground">Simple, transparent pricing</h2>
            <p className="mt-3 text-muted-foreground">No hidden fees. Scale as you grow.</p>
          </motion.div>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {tiers.map((tier, i) => (
              <motion.div key={tier.name} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }}
                className={cn("glass rounded-2xl p-7 flex flex-col", tier.highlight && "gradient-border ring-1 ring-primary/20")}
              >
                {tier.highlight && (
                  <Badge className="mb-4 w-fit bg-primary/15 text-primary border-primary/25">Most Popular</Badge>
                )}
                <h3 className="font-heading text-lg font-bold text-foreground">{tier.name}</h3>
                <div className="mt-3 flex items-baseline gap-0.5">
                  <span className="font-heading text-3xl font-bold text-foreground">{tier.price}</span>
                  <span className="text-sm text-muted-foreground">{tier.period}</span>
                </div>
                <p className="mt-2 text-[13px] text-muted-foreground">{tier.desc}</p>
                <ul className="mt-6 flex-1 space-y-2.5">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-[13px] text-muted-foreground">
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button className={cn("mt-8 w-full", tier.highlight && "glow-blue")} variant={tier.highlight ? "default" : "outline"} asChild>
                  <Link href={tier.href}>{tier.cta}</Link>
                </Button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-navy-900/40 px-6 py-20 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="mx-auto max-w-xl">
          <Star className="mx-auto mb-4 h-10 w-10 text-amber-400" />
          <h2 className="font-heading text-3xl font-bold text-foreground">Ready to transform your hiring?</h2>
          <p className="mt-4 text-muted-foreground">Join teams already using PATHS to hire faster, fairer, and smarter.</p>
          <Button className="mt-8 gap-2 glow-blue" size="lg" asChild>
            <Link href="/company-signup">Create Company Account <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        </motion.div>
      </section>
    </div>
  );
}
