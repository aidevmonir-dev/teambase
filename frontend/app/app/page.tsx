"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button, Card, Meter, Notice, Select } from "@/components/ui";
import { api, type Usage } from "@/lib/api";
import { can, useSession } from "@/lib/session";

interface Project {
  id: number;
  name: string;
  status: "planned" | "active" | "done";
  created_by: string | null;
  updated_at: string;
}

const STATUS_LABEL = { planned: "Planned", active: "Active", done: "Done" } as const;

export default function ProjectsPage() {
  const { me } = useSession();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    const data = await api<{ projects: Project[]; usage: Usage }>("org/projects/");
    setProjects(data.projects);
    setUsage(data.usage);
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load, me.organization.id]);

  async function add(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("org/projects/", { method: "POST", body: { name } });
      setName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add the project.");
    }
  }

  async function setStatus(project: Project, status: string) {
    setError("");
    try {
      await api(`org/projects/${project.id}/`, { method: "PATCH", body: { status } });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update the project.");
    }
  }

  async function remove(project: Project) {
    setError("");
    try {
      await api(`org/projects/${project.id}/`, { method: "DELETE" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the project.");
    }
  }

  const full = usage ? usage.projects_used >= usage.projects : false;

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-navy">Projects</h1>
        <p className="text-sm text-muted">
          The example feature: data that belongs to {me.organization.name} only. Replace it with your own product.
        </p>
      </div>
      {error ? <Notice kind="error">{error}</Notice> : null}
      <Card>
        <form onSubmit={add} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="grid flex-1 gap-1 text-sm font-medium text-muted">
            New project
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              required
              placeholder="e.g. Autumn catalogue"
              className="rounded-lg border-[1.5px] border-line px-3 py-2 text-base text-ink outline-none focus:border-coral"
            />
          </label>
          <Button type="submit" disabled={full}>Add project</Button>
        </form>
        {usage ? (
          <div className="mt-4 grid gap-2">
            <Meter label="Projects on your plan" used={usage.projects_used} limit={usage.projects} />
            {full ? (
              <p className="text-sm">
                You have reached the limit of your plan. <Link className="font-semibold text-navy underline" href="/app/billing/">See plans</Link>
              </p>
            ) : null}
          </div>
        ) : null}
      </Card>

      {projects === null ? (
        <p className="text-muted">Loading projects…</p>
      ) : projects.length === 0 ? (
        <Card><p className="text-muted">No projects yet. Add the first one above.</p></Card>
      ) : (
        <ul className="grid gap-3">
          {projects.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-white px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{p.name}</p>
                <p className="text-xs text-muted">
                  {p.created_by ? `Added by ${p.created_by} · ` : ""}updated {new Date(p.updated_at).toLocaleDateString()}
                </p>
              </div>
              <Select aria-label={`Status of ${p.name}`} value={p.status} onChange={(e) => void setStatus(p, e.target.value)}>
                {Object.entries(STATUS_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </Select>
              {can(me, "admin") || p.created_by === me.user.name ? (
                <Button variant="danger" onClick={() => void remove(p)}>Delete</Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
