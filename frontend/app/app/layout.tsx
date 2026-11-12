"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Logo, RoleBadge } from "@/components/ui";
import { api, type Me } from "@/lib/api";
import { can, SessionProvider, useSession } from "@/lib/session";

function Shell({ children }: { children: ReactNode }) {
  const { me, setMe } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [switching, setSwitching] = useState(false);

  const links = [
    { href: "/app/", label: "Projects", show: true },
    { href: "/app/team/", label: "Team", show: true },
    { href: "/app/billing/", label: "Billing", show: true },
    { href: "/app/activity/", label: "Activity", show: can(me, "admin") },
    { href: "/app/settings/", label: "Settings", show: true },
  ];

  async function switchTo(id: string) {
    setSwitching(true);
    try {
      setMe(await api<Me>(`orgs/${id}/switch/`, { method: "POST" }));
      router.push("/app/");
    } finally {
      setSwitching(false);
    }
  }

  async function logout() {
    await api("auth/logout/", { method: "POST" }).catch(() => undefined);
    window.location.href = "/";
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      {me.user.is_demo ? (
        <p className="bg-navy px-5 py-2 text-center text-sm text-white">
          You are in a demo workspace with sample data. Everything works, nothing is real, and it is deleted after 24 hours.
        </p>
      ) : null}
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-white px-5 py-3">
        <Link href="/app/" aria-label="TeamBase dashboard">
          <Logo />
        </Link>
        <label className="ml-2 flex items-center gap-2 text-sm">
          <span className="sr-only">Organisation</span>
          <select
            value={me.organization.id}
            disabled={switching}
            onChange={(e) => void switchTo(e.target.value)}
            className="max-w-56 rounded-lg border border-line bg-white px-2 py-1.5 font-semibold text-navy"
          >
            {me.organizations.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </label>
        <RoleBadge role={me.organization.role} />
        <span className="ml-auto hidden text-sm text-muted sm:inline">{me.user.name}</span>
        <button onClick={() => void logout()} className="text-sm font-semibold text-navy underline">Log out</button>
      </header>
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-6 md:flex-row">
        <nav aria-label="Workspace" className="flex gap-1 overflow-x-auto md:w-48 md:flex-col">
          {links.filter((l) => l.show).map((l) => {
            const active = l.href === "/app/" ? pathname === "/app/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm font-semibold whitespace-nowrap ${active ? "bg-white text-navy shadow-[inset_3px_0_0_var(--color-coral)]" : "text-muted hover:bg-white"}`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <Shell>{children}</Shell>
    </SessionProvider>
  );
}
