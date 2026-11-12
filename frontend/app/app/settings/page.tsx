"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button, Card, Field, Notice } from "@/components/ui";
import { api, type Me } from "@/lib/api";
import { can, useSession } from "@/lib/session";

export default function SettingsPage() {
  const { me, setMe } = useSession();
  const router = useRouter();
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  async function act(action: () => Promise<Me>, success: string) {
    setMessage(null);
    try {
      setMe(await action());
      setMessage({ kind: "success", text: success });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "That did not work." });
    }
  }

  function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = new FormData(event.currentTarget).get("name");
    void act(() => api<Me>("org/", { method: "PATCH", body: { name } }), "The organisation was renamed.");
  }

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const name = new FormData(formElement).get("name");
    void act(async () => {
      const me = await api<Me>("orgs/", { method: "POST", body: { name } });
      formElement.reset();
      router.push("/app/");
      return me;
    }, "Organisation created. You are its owner.");
  }

  return (
    <div className="grid gap-5">
      <h1 className="font-display text-2xl font-bold text-navy">Settings</h1>
      {message ? <Notice kind={message.kind}>{message.text}</Notice> : null}

      <Card>
        <h2 className="mb-3 font-display font-semibold text-navy">Organisation</h2>
        {can(me, "admin") ? (
          <form onSubmit={rename} className="flex flex-col gap-3 sm:flex-row sm:items-end" key={me.organization.id}>
            <div className="flex-1"><Field label="Name" name="name" defaultValue={me.organization.name} required maxLength={120} /></div>
            <Button type="submit">Save name</Button>
          </form>
        ) : (
          <p className="text-sm text-muted">{me.organization.name}. Only admins and owners can rename it.</p>
        )}
      </Card>

      <Card>
        <h2 className="mb-1 font-display font-semibold text-navy">Create another organisation</h2>
        <p className="mb-3 text-sm text-muted">For a second company or client. You can switch between organisations at the top of the page.</p>
        <form onSubmit={create} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1"><Field label="Name" name="name" required maxLength={120} /></div>
          <Button type="submit" variant="quiet">Create</Button>
        </form>
      </Card>

      <Card>
        <h2 className="mb-1 font-display font-semibold text-navy">Leave {me.organization.name}</h2>
        <p className="mb-3 text-sm text-muted">You lose access to its projects. The only owner has to hand over ownership first.</p>
        <Button variant="danger" onClick={() => void act(() => api<Me>("org/leave/", { method: "POST" }), "You left the organisation.")}>
          Leave organisation
        </Button>
      </Card>

      <Card>
        <h2 className="mb-1 font-display font-semibold text-navy">Your account</h2>
        <p className="text-sm text-muted">{me.user.name} · {me.user.email}</p>
      </Card>
    </div>
  );
}
