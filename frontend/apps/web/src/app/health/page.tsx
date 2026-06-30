"use client";

import { useApiHealth } from "@/lib/hooks";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";

/**
 * Diagnostic route: verifies the browser can reach `GET /api/v1/health`.
 * Not linked from production navigation; open `/_health` manually when debugging connectivity.
 */
export default function HealthCheckPage() {
  const { data, isLoading, isError, error, refetch } = useApiHealth();

  if (isLoading) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8">
        <p className="font-heading text-lg font-semibold text-destructive">
          Backend unreachable
        </p>
        <p className="text-sm text-muted-foreground">
          {error?.message ?? "Could not complete GET /api/v1/health."}
        </p>
        <Button type="button" variant="secondary" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8">
        <p className="text-muted-foreground">
          The health endpoint returned no JSON body. Check the API and try again.
        </p>
        <Button type="button" variant="secondary" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-4 p-8">
      <h1 className="font-heading text-2xl font-bold tracking-tight">API health</h1>
      <p
        className={cn(
          "text-sm",
          data.status === "ok" ? "text-emerald-600" : "text-muted-foreground",
        )}
      >
        status: <span className="font-mono">{data.status}</span>
      </p>
      <pre className="glass rounded-xl p-4 text-xs overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
      <Button type="button" variant="outline" size="sm" onClick={() => void refetch()}>
        Refresh
      </Button>
    </div>
  );
}
