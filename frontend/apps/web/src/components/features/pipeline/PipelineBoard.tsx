"use client";

import { useState, useCallback, useEffect } from "react";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { GripVertical, RotateCcw } from "lucide-react";
import { PipelineColumn } from "./PipelineColumn";
import { CandidateCard } from "./CandidateCard";
import { useMoveApplicationStage } from "@/lib/hooks";
import type { CandidateInPipeline, KanbanStage, CandidateListPage } from "@/types";
import { KANBAN_STAGES, KANBAN_STAGE_LABELS } from "@/types";

interface Props {
  jobId: string;
  candidates: CandidateInPipeline[];
  stageCounts: Record<KanbanStage, number>;
}

// Column sortable ids are namespaced so they never collide with candidate
// applicationIds (uuids) or the per-stage droppable ids (the raw stage key).
const COL_PREFIX = "col-";

const orderStorageKey = (jobId: string) => `paths:pipeline-order:${jobId}`;

/** Read a saved per-job column order; fall back to the default on anything odd. */
function loadOrder(jobId: string): KanbanStage[] {
  if (typeof window === "undefined") return KANBAN_STAGES;
  try {
    const raw = window.localStorage.getItem(orderStorageKey(jobId));
    if (!raw) return KANBAN_STAGES;
    const parsed = JSON.parse(raw);
    if (
      Array.isArray(parsed) &&
      parsed.length === KANBAN_STAGES.length &&
      KANBAN_STAGES.every((s) => parsed.includes(s))
    ) {
      return parsed as KanbanStage[];
    }
  } catch {
    /* ignore — use default */
  }
  return KANBAN_STAGES;
}

// ── A column that can be dragged to reorder the workflow ──────────────────
function SortableColumn({
  stage,
  label,
  count,
  candidates,
  jobId,
}: {
  stage: KanbanStage;
  label: string;
  count: number;
  candidates: CandidateInPipeline[];
  jobId: string;
}) {
  const {
    setNodeRef,
    setActivatorNodeRef,
    listeners,
    attributes,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: `${COL_PREFIX}${stage}` });

  const style: React.CSSProperties = {
    transform: transform
      ? `translate3d(${transform.x}px, ${transform.y}px, 0)`
      : undefined,
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 20 : undefined,
  };

  return (
    <div ref={setNodeRef} style={style} className="h-full">
      <PipelineColumn
        stageKey={stage}
        label={label}
        count={count}
        candidates={candidates}
        jobId={jobId}
        dragHandle={
          // Only the grip starts a column drag — card dragging inside the
          // column body stays untouched.
          <button
            ref={setActivatorNodeRef}
            {...attributes}
            {...listeners}
            type="button"
            aria-label={`Reorder ${label} stage`}
            title="Drag to reorder this stage"
            className="cursor-grab text-muted-foreground/50 transition-colors hover:text-foreground active:cursor-grabbing"
          >
            <GripVertical className="h-3.5 w-3.5" />
          </button>
        }
      />
    </div>
  );
}

