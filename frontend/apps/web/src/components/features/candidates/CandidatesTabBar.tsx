"use client";

/**
 * Shared tab bar for everything under /candidates (fix2.md §2).
 *
 *   /candidates          → Pipeline
 *   /candidates/sources  → Candidate Sources (CSV import, duplicates,
 *                          incomplete profiles, default matching params)
 *
 * Sub-pages of /candidates/[id]/* don't render this bar.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Pipeline",    href: "/candidates" },
  { label: "Find Talent", href: "/candidates/outreach" },
  { label: "Sources",     href: "/candidates/sources" },
  { label: "Duplicates",  href: "/candidates/duplicates" },
];

export function CandidatesTabBar() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 border-b border-border/40 -mb-px">
      {TABS.map(({ label, href }) => {
        const active =
          href === "/candidates"
            ? pathname === "/candidates"
            : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "shrink-0 px-4 py-2 text-[13px] font-medium border-b-2 transition-colors",
              active
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
