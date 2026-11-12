"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { AuthShell } from "@/components/AuthShell";
import { Button, Field, Notice } from "@/components/ui";
import { api, ApiError, type Me } from "@/lib/api";

function SignupForm() {
  const router = useRouter();
  const params = useSearchParams();
  const inviteToken = params.get("invite") ?? "";
  const invitedEmail = params.get("email") ?? "";
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setFields({});
    try {
      await api<Me>("auth/signup/", {
        method: "POST",
        body: {
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
          organization: form.get("organization") ?? "",
          invite_token: inviteToken,
        },
      });
      router.push("/app/");
    } catch (e) {
      if (e instanceof ApiError) {
        setFields(e.fields);
        if (!Object.keys(e.fields).length || e.fields.invite_token) setError(e.fields.invite_token ?? e.message);
      } else {
        setError("Could not create the account.");
      }
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      {inviteToken ? <Notice>You are joining an organisation by invitation. Use the email address the invitation was sent to.</Notice> : null}
      {error ? <Notice kind="error">{error}</Notice> : null}
      <Field label="Your name" name="name" autoComplete="name" required error={fields.name} />
      <Field label="Work email" name="email" type="email" autoComplete="email" required defaultValue={invitedEmail} readOnly={!!invitedEmail} error={fields.email} />
      <Field label="Password" name="password" type="password" autoComplete="new-password" required minLength={10} hint="At least 10 characters, not a common password." error={fields.password} />
      {inviteToken ? null : <Field label="Company or team name" name="organization" required error={fields.organization} />}
      <Button type="submit" disabled={busy}>{busy ? "Creating your account…" : "Create account"}</Button>
    </form>
  );
}

export default function SignupPage() {
  return (
    <AuthShell title="Create your account" footer={<>Already have an account? <Link className="font-semibold text-navy underline" href="/login/">Log in</Link></>}>
      <Suspense>
        <SignupForm />
      </Suspense>
    </AuthShell>
  );
}
