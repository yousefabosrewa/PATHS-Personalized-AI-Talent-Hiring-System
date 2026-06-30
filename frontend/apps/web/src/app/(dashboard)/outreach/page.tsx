"use client";

/**
 * Legacy /outreach route — folded into the unified Outreach workspace at
 * /org/matching (fix4.md §2). Anyone landing here from an old deep link is
 * redirected client-side; we keep the route file so the path itself doesn't
 * 404 while the redirect happens.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export default function LegacyOutreachRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/org/matching");
  }, [router]);

  return (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      Opening the Outreach workspace…
    </div>
  );
}
