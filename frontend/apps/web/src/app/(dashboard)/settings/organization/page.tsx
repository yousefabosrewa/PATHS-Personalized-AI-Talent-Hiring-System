"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Building2,
  ShieldCheck,
  Save,
  Loader2,
  Globe,
  PlugZap,
  Unplug,
  CheckCircle2,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useOrganization } from "@/lib/hooks";
import { api } from "@/lib/api/client";

interface LinkedInAccountState {
  connected: boolean;
  email: string | null;
  connected_at: string | null;
  has_jsessionid: boolean;
  cookies_file_path: string;
  cookies_file_present: boolean;
}

function Section({ icon: Icon, title, description, children }: {
  icon: typeof Building2; title: string; description: string; children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl p-5 space-y-4"
    >
      <div className="flex items-start gap-3 pb-3 border-b border-border/40">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/20">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h3 className="font-heading text-[15px] font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </motion.div>
  );
}

export default function OrganizationPage() {
  const { data: org } = useOrganization();
  const qc = useQueryClient();

  // Controlled state for the editable Profile fields — was missing entirely,
  // which is why nothing saved. `website` + `headcount` are not yet on the
  // backend Organization schema; the inputs stay visible but only name and
  // industry are persisted (matches what the model actually stores).
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [website, setWebsite] = useState("");
  const [headcount, setHeadcount] = useState("");
  useEffect(() => {
    if (!org) return;
    setName(org.name ?? "");
    setIndustry(org.industry ?? "");
    setWebsite(org.website ?? "");
    setHeadcount(org.headcount ?? "");
  }, [org]);

  const saveProfile = useMutation({
    mutationFn: async (body: {
      name?: string;
      industry?: string;
      website?: string | null;
      company_size?: string | null;
    }) => api.patch<unknown>("/api/v1/organizations/me", body),
    onSuccess: () => {
      // useOrganization caches under ["organization"] in the existing hook —
      // invalidate any plausible key so the UI re-fetches the fresh row.
      qc.invalidateQueries({ queryKey: ["organization"] });
      qc.invalidateQueries({ queryKey: ["organizations", "me"] });
      qc.invalidateQueries({ queryKey: ["org"] });
      toast.success("Organization profile saved");
    },
    onError: (e) =>
      toast.error(
        e instanceof Error ? e.message : "Could not save organization profile",
      ),
  });

  async function handleSaveProfile() {
    if (!org) return;
    // Empty string => null on the server (clears the field).
    await saveProfile.mutateAsync({
      name: name.trim() || undefined,
      industry: industry.trim() || undefined,
      website: website.trim(),
      company_size: headcount.trim() || undefined,
    });
  }

  if (!org) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">Organization</h1>
        <p className="text-sm text-muted-foreground">Manage {org.name}&apos;s settings and configuration.</p>
      </div>

      {/* Profile */}
      <Section icon={Building2} title="Profile" description="Basic organization information">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5 col-span-2">
            <Label className="text-sm">Organization Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Industry</Label>
            <Input
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="h-9"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm">Headcount</Label>
            <Select value={headcount || undefined} onValueChange={(v) => setHeadcount(v ?? "")}>
              <SelectTrigger className="h-9"><SelectValue placeholder="Select…" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="1–10">1–10</SelectItem>
                <SelectItem value="11–50">11–50</SelectItem>
                <SelectItem value="51–200">51–200</SelectItem>
                <SelectItem value="201–500">201–500</SelectItem>
                <SelectItem value="501–1,000">501–1,000</SelectItem>
                <SelectItem value="1,000+">1,000+</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5 col-span-2">
            <Label className="text-sm">Website</Label>
            <Input
              type="url"
              placeholder="https://…"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              className="h-9"
            />
          </div>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={handleSaveProfile}
          disabled={saveProfile.isPending}
        >
          {saveProfile.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          {saveProfile.isPending ? "Saving…" : "Save Changes"}
        </Button>
      </Section>

      {/* LinkedIn account for sourcing */}
      <LinkedInAccountSection organizationId={String(org.id)} />

      {/* Fairness & Privacy */}
      <Section icon={ShieldCheck} title="Fairness & Privacy" description="Anonymization and bias settings">
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 p-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Anonymization Level</p>
              <p className="text-xs text-muted-foreground">Controls which PII fields are redacted before scoring</p>
            </div>
            <Select defaultValue={org.settings.anonymizationLevel}>
              <SelectTrigger className="h-8 w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="strict">Strict</SelectItem>
                <SelectItem value="standard">Standard</SelectItem>
                <SelectItem value="minimal">Minimal</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 p-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Outbound Sourcing</p>
              <p className="text-xs text-muted-foreground">Allow Sourcing Agent to discover passive candidates</p>
            </div>
            <Switch defaultChecked={org.settings.outboundSourcingEnabled} />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 p-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Technical Assessments</p>
              <p className="text-xs text-muted-foreground">Enable Assessment Agent for technical roles</p>
            </div>
            <Switch defaultChecked={org.settings.assessmentEnabled} />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-border/40 bg-muted/20 p-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Data Retention</p>
              <p className="text-xs text-muted-foreground">Days to retain candidate data after rejection</p>
            </div>
            <Select defaultValue={String(org.settings.retentionDays)}>
              <SelectTrigger className="h-8 w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="180">180 days</SelectItem>
                <SelectItem value="365">365 days</SelectItem>
                <SelectItem value="730">2 years</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Section>

      {/* Plan + Default Scoring Weights sections intentionally removed
          (full_Fix_instruction.md §15) — the underlying fields remain in
          the data model so other features that read them are unaffected. */}
    </div>
  );
}

