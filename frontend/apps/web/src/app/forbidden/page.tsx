"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6">
      <ShieldAlert className="h-12 w-12 text-muted-foreground" aria-hidden />
      <h1 className="font-heading text-2xl font-bold text-foreground">Access denied</h1>
      <p className="max-w-md text-center text-sm text-muted-foreground">
        You do not have permission to open this area. Sign in with the right account type or go back
        to your dashboard.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        <Button asChild variant="default">
          <Link href="/login">Sign in</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/dashboard">Organization dashboard</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/candidate/dashboard">Candidate portal</Link>
        </Button>
      </div>
    </div>
  );
}
