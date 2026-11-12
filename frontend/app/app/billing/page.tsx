"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Button, Card, Meter, Notice } from "@/components/ui";
import { api, type PlanId, type Usage } from "@/lib/api";
import { useSession } from "@/lib/session";

interface Plan { id: PlanId; name: string; price_month: string; seats: number; projects: number }
interface Billing { plan: PlanId; plans: Plan[]; usage: Usage; mode: "stripe" | "demo"; can_manage: boolean; has_subscription: boolean }

function BillingView() {
  const { refresh } = useSession();
  const checkout = useSearchParams().get("checkout");
  const [data, setData] = useState<Billing | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState<PlanId | "portal" | null>(null);

  const load = useCallback(async () => setData(await api<Billing>("org/billing/")), []);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);

  async function choose(plan: Plan) {
    setBusy(plan.id);
    setError("");
    setDone("");
    try {
      const result = await api<{ url?: string; changed?: boolean }>("org/billing/change/", { method: "POST", body: { plan: plan.id } });
      if (result.url) {
        window.location.href = result.url; // Stripe Checkout
        return;
      }
      setDone(`You are now on the ${plan.name} plan. Demo billing: no payment was taken.`);
      await Promise.all([load(), refresh()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not change the plan.");
    } finally {
      setBusy(null);
    }
  }

  async function portal() {
    setBusy("portal");
    try {
      const result = await api<{ url: string }>("org/billing/portal/", { method: "POST" });
      window.location.href = result.url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open billing management.");
      setBusy(null);
    }
  }

  if (!data) return error ? <Notice kind="error">{error}</Notice> : <p className="text-muted">Loading billing…</p>;

  return (
    <div className="grid gap-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-navy">Billing</h1>
        <p className="text-sm text-muted">Plans set how many seats and projects an organisation can have. Only owners can change the plan.</p>
      </div>
      {data.mode === "demo" ? (
        <Notice>Demo billing mode: no Stripe keys are configured, so plan changes apply at once and no payment is taken.</Notice>
      ) : null}
      {checkout === "success" ? <Notice kind="success">Payment received. Your plan updates as soon as Stripe confirms it, usually within a few seconds.</Notice> : null}
      {checkout === "cancelled" ? <Notice>Checkout was cancelled. Nothing has changed.</Notice> : null}
      {done ? <Notice kind="success">{done}</Notice> : null}
      {error ? <Notice kind="error">{error}</Notice> : null}

      <Card className="grid gap-3">
        <Meter label="Seats" used={data.usage.seats_used} limit={data.usage.seats} />
        <Meter label="Projects" used={data.usage.projects_used} limit={data.usage.projects} />
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {data.plans.map((plan) => {
          const current = plan.id === data.plan;
          return (
            <article key={plan.id} className={`flex flex-col rounded-2xl border bg-white p-6 ${current ? "border-coral shadow-[0_0_0_3px_#ffe4dc]" : "border-line"}`}>
              <h2 className="font-display text-lg font-bold text-navy">{plan.name}</h2>
              <p className="mt-1 text-3xl font-bold">
                €{plan.price_month}<span className="text-sm font-normal text-muted"> / month</span>
              </p>
              <ul className="mt-4 grid gap-1 text-sm">
                <li>{plan.seats} seats</li>
                <li>{plan.projects} projects</li>
              </ul>
              <div className="mt-auto pt-5">
                {current ? (
                  <p className="text-sm font-semibold text-good">Your current plan</p>
                ) : data.can_manage ? (
                  <Button className="w-full" variant={plan.id === "free" ? "quiet" : "primary"} disabled={busy !== null} onClick={() => void choose(plan)}>
                    {busy === plan.id ? "Working…" : plan.id === "free" ? "Downgrade to Free" : `Switch to ${plan.name}`}
                  </Button>
                ) : (
                  <p className="text-sm text-muted">Ask an owner to change the plan.</p>
                )}
              </div>
            </article>
          );
        })}
      </div>
      {data.can_manage && data.has_subscription ? (
        <Button variant="quiet" className="justify-self-start" disabled={busy !== null} onClick={() => void portal()}>
          Manage billing and invoices
        </Button>
      ) : null}
    </div>
  );
}

export default function BillingPage() {
  return (
    <Suspense>
      <BillingView />
    </Suspense>
  );
}
