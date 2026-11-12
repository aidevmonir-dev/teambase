import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "danger" }) {
  const styles = {
    primary: "bg-coral text-white hover:bg-coral-dark",
    quiet: "bg-white text-navy border border-line hover:bg-page",
    danger: "bg-white text-bad border border-line hover:bg-bad-bg",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
    />
  );
}

export function Field({ label, error, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }) {
  return (
    <label className="grid gap-1 text-sm font-medium text-muted">
      {label}
      <input
        {...props}
        aria-invalid={error ? true : undefined}
        className={`rounded-lg border-[1.5px] bg-white px-3 py-2 text-base font-normal text-ink outline-none focus:border-coral ${error ? "border-bad" : "border-line"}`}
      />
      {error ? <span className="text-sm font-normal text-bad">{error}</span> : hint ? <span className="text-xs font-normal">{hint}</span> : null}
    </label>
  );
}

export function Select({ label, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { label?: string; children: ReactNode }) {
  const select = (
    <select {...props} className="rounded-lg border-[1.5px] border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-coral">
      {children}
    </select>
  );
  if (!label) return select;
  return (
    <label className="grid gap-1 text-sm font-medium text-muted">
      {label}
      {select}
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  // Callers pass "p-0" for edge-to-edge lists; only add the default padding when they set none.
  const padding = /(^|\s)p-\d/.test(className) ? "" : "p-6";
  return <section className={`overflow-hidden rounded-2xl border border-line bg-white ${padding} ${className}`}>{children}</section>;
}

export function Notice({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  const styles = {
    info: "bg-[#fff8e1] border-[#f0dfa6] text-ink",
    error: "bg-bad-bg border-[#f3c3be] text-bad",
    success: "bg-good-bg border-[#bfe3cc] text-good",
  }[kind];
  return (
    <p role={kind === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>
      {children}
    </p>
  );
}

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2 font-display text-lg font-bold text-navy">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon.svg" width={28} height={28} alt="" />
      TeamBase
    </span>
  );
}

export function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    owner: "bg-navy text-white",
    admin: "bg-[#fff3e0] text-[#9a5a00]",
    member: "bg-page text-muted",
  };
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${styles[role] ?? styles.member}`}>{role}</span>;
}

export function Meter({ label, used, limit }: { label: string; used: number; limit: number }) {
  const percent = Math.min(100, Math.round((used / Math.max(limit, 1)) * 100));
  const full = used >= limit;
  return (
    <div className="grid gap-1 text-sm">
      <div className="flex justify-between">
        <span className="font-medium">{label}</span>
        <span className={full ? "font-semibold text-bad" : "text-muted"}>
          {used} of {limit}
        </span>
      </div>
      <div className="h-2 rounded-full bg-page" aria-hidden>
        <div className={`h-2 rounded-full ${full ? "bg-bad" : "bg-navy"}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
