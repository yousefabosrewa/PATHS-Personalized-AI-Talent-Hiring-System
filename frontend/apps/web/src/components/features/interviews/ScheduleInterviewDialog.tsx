"use client";

/**
 * ScheduleInterviewDialog
 *
 * Modal for scheduling an interview for a candidate.
 * Calls POST /api/v1/interviews (via useScheduleInterview hook).
 *
 * Usage:
 *   <ScheduleInterviewDialog
 *     jobId={job.id}
 *     candidateId={candidate.id}
 *     applicationId={application.id}
 *     trigger={<Button>Schedule Interview</Button>}
 *     onScheduled={() => refetch()}
 *   />
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CalendarDays, Loader2, Video } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useScheduleInterview } from "@/lib/hooks";

// ── Validation schema ────────────────────────────────────────────────────────

const schema = z.object({
  interview_type: z.enum(["hr", "technical", "mixed"]),
  scheduled_start: z.string().min(1, "Start date/time is required"),
  scheduled_end: z.string().min(1, "End date/time is required"),
  meeting_url: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  interviewer_notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  jobId: string;
  candidateId: string;
  applicationId: string;
  orgId: string;
  trigger: React.ReactNode;
  onScheduled?: () => void;
}

export function ScheduleInterviewDialog({
  applicationId,
  orgId,
  trigger,
  onScheduled,
}: Props) {
  const [open, setOpen] = useState(false);
  const { mutateAsync: schedule, isPending } = useScheduleInterview();

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      interview_type: "hr",
      scheduled_start: "",
      scheduled_end: "",
      meeting_url: "",
      interviewer_notes: "",
    },
  });

  const interviewType = watch("interview_type");

  async function onSubmit(values: FormValues) {
    try {
      await schedule({
        application_id: applicationId,
        organization_id: orgId,
        interview_type: values.interview_type,
        slot_start: new Date(values.scheduled_start).toISOString(),
        slot_end: new Date(values.scheduled_end).toISOString(),
        manual_meeting_url: values.meeting_url || undefined,
      });
      toast.success("Interview scheduled successfully");
      reset();
      setOpen(false);
      onScheduled?.();
    } catch {
      toast.error("Failed to schedule interview — please try again.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={trigger as React.ReactElement} />

      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-primary" />
            Schedule Interview
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          {/* Interview type */}
          <div className="space-y-1.5">
            <Label htmlFor="interview_type">Interview Type</Label>
            <Select
              value={interviewType}
              onValueChange={(v) => setValue("interview_type", v as FormValues["interview_type"])}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hr">HR Interview</SelectItem>
                <SelectItem value="technical">Technical Interview</SelectItem>
                <SelectItem value="mixed">Mixed (HR + Technical)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Date/time range */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="scheduled_start">Start</Label>
              <Input
                id="scheduled_start"
                type="datetime-local"
                {...register("scheduled_start")}
                className="text-sm"
              />
              {errors.scheduled_start && (
                <p className="text-xs text-destructive">{errors.scheduled_start.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="scheduled_end">End</Label>
              <Input
                id="scheduled_end"
                type="datetime-local"
                {...register("scheduled_end")}
                className="text-sm"
              />
              {errors.scheduled_end && (
                <p className="text-xs text-destructive">{errors.scheduled_end.message}</p>
              )}
            </div>
          </div>

          {/* Meeting URL */}
          <div className="space-y-1.5">
            <Label htmlFor="meeting_url" className="flex items-center gap-1.5">
              <Video className="h-3.5 w-3.5" />
              Meeting URL <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="meeting_url"
              placeholder="https://meet.google.com/…"
              {...register("meeting_url")}
            />
            {errors.meeting_url && (
              <p className="text-xs text-destructive">{errors.meeting_url.message}</p>
            )}
          </div>

          {/* Interviewer notes */}
          <div className="space-y-1.5">
            <Label htmlFor="interviewer_notes">
              Notes <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="interviewer_notes"
              placeholder="Topics to cover, special instructions…"
              {...register("interviewer_notes")}
            />
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending} className="gap-2">
              {isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Schedule
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
