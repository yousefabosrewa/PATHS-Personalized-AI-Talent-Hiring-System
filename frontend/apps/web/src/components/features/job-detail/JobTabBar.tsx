"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

interface Tab {
  label: string;
  href: string;
}

interface Props {
  jobId: string;
}

export function JobTabBar({ jobId }: Props) {
  const pathname = usePathname();
  const base = `/jobs/${jobId}`;

  const tabs: Tab[] = [
    { label: "Overview", href: base },
    { label: "Screening", href: `${base}/screening` },
    { label: "Candidates", href: `${base}/candidates` },
    { label: "Assessment", href: `${base}/assessment` },
    { label: "Interviews", href: `${base}/interviews` },
    { label: "Decision", href: `${base}/decision` },
  ];

  return (
    <nav className="flex gap-1 border-b border-border overflow-x-auto">
      {tabs.map(({ label, href }) => {
        const active =
          href === base ? pathname === base : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "shrink-0 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
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
