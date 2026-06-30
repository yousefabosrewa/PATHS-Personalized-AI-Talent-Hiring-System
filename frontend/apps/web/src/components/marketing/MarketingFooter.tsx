"use client";

import Link from "next/link";
import { Shield, Globe, FileText } from "lucide-react";
import { PathsWordmark } from "@/components/ui/PathsWordmark";

/** Clears stored consent so the banner re-appears on next page load. */
function CookieSettingsButton() {
  return (
    <button
      onClick={() => {
        localStorage.removeItem("paths-cookie-consent");
        window.location.reload();
      }}
      className="text-[12px] text-slate-400 hover:text-slate-600 underline underline-offset-2 transition-colors"
    >
      Cookie settings
    </button>
  );
}

const cols = [
  {
    heading: "Product",
    links: [
      { label: "How it Works",   href: "/how-it-works"    },
      { label: "For Candidates", href: "/for-candidates"  },
      { label: "For Companies",  href: "/for-companies"   },
      { label: "Open Jobs",       href: "/careers"          },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About PATHS",     href: "#"                },
      { label: "Privacy Policy",  href: "/legal/privacy"   },
      { label: "Terms of Service",href: "/legal/terms"     },
      { label: "Platform Status", href: "/status"          },
      { label: "Contact",         href: "#"                },
    ],
  },
  {
    heading: "Get Started",
    links: [
      { label: "Create Profile", href: "/candidate-signup" },
      { label: "Sign In",         href: "/login"            },
      { label: "Request Demo",    href: "#"                 },
      { label: "API Docs",        href: "#"                 },
    ],
  },
];

const compliance = [
  { icon: Shield,   label: "Egypt PDPL"    },
  { icon: Globe,    label: "EU AI Act"      },
  { icon: FileText, label: "EEOC Compliant" },
];

export default function MarketingFooter() {
  return (
    <footer className="border-t border-slate-100 bg-white">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-4">

          {/* ── Brand column ─────────────────────────────────── */}
          <div className="space-y-5">
            <Link href="/" className="inline-block">
              <PathsWordmark variant="footer" />
            </Link>

            <p className="text-[13px] leading-relaxed text-slate-500">
              Evidence-driven, human-in-the-loop hiring that reduces bias
              and accelerates decisions.
            </p>

            {/* Compliance badges */}
            <div className="flex flex-wrap gap-2 pt-1">
              {compliance.map(({ icon: Icon, label }) => (
                <span
                  key={label}
                  className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10.5px] font-medium text-slate-500"
                >
                  <Icon className="h-3 w-3" />
                  {label}
                </span>
              ))}
            </div>
          </div>

          {/* ── Link columns ─────────────────────────────────── */}
          {cols.map((col) => (
            <div key={col.heading}>
              <p className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                {col.heading}
              </p>
              <ul className="space-y-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-[13px] text-slate-500 transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* ── Bottom row ───────────────────────────────────────── */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-slate-100 pt-8 sm:flex-row">
          <p className="text-[12px] text-slate-400">
            © 2026 PATHS AI. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <CookieSettingsButton />
            <p className="text-[12px] text-slate-300">
              Built to reduce bias. Designed for transparency.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
