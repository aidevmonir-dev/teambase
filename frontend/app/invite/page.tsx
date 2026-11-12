"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { Button, Notice } from "@/components/ui";
import { api, type Me } from "@/lib/api";

interface Preview {
  valid: boolean;
  organization?: string;
  email?: string;
  role?: string;
  invited_by?: string | null;
  signed_in_as?: string | null;
}

function Invitation() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setPreview({ valid: false });
      return;
    }
    api<Preview>(`invitations/${encodeURIComponent(token)}/`).then(setPreview, () => setPreview({ valid: false }));
  }, [token]);

  async function accept() {
    setBusy(true);
    setError("");
    try {
      await api<Me>(`invitations/${encodeURIComponent(token)}/accept/`, { method: "POST" });
      router.push("/app/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not accept the invitation.");
      setBusy(false);
    }
  }

  if (!preview) return <p className="text-muted">Checking the invitation…</p>;
  if (!preview.valid) {
    return <Notice kind="error">This invitation has expired or was already used. Ask the person who invited you for a new link.</Notice>;
  }

  const sameUser = preview.signed_in_as?.toLowerCase() === preview.email?.toLowerCase();
  return (
    <div className="grid gap-4">
      <p>
        {preview.invited_by ? `${preview.invited_by} invited you` : "You have been invited"} to join <strong>{preview.organization}</strong> as{" "}
        {preview.role === "admin" ? "an admin" : "a member"}.
      </p>
      {error ? <Notice kind="error">{error}</Notice> : null}
      {sameUser ? (
        <Button onClick={accept} disabled={busy}>{busy ? "Joining…" : `Join ${preview.organization}`}</Button>
      ) : preview.signed_in_as ? (
        <Notice>
          This invitation is for {preview.email}, but you are signed in as {preview.signed_in_as}. Log out and sign in with the invited address.
        </Notice>
      ) : (
        <div className="grid gap-2">
          <Link
            className="inline-flex justify-center rounded-lg bg-coral px-4 py-2 text-sm font-semibold text-white hover:bg-coral-dark"
            href={`/signup/?invite=${encodeURIComponent(token)}&email=${encodeURIComponent(preview.email ?? "")}`}
          >
            Create an account to join
          </Link>
          <Link className="text-center text-sm font-semibold text-navy underline" href={`/login/?next=${encodeURIComponent(`/invite/?token=${token}`)}`}>
            I already have an account
          </Link>
        </div>
      )}
    </div>
  );
}

export default function InvitePage() {
  return (
    <AuthShell title="You have been invited">
      <Suspense>
        <Invitation />
      </Suspense>
    </AuthShell>
  );
}
