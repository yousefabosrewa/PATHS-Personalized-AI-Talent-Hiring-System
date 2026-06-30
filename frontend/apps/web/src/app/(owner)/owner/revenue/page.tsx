"use client";

import { useState } from "react";
import { TrendingUp, Calendar } from "lucide-react";
import { useRevenueAnalytics, useRevenueSummary } from "@/lib/hooks";

function fmt(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

export default function RevenueAnalyticsPage() {
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  const [from, setFrom] = useState(thirtyDaysAgo.toISOString().slice(0, 10));
  const [to, setTo] = useState(today.toISOString().slice(0, 10));

  const { data: points = [], isLoading } = useRevenueAnalytics({ from, to });
  const { data: summary } = useRevenueSummary();

  const total = points.reduce((acc, p) => acc + p.amount_cents, 0);
  const maxAmount = Math.max(...points.map((p) => p.amount_cents), 1);

  return (
    <div className="mx-auto max-w-5xl px-8 py-10 space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Revenue Analytics</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Invoice payments over time.
          </p>
        </div>
      </div>

      {/* Date filters */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/50 bg-white p-4 shadow-sm">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <label className="text-sm font-medium">From</label>
        <input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          className="rounded-lg border border-border/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <label className="text-sm font-medium">To</label>
        <input
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="rounded-lg border border-border/50 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
        <span className="ml-auto text-sm font-semibold text-primary">
          Total: {fmt(total)}
        </span>
      </div>

      {/* Summary row */}
      {summary && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "MRR", value: fmt(summary.mrr_cents) },
            { label: "ARR", value: fmt(summary.arr_cents) },
            { label: "Churn (30d)", value: `${(summary.churn_rate_30d * 100).toFixed(2)}%` },
          ].map((m) => (
            <div key={m.label} className="rounded-xl border border-border/50 bg-white p-4 shadow-sm text-center">
              <p className="text-xs font-semibold uppercase text-muted-foreground">{m.label}</p>
              <p className="mt-1 text-2xl font-bold">{m.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Bar chart */}
      <div className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
        <h2 className="mb-4 font-heading text-lg font-semibold">Daily Revenue</h2>
        {isLoading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : points.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No paid invoices in this date range.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <div className="flex h-48 items-end gap-1.5" style={{ minWidth: `${points.length * 28}px` }}>
              {points.map((p, i) => {
                const pct = (p.amount_cents / maxAmount) * 100;
                return (
                  <div key={i} className="flex flex-1 flex-col items-center gap-1 group">
                    <div
                      className="w-full rounded-t-sm bg-primary/70 group-hover:bg-primary transition-colors relative"
                      style={{ height: `${pct}%`, minHeight: 2 }}
                    >
                      <span className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-foreground px-1 py-0.5 text-[9px] text-white opacity-0 group-hover:opacity-100 transition-opacity">
                        {fmt(p.amount_cents)}
                      </span>
                    </div>
                    <span className="rotate-45 text-[9px] text-muted-foreground">
                      {p.date?.slice(5) ?? ""}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      {points.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/30 bg-muted/20 text-xs font-semibold uppercase text-muted-foreground">
                <th className="px-5 py-3 text-left">Date</th>
                <th className="px-5 py-3 text-right">Amount</th>
                <th className="px-5 py-3 text-right">Currency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {[...points].reverse().map((p, i) => (
                <tr key={i} className="hover:bg-muted/10">
                  <td className="px-5 py-2.5 font-mono text-xs">{p.date}</td>
                  <td className="px-5 py-2.5 text-right font-semibold">
                    {fmt(p.amount_cents)}
                  </td>
                  <td className="px-5 py-2.5 text-right text-muted-foreground">
                    {p.currency}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
