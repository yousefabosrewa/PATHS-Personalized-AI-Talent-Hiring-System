"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Database, Loader2, AlertCircle, CheckCircle2, Circle,
  Layers, BookOpen, FileText,
  Upload, Trash2, RefreshCw, ShieldAlert, FileUp,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
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
import { cn } from "@/lib/utils/cn";
import { useCollections, useOrganization } from "@/lib/hooks";
import { api } from "@/lib/api/client";
import type { BackendQdrantCollection } from "@/lib/api";

// ── Company Files (fix2_1.md Feature 1) ──────────────────────────────────

const COMPANY_FILE_CATEGORIES: { value: string; label: string }[] = [
  { value: "company_overview", label: "Company overview" },
  { value: "culture_and_values", label: "Culture and values" },
  { value: "hiring_policy", label: "Hiring policy" },
  { value: "role_levels_and_career_paths", label: "Role levels and career paths" },
  { value: "benefits_and_compensation", label: "Benefits and compensation guidelines" },
  { value: "technical_stack", label: "Technical stack" },
  { value: "team_structure", label: "Team structure / org chart" },
  { value: "interview_guidelines", label: "Interview guidelines" },
  { value: "onboarding_documents", label: "Onboarding documents" },
  { value: "legal_compliance_reference", label: "Legal / compliance reference" },
  { value: "other", label: "Other" },
];

const LEGAL_CATEGORY = "legal_compliance_reference";

interface CompanyFile {
  id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  category: string;
  description: string | null;
  status: "uploaded" | "processing" | "indexed" | "failed";
  is_legal_or_compliance_context: boolean;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  indexed_at: string | null;
}

interface CompanyFileList {
  total: number;
  items: CompanyFile[];
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

const statusConfig: Record<
  string,
  { icon: typeof CheckCircle2; color: string; label: string }
> = {
  green: { icon: CheckCircle2, color: "text-emerald-400", label: "Active" },
  yellow: { icon: AlertCircle, color: "text-amber-400", label: "Degraded" },
  red: { icon: AlertCircle, color: "text-red-400", label: "Error" },
  grey: { icon: Circle, color: "text-muted-foreground", label: "Unknown" },
};

function getStatusConfig(status: string | null | undefined) {
  if (!status) return statusConfig.grey;
  const s = status.toLowerCase();
  if (s === "green" || s === "active" || s === "healthy") return statusConfig.green;
  if (s === "yellow" || s === "degraded") return statusConfig.yellow;
  if (s === "red" || s === "error" || s === "unhealthy") return statusConfig.red;
  return statusConfig.grey;
}

function CollectionCard({
  collection,
  index,
}: {
  collection: BackendQdrantCollection;
  index: number;
}) {
  const cfg = getStatusConfig(collection.status);
  const StatusIcon = cfg.icon;

  // Show a vector count only when it's a real, positive number — the raw
  // "—" / fixed dimension stats were meaningless, so the card now just shows
  // the collection name + Active status (plus a count if one is available).
  const vectorCount =
    typeof collection.vectors_count === "number" && collection.vectors_count > 0
      ? collection.vectors_count
      : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index }}
      className="glass rounded-xl p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Layers className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0">
            <p className="font-heading text-sm font-bold text-foreground truncate">
              {collection.name}
            </p>
            {vectorCount != null && (
              <p className="text-[11px] text-muted-foreground">
                {formatNumber(vectorCount)} vectors
              </p>
            )}
          </div>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "gap-1.5 text-[10px] shrink-0",
            cfg.color,
          )}
        >
          <StatusIcon className="h-3 w-3" />
          {cfg.label}
        </Badge>
      </div>
    </motion.div>
  );
}

