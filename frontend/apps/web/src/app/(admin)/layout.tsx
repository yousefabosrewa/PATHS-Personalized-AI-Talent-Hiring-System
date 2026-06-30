"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Building2, Users, FileSearch, Activity, ShieldCheck, LogOut,
  Bot, Cpu, Flag, Settings, BarChart3,
} from "lucide-react";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";

const navItems = [
  { href: "/admin",                       label: "Overview",       icon: Activity },
  { href: "/admin/analytics",            label: "Analytics",      icon: BarChart3 },
  { href: "/admin/organization-requests", label: "Access Requests", icon: FileSearch },
  { href: "/admin/organizations",         label: "Organizations",  icon: Building2 },
  { href: "/admin/users",                 label: "Users",          icon: Users },
  { href: "/admin/agents",               label: "Agent Monitor",  icon: Bot },
  { href: "/admin/system",               label: "System Health",  icon: Cpu },
  { href: "/admin/flags",                label: "Feature Flags",  icon: Flag },
  { href: "/admin/audit",                label: "Audit Log",      icon: ShieldCheck },
  { href: "/admin/settings",             label: "Settings",       icon: Settings },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, _hasHydrated, logout } = useAuthStore();

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.replace("/login?next=/admin");
      return;
    }
    if (!user?.isPlatformAdmin && user?.accountType !== "platform_admin") {
      router.replace("/forbidden");
    }
  }, [_hasHydrated, isAuthenticated, user, router]);

  if (!_hasHydrated || !isAuthenticated || !(user?.isPlatformAdmin || user?.accountType === "platform_admin")) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border/50 bg-white/60 backdrop-blur-sm lg:flex">
        <div className="border-b border-border/40 p-6">
          <p className="font-heading text-lg font-bold">PATHS Admin</p>
          <p className="text-xs text-muted-foreground">Platform control plane</p>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border/40 p-3">
          <div className="mb-2 px-3 py-2">
            <p className="text-xs text-muted-foreground">Signed in as</p>
            <p className="truncate text-sm font-medium">{user?.email}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/40 hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
