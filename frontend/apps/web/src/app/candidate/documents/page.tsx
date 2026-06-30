"use client";

import { useState, useRef, useCallback, useMemo } from "react";
import { motion } from "framer-motion";
import { Upload, FileText, CheckCircle2, Clock, AlertCircle, Trash2, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCandidateProfile, useCVUpload } from "@/lib/hooks";
import { cvIngestionApi, candidatePortalApi } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { createEmptyCandidateProfile } from "@/lib/candidate/portal-profile";
import type { UploadedDocument } from "@/types/candidate-profile.types";
import { cn } from "@/lib/utils/cn";

const statusIcons = {
  processing: Clock,
  processed:  CheckCircle2,
  failed:     AlertCircle,
};

const statusColors = {
  processing: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  processed:  "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  failed:     "border-rose-500/30 bg-rose-500/10 text-rose-400",
};

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Render a real upload date — never the Unix epoch / "1/1/1970". Returns an
 * em-dash when the value is missing or parses to a nonsensical timestamp.
 */
function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  // < 1970-01-02 = an epoch sentinel from older data, not a real upload.
  if (!Number.isFinite(t) || t < 86_400_000) return "—";
  return new Date(iso).toLocaleDateString();
}

export default function DocumentsPage() {
  const { data: profile = createEmptyCandidateProfile(), refetch: refetchProfile } =
    useCandidateProfile();
  const uploadCV = useCVUpload();
  const qc = useQueryClient();
  const [localUploads, setLocalUploads] = useState<UploadedDocument[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const documents = useMemo(() => {
    // `profile.documents` already includes the CV (it is documents[0]); do not
    // also unshift `cvDocument` or the same file would be listed twice.
    const fromProfile = [...(profile.documents ?? [])];
    const serverIds = new Set(fromProfile.map((d) => d.id));
    const pendingLocal = localUploads.filter((d) => !serverIds.has(d.id));
    return [...pendingLocal, ...fromProfile];
  }, [profile.documents, localUploads]);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    if (file.size > 10 * 1024 * 1024) {
      setError("File too large. Max 10 MB.");
      return;
    }
    const validTypes = ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
    if (!validTypes.includes(file.type)) {
      setError("Invalid file type. Please upload a PDF or Word document.");
      return;
    }

    const newDoc: UploadedDocument = {
      id: crypto.randomUUID(),
      fileName: file.name,
      fileSize: file.size,
      mimeType: file.type,
      uploadedAt: new Date().toISOString(),
      status: "processing",
    };
    setUploading(true);
    setLocalUploads((prev) => [newDoc, ...prev]);

    try {
      // Upload returns immediately with a job id — the file is already saved,
      // parsing runs in the background. Poll the job, then refresh the profile
      // so the persisted CV appears in the list below without a manual reload.
      const job = await uploadCV.mutateAsync({ file });
      const jobId = job?.job_id;
      // The file is already saved server-side the moment upload returns —
      // surface it right away and drop the optimistic placeholder so the
      // persisted document shows in "Uploaded Files" without waiting for
      // background extraction to finish.
      await refetchProfile();
      setLocalUploads((prev) => prev.filter((d) => d.id !== newDoc.id));
      let failed = false;
      if (jobId) {
        // CV parsing can take ~2 min when the primary free model is rate-limited
        // and the client falls through the free-model chain.
        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 5000));
          try {
            const st = await cvIngestionApi.getJobStatus(jobId);
            if (st.status === "completed" || st.status === "failed") {
              failed = st.status === "failed";
              break;
            }
          } catch {
            /* transient — keep polling */
          }
        }
      }
      // Extraction finished (or timed out) — refresh again to pick up the
      // extracted skills/experience and recompute downstream views.
      await refetchProfile();
      qc.invalidateQueries({ queryKey: ["candidate", "learning-hub"] });
      if (failed) {
        setError(
          "Your CV is saved and listed below. Automatic skill extraction didn't fully finish this time — we kept what we could. You can re-upload to retry.",
        );
      }
    } catch (e) {
      setLocalUploads((prev) => prev.map((d) => (d.id === newDoc.id ? { ...d, status: "failed" } : d)));
      setError(e instanceof Error ? e.message : "Upload failed. Try again.");
    } finally {
      setUploading(false);
    }
  }, [uploadCV, refetchProfile]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = useCallback(async (id: string) => {
    // Local optimistic entry that was never persisted server-side — drop it.
    if (localUploads.some((d) => d.id === id)) {
      setLocalUploads((prev) => prev.filter((d) => d.id !== id));
      return;
    }
    setDeletingId(id);
    try {
      await candidatePortalApi.deleteDocument(id);
      await refetchProfile();
      // Extracted profile data (skills, education, …) is intentionally kept,
      // but a Learning Hub recompute is cheap — let it refresh too.
      qc.invalidateQueries({ queryKey: ["candidate", "learning-hub"] });
      toast.success("Document deleted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not delete document");
    } finally {
      setDeletingId(null);
    }
  }, [localUploads, refetchProfile, qc]);

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-2xl">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <h1 className="font-heading text-3xl font-bold text-foreground">Documents</h1>
          <p className="mt-1 text-sm text-muted-foreground">Upload and manage your CV and supporting documents.</p>
        </motion.div>

        {/* Upload zone */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <div
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            onClick={() => !uploading && inputRef.current?.click()}
            className={cn(
              "relative flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-10 text-center transition-all mb-6",
              uploading ? "cursor-not-allowed opacity-60" : "",
              isDragging ? "border-primary/60 bg-primary/5" : "border-border/50 hover:border-primary/40 hover:bg-muted/10"
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              className="sr-only"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            {uploading ? (
              <>
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <p className="text-sm font-semibold text-foreground">Uploading…</p>
              </>
            ) : (
              <>
                <div className={cn("flex h-14 w-14 items-center justify-center rounded-2xl transition-colors", isDragging ? "bg-primary/15" : "bg-muted/30")}>
                  <Upload className={cn("h-6 w-6", isDragging ? "text-primary" : "text-muted-foreground")} />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{isDragging ? "Drop it here" : "Drag & drop your CV"}</p>
                  <p className="mt-1 text-xs text-muted-foreground">or click to browse · PDF, DOC, DOCX · Max 10 MB</p>
                </div>
              </>
            )}
          </div>

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-xs text-destructive">
              <X className="h-3.5 w-3.5 shrink-0" />
              {error}
              <button onClick={() => setError(null)} className="ml-auto opacity-70 hover:opacity-100"><X className="h-3 w-3" /></button>
            </div>
          )}
        </motion.div>

        {/* Documents list */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground/50">Uploaded Files ({documents.length})</p>

          {documents.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 py-12 text-center">
              <FileText className="mx-auto mb-3 h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">No documents yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc, i) => {
                const StatusIcon = statusIcons[doc.status];
                return (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="glass rounded-xl p-4 flex items-center gap-4"
                  >
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-muted/30">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">{doc.fileName}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {formatBytes(doc.fileSize)} · {formatDate(doc.uploadedAt)}
                      </p>
                    </div>
                    <Badge variant="outline" className={cn("text-[10px] shrink-0 flex items-center gap-1", statusColors[doc.status])}>
                      <StatusIcon className="h-3 w-3" />
                      {doc.status === "processing" ? "Processing…" : doc.status === "processed" ? "Processed" : "Failed"}
                    </Badge>
                    <button
                      type="button"
                      onClick={() => handleDelete(doc.id)}
                      disabled={deletingId === doc.id}
                      className="shrink-0 text-muted-foreground/40 hover:text-destructive transition-colors disabled:opacity-50"
                      aria-label="Delete document"
                    >
                      {deletingId === doc.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </button>
                  </motion.div>
                );
              })}
            </div>
          )}
        </motion.div>

        <p className="mt-6 text-[11px] text-muted-foreground/60">
          Uploaded documents are stored securely. Your CV is only shared with recruiters when you consent to de-anonymization. AI processing extracts skills and experience to strengthen your profile.
        </p>
      </div>
    </div>
  );
}
