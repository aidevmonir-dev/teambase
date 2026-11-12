"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Logo, Notice } from "@/components/ui";
import { api, type Me } from "@/lib/api";

const FEATURES = [
  ["Organisations as tenants", "Every record belongs to an organisation, and every query is scoped to the signed-in member's organisation. Users can belong to several and switch between them."],
  ["Roles that mean something", "Owners handle billing and roles, admins manage the team, members do the work. Enforced on the server, tested in the suite."],
  ["Invitations and seat limits", "Invite by email with a one-time link. Open invitations count against the plan's seats, so a team cannot outgrow its plan."],
  ["Plans and Stripe billing", "Free, Pro and Business with seat and project limits. Stripe Checkout to upgrade, signed webhooks to confirm, a customer portal to manage."],
  ["Audit log", "Who invited whom, who changed a role, who upgraded the plan. Visible to admins under Activity."],
  ["One deploy, one origin", "Django serves the REST API and the exported Next.js app together. Session cookies with CSRF, no tokens in local storage."],
];

export default function Home() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function tryDemo() {
    setBusy(true);
    setError("");
    try {
      await api<Me>("auth/demo/", { method: "POST" });
      router.push("/app/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the demo.");
      setBusy(false);
    }
  }

  return (
    <>
      <header className="flex items-center gap-4 border-b border-line bg-white px-5 py-3">
        <Logo />
        <span className="mr-auto text-sm text-muted">
          A demo by <a className="underline" href="https://devomio.com/">Devomio</a>
        </span>
        <Link href="/login/" className="text-sm font-semibold text-navy">Log in</Link>
        <a href="https://github.com/aidevmonir-dev/teambase" className="hidden text-sm font-semibold text-navy underline sm:inline">Source on GitHub</a>
      </header>

      <main className="mx-auto w-full max-w-5xl px-5 py-14">
        <h1 className="max-w-3xl font-display text-4xl font-bold leading-tight text-navy sm:text-5xl">
          The part every SaaS needs, built once and tested.
        </h1>
        <p className="mt-5 max-w-2xl text-lg">
          TeamBase is a starter for multi-tenant products: sign-up, organisations, roles, invitations, plans with limits,
          Stripe billing and an audit log. Django REST backend, Next.js frontend, one deployment.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button onClick={tryDemo} disabled={busy} className="px-6 py-3 text-base">
            {busy ? "Setting up your demo…" : "Try the demo"}
          </Button>
          <Link href="/signup/" className="inline-flex items-center rounded-lg border border-line bg-white px-6 py-3 font-semibold text-navy hover:bg-page">
            Create an account
          </Link>
        </div>
        <p className="mt-3 text-sm text-muted">The demo signs you in to a sample company with a team and projects. It is deleted after 24 hours.</p>
        {error ? <div className="mt-4 max-w-xl"><Notice kind="error">{error}</Notice></div> : null}

        <section className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-label="What is included">
          {FEATURES.map(([title, text]) => (
            <article key={title} className="rounded-2xl border border-line bg-white p-5">
              <h2 className="font-display text-base font-semibold text-navy">{title}</h2>
              <p className="mt-2 text-sm text-muted">{text}</p>
            </article>
          ))}
        </section>
      </main>

      <footer className="mt-auto border-t border-line bg-white px-5 py-5 text-sm text-muted">
        <p className="mx-auto max-w-5xl">
          Built by <a className="underline" href="https://devomio.com/">Devomio</a>. Need a SaaS product built on a base like this?{" "}
          <a className="underline" href="mailto:hello@devomio.com">hello@devomio.com</a>
        </p>
      </footer>
    </>
  );
}