export function PipelineBoard({ jobId, candidates, stageCounts }: Props) {
  const qc = useQueryClient();
  const { mutateAsync: moveStage } = useMoveApplicationStage(jobId);
  const [activeCandidate, setActiveCandidate] = useState<CandidateInPipeline | null>(null);

  // Per-job column order, customizable by the user. Loaded after mount to
  // avoid an SSR/hydration mismatch.
  const [order, setOrder] = useState<KanbanStage[]>(KANBAN_STAGES);
  useEffect(() => {
    setOrder(loadOrder(jobId));
  }, [jobId]);

  const persistOrder = useCallback(
    (next: KanbanStage[]) => {
      setOrder(next);
      try {
        window.localStorage.setItem(orderStorageKey(jobId), JSON.stringify(next));
      } catch {
        /* ignore */
      }
    },
    [jobId],
  );

  const resetOrder = useCallback(() => {
    try {
      window.localStorage.removeItem(orderStorageKey(jobId));
    } catch {
      /* ignore */
    }
    setOrder(KANBAN_STAGES);
  }, [jobId]);

  const isCustomOrder = order.some((s, i) => s !== KANBAN_STAGES[i]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const byStage = useCallback(
    (stage: KanbanStage) => candidates.filter((c) => c.pipelineStage === stage),
    [candidates],
  );

  const handleDragStart = ({ active }: DragStartEvent) => {
    // Column reorder drags carry the col- prefix — no candidate overlay.
    if (String(active.id).startsWith(COL_PREFIX)) return;
    const found = candidates.find((c) => c.applicationId === active.id);
    setActiveCandidate(found ?? null);
  };

  const handleDragEnd = async ({ active, over }: DragEndEvent) => {
    setActiveCandidate(null);
    if (!over) return;

    const activeId = String(active.id);
    const overId = String(over.id);

    // ── Column reorder ──────────────────────────────────────────────────
    if (activeId.startsWith(COL_PREFIX)) {
      const fromStage = activeId.slice(COL_PREFIX.length) as KanbanStage;
      const overStage = (
        overId.startsWith(COL_PREFIX) ? overId.slice(COL_PREFIX.length) : overId
      ) as KanbanStage;
      const from = order.indexOf(fromStage);
      const to = order.indexOf(overStage);
      if (from !== -1 && to !== -1 && from !== to) {
        persistOrder(arrayMove(order, from, to));
      }
      return;
    }

    // ── Candidate card move ─────────────────────────────────────────────
    // `over` may resolve to a column droppable (stage key), a column sortable
    // (col-stage), or another candidate card (applicationId) — normalize all
    // three to the destination stage.
    let targetStage: KanbanStage | null = null;
    if (overId.startsWith(COL_PREFIX)) {
      targetStage = overId.slice(COL_PREFIX.length) as KanbanStage;
    } else if ((KANBAN_STAGES as readonly string[]).includes(overId)) {
      targetStage = overId as KanbanStage;
    } else {
      const overCard = candidates.find((c) => c.applicationId === overId);
      targetStage = overCard ? overCard.pipelineStage : null;
    }
    if (!targetStage) return;

    const appId = activeId;
    const cand = candidates.find((c) => c.applicationId === appId);
    if (!cand || cand.pipelineStage === targetStage) return;

    // Optimistic update: patch cache immediately
    const queryKey = ["jobCandidates", jobId, {}];
    const snapshot = qc.getQueryData<CandidateListPage>(queryKey);
    qc.setQueryData<CandidateListPage>(queryKey, (old) => {
      if (!old) return old;
      return {
        ...old,
        items: old.items.map((item) =>
          item.applicationId === appId
            ? { ...item, pipelineStage: targetStage as KanbanStage }
            : item,
        ),
      };
    });

    try {
      await moveStage({ appId, stage: targetStage });
    } catch {
      qc.setQueryData(queryKey, snapshot);
      toast.error("Failed to move candidate. Please try again.");
    }
  };

  return (
    <div className="space-y-2">
      {/* Reorder hint + reset */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] text-muted-foreground">
          Drag the{" "}
          <GripVertical className="inline h-3 w-3 -mt-0.5 align-middle" /> handle on a
          stage to arrange your own workflow order. Drag candidate cards between
          stages to move them.
        </p>
        {isCustomOrder && (
          <button
            type="button"
            onClick={resetOrder}
            className="flex shrink-0 items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            <RotateCcw className="h-3 w-3" /> Reset order
          </button>
        )}
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={order.map((s) => `${COL_PREFIX}${s}`)}
          strategy={horizontalListSortingStrategy}
        >
          <div className="flex gap-3 overflow-x-auto pb-4" style={{ minHeight: "60vh" }}>
            {order.map((stage) => (
              <SortableColumn
                key={stage}
                stage={stage}
                label={KANBAN_STAGE_LABELS[stage]}
                count={stageCounts[stage] ?? 0}
                candidates={byStage(stage)}
                jobId={jobId}
              />
            ))}
          </div>
        </SortableContext>

        <DragOverlay>
          {activeCandidate && (
            <div className="rotate-1 opacity-90">
              <CandidateCard candidate={activeCandidate} jobId={jobId} />
            </div>
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
