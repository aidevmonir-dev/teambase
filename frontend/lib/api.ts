// A tiny client for the Django API. Same origin, session cookie, CSRF header on every write.

export type Role = "owner" | "admin" | "member";
export type PlanId = "free" | "pro" | "business";

export interface Me {
  user: { id: number; name: string; email: string; is_demo: boolean };
  organization: { id: number; name: string; plan: PlanId; role: Role };
  organizations: { id: number; name: string; role: Role }[];
}

export interface Usage {
  seats_used: number;
  seats: number;
  projects_used: number;
  projects: number;
}

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;

  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

let csrfReady: Promise<void> | null = null;
function ensureCsrf(): Promise<void> {
  if (csrfToken()) return Promise.resolve();
  csrfReady ??= fetch("/api/auth/csrf/", { credentials: "same-origin" }).then(() => undefined);
  return csrfReady;
}

/** Turns a DRF error body ({"detail": ...} or {"field": [..]}) into one readable message plus per-field text. */
function readError(status: number, body: unknown): ApiError {
  const fields: Record<string, string> = {};
  let message = "";
  if (body && typeof body === "object") {
    for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
      const text = Array.isArray(value) ? value.join(" ") : String(value);
      if (key === "detail" || key === "non_field_errors") message = text;
      else fields[key] = text;
    }
  }
  if (!message) message = Object.values(fields)[0] ?? (status >= 500 ? "Something went wrong on our side. Try again." : "That request was not accepted.");
  return new ApiError(status, message, fields);
}

export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = csrfToken();
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`/api/${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) throw readError(response.status, body);
  return body as T;
}
