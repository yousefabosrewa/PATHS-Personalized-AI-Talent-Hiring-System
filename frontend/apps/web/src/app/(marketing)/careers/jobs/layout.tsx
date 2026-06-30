import type { Metadata } from "next";

// Metadata must live in a Server Component; the job board page itself is a
// Client Component ("use client"), which cannot export `metadata`.
export const metadata: Metadata = {
  title: "Jobs — PATHS AI Hiring",
  description:
    "Browse open positions from companies using PATHS AI hiring platform.",
};

export default function JobsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
