"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { AuthShell } from "@/components/AuthShell";
import { Button, Field, Notice } from "@/components/ui";
import { api, type Me } from "@/lib/api";

function safeNext(value: string | null): string {
  // Only follow local paths, so a crafted link cannot send people to another site after login.
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/app/";
}

function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api<Me>("auth/login/", { method: "POST", body: { email: form.get("email"), password: form.get("password") } });
      router.push(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not sign in.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      {error ? <Notice kind="error">{error}</Notice> : null}
      <Field label="Email" name="email" type="email" autoComplete="email" required />
      <Field label="Password" name="password" type="password" autoComplete="current-password" required />
      <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Log in"}</Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthShell title="Log in" footer={<>No account yet? <Link className="font-semibold text-navy underline" href="/signup/">Create one</Link></>}>
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
