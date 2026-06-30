"use client";

/**
 * Floating, context-aware support assistant.
 *
 * Mounted once in the dashboard layout, it sits as a floating button in the
 * bottom-right of every recruiter page. It reads the current pathname to work
 * out WHICH page/section/record the user is on, and the backend answers grounded
 * in that context. Memory is per-context: each page (and each individual job /
 * candidate) keeps its own conversation thread, reloaded when you navigate.
 */

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { MessageCircle, X, Send, Loader2, Trash2, Bot, Sparkles } from "lucide-react";
import { assistantApi, type BackendAssistantMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

type Ctx = { key: string; entityId: string; label: string };

/** Map the current pathname → an assistant context (key + entity + label). */
function deriveContext(pathname: string): Ctx {
  const seg = pathname.replace(/\/+$/, "").split("/").filter(Boolean);

  if (seg[0] === "candidates") {
    return seg[1]
      ? { key: "candidate", entityId: seg[1], label: "Candidate profile" }
      : { key: "candidates", entityId: "", label: "Candidates" };
  }

  if (seg[0] === "jobs") {
    if (!seg[1]) return { key: "jobs", entityId: "", label: "Jobs" };
    const jobId = seg[1];
    const sub = seg[2];
    if (sub === "candidates") {
      return seg[3]
        ? { key: "candidate", entityId: seg[3], label: "Candidate profile" }
        : { key: "candidates", entityId: "", label: "Candidates" };
    }
    if (sub === "screening") return { key: "screening", entityId: jobId, label: "Screening" };
    if (sub === "assessment") return { key: "assessment", entityId: jobId, label: "Assessment" };
    if (sub === "interviews") return { key: "interviews", entityId: jobId, label: "Interviews" };
    if (sub === "decision") return { key: "decision", entityId: jobId, label: "Decision support" };
    if (sub === "edit") return { key: "job", entityId: jobId, label: "Edit job" };
    return { key: "job", entityId: jobId, label: "Job" };
  }

  if (seg[0] === "approvals") return { key: "approvals", entityId: "", label: "Approvals" };
  if (seg[0] === "assessments") return { key: "assessment", entityId: "", label: "Assessment" };
  if (seg[0] === "interviews") {
    return seg[1]
      ? { key: "interviews", entityId: seg[1], label: "Interviews" }
      : { key: "interviews", entityId: "", label: "Interviews" };
  }
  if (seg[0] === "source-candidate") return { key: "source_candidate", entityId: "", label: "Source Candidate" };
  if (seg[0] === "dashboard") return { key: "dashboard", entityId: "", label: "Dashboard" };
  if (seg[0] === "settings" && seg[1] === "members") return { key: "members", entityId: "", label: "Team Members" };

  return { key: "general", entityId: "", label: "PATHS" };
}

type Msg = { role: "user" | "assistant"; content: string };

export function AssistantWidget() {
  const pathname = usePathname() || "/";
  const ctx = deriveContext(pathname);
  const ctxId = `${ctx.key}:${ctx.entityId}`;

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const loadedCtx = useRef<string | null>(null);

  // Load this context's thread when the panel opens or the context changes.
  useEffect(() => {
    if (!open) return;
    if (loadedCtx.current === ctxId) return;
    loadedCtx.current = ctxId;
    let cancelled = false;
    setLoadingHistory(true);
    setMessages([]);
    assistantApi
      .history(ctx.key, ctx.entityId || undefined)
      .then((res) => {
        if (cancelled) return;
        setMessages(
          (res.items ?? []).map((m: BackendAssistantMessage) => ({
            role: m.role,
            content: m.content,
          })),
        );
      })
      .catch(() => { if (!cancelled) setMessages([]); })
      .finally(() => { if (!cancelled) setLoadingHistory(false); });
    return () => { cancelled = true; };
  }, [open, ctxId, ctx.key, ctx.entityId]);

  // Auto-scroll to the latest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending, loadingHistory]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setSending(true);
    try {
      const res = await assistantApi.chat({
        context_key: ctx.key,
        entity_id: ctx.entityId || undefined,
        message: text,
      });
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content:
            e instanceof Error
              ? `Sorry, I hit an error: ${e.message}`
              : "Sorry, something went wrong. Please try again.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  async function clearThread() {
    try {
      await assistantApi.clear(ctx.key, ctx.entityId || undefined);
    } catch { /* ignore */ }
    setMessages([]);
  }

  return (
    <>
      {/* Floating launcher */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open PATHy assistant"
          className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <MessageCircle className="h-6 w-6" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-5 right-5 z-50 flex h-[34rem] max-h-[80vh] w-[24rem] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-border/60 bg-popover shadow-2xl">
          {/* Header */}
          <div className="flex items-center gap-2 border-b border-border/50 bg-muted/30 px-4 py-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Bot className="h-4 w-4" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-tight text-foreground">PATHy</p>
              <p className="truncate text-[11px] text-muted-foreground">
                Helping with: <span className="text-primary">{ctx.label}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={() => void clearThread()}
              title="Clear this conversation"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              title="Close"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {loadingHistory ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <Sparkles className="h-7 w-7 text-primary/40" />
                <p className="text-sm font-medium text-foreground">
                  Hi! I&apos;m PATHy, your assistant for the {ctx.label} page.
                </p>
                <p className="text-[12px] text-muted-foreground">
                  Ask me anything about what you can do here. I keep a separate
                  memory for each page.
                </p>
              </div>
            ) : (
              messages.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    "flex",
                    m.role === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-[13px] leading-relaxed",
                      m.role === "user"
                        ? "rounded-br-sm bg-primary text-primary-foreground"
                        : "rounded-bl-sm bg-muted text-foreground",
                    )}
                  >
                    {m.content}
                  </div>
                </div>
              ))
            )}
            {sending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-sm bg-muted px-3 py-2 text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span className="text-[12px]">Thinking…</span>
                </div>
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="border-t border-border/50 bg-muted/20 p-2.5">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void send();
                  }
                }}
                rows={1}
                placeholder={`Ask about ${ctx.label.toLowerCase()}…`}
                className="max-h-28 min-h-[2.4rem] flex-1 resize-none rounded-xl border border-border/60 bg-background px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/20"
              />
              <button
                type="button"
                onClick={() => void send()}
                disabled={!input.trim() || sending}
                aria-label="Send"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
