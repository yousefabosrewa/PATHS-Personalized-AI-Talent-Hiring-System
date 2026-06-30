"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/layout/brand-logo";
import { cn } from "@/lib/utils/cn";

const navLinks = [
  { label: "How it Works",  href: "/how-it-works"   },
  { label: "For Candidates", href: "/for-candidates" },
  { label: "For Companies",  href: "/for-companies"  },
  { label: "Jobs",            href: "/careers"        },
];

export default function MarketingNav() {
  const pathname    = usePathname();
  const [scrolled,    setScrolled]    = useState(false);
  const [mobileOpen,  setMobileOpen]  = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "sticky top-0 z-50 w-full transition-all duration-300",
        scrolled
          ? "bg-white/95 backdrop-blur-md shadow-[0_1px_0_oklch(0.90_0.010_252)]"
          : "bg-white/80 backdrop-blur-sm",
      )}
    >
      <nav className="mx-auto flex h-[68px] max-w-7xl items-center justify-between px-5 sm:px-8">

        {/* ── Logo ─────────────────────────────────────────── */}
        <Link href="/" className="flex items-center shrink-0 py-1">
          <BrandLogo className="h-11 w-auto" />
        </Link>

        {/* ── Desktop links ────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-0.5">
          {navLinks.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "relative rounded-lg px-3.5 py-2 text-[13.5px] font-medium transition-colors duration-150",
                  active
                    ? "text-foreground"
                    : "text-slate-500 hover:text-foreground",
                )}
              >
                {active && (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute inset-0 rounded-lg bg-slate-100"
                    transition={{ type: "spring", stiffness: 400, damping: 35 }}
                  />
                )}
                <span className="relative">{link.label}</span>
              </Link>
            );
          })}
        </div>

        {/* ── Desktop CTAs ─────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-2.5">
          <Link
            href="/login"
            className="text-[13.5px] font-medium text-slate-500 hover:text-foreground transition-colors px-3 py-2"
          >
            Sign In
          </Link>
          <Button
            size="sm"
            className={cn(
              "h-9 gap-1.5 rounded-lg px-4 text-[13px] font-semibold",
              "bg-[oklch(0.50_0.22_264)] text-white",
              "hover:bg-[oklch(0.46_0.24_264)] active:scale-[0.97]",
              "shadow-[0_1px_3px_oklch(0.50_0.22_264/30%),0_4px_12px_oklch(0.50_0.22_264/16%)]",
              "transition-all duration-150",
            )}
            asChild
          >
            <Link href="/candidate-signup">
              Get Started <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>

        {/* ── Mobile hamburger ─────────────────────────────── */}
        <button
          className="md:hidden flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:text-foreground hover:bg-slate-100 transition-colors"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {/* ── Mobile drawer ────────────────────────────────────── */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            key="mobile-menu"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="md:hidden overflow-hidden border-t border-slate-100 bg-white"
          >
            <div className="flex flex-col gap-1 p-4">
              {navLinks.map((link) => {
                const active = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={cn(
                      "rounded-lg px-4 py-2.5 text-sm font-medium transition-colors",
                      active
                        ? "bg-slate-100 text-foreground"
                        : "text-slate-500 hover:bg-slate-50 hover:text-foreground",
                    )}
                  >
                    {link.label}
                  </Link>
                );
              })}

              <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
                <Link
                  href="/login"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-4 py-2.5 text-sm font-medium text-slate-500 hover:bg-slate-50 hover:text-foreground transition-colors"
                >
                  Sign In
                </Link>
                <Button
                  className="gap-1.5 bg-[oklch(0.50_0.22_264)] text-white hover:bg-[oklch(0.46_0.24_264)]"
                  asChild
                >
                  <Link href="/candidate-signup" onClick={() => setMobileOpen(false)}>
                    Get Started <ChevronRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
