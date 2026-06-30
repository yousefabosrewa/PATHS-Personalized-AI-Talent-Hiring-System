"use client";

import { useState } from "react";
import { Megaphone, Plus, Send } from "lucide-react";
import { useOwnerAnnouncements, useCreateAnnouncement } from "@/lib/hooks";

const BANNER_COLORS = [
  { value: "blue", label: "Blue", cls: "bg-blue-500" },
  { value: "green", label: "Green", cls: "bg-green-500" },
  { value: "amber", label: "Amber", cls: "bg-amber-500" },
  { value: "red", label: "Red", cls: "bg-red-500" },
];

export default function OwnerAnnouncementsPage() {
  const { data: announcements = [], isLoading } = useOwnerAnnouncements();
  const create = useCreateAnnouncement();

  const [showForm, setShowForm] = useState(false);
  const [content, setContent] = useState("");
  const [bannerEnabled, setBannerEnabled] = useState(false);
  const [bannerColor, setBannerColor] = useState("blue");
  const [scheduledAt, setScheduledAt] = useState("");

  const handleCreate = async () => {
    if (!content.trim()) return;
    try {
      await create.mutateAsync({
        content: content.trim(),
        in_app_banner_enabled: bannerEnabled,
        banner_color: bannerColor,
        scheduled_at: scheduledAt || null,
      });
      setContent("");
      setBannerEnabled(false);
      setBannerColor("blue");
      setScheduledAt("");
      setShowForm(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to create announcement");
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-8 py-10 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold">Announcements</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Send platform-wide messages to all org users.
          </p>
        </div>
        <button
          onClick={() => setShowForm((p) => !p)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> New announcement
        </button>
      </div>

      {/* Compose form */}
      {showForm && (
        <div className="rounded-xl border border-primary/30 bg-white p-5 shadow-md space-y-4">
          <h3 className="font-heading text-lg font-semibold">Compose Announcement</h3>

          <div>
            <label className="mb-1.5 block text-sm font-semibold">Message</label>
            <textarea
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Platform-wide message visible to all users…"
              className="w-full rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <p className="mt-1 text-right text-xs text-muted-foreground">
              {content.length} chars
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/10 p-3">
            <div>
              <p className="text-sm font-semibold">In-app banner</p>
              <p className="text-xs text-muted-foreground">
                Show a dismissible banner on the dashboard.
              </p>
            </div>
            <button
              role="switch"
              aria-checked={bannerEnabled}
              onClick={() => setBannerEnabled((p) => !p)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                bannerEnabled ? "bg-primary" : "bg-gray-200"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  bannerEnabled ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {bannerEnabled && (
            <div>
              <label className="mb-2 block text-sm font-semibold">Banner colour</label>
              <div className="flex gap-2">
                {BANNER_COLORS.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => setBannerColor(c.value)}
                    className={`h-8 w-8 rounded-full ${c.cls} transition-all ${
                      bannerColor === c.value
                        ? "ring-2 ring-offset-2 ring-foreground/50 scale-110"
                        : "opacity-60 hover:opacity-100"
                    }`}
                    title={c.label}
                  />
                ))}
              </div>

              {/* Preview */}
              <div
                className={`mt-3 rounded-lg p-3 text-sm font-medium text-white ${
                  BANNER_COLORS.find((c) => c.value === bannerColor)?.cls ?? "bg-blue-500"
                }`}
              >
                {content || "Preview: your announcement text will appear here."}
              </div>
            </div>
          )}

          <div>
            <label className="mb-1.5 block text-sm font-semibold">
              Schedule for (optional)
            </label>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className="rounded-lg border border-border/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowForm(false)}
              className="rounded-lg border border-border/50 px-3 py-1.5 text-sm hover:bg-muted/30"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!content.trim() || create.isPending}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              {create.isPending ? "Sending…" : "Send announcement"}
            </button>
          </div>
        </div>
      )}

      {/* List */}
      <div className="rounded-xl border border-border/50 bg-white shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : announcements.length === 0 ? (
          <div className="flex flex-col items-center p-10 text-muted-foreground">
            <Megaphone className="mb-3 h-8 w-8 opacity-30" />
            <p className="text-sm">No announcements yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-border/30">
            {announcements.map((ann) => (
              <div key={ann.id} className="p-5">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    {new Date(ann.created_at).toLocaleString()}
                  </span>
                  <div className="flex items-center gap-2">
                    {ann.in_app_banner_enabled && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold text-white ${
                          BANNER_COLORS.find((c) => c.value === ann.banner_color)?.cls ??
                          "bg-blue-500"
                        }`}
                      >
                        Banner: {ann.banner_color}
                      </span>
                    )}
                    {ann.sent_at ? (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700">
                        Sent
                      </span>
                    ) : (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
                        Pending
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-sm">{ann.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