// ── LinkedIn account (Source Candidate / MCP integration) ────────────────

function LinkedInAccountSection({ organizationId }: { organizationId: string }) {
  const qc = useQueryClient();
  const stateQuery = useQuery({
    queryKey: ["organization", organizationId, "linkedin-account"],
    queryFn: () =>
      api.get<LinkedInAccountState>(
        `/api/v1/organizations/${encodeURIComponent(organizationId)}/linkedin-account`,
      ),
  });
  const account = stateQuery.data;

  const [email, setEmail] = useState("");
  const [liAt, setLiAt] = useState("");
  const [jsessionid, setJsessionid] = useState("");

  useEffect(() => {
    if (!account) return;
    setEmail(account.email ?? "");
    // Cookies themselves are never sent back from the API — inputs stay empty.
    setLiAt("");
    setJsessionid("");
  }, [account]);

  const connect = useMutation({
    mutationFn: (body: { email?: string; li_at: string; jsessionid?: string }) =>
      api.post<LinkedInAccountState>(
        `/api/v1/organizations/${encodeURIComponent(organizationId)}/linkedin-account`,
        body,
      ),
    onSuccess: (res) => {
      qc.setQueryData(
        ["organization", organizationId, "linkedin-account"],
        res,
      );
      toast.success("LinkedIn account connected — Source Candidate will use it next.");
      setLiAt("");
      setJsessionid("");
    },
    onError: (err) =>
      toast.error(
        err instanceof Error ? err.message : "Failed to connect LinkedIn account",
      ),
  });

  const disconnect = useMutation({
    mutationFn: () =>
      api.delete<LinkedInAccountState>(
        `/api/v1/organizations/${encodeURIComponent(organizationId)}/linkedin-account`,
      ),
    onSuccess: (res) => {
      qc.setQueryData(
        ["organization", organizationId, "linkedin-account"],
        res,
      );
      toast.success("LinkedIn account disconnected.");
    },
    onError: (err) =>
      toast.error(
        err instanceof Error ? err.message : "Failed to disconnect LinkedIn account",
      ),
  });

  function onConnect() {
    if (!liAt || liAt.trim().length < 10) {
      toast.error("Paste your li_at cookie value (it's a long string).");
      return;
    }
    connect.mutate({
      email: email.trim() || undefined,
      li_at: liAt.trim(),
      jsessionid: jsessionid.trim() || undefined,
    });
  }

  return (
    <Section
      icon={Globe}
      title="LinkedIn Account"
      description="Connect your recruiter LinkedIn account so Source Candidate can fetch open-to-work profiles through the LinkedIn MCP server."
    >
      <div className="flex items-center gap-2 flex-wrap">
        {account?.connected ? (
          <>
            <Badge
              variant="outline"
              className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300 text-[10px]"
            >
              <CheckCircle2 className="h-3 w-3" /> Connected
              {account.email ? ` as ${account.email}` : ""}
            </Badge>
            {account.cookies_file_present ? (
              <Badge
                variant="outline"
                className="border-sky-500/40 bg-sky-500/10 text-sky-300 text-[10px]"
              >
                MCP cookies file present
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className="border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px]"
              >
                MCP cookies file missing — saving will rewrite it
              </Badge>
            )}
          </>
        ) : (
          <Badge variant="outline" className="text-muted-foreground text-[10px]">
            Not connected
          </Badge>
        )}
      </div>

      <div className="space-y-3">
        <div className="space-y-1.5">
          <Label className="text-sm">LinkedIn email (display only)</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="recruiter@company.com"
            className="h-9"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-sm">
            li_at cookie <span className="text-destructive">*</span>
          </Label>
          <Input
            type="password"
            value={liAt}
            onChange={(e) => setLiAt(e.target.value)}
            placeholder={
              account?.connected
                ? "Paste a new li_at value to rotate, or leave empty"
                : "Paste the li_at cookie value from your LinkedIn session"
            }
            className="h-9"
          />
          <p className="text-[11px] text-muted-foreground">
            How to get it: sign in to linkedin.com, open DevTools → Application
            → Cookies → https://www.linkedin.com, copy the <code>li_at</code> value.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label className="text-sm">JSESSIONID (optional)</Label>
          <Input
            type="password"
            value={jsessionid}
            onChange={(e) => setJsessionid(e.target.value)}
            placeholder="Optional — improves auth stability"
            className="h-9"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Button
          size="sm"
          className="gap-1.5"
          onClick={onConnect}
          disabled={connect.isPending}
        >
          {connect.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <PlugZap className="h-3.5 w-3.5" />
          )}
          {account?.connected ? "Update credentials" : "Connect LinkedIn"}
        </Button>
        {account?.connected && (
          <Button
            size="sm"
            variant="ghost"
            className="gap-1.5 text-destructive"
            onClick={() => disconnect.mutate()}
            disabled={disconnect.isPending}
          >
            {disconnect.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Unplug className="h-3.5 w-3.5" />
            )}
            Disconnect
          </Button>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground/80">
        Cookies are encrypted at rest and written to{" "}
        <code>{account?.cookies_file_path ?? "~/.linkedin-mcp/cookies.json"}</code>{" "}
        so the LinkedIn MCP server uses your authenticated session for{" "}
        <em>Add to Process</em>. They&apos;re never returned to the browser
        after saving.
      </p>
    </Section>
  );
}