export default function KnowledgeBasePage() {
  const { data: collections = [], isLoading, isError } = useCollections();

  const connectedCount = collections.filter(
    (c: BackendQdrantCollection) =>
      getStatusConfig(c.status).label === "Active",
  ).length;
  const isConnected = collections.length === 0 || connectedCount > 0;

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8 max-w-5xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <Database className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">
            Knowledge Base
          </h1>
          <p className="text-sm text-muted-foreground">
            Vector storage powered by Qdrant — collections, embeddings, and
            semantic search for the hiring pipeline.
          </p>
        </div>
      </motion.div>

      {/* ── Company Files (fix2_1.md Feature 1) ──────────────────────── */}
      <CompanyFilesSection />

      {/* ── Status summary cards ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.03 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <p className="text-2xl font-bold text-foreground">
            {collections.length}
          </p>
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Layers className="h-3 w-3" /> Total collections
          </p>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.09 }}
          className="glass rounded-xl p-4 space-y-1"
        >
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex h-2.5 w-2.5 rounded-full",
                isConnected ? "bg-emerald-400" : "bg-red-400",
              )}
            />
            <p className="text-sm font-semibold text-foreground">
              {isConnected ? "Connected" : "Disconnected"}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            Qdrant database status
          </p>
        </motion.div>
      </div>

      {/* ── Loading state ───────────────────────────────────────────── */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading collections…
        </div>
      )}

      {/* ── Error state ─────────────────────────────────────────────── */}
      {isError && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass gradient-border rounded-2xl p-6 text-center space-y-3"
        >
          <AlertCircle className="h-8 w-8 text-red-400 mx-auto" />
          <p className="text-sm font-medium text-foreground">
            Knowledge Base is not available
          </p>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Verify that Qdrant is running and the backend API is configured.
          </p>
        </motion.div>
      )}

      {/* ── Empty state ─────────────────────────────────────────────── */}
      {!isLoading && !isError && collections.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass gradient-border rounded-2xl p-8 text-center space-y-3"
        >
          <BookOpen className="h-10 w-10 text-muted-foreground mx-auto" />
          <p className="text-sm font-semibold text-foreground">
            No vector collections found
          </p>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Knowledge Base is powered by Qdrant. Collections are created
            automatically when documents are ingested.
          </p>
        </motion.div>
      )}

      {/* ── Collections list ────────────────────────────────────────── */}
      {!isLoading && !isError && collections.length > 0 && (
        <div className="space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex items-center gap-2"
          >
            <Layers className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold tracking-wider text-foreground">
              Collections
            </h2>
            <Badge variant="outline" className="ml-auto text-[10px]">
              {collections.length}
            </Badge>
          </motion.div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {collections.map((c, i) => (
              <CollectionCard key={c.name} collection={c} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Semantic Search & RAG Test panel removed per request. */}
    </div>
  );
}

// ── Company Files section ─────────────────────────────────────────────────

const FILE_STATUS_STYLE: Record<string, string> = {
  uploaded: "border-slate-500/30 text-slate-300",
  processing: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  indexed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  failed: "border-red-500/40 bg-red-500/10 text-red-300",
};

function categoryLabel(value: string): string {
  return (
    COMPANY_FILE_CATEGORIES.find((c) => c.value === value)?.label ?? value
  );
}

function CompanyFilesSection() {
  const { data: org } = useOrganization();
  const orgId = org?.id ? String(org.id) : "";
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [category, setCategory] = useState("company_overview");
  const [description, setDescription] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const filesQuery = useQuery({
    queryKey: ["company-files", orgId],
    queryFn: () =>
      api.get<CompanyFileList>(
        `/api/v1/organizations/${encodeURIComponent(orgId)}/knowledge-files`,
      ),
    enabled: Boolean(orgId),
    // Poll while anything is still processing so the status badge updates.
    refetchInterval: (q) => {
      const items = (q.state.data as CompanyFileList | undefined)?.items ?? [];
      return items.some((f) => f.status === "processing" || f.status === "uploaded")
        ? 3000
        : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", category);
      if (description.trim()) fd.append("description", description.trim());
      return api.postForm<CompanyFile>(
        `/api/v1/organizations/${encodeURIComponent(orgId)}/knowledge-files`,
        fd,
      );
    },
    onSuccess: () => {
      toast.success("Company file uploaded — indexing in the background.");
      setPendingFile(null);
      setDescription("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      qc.invalidateQueries({ queryKey: ["company-files", orgId] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Upload failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: (fileId: string) =>
      api.delete<unknown>(
        `/api/v1/organizations/${encodeURIComponent(orgId)}/knowledge-files/${fileId}`,
      ),
    onSuccess: () => {
      toast.success("File removed");
      qc.invalidateQueries({ queryKey: ["company-files", orgId] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Delete failed"),
  });

  const reindexMutation = useMutation({
    mutationFn: (fileId: string) =>
      api.post<unknown>(
        `/api/v1/organizations/${encodeURIComponent(orgId)}/knowledge-files/${fileId}/reindex`,
        {},
      ),
    onSuccess: () => {
      toast.success("Re-indexing started");
      qc.invalidateQueries({ queryKey: ["company-files", orgId] });
    },
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "Re-index failed"),
  });

  const items = filesQuery.data?.items ?? [];
  const isLegal = category === LEGAL_CATEGORY;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass gradient-border rounded-2xl p-6 space-y-5"
    >
      <div className="flex items-center gap-2">
        <FileUp className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold tracking-wider text-foreground">
          Company Files
        </h2>
        <Badge variant="outline" className="text-[10px] ml-auto">
          {items.length} file{items.length === 1 ? "" : "s"}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Upload company documents that help PATHS understand your organization,
        hiring style, culture, policies, role expectations, and internal
        context. Legal or compliance files are treated as read-only reference
        context and are not used as legal advice.
      </p>

      {/* Upload controls */}
      <div className="space-y-3 rounded-lg border border-border/50 bg-muted/10 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs">File category</Label>
            <Select value={category} onValueChange={(v) => setCategory(v ?? "other")}>
              <SelectTrigger size="sm" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COMPANY_FILE_CATEGORIES.map((c) => (
                  <SelectItem key={c.value} value={c.value}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Description (optional)</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. 2026 engineering levels guide"
              className="h-9 text-xs"
            />
          </div>
        </div>

        {isLegal && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-[11px] text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span>
              Legal / compliance files are stored as read-only reference context.
              Agents use them only to understand company constraints — never to
              rewrite, summarize as legal advice, or make binding decisions.
            </span>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md,.markdown,.csv"
          className="hidden"
          onChange={(e) => setPendingFile(e.target.files?.[0] ?? null)}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => fileInputRef.current?.click()}
            disabled={!orgId}
          >
            <Upload className="h-3.5 w-3.5" />
            Choose file
          </Button>
          {pendingFile && (
            <span className="text-xs text-muted-foreground truncate max-w-[220px]">
              {pendingFile.name}
            </span>
          )}
          <Button
            size="sm"
            className="gap-1.5 ml-auto"
            onClick={() => pendingFile && uploadMutation.mutate(pendingFile)}
            disabled={!pendingFile || uploadMutation.isPending}
          >
            {uploadMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="h-3.5 w-3.5" />
            )}
            Upload Company File
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground">
          Supported: PDF, DOCX, TXT, MD, CSV · max 15 MB.
        </p>
      </div>

      {/* File list */}
      {filesQuery.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading files…
        </div>
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-3">
          No company files yet. Upload documents to give agents company context.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((f) => (
            <div
              key={f.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border/50 bg-muted/10 p-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <p className="text-sm text-foreground truncate max-w-[260px]">
                    {f.file_name}
                  </p>
                  {f.is_legal_or_compliance_context && (
                    <Badge
                      variant="outline"
                      className="border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px] gap-1"
                    >
                      <ShieldAlert className="h-3 w-3" /> Read-only legal context
                    </Badge>
                  )}
                </div>
                <p className="text-[11px] text-muted-foreground">
                  {categoryLabel(f.category)}
                  {f.chunk_count ? ` · ${f.chunk_count} chunks indexed` : ""}
                  {f.description ? ` · ${f.description}` : ""}
                </p>
                {f.status === "failed" && f.error_message && (
                  <p className="text-[10px] text-red-400">{f.error_message}</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] capitalize gap-1",
                    FILE_STATUS_STYLE[f.status] ?? "",
                  )}
                >
                  {f.status === "processing" && (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                  {f.status}
                </Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  title="Re-index"
                  onClick={() => reindexMutation.mutate(f.id)}
                  disabled={reindexMutation.isPending}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  title="Delete"
                  onClick={() => deleteMutation.mutate(f.id)}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
