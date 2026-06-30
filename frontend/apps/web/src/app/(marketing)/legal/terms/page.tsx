import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — PATHS",
  description: "PATHS Terms of Service governing use of the platform.",
};

const SECTIONS = [
  {
    title: "1. Acceptance",
    content: `By creating an account or using the PATHS platform, you agree to these Terms. If you do not agree, do not use the service.`,
  },
  {
    title: "2. Service description",
    content: `PATHS is an AI-powered talent acquisition platform that helps organisations find, screen, and hire candidates. Features include automated CV screening, interview scheduling, bias reduction tools, and analytics dashboards.`,
  },
  {
    title: "3. Accounts",
    content: `• You must be 18 or over to create an account.
• You are responsible for keeping your credentials secure.
• You must not share your account with others.
• We may suspend accounts that breach these Terms.`,
  },
  {
    title: "4. Acceptable use",
    content: `You must not:
• Use the platform to discriminate unlawfully on protected characteristics.
• Upload malicious files or attempt to compromise platform security.
• Reverse-engineer, scrape, or copy any part of the platform.
• Impersonate others or submit false information.
• Use the platform for any purpose that violates applicable law.`,
  },
  {
    title: "5. AI features and human oversight",
    content: `PATHS uses AI to assist—not replace—human hiring decisions. All AI outputs are recommendations. Hiring organisations remain solely responsible for final employment decisions. You must not make automated decisions about candidates without a meaningful human review step.`,
  },
  {
    title: "6. Data and privacy",
    content: `Our Privacy Policy (at /legal/privacy) explains how we process personal data. By using the platform you confirm you have lawful grounds to process any candidate data you upload.`,
  },
  {
    title: "7. Intellectual property",
    content: `The PATHS platform, branding, and all software are owned by PATHS Ltd. You retain ownership of data you upload. You grant us a limited licence to process that data to deliver the service.`,
  },
  {
    title: "8. Billing and refunds",
    content: `Subscription plans are billed monthly or annually. Refunds are not available for partial billing periods. We may change pricing on 30 days' notice. If you cancel, your access continues until the end of the paid period.`,
  },
  {
    title: "9. Limitation of liability",
    content: `To the maximum extent permitted by law, PATHS Ltd shall not be liable for indirect, incidental, or consequential damages. Our total liability in any 12-month period shall not exceed the fees you paid to us in that period.`,
  },
  {
    title: "10. Governing law",
    content: `These Terms are governed by English law. Disputes shall be resolved in the courts of England and Wales.`,
  },
  {
    title: "11. Changes",
    content: `We may update these Terms. We will notify you by email and in-app banner at least 14 days before material changes take effect. Continued use after that date constitutes acceptance.`,
  },
  {
    title: "12. Contact",
    content: `PATHS Ltd\nEmail: legal@paths.ai`,
  },
];

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-heading text-4xl font-bold mb-2">Terms of Service</h1>
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
