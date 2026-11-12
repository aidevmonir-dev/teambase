import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "./ui";

export function AuthShell({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-5 py-12">
      <Link href="/" aria-label="TeamBase home" className="mb-8">
        <Logo />
      </Link>
      <div className="w-full max-w-md rounded-2xl border border-line bg-white p-7">
        <h1 className="mb-5 font-display text-2xl font-bold text-navy">{title}</h1>
        {children}
      </div>
      {footer ? <div className="mt-5 text-sm text-muted">{footer}</div> : null}
    </main>
  );
}
