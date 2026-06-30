"use client";

/**
 * Cookie Consent Banner — PATHS-176
 *
 * Shown on first visit. Sets a localStorage key with the user's choice.
 * Analytics and marketing cookies are only enabled after explicit opt-in.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { X, Cookie } from "lucide-react";

type ConsentState = {
  analytics: boolean;
  marketing: boolean;
  decided: boolean;
};

const STORAGE_KEY = "paths-cookie-consent";

function load(): ConsentState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function save(state: ConsentState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function CookieConsent() {
  const [consent, setConsent] = useState<ConsentState | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [pendingAnalytics, setPendingAnalytics] = useState(false);
  const [pendingMarketing, setPendingMarketing] = useState(false);

  useEffect(() => {
    const stored = load();
    setConsent(stored);
  }, []);

  // Don't render if consent already given or on SSR
  if (consent?.decided) return null;
  if (consent === undefined) return null; // Hydrating

  const acceptAll = () => {
    const state = { analytics: true, marketing: true, decided: true };
    save(state);
    setConsent(state);
  };

  const rejectAll = () => {
    const state = { analytics: false, marketing: false, decided: true };
    save(state);
    setConsent(state);
  };

  const saveCustom = () => {
    const state = { analytics: pendingAnalytics, marketing: pendingMarketing, decided: true };
    save(state);
    setConsent(state);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border/50 bg-white shadow-2xl">
      <div className="mx-auto max-w-5xl px-6 py-4">
        {!showDetails ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <Cookie className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <p className="text-sm text-muted-foreground">
                We use cookies to improve your experience.{" "}
                <Link href="/legal/privacy" className="font-medium text-primary hover:underline">
                  Privacy policy
                </Link>
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowDetails(true)}
                className="rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium hover:bg-muted/30"
              >
                Customise
              </button>
              <button
                onClick={rejectAll}
                className="rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium hover:bg-muted/30"
              >
                Reject all
              </button>
              <button
                onClick={acceptAll}
                className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary/90"
              >
                Accept all
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Cookie settings</h3>
              <button
                onClick={() => setShowDetails(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Necessary — always on */}
            <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/10 p-3">
              <div>
                <p className="text-sm font-medium">Strictly necessary</p>
                <p className="text-xs text-muted-foreground">Session management, security. Cannot be disabled.</p>
              </div>
              <span className="text-xs font-semibold text-green-600">Always on</span>
            </div>

            {/* Analytics */}
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <div>
                <p className="text-sm font-medium">Analytics</p>
                <p className="text-xs text-muted-foreground">Help us understand how the platform is used.</p>
              </div>
              <button
                role="switch"
                aria-checked={pendingAnalytics}
                onClick={() => setPendingAnalytics((p) => !p)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                  pendingAnalytics ? "bg-primary" : "bg-gray-200"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    pendingAnalytics ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            {/* Marketing */}
            <div className="flex items-center justify-between rounded-lg border border-border/40 p-3">
              <div>
                <p className="text-sm font-medium">Marketing</p>
                <p className="text-xs text-muted-foreground">Track which campaigns brought you here.</p>
              </div>
              <button
                role="switch"
                aria-checked={pendingMarketing}
                onClick={() => setPendingMarketing((p) => !p)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                  pendingMarketing ? "bg-primary" : "bg-gray-200"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    pendingMarketing ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={rejectAll}
                className="rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium hover:bg-muted/30"
              >
                Reject all
              </button>
              <button
                onClick={saveCustom}
                className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary/90"
              >
                Save preferences
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
