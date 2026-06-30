"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  UserPlus, Mail, MoreHorizontal, Loader2, CheckCircle2, Copy,
  RefreshCw, Trash2, Eye, EyeOff, AlertTriangle, ArrowLeft, Send,
} from "lucide-react";
import { membersApi } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  useMembers, useInviteMember, useResendInvite, useRemoveMember,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores/auth.store";
import { cn } from "@/lib/utils/cn";
import { relativeTime, shortDate, initials } from "@/lib/utils/format";
import type { Member, UserRole } from "@/types";

const inviteSchema = z.object({
  full_name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role: z.enum(["recruiter", "hiring_manager", "interviewer", "admin"]),
});
type InviteForm = z.infer<typeof inviteSchema>;

const roleConfig: Record<UserRole, { label: string; color: string }> = {
  admin:          { label: "Admin",          color: "bg-violet-500/10 text-violet-400 border-violet-500/20" },
  super_admin:    { label: "Super Admin",    color: "bg-destructive/10 text-red-400 border-destructive/20" },
  recruiter:      { label: "Recruiter",      color: "bg-primary/10 text-primary border-primary/20" },
  hiring_manager: { label: "Hiring Mgr.",    color: "bg-teal-500/10 text-teal-400 border-teal-500/20" },
  interviewer:    { label: "Interviewer",    color: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20" },
  candidate:      { label: "Candidate",      color: "bg-muted/40 text-muted-foreground border-border/40" },
};

const statusConfig: Record<string, { label: string; color: string }> = {
  active:    { label: "Active",    color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  pending:   { label: "Pending",   color: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  invited:   { label: "Pending",   color: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
  inactive:  { label: "Inactive",  color: "bg-muted/40 text-muted-foreground border-border/40" },
  suspended: { label: "Suspended", color: "bg-destructive/10 text-red-400 border-destructive/20" },
};

// Auto-generate a memorable temp password if the inviter prefers
function generateTempPassword(): string {
  const adj = ["brisk", "lucid", "quick", "swift", "calm", "bold", "keen", "fair"];
  const noun = ["sparrow", "compass", "harbor", "lantern", "ember", "stream", "summit", "willow"];
  const pick = (arr: string[]) => arr[Math.floor(Math.random() * arr.length)];
  return `${pick(adj)}-${pick(noun)}-${Math.floor(1000 + Math.random() * 9000)}`;
}

// ── Row action menu ─────────────────────────────────────────────────────────

function MemberActionsMenu({
  member,
  orgId,
  onResent,
  onRemoved,
}: {
  member: Member;
  orgId: string;
  onResent: (info: { email: string; password: string }) => void;
  onRemoved: () => void;
}) {
  const resend = useResendInvite();
  const remove = useRemoveMember();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isExpired = member.status === "inactive";
  const canReinvite =
    member.status === "pending" || member.status === "invited" || isExpired;

  const handleResend = async () => {
    const password = generateTempPassword();
    try {
      await resend.mutateAsync({
        orgId,
        membershipId: member.id,
        temporaryPassword: password,
      });
      onResent({ email: member.email, password });
    } catch {
      // The dropdown will close automatically; surface errors via alert below
    }
  };

  const handleDelete = async () => {
    await remove.mutateAsync({ orgId, membershipId: member.id });
    setConfirmDelete(false);
    onRemoved();
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-50 group-hover:opacity-100"
              aria-label="Member actions"
            />
          }
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
            {member.name}
          </div>
          {canReinvite && (
            <DropdownMenuItem
              onClick={handleResend}
              disabled={resend.isPending}
              className="gap-2 text-xs"
            >
              {resend.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              {isExpired ? "Re-invite (restart 2-day window)" : "Resend invite"}
            </DropdownMenuItem>
          )}
          <DropdownMenuItem
            onClick={() => setConfirmDelete(true)}
            className="gap-2 text-xs text-rose-400 focus:bg-rose-500/10 focus:text-rose-300"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove from organisation
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="glass border-border/60 max-w-sm">
          <DialogHeader>
            <DialogTitle className="font-heading text-base flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-400" />
              Remove member
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Remove <span className="font-semibold text-foreground">{member.name}</span>{" "}
            from this organisation? Their user account stays — they just
            lose access here.
          </p>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirmDelete(false)}
              disabled={remove.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={remove.isPending}
              className="gap-1.5"
            >
              {remove.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Credentials display (after invite or resend) ────────────────────────────

function CredentialsCard({ email, password }: { email: string; password: string }) {
  const [revealed, setRevealed] = useState(true);
  const [copied, setCopied] = useState<"email" | "password" | "both" | null>(null);

  const copy = async (text: string, key: "email" | "password" | "both") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // clipboard blocked — user can select manually
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-emerald-300">
          Temporary credentials
        </p>
        <button
          type="button"
          onClick={() => setRevealed(!revealed)}
          className="text-muted-foreground hover:text-foreground"
          aria-label={revealed ? "Hide password" : "Show password"}
        >
          {revealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>
      <div className="space-y-1.5 text-[12px]">
        <div className="flex items-center justify-between gap-2 rounded-md border border-border/40 bg-background/40 px-2.5 py-1.5">
          <span className="text-muted-foreground">Email</span>
          <span className="flex items-center gap-1.5">
            <span className="font-mono text-foreground">{email}</span>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => copy(email, "email")}
              aria-label="Copy email"
            >
              {copied === "email" ? (
                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          </span>
        </div>
        <div className="flex items-center justify-between gap-2 rounded-md border border-border/40 bg-background/40 px-2.5 py-1.5">
          <span className="text-muted-foreground">Password</span>
          <span className="flex items-center gap-1.5">
            <span className="font-mono text-foreground">
              {revealed ? password : "•".repeat(Math.max(6, password.length))}
            </span>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={() => copy(password, "password")}
              aria-label="Copy password"
            >
              {copied === "password" ? (
                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
              ) : (
                <Copy className="h-3 w-3" />
              )}
            </button>
          </span>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-full gap-1.5 text-xs"
          onClick={() =>
            copy(`Email: ${email}\nTemporary password: ${password}`, "both")
          }
        >
          {copied === "both" ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Copied!
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" /> Copy both
            </>
          )}
        </Button>
      </div>
      <p className="text-[10px] text-emerald-200/70">
        The invitation email was also sent to this address. If SMTP isn’t
        configured the email is logged on the backend instead — share these
        credentials with the new member manually.
      </p>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function MembersPage() {
  const { data: members = [] } = useMembers();
  const { mutateAsync: invite, isPending } = useInviteMember();
  const orgId = useAuthStore((s) => s.user?.orgId ?? "");
  const orgName = useAuthStore((s) => s.user?.orgName ?? "your organisation");
  const userRole = useAuthStore((s) => s.user?.role);
  const userPermissions = useAuthStore((s) => s.user?.permissions ?? []);
  const canInvite =
    userRole === "admin" ||
    userPermissions.includes("org.manage_members");

  const [dialogOpen, setDialogOpen] = useState(false);
  // After-invite credentials displayed inline so HR can copy them even when
  // SMTP isn't configured. Cleared when the dialog is reopened.
  const [credentials, setCredentials] = useState<{ email: string; password: string } | null>(null);
  // After-resend toast (top of the table) so HR sees the fresh credentials.
  const [resendCreds, setResendCreds] = useState<{ email: string; password: string } | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  // Approval step: the exact email (recipient + subject + body) is shown
  // first; nothing is created or sent until the admin approves it.
  const [preview, setPreview] = useState<{ to: string; subject: string; body: string } | null>(null);
  const [pendingForm, setPendingForm] = useState<InviteForm | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const { register, handleSubmit, formState: { errors }, setValue, watch, reset } = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "recruiter" },
  });
  const passwordValue = watch("password");

  const fillGenerated = () => setValue("password", generateTempPassword());

  const closeDialog = () => {
    setDialogOpen(false);
    setCredentials(null);
    setInviteError(null);
    setPreview(null);
    setPendingForm(null);
    reset();
  };

  // Step 1 — compose the exact email and show it for approval. Nothing is
  // created or sent yet.
  const onPreview = async (data: InviteForm) => {
    setInviteError(null);
    setPreviewLoading(true);
    try {
      const composed = await membersApi.invitePreview(orgId, {
        full_name: data.full_name,
        email: data.email,
        password: data.password,
        role_code: data.role,
      });
      setPendingForm(data);
      setPreview(composed);
    } catch (e) {
      setInviteError(e instanceof Error ? e.message : "Could not build the email preview.");
    } finally {
      setPreviewLoading(false);
    }
  };

  // Step 2 — admin approved the email: create the member + send it.
  const approveAndSend = async () => {
    if (!pendingForm) return;
    setInviteError(null);
    try {
      await invite({
        orgId,
        full_name: pendingForm.full_name,
        email: pendingForm.email,
        password: pendingForm.password,
        role_code: pendingForm.role,
      });
      setCredentials({ email: pendingForm.email, password: pendingForm.password });
      setPreview(null);
      setPendingForm(null);
    } catch (e) {
      setInviteError(e instanceof Error ? e.message : "Invite failed.");
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-foreground">Team Members</h1>
          <p className="text-sm text-muted-foreground">{members.length} members in {orgName}</p>
        </div>
        {canInvite && (
          <Button
            size="sm"
            className="gap-1.5 h-9"
            onClick={() => { setDialogOpen(true); setCredentials(null); setInviteError(null); reset(); }}
          >
            <UserPlus className="h-3.5 w-3.5" /> Invite Member
          </Button>
        )}
      </div>

      {/* Banner: just-resent credentials */}
      {resendCreds && (
        <div className="glass rounded-xl p-4">
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-[10px] uppercase tracking-wider text-emerald-300">
                Invite resent
              </Badge>
              <p className="text-[12px] text-muted-foreground">
                New temporary password set for <span className="text-foreground">{resendCreds.email}</span>
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setResendCreds(null)}>Dismiss</Button>
          </div>
          <CredentialsCard email={resendCreds.email} password={resendCreds.password} />
        </div>
      )}

      {/* Table */}
      <div className="glass rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border/40 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground/60">
              <th className="px-4 py-3 text-left">Member</th>
              <th className="px-4 py-3 text-left">Role</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Invited</th>
              <th className="px-4 py-3 text-left">Activated</th>
              <th className="px-4 py-3 text-left">Joined</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {members.map((member, i) => {
              const roleConf = roleConfig[member.role];
              const statConf = statusConfig[member.status] ?? statusConfig.active;
              return (
                <motion.tr
                  key={member.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="group hover:bg-muted/20 transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={member.avatar} />
                        <AvatarFallback className="bg-primary/10 text-primary text-[11px]">
                          {initials(member.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <p className="text-sm font-semibold text-foreground">{member.name}</p>
                        <p className="text-[11px] text-muted-foreground">{member.email}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full border px-2 py-0.5 text-[11px] font-semibold", roleConf.color)}>
                      {roleConf.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full border px-2 py-0.5 text-[11px] font-semibold", statConf.color)}>
                      {statConf.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[12px] text-muted-foreground">
                    {member.invitedAt ? relativeTime(member.invitedAt) : "—"}
                  </td>
                  <td className="px-4 py-3 text-[12px] text-muted-foreground">
                    {member.activatedAt
                      ? shortDate(member.activatedAt)
                      : member.status === "pending"
                        ? "—"
                        : shortDate(member.joinedAt)}
                  </td>
                  <td className="px-4 py-3 text-[12px] text-muted-foreground">
                    {shortDate(member.joinedAt)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {canInvite && (
                      <MemberActionsMenu
                        member={member}
                        orgId={orgId}
                        onResent={(info) => setResendCreds(info)}
                        onRemoved={() => {/* hooks already invalidate query */}}
                      />
                    )}
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Invite dialog */}
      <Dialog open={dialogOpen} onOpenChange={(v) => { if (!v) closeDialog(); else setDialogOpen(true); }}>
        <DialogContent className={cn("glass border-border/60", preview && !credentials ? "max-w-lg" : "max-w-sm")}>
          <DialogHeader>
            <DialogTitle className="font-heading text-base flex items-center gap-2">
              {preview && !credentials ? (
                <><Mail className="h-4 w-4 text-primary" /> Review invitation email</>
              ) : (
                <><UserPlus className="h-4 w-4 text-primary" /> Invite Team Member</>
              )}
            </DialogTitle>
          </DialogHeader>
          {!credentials && preview ? (
            <div className="space-y-4 py-1">
              <p className="text-xs text-muted-foreground">
                This is the exact email that will be sent. Nothing is sent until you approve it.
              </p>
              <div className="space-y-2">
                <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">To</p>
                  <p className="text-sm font-mono text-foreground">{preview.to}</p>
                </div>
                <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">Subject</p>
                  <p className="text-sm text-foreground">{preview.subject}</p>
                </div>
                <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 mb-1">Message</p>
                  <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/90 font-sans">
                    {preview.body}
                  </pre>
                </div>
              </div>
              {inviteError && <p className="text-xs text-rose-400">{inviteError}</p>}
              <DialogFooter className="gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => { setPreview(null); setInviteError(null); }}
                  disabled={isPending}
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Back to edit
                </Button>
                <Button type="button" size="sm" onClick={approveAndSend} disabled={isPending} className="gap-1.5">
                  {isPending
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Sending…</>
                    : <><Send className="h-3.5 w-3.5" /> Approve &amp; Send</>}
                </Button>
              </DialogFooter>
            </div>
          ) : credentials ? (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                <p className="font-semibold text-foreground text-sm">Invite sent</p>
              </div>
              <p className="text-xs text-muted-foreground">
                The new member appears as <span className="font-semibold text-amber-300">Pending</span>.
                Their status flips to <span className="font-semibold text-emerald-300">Active</span> the
                first time they sign in. If they don&apos;t sign in within{" "}
                <span className="font-semibold text-foreground">2 days</span>, the invite expires and
                they become <span className="font-semibold text-muted-foreground">Inactive</span> — you
                can re-invite them anytime.
              </p>
              <CredentialsCard email={credentials.email} password={credentials.password} />
              <DialogFooter>
                <Button type="button" size="sm" onClick={closeDialog}>Done</Button>
              </DialogFooter>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onPreview)} className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label className="text-sm">Full name</Label>
                <Input
                  placeholder="Jane Smith"
                  {...register("full_name")}
                  className={cn("h-9", errors.full_name && "border-destructive")}
                />
                {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Email address</Label>
                <Input
                  type="email"
                  placeholder="colleague@techcorp.io"
                  {...register("email")}
                  className={cn("h-9", errors.email && "border-destructive")}
                />
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm flex items-center justify-between">
                  Temporary password
                  <button
                    type="button"
                    onClick={fillGenerated}
                    className="text-[10px] font-medium text-primary hover:underline"
                  >
                    Generate
                  </button>
                </Label>
                <Input
                  type="text"
                  placeholder="Min. 8 characters"
                  {...register("password")}
                  className={cn("h-9 font-mono text-[12px]", errors.password && "border-destructive")}
                />
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                <p className="text-[10px] text-muted-foreground/60">
                  Shown once after invite so you can pass it along. The member changes it after first login.
                </p>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Role</Label>
                <Select defaultValue="recruiter" onValueChange={(v) => setValue("role", v as InviteForm["role"])}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="recruiter">Recruiter</SelectItem>
                    <SelectItem value="hiring_manager">Hiring Manager</SelectItem>
                    <SelectItem value="interviewer">Interviewer</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {inviteError && (
                <p className="text-xs text-rose-400">{inviteError}</p>
              )}

              <DialogFooter>
                <Button type="button" variant="ghost" size="sm" onClick={closeDialog}>Cancel</Button>
                <Button type="submit" size="sm" disabled={previewLoading || !passwordValue} className="gap-1.5">
                  {previewLoading
                    ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Preparing…</>
                    : <><Eye className="h-3.5 w-3.5" /> Preview Email</>}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
