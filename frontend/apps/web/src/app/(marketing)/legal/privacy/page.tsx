import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — PATHS",
  description: "PATHS privacy policy: how we collect, use, and protect your data.",
};

const SECTIONS = [
  {
    title: "1. Who we are",
    content: `PATHS (\"PATHS Platform\", \"we\", \"our\") is an AI-powered talent acquisition platform operated by PATHS Ltd. Our registered address and data protection contact are listed at the end of this document.`,
  },
  {
    title: "2. What data we collect",
    content: `We collect:
• Identity & contact data: name, email, phone, location provided at registration.
• CV/résumé data: professional history, skills, education, and certifications extracted from uploaded documents.
• Usage data: pages visited, features used, timestamps, IP addresses.
• Communication data: emails and messages sent through the platform.
• Billing data: plan selections and invoice records (card details are processed directly by Stripe, not stored by us).`,
  },
  {
    title: "3. How we use your data",
    content: `We use your data to:
• Provide, operate, and improve the PATHS platform.
• Match candidates with job opportunities.
• Send transactional notifications (interview invites, decision emails).
• Comply with legal obligations.
• Conduct analytics to improve AI model performance (always on aggregated or anonymised data).`,
  },
  {
    title: "4. Legal bases",
    content: `Under UK GDPR / EU GDPR our lawful bases are:
• Contract performance: processing necessary to deliver the service you signed up for.
• Legitimate interests: fraud prevention, security, and platform improvement.
• Consent: marketing communications and non-essential cookies (you can withdraw at any time).
• Legal obligation: retaining records as required by applicable law.`,
  },
  {
    title: "5. Data retention",
    content: `• CVs and candidate profiles: 24 months from last activity, or until you request deletion.
• Interview transcripts: 18 months.
• Hire/reject decisions: 7 years (legal hold requirement for employment records).
• Account data: deleted 30 days after you request account closure.`,
  },
  {
    title: "6. Your rights",
    content: `Under GDPR you have the right to:
• Access — request a copy of your personal data (use the Export button in Settings).
• Rectification — correct inaccurate data.
• Erasure — ask us to delete your data (subject to legal hold obligations).
• Restriction — ask us to limit processing.
• Portability — receive your data in a machine-readable format.
• Objection — object to processing based on legitimate interests.
To exercise any of these rights, email privacy@paths.ai.`,
  },
  {
    title: "7. Cookies",
    content: `We use:
• Strictly necessary cookies: session management and security. These cannot be disabled.
• Analytics cookies: usage measurement (opt-in via the cookie banner).
• Marketing cookies: campaign attribution (opt-in, never enabled by default).
You can change your cookie preferences at any time using the cookie settings link in the footer.`,
  },
  {
    title: "8. Third parties",
    content: `We share data with:
• Stripe (payment processing)
• OpenRouter / Anthropic (AI inference — no training on your data per our DPA)
• Qdrant Cloud (vector storage)
• Vercel / Fly.io (hosting)
All processors are under DPAs with equivalent GDPR protections.`,
  },
  {
    title: "9. Contact",
    content: `Data controller: PATHS Ltd\nEmail: privacy@paths.ai\n\nIf you are unhappy with how we handle your data, you can complain to the ICO (UK) or the supervisory authority in your country.`,
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-heading text-4xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-sm text-muted-foreground mb-10">
        Last updated: 15 May 2026
      </p>
      <div className="space-y-8">
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2 className="text-xl font-semibold mb-3">{s.title}</h2>
            <div className="text-sm text-muted-foreground whitespace-pre-line leading-relaxed">
              {s.content}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
