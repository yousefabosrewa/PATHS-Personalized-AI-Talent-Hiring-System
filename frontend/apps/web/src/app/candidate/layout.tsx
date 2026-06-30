"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  LayoutDashboard, User, FileText, Briefcase, Settings, LogOut, Search,
  GraduationCap, FileSearch, TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { BrandLogo } from "@/components/layout/brand-logo";
import { useCandidateProfile } from "@/lib/hooks";
import { createEmptyCandidateProfile } from "@/lib/candidate/portal-profile";
import { useAuthStore } from "@/lib/stores/auth.store";

const NAV_LINKS = [
  { href: "/candidate/dashboard",                              label: "Dashboard",      Icon: LayoutDashboard },
  { href: "/candidate/discover",                               label: "Open Jobs",      Icon: Search          },
  { href: "/candidate/profile",                                label: "My Profile",     Icon: User            },
  // fix8&9 Update 1 — JD analysis lives on the candidate side now.
  { href: "/candidate/profile/job-description-analysis",       label: "JD Analysis",    Icon: FileSearch      },
  { href: "/candidate/learning-hub",                           label: "Learning Hub",   Icon: GraduationCap   },
  { href: "/candidate/documents",                              label: "Documents",      Icon: FileText        },
  { href: "/candidate/applications",                           label: "Applications",   Icon: Briefcase       },
  { href: "/candidate/development",                            label: "Development & Growth", Icon: TrendingUp },
];

export default function CandidateLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, _hasHydrated, user, logout } = useAuthStore();
  const { data: profile = createEmptyCandidateProfile(), isLoading } = useCandidateProfile();

  const isCandidateSession =
    user?.accountType === "candidate" || user?.role === "candidate";

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!isCandidateSession) {
      router.replace("/dashboard");
    }
  }, [_hasHydrated, isAuthenticated, isCandidateSession, router]);
  const displayName = profile.fullName.trim() || (isLoading ? "…" : "Candidate");
  const displayTitle = profile.currentTitle.trim() || (isLoading ? "" : "—");

  if (!_hasHydrated || !isAuthenticated || !isCandidateSession) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border/40 bg-navy-950 lg:flex">
        {/* Logo */}
        <div className="border-b border-border/40 px-5 py-5">
          <Link href="/" className="flex flex-col items-start gap-1.5">
            <BrandLogo className="h-14 w-auto max-w-[170px]" />
            <span className="pl-0.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Candidate Portal
            </span>
          </Link>
        </div>

        {/* User info */}
        <div className="border-b border-border/40 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/20 text-sm font-bold text-primary mb-2">
            {displayName.charAt(0)}
          </div>
          <p className="text-sm font-semibold text-foreground truncate">{displayName}</p>
          <p className="text-[11px] text-muted-foreground truncate">{displayTitle}</p>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {NAV_LINKS.map(({ href, label, Icon }) => {
            const active = pathname === href || (href !== "/candidate/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Footer
            Removed the prior /candidate/settings link — that route does not
            exist and would 404. Profile editing lives at /candidate/profile/edit
            which is reachable from the My Profile page. If a generic candidate
            settings surface is needed later (notifications, language, privacy),
            add it as a real page first, then re-introduce a sidebar entry. */}
        <div className="border-t border-border/40 p-4 space-y-1">
          <Link href="/candidate/profile/edit" className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-all">
            <Settings className="h-4 w-4" /> Edit Profile
          </Link>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-all"
          >
            <LogOut className="h-4 w-4" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-border/40 bg-background/90 backdrop-blur px-4 py-3">
        <Link href="/" className="flex items-center">
          <BrandLogo className="h-9 w-auto max-w-[130px]" />
        </Link>
        <div className="flex items-center gap-1">
          {NAV_LINKS.map(({ href, Icon }) => (
            <Link key={href} href={href} className={cn("flex h-9 w-9 items-center justify-center rounded-lg transition-colors", pathname.startsWith(href) ? "bg-primary/15 text-primary" : "text-muted-foreground")}>
              <Icon className="h-4 w-4" />
            </Link>
          ))}
        </div>
      </div>

      {/* Main */}
      <main className="flex-1 overflow-y-auto lg:pt-0 pt-16">
        {children}
      </main>
    </div>
  );
}
