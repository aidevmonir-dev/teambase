"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button, Card, Field, Meter, Notice, RoleBadge, Select } from "@/components/ui";
import { api, ApiError, type Role, type Usage } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Member { id: number; user_id: number; name: string; email: string; role: Role; joined_at: string }
interface Invite { id: number; email: string; role: Role; expires_at: string; is_open: boolean; link?: string }
interface TeamData { members: Member[]; invitations: Invite[]; usage: Usage; can_manage: boolean; can_change_roles: boolean }

export default function TeamPage() {
  const { me } = useSession();
  const [team, setTeam] = useState<TeamData | null>(null);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [copied, setCopied] = useState<number | null>(null);

  const load = useCallback(async () => setTeam(await api<TeamData>("org/members/")), []);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load, me.organization.id]);

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
    }
  }

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setError("");
    setFieldError("");
    try {
      await api("org/invitations/", { method: "POST", body: { email: form.get("email"), role: form.get("role") } });
      formElement.reset();
      await load();
    } catch (e) {
      if (e instanceof ApiError && e.fields.email) setFieldError(e.fields.email);
      else setError(e instanceof Error ? e.message : "Could not send the invitation.");
    }
  }

  async function copy(invitation: Invite) {
    if (!invitation.link) return;
    await navigator.clipboard.writeText(invitation.link);
    setCopied(invitation.id);
    setTimeout(() => setCopied(null), 2000);
  }

  if (!team) return error ? <Notice kind="error">{error}</Notice> : <p className="text-muted">Loading the team…</p>;
  const seatsFull = team.usage.seats_used >= team.usage.seats;
  const isOwner = team.can_change_roles;

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-navy">Team</h1>
        <p className="text-sm text-muted">Owners manage billing and roles. Admins invite and remove members. Members work on projects.</p>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}

      <Card>
        <Meter label="Seats used (members and open invitations)" used={team.usage.seats_used} limit={team.usage.seats} />
        {team.can_manage ? (
          <form onSubmit={invite} className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
            <Field label="Invite by email" name="email" type="email" required placeholder="name@company.com" error={fieldError} />
            <Select label="Role" name="role" defaultValue="member">
              <option value="member">Member</option>
              {isOwner ? <option value="admin">Admin</option> : null}
            </Select>
            <Button type="submit" disabled={seatsFull}>Send invitation</Button>
          </form>
        ) : null}
        {team.can_manage && seatsFull ? (
          <p className="mt-3 text-sm">
            All seats are in use. <Link className="font-semibold text-navy underline" href="/app/billing/">Upgrade the plan</Link> to invite more people.
          </p>
        ) : null}
      </Card>

      <Card className="p-0">
        <h2 className="border-b border-line px-6 py-4 font-display font-semibold text-navy">Members</h2>
        <ul>
          {team.members.map((m) => {
            const self = m.user_id === me.user.id;
            const canRemove = team.can_manage && !self && (m.role === "member" || isOwner);
            return (
              <li key={m.id} className="flex flex-wrap items-center gap-3 border-b border-line px-6 py-3 last:border-0">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{m.name}{self ? " (you)" : ""}</p>
                  <p className="truncate text-sm text-muted">{m.email}</p>
                </div>
                {isOwner && !self ? (
                  <Select aria-label={`Role of ${m.name}`} value={m.role} onChange={(e) => void run(() => api(`org/members/${m.id}/`, { method: "PATCH", body: { role: e.target.value } }))}>
                    <option value="owner">Owner</option>
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                  </Select>
                ) : (
                  <RoleBadge role={m.role} />
                )}
                {canRemove ? (
                  <Button variant="danger" onClick={() => void run(() => api(`org/members/${m.id}/`, { method: "DELETE" }))}>Remove</Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </Card>

      {team.can_manage ? (
        <Card className="p-0">
          <h2 className="border-b border-line px-6 py-4 font-display font-semibold text-navy">Pending invitations</h2>
          {team.invitations.length === 0 ? (
            <p className="px-6 py-4 text-sm text-muted">No pending invitations.</p>
          ) : (
            <ul>
              {team.invitations.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-3 border-b border-line px-6 py-3 last:border-0">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{i.email}</p>
                    <p className="text-sm text-muted">
                      {i.is_open ? `Expires ${new Date(i.expires_at).toLocaleDateString()}` : "Expired"} · joins as {i.role}
                    </p>
                  </div>
                  {i.link ? (
                    <Button variant="quiet" onClick={() => void copy(i)}>{copied === i.id ? "Link copied" : "Copy invite link"}</Button>
                  ) : null}
                  <Button variant="danger" onClick={() => void run(() => api(`org/invitations/${i.id}/`, { method: "DELETE" }))}>Revoke</Button>
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-6 py-3 text-xs text-muted">This demo sends no email: copy the link and share it. Connect an email provider to send it automatically.</p>
        </Card>
      ) : null}
    </div>
  );
}
