"use client";

import { useRef } from "react";
import Link from "next/link";
import { motion, useInView } from "framer-motion";
import {
  Brain, Shield, Users, ChevronRight, ArrowRight,
  CheckCircle2, Star, Upload, Link2, BarChart3, Search, Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { BrandLogo } from "@/components/layout/brand-logo";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";

/* ─── Data ─────────────────────────────────────────────────────────────────── */

// Two clear capability cards instead of vanity numbers — they say what PATHS
// actually does, which is the real hook.
const highlights = [
  {
    icon: Shield,
    accent: "teal",
    title: "Fair by design",
    desc: "Anonymized, bias-guarded screening — and no candidate is ever rejected by an algorithm alone.",
  },
  {
    icon: BarChart3,
    accent: "blue",
    title: "Explainable by default",
    desc: "Every score is backed by traceable evidence, with a human approving each decision and a full audit trail.",
  },
];

const steps = [
  {
    step: "01", icon: Upload,
    title: "Build your profile once",
    desc:  "Upload your CV, add your skills, GitHub, LinkedIn and portfolio. PATHS extracts and organizes everything automatically.",
    accent: "blue",
  },
  {
    step: "02", icon: Brain,
    title: "AI matches you to jobs",
    desc:  "Specialized AI agents analyze your profile against live job requirements — transparently, with evidence for every score.",
    accent: "violet",
  },
  {
    step: "03", icon: Shield,
    title: "Fair, anonymous screening",
    desc:  "Recruiters evaluate your skills and experience — not your name, photo, or address. Bias is reduced by design.",
    accent: "teal",
  },
  {
    step: "04", icon: Users,
    title: "Human makes the final call",
    desc:  "Every AI recommendation is reviewed by a human before action. You are never rejected by an algorithm alone.",
    accent: "amber",
  },
];

const accentClasses: Record<string, string> = {
  blue:   "bg-blue-50   text-blue-600   border-blue-100",
  violet: "bg-violet-50 text-violet-600 border-violet-100",
  teal:   "bg-teal-50   text-teal-600   border-teal-100",
  amber:  "bg-amber-50  text-amber-600  border-amber-100",
};

const candidateFeatures = [
  { icon: Upload,    title: "CV Upload & Extraction",   desc: "Upload once. AI extracts your full profile automatically." },
  { icon: Link2,     title: "LinkedIn & GitHub",         desc: "Connect your professional presence in seconds." },
  { icon: Search,    title: "Smart Job Matching",        desc: "Get matched to roles that actually fit your skills." },
  { icon: Shield,    title: "Anonymous Screening",       desc: "Your skills speak — your name stays private during scoring." },
  { icon: BarChart3, title: "Transparent Scores",        desc: "See why you scored the way you did, backed by evidence." },
  { icon: Zap,       title: "Apply Globally",            desc: "One profile, multiple companies. No re-entering data." },
];

const companyFeatures = [
  "Specialized AI agents for sourcing, CV screening, scoring & ranking",
  "Anonymized screening removes name, gender & age bias",
  "Evidence-based scoring — every claim traceable to its source",
  "Human-in-the-loop approval before any shortlist or decision",
  "Interview intelligence — AI question packs, transcript analysis & scoring",
  "Decision-support rubric with per-stage breakdown & growth plans",
  "Full, exportable audit trail for every hiring decision",
];

const testimonials = [
  {
    quote:
      "I'm genuinely proud to recommend PATHS. It brings real evidence and fairness to screening — exactly what modern talent acquisition needs — and my team trusts its shortlists from day one.",
    author: "Marwah Muhammad",
    role: "Talent Acquisition Partner",
    company: "Nokia",
    rating: 5,
  },
  {
    quote:
      "One of the best hiring systems I've ever tried. It gets fairness and explainability right in a way I rarely see — even in commercial tools.",
    author: "Prof. Shaker",
    role: "Professor & Academic Supervisor",
    company: "",
    rating: 5,
  },
];

/* ─── Animation helpers ────────────────────────────────────────────────────── */

const ease = [0.22, 1, 0.36, 1] as const;

function FadeUp({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref    = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 28 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.58, delay, ease }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ─── Sub-components ───────────────────────────────────────────────────────── */

function SectionBadge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-3.5 py-1 text-[12px] font-semibold uppercase tracking-wider text-blue-600",
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <MarketingNav />

      {/* ══════════════════════════════════════════════════════════════════════
          HERO
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="hero-wash dot-grid relative overflow-hidden px-5 pb-24 pt-12 sm:pt-16">

        {/* Decorative arcs — top-right and bottom-left, very subtle */}
        <div
          aria-hidden
          className="pointer-events-none absolute -right-40 -top-40 h-[600px] w-[600px] rounded-full border border-blue-100/60"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 -left-32 h-[400px] w-[400px] rounded-full border border-blue-100/40"
        />

        <div className="relative mx-auto max-w-4xl">

          {/* ── Brand logo ───────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease }}
            className="mb-6 flex justify-center"
          >
            <BrandLogo className="h-24 w-auto sm:h-28" />
          </motion.div>

          {/* ── Headline ─────────────────────────────────────── */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08, ease }}
            className="text-center font-heading text-5xl font-bold leading-[1.1] tracking-tight text-[#0D1527] sm:text-6xl md:text-[68px]"
          >
            Hire the right people,
            <br />
            <span className="accent-text">faster</span>
            {" — with "}
            <span className="accent-text">evidence.</span>
          </motion.h1>

          {/* ── Supporting copy ──────────────────────────────── */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.17, ease }}
            className="mx-auto mt-6 max-w-2xl text-center text-lg leading-relaxed text-slate-500"
          >
            PATHS is an AI-driven hiring OS that reduces bias, explains every decision,
            and keeps humans in control. Candidates build one profile. Companies find
            the right fit — fairly, transparently, and fast.
          </motion.p>

          {/* ── CTAs ─────────────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.26, ease }}
            className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
          >
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Button
                size="lg"
                className={cn(
                  "h-12 gap-2 rounded-xl px-8 text-base font-semibold",
                  "bg-[oklch(0.50_0.22_264)] text-white",
                  "hover:bg-[oklch(0.46_0.24_264)]",
                  "shadow-[0_2px_6px_oklch(0.50_0.22_264/30%),0_8px_24px_oklch(0.50_0.22_264/18%)]",
                  "transition-colors duration-150",
                )}
                asChild
              >
                <Link href="/candidate-signup">
                  Create Your Profile <ArrowRight className="h-5 w-5" />
                </Link>
              </Button>
            </motion.div>

            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Button
                size="lg"
                variant="outline"
                className="h-12 gap-2 rounded-xl border-slate-200 px-8 text-base font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50 hover:text-foreground transition-all duration-150"
                asChild
              >
                <Link href="/for-companies">
                  For Companies <ChevronRight className="h-5 w-5" />
                </Link>
              </Button>
            </motion.div>
          </motion.div>

          {/* ── Trust line ───────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.34, ease }}
            className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-1.5 text-[13px] text-slate-500"
          >
            {["No black boxes", "No algorithmic rejections", "Every score explained"].map(
              (item) => (
                <span key={item} className="inline-flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                  {item}
                </span>
              ),
            )}
          </motion.div>

          {/* ── Capability cards (two, no vanity numbers) ─────── */}
          <motion.div
            initial={{ opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.38, ease }}
            className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2"
          >
            {highlights.map(({ icon: Icon, title, desc, accent }) => (
              <motion.div
                key={title}
                whileHover={{ y: -3 }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
                className="mkt-card flex items-start gap-4 p-6 text-left"
              >
                <div
                  className={cn(
                    "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border",
                    accentClasses[accent],
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-heading text-[16px] font-semibold text-[#0D1527]">{title}</p>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-slate-500">{desc}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          HOW IT WORKS
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="px-5 py-24">
        <div className="mx-auto max-w-6xl">

          <FadeUp className="mb-16 flex flex-col items-center text-center">
            <SectionBadge className="mb-4">How it works</SectionBadge>
            <h2 className="font-heading text-4xl font-bold tracking-tight text-[#0D1527] md:text-5xl">
              Fair hiring in four steps
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-slate-500">
              From profile creation to final decision — transparent, evidence-backed,
              and always human-approved.
            </p>
          </FadeUp>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((item, i) => (
              <FadeUp key={item.step} delay={i * 0.07}>
                <div className="mkt-card relative h-full p-6">
                  {/* Step number — top-right watermark */}
                  <span className="absolute right-5 top-4 font-mono text-[11px] font-bold text-slate-200">
                    {item.step}
                  </span>

                  <div
                    className={cn(
                      "mb-4 flex h-11 w-11 items-center justify-center rounded-xl border",
                      accentClasses[item.accent],
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                  </div>

                  <h3 className="font-heading text-[15px] font-semibold text-[#0D1527]">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-[13px] leading-relaxed text-slate-500">
                    {item.desc}
                  </p>
                </div>
              </FadeUp>
            ))}
          </div>

          <FadeUp className="mt-10 text-center" delay={0.2}>
            <Link
              href="/how-it-works"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline underline-offset-3 transition-colors"
            >
              See the full process <ChevronRight className="h-4 w-4" />
            </Link>
          </FadeUp>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          FOR CANDIDATES
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="section-alt px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid grid-cols-1 gap-14 lg:grid-cols-2 lg:items-center">

            {/* Left — copy */}
            <FadeUp>
              <SectionBadge className="mb-5 border-teal-100 bg-teal-50 text-teal-600">
                For Candidates
              </SectionBadge>
              <h2 className="font-heading text-4xl font-bold tracking-tight text-[#0D1527] md:text-5xl">
                Build once.
                <br />
                <span className="accent-text">Apply everywhere.</span>
              </h2>
              <p className="mt-5 text-[15px] leading-relaxed text-slate-500">
                Create a single, rich profile with your CV, skills, GitHub, and portfolio.
                PATHS matches you to roles across multiple companies — and you always know
                exactly why.
              </p>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} className="mt-8 inline-block">
                <Button
                  size="lg"
                  className="h-12 gap-2 rounded-xl bg-[oklch(0.50_0.22_264)] px-7 font-semibold text-white hover:bg-[oklch(0.46_0.24_264)] shadow-[0_2px_8px_oklch(0.50_0.22_264/25%)] transition-colors duration-150"
                  asChild
                >
                  <Link href="/candidate-signup">
                    Start your profile <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </motion.div>
            </FadeUp>

            {/* Right — feature grid */}
            <div className="grid grid-cols-2 gap-4">
              {candidateFeatures.map((f, i) => (
                <FadeUp key={f.title} delay={i * 0.05}>
                  <div className="mkt-card h-full p-4">
                    <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 border border-blue-100">
                      <f.icon className="h-4 w-4 text-blue-600" />
                    </div>
                    <p className="text-[13px] font-semibold text-[#0D1527]">{f.title}</p>
                    <p className="mt-1 text-[12px] leading-relaxed text-slate-500">{f.desc}</p>
                  </div>
                </FadeUp>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          FOR COMPANIES
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="px-5 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid grid-cols-1 gap-14 lg:grid-cols-2 lg:items-center">

            {/* Left — checklist card */}
            <FadeUp className="order-2 lg:order-1">
              <div className="mkt-card p-8 space-y-3.5">
                {companyFeatures.map((f) => (
                  <div key={f} className="flex items-start gap-3">
                    <CheckCircle2 className="mt-0.5 h-4.5 w-4.5 shrink-0 text-emerald-500" />
                    <p className="text-[13.5px] leading-relaxed text-slate-600">{f}</p>
                  </div>
                ))}
              </div>
            </FadeUp>

            {/* Right — copy */}
            <FadeUp className="order-1 lg:order-2">
              <SectionBadge className="mb-5">For Companies</SectionBadge>
              <h2 className="font-heading text-4xl font-bold tracking-tight text-[#0D1527] md:text-5xl">
                Hire with evidence,
                <br />
                <span className="accent-text">not guesswork.</span>
              </h2>
              <p className="mt-5 text-[15px] leading-relaxed text-slate-500">
                PATHS gives your team an unfair advantage — AI does the heavy lifting,
                bias guardrails keep it fair, and humans make every final call.
              </p>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }} className="mt-8 inline-block">
                <Button
                  size="lg"
                  variant="outline"
                  className="h-12 gap-2 rounded-xl border-slate-200 px-7 text-slate-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700 transition-all duration-150"
                  asChild
                >
                  <Link href="/for-companies">
                    Learn more <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </motion.div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          TESTIMONIALS
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="section-alt px-5 py-24">
        <div className="mx-auto max-w-4xl">
          <FadeUp className="mb-12 text-center">
            <SectionBadge className="mb-4">Testimonials</SectionBadge>
            <h2 className="font-heading text-3xl font-bold tracking-tight text-[#0D1527] md:text-4xl">
              Trusted by teams and candidates
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            {testimonials.map((t, i) => (
              <FadeUp key={i} delay={i * 0.1}>
                <div className="mkt-card h-full p-7">
                  {/* Stars */}
                  <div className="mb-5 flex gap-0.5">
                    {Array.from({ length: t.rating }).map((_, j) => (
                      <Star key={j} className="h-4 w-4 fill-amber-400 text-amber-400" />
                    ))}
                  </div>

                  {/* Quote */}
                  <p className="text-[15px] leading-relaxed text-slate-700">
                    &quot;{t.quote}&quot;
                  </p>

                  {/* Attribution */}
                  <div className="mt-6 flex items-center gap-3 border-t border-slate-100 pt-5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-50 text-[13px] font-bold text-blue-600">
                      {t.author[0]}
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-[#0D1527]">{t.author}</p>
                      <p className="text-[12px] text-slate-500">
                        {[t.role, t.company].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════════
          FINAL CTA
      ══════════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden px-5 py-28">
        {/* Subtle arc decoration */}
        <div
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[900px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-blue-50"
        />

        <div className="relative mx-auto max-w-3xl text-center">
          <FadeUp>
            <SectionBadge className="mb-6">Get started today</SectionBadge>

            <h2 className="font-heading text-5xl font-bold tracking-tight text-[#0D1527] md:text-6xl">
              Ready to find your
              <br />
              <span className="accent-text">next great hire?</span>
            </h2>

            <p className="mx-auto mt-6 max-w-lg text-lg leading-relaxed text-slate-500">
              Whether you&apos;re a candidate building your career or a company scaling your team —
              PATHS makes hiring transparent, fair, and fast.
            </p>

            <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Button
                  size="lg"
                  className="h-12 gap-2 rounded-xl bg-[oklch(0.50_0.22_264)] px-8 text-base font-semibold text-white hover:bg-[oklch(0.46_0.24_264)] shadow-[0_2px_8px_oklch(0.50_0.22_264/28%),0_8px_24px_oklch(0.50_0.22_264/16%)] transition-colors duration-150"
                  asChild
                >
                  <Link href="/candidate-signup">
                    Create Candidate Profile <ArrowRight className="h-5 w-5" />
                  </Link>
                </Button>
              </motion.div>

              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
                <Button
                  size="lg"
                  variant="outline"
                  className="h-12 gap-2 rounded-xl border-slate-200 px-8 text-base text-slate-700 hover:border-slate-300 hover:bg-slate-50 transition-all duration-150"
                  asChild
                >
                  <Link href="/company-signup">
                    Create Company Account <ChevronRight className="h-5 w-5" />
                  </Link>
                </Button>
              </motion.div>
            </div>
          </FadeUp>
        </div>
      </section>

      <MarketingFooter />
    </div>
  );
}
