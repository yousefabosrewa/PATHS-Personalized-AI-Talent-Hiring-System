"use client";

import { Globe, TrendingUp, Users, MousePointerClick } from "lucide-react";
import { useMarketingAnalytics } from "@/lib/hooks";

export default function OwnerMarketingPage() {
  const { data, isLoading } = useMarketingAnalytics();

  return (
    <div className="mx-auto max-w-4xl px-8 py-10 space-y-8">
      <div>
        <h1 className="font-heading text-3xl font-bold">Marketing Analytics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          UTM funnel from analytics events — sessions, signups, conversions.
        </p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-border/40 bg-muted/20" />
          ))}
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { label: "Sessions", value: data.sessions, icon: Globe },
              { label: "Signups", value: data.signups, icon: Users },
              { label: "Conversions", value: data.conversions, icon: MousePointerClick },
            ].map((m) => {
              const Icon = m.icon;
              return (
                <div key={m.label} className="rounded-xl border border-border/50 bg-white p-5 shadow-sm">
                  <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                    <Icon className="h-4 w-4 text-primary" />
                    {m.label}
                  </div>
                  <p className="text-3xl font-bold">{m.value.toLocaleString()}</p>
                </div>
              );
            })}
          </div>

          {data.by_utm_source.length > 0 ? (
            <div className="rounded-xl border border-border/50 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-border/40 p-5">
                <h2 className="font-heading text-lg font-semibold">By UTM Source</h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/30 bg-muted/20 text-xs font-semibold uppercase text-muted-foreground">
                    <th className="px-5 py-3 text-left">Source</th>
                    <th className="px-5 py-3 text-right">Sessions</th>
                    <th className="px-5 py-3 text-right">Signups</th>
                    <th className="px-5 py-3 text-right">Conv. rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/20">
                  {data.by_utm_source.map((row) => (
                    <tr key={row.source} className="hover:bg-muted/10">
                      <td className="px-5 py-2.5 font-medium">{row.source}</td>
                      <td className="px-5 py-2.5 text-right">{row.sessions}</td>
                      <td className="px-5 py-2.5 text-right">{row.signups}</td>
                      <td className="px-5 py-2.5 text-right text-muted-foreground">
                        {row.sessions > 0
                          ? `${((row.signups / row.sessions) * 100).toFixed(1)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-xl border border-border/40 bg-muted/10 p-8 text-center">
              <Globe className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
              <p className="text-sm font-medium text-muted-foreground">
                No UTM source data yet.
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Add UTM parameters to your marketing links to track traffic sources.
              </p>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
