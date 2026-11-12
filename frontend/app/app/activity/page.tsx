"use client";

import { useEffect, useState } from "react";
import { Card, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Event { id: number; action: string; detail: string; actor: string; at: string }

const LABELS: Record<string, string> = {
  "organisation.created": "created the organisation",
  "organisation.renamed": "renamed the organisation",
  "member.added": "added a member",
  "member.removed": "removed a member",
  "member.left": "left the organisation",
  "member.role_changed": "changed a role",
  "invitation.sent": "sent an invitation",
  "invitation.revoked": "revoked an invitation",
  "invitation.accepted": "accepted an invitation",
  "project.created": "added a project",
  "project.updated": "updated a project",
  "project.deleted": "deleted a project",
  "plan.changed": "changed the plan",
};

export default function ActivityPage() {
  const { me } = useSession();
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ events: Event[] }>("org/activity/").then((d) => setEvents(d.events), (e) => setError(e.message));
  }, [me.organization.id]);

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-navy">Activity</h1>
        <p className="text-sm text-muted">Who did what in {me.organization.name}. Visible to admins and owners.</p>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {events === null && !error ? <p className="text-muted">Loading activity…</p> : null}
      {events ? (
        <Card className="p-0">
          <ol>
            {events.map((e) => (
              <li key={e.id} className="flex flex-wrap gap-x-3 gap-y-1 border-b border-line px-6 py-3 text-sm last:border-0">
                <span className="w-36 shrink-0 text-muted">{new Date(e.at).toLocaleString()}</span>
                <span className="min-w-0 flex-1">
                  <strong>{e.actor}</strong> {LABELS[e.action] ?? e.action}
                  {e.detail ? <span className="text-muted">: {e.detail}</span> : null}
                </span>
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}
