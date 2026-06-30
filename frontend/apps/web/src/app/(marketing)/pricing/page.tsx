import type { Metadata } from "next";

import PricingPage from "./pricing-client";

// Server Component: owns the route metadata. The interactive UI lives in the
// "use client" sibling module (pricing-client.tsx) — Next.js disallows
// exporting `metadata` from a Client Component.
export const metadata: Metadata = {
  title: "Pricing — PATHS AI Hiring",
  description:
    "Simple, transparent pricing for AI-powered hiring. Start free, scale as you grow.",
};

export default function Page() {
  return <PricingPage />;
}
