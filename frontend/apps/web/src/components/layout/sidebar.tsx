"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Users, Briefcase, CheckSquare,
  ChevronLeft, ChevronRight,
  Building2, Shield, ShieldCheck, Calendar, Sparkles, ClipboardCheck,
  Library, Contact, CalendarClock,
} from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { BrandLogo } from "@/components/layout/brand-logo";
import { useUIStore } from "@/lib/stores/ui.store";
import { usePendingApprovals } from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";

// Approvals is a manager-level decision queue — only HR Managers / Hiring
// Managers (and admins) see it. Regular HR / recruiters do not.
const APPROVALS_ROLES = new Set([
  "hr_manager",
  "hiring_manager",
  "manager",
  "org_admin",
  "admin",
]);

/**
 * Company workspace sidebar — 4 groups, organized around the hiring
 * workflow rather than around individual agents.
 *
 * fix2.md §2 / §9: removed three top-level sidebar entries:
 *   - "Candidate Sources"     → moved inside /candidates as a tab
 *   - "CV Processing"         → folded into /candidates → Sources (CSV upload)
 *   - "Duplicate Candidates"  → folded into /candidates → Sources (Duplicates)
 *
 * Old routes still exist on the backend; the frontend redirects them
 * client-side from their own page.tsx files so deep links don't 404.
 */
const navItems = [
  {
    group: "Workspace",
    items: [
      { label: "Dashboard",         href: "/dashboard",         icon: LayoutDashboard },
      { label: "Jobs",              href: "/jobs",              icon: Briefcase },
      { label: "Candidates",        href: "/candidates",        icon: Users },
    ],
  },
  {
    group: "Hiring Workflow",
    // Outreach moved into Candidates → Outreach (/candidates/outreach). The
    // standalone sidebar entry was removed; /org/matching still resolves for
    // deep links and renders the same unified search workspace.
    items: [
      { label: "Approvals",       href: "/approvals",         icon: CheckSquare, badge: true },
      { label: "Assessments",     href: "/org/assessments",   icon: ClipboardCheck },
      { label: "Interviews",      href: "/interviews",        icon: Calendar },
      { label: "Source Candidate", href: "/source-candidate", icon: Sparkles },
    ],
  },
  {
    group: "AI Operations",
    // fix8&9 Update 1 — "Job Description Analysis" was removed from the
    // org sidebar; the feature now lives on the candidate side at
    // /candidate/profile/job-description-analysis. The /org/job-ingestion
    // route itself stays available (it's the job-import pipeline, not a
    // JD analyser) but is no longer surfaced under a misleading label.
    items: [
      { label: "Company Knowledge Base",   href: "/org/knowledge-base",      icon: Library },
      { label: "Fairness & Compliance",    href: "/org/bias",                icon: ShieldCheck },
      { label: "Contact Finder",           href: "/org/contact-enrichment",  icon: Contact },
    ],
  },
  {
    group: "Organization",
    items: [
      { label: "Members",        href: "/settings/members",      icon: Users },
      { label: "Organization",   href: "/settings/organization", icon: Building2 },
      { label: "Calendar",       href: "/settings/calendar",     icon: CalendarClock },
      { label: "Audit Log",      href: "/audit",                 icon: Shield },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { data: pending = [] } = usePendingApprovals();
  const pendingCount = pending.length;

  const { user: authUser } = useAuthStore();
  const role = String(authUser?.role ?? authUser?.accountType ?? "").toLowerCase();
  const canSeeApprovals = APPROVALS_ROLES.has(role);

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 64 : 240 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="relative flex h-screen flex-col border-r border-sidebar-border bg-sidebar overflow-hidden shrink-0"
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-center px-3 border-b border-sidebar-border shrink-0">
        <Link href="/dashboard" className="flex items-center justify-center min-w-0">
          <BrandLogo
            className={cn(
              "transition-all",
              sidebarCollapsed ? "h-11 w-11" : "h-14 w-auto max-w-[200px]",
            )}
          />
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-5">
        {navItems.map((group) => (
          <div key={group.group}>
            <AnimatePresence>
              {!sidebarCollapsed && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60"
                >
                  {group.group}
                </motion.p>
              )}
            </AnimatePresence>
            <ul className="space-y-0.5">
              {group.items
                .filter((item) => item.href !== "/approvals" || canSeeApprovals)
                .map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "group relative flex items-center gap-2.5 rounded-md px-2 py-2 text-sm font-medium transition-all duration-150",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
                      )}
                    >
                      {active && (
                        <motion.div
                          layoutId="sidebar-active"
                          className="absolute inset-0 rounded-md bg-sidebar-accent"
                          transition={{ type: "spring", stiffness: 400, damping: 35 }}
                        />
                      )}
                      <Icon
                        className={cn(
                          "relative h-4 w-4 shrink-0 transition-colors",
                          active ? "text-primary" : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/80"
                        )}
                      />
                      <AnimatePresence>
                        {!sidebarCollapsed && (
                          <motion.span
                            initial={{ opacity: 0, x: -6 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -6 }}
                            transition={{ duration: 0.16 }}
                            className="relative flex-1 truncate"
                          >
                            {item.label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                      {item.badge && pendingCount > 0 && !sidebarCollapsed && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="relative ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/20 px-1.5 text-[10px] font-bold text-primary ring-1 ring-primary/30"
                        >
                          {pendingCount}
                        </motion.span>
                      )}
                      {item.badge && pendingCount > 0 && sidebarCollapsed && (
                        <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-primary" />
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-sidebar-border bg-sidebar text-muted-foreground shadow-sm transition-colors hover:text-foreground z-10"
        aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {sidebarCollapsed
          ? <ChevronRight className="h-3 w-3" />
          : <ChevronLeft className="h-3 w-3" />}
      </button>
    </motion.aside>
  );
}
