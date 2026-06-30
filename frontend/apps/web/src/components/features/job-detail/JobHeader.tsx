"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Pencil, Archive, ArchiveRestore, Trash2 } from "lucide-react";
import { useUpdateJob, useDeleteJob } from "@/lib/hooks";
import type { JobDetail } from "@/types";

interface Props {
  job: JobDetail;
}

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  inactive: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  closed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  draft: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

export function JobHeader({ job }: Props) {
  const router = useRouter();
  const updateJob = useUpdateJob(job.id);
  const deleteJob = useDeleteJob(job.id);

  const isArchived = job.status === "closed";
  const busy = updateJob.isPending || deleteJob.isPending;

  function handleEdit() {
    router.push(`/jobs/${job.id}/edit`);
  }

  function handleArchiveToggle() {
    updateJob.mutate(
      isArchived
        ? { status: "active", is_active: true }
        : { status: "closed", is_active: false },
      {
        onSuccess: () =>
          toast.success(isArchived ? "Job restored" : "Job archived"),
        onError: () =>
          toast.error(
            isArchived ? "Could not restore job" : "Could not archive job",
          ),
      },
    );
  }

  function handleDelete() {
    const ok = window.confirm(
      `Delete "${job.title}"?\n\nThis permanently removes the job along with its ` +
        `applications, interviews, assessments and decisions. This cannot be undone.`,
    );
    if (!ok) return;
    deleteJob.mutate(undefined, {
      onSuccess: () => {
        toast.success("Job deleted");
        router.push("/jobs");
      },
      onError: () =>
        toast.error(
          "Could not delete this job. It may still have linked records.",
        ),
    });
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-2xl font-bold">{job.title}</h1>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              STATUS_COLORS[job.status] ?? STATUS_COLORS.inactive
            }`}
          >
            {job.status}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {[job.department, job.location, job.employmentType]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <DropdownMenu>
          <DropdownMenuTrigger
            disabled={busy}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md p-0 text-sm font-medium hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
          >
            <MoreHorizontal className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem className="gap-2" onClick={handleEdit}>
              <Pencil className="h-3.5 w-3.5" /> Edit Job
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2" onClick={handleArchiveToggle}>
              {isArchived ? (
                <>
                  <ArchiveRestore className="h-3.5 w-3.5" /> Unarchive
                </>
              ) : (
                <>
                  <Archive className="h-3.5 w-3.5" /> Archive
                </>
              )}
            </DropdownMenuItem>
            <DropdownMenuItem
              className="gap-2 text-destructive focus:text-destructive"
              onClick={handleDelete}
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
