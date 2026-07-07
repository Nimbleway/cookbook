"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { ArrowRight, CheckCircle2, Loader2, X } from "lucide-react";
import { conferenceConfig } from "@/lib/config";
import { useToast } from "./toast";

// One in-app lead form, opened from anywhere via useLeadModal().open().
// Email-first capture (no mail-app handoff): name + email POST to /api/lead.
// Every "let's meet" CTA in the app funnels here so there's a single,
// consistent capture experience.
type LeadContext = { keyword?: string; brand?: string | null };
type LeadModalApi = { open: (ctx?: LeadContext) => void };

const LeadModalContext = createContext<LeadModalApi | null>(null);

export function useLeadModal(): LeadModalApi {
  const ctx = useContext(LeadModalContext);
  if (!ctx) throw new Error("useLeadModal must be used within <LeadModalProvider>");
  return ctx;
}

export function LeadModalProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [leadCtx, setLeadCtx] = useState<LeadContext>({});
  const openModal = useCallback((ctx?: LeadContext) => {
    setLeadCtx(ctx ?? {});
    setOpen(true);
  }, []);

  return (
    <LeadModalContext.Provider value={{ open: openModal }}>
      {children}
      {open && <LeadModal ctx={leadCtx} onClose={() => setOpen(false)} />}
    </LeadModalContext.Provider>
  );
}

function LeadModal({ ctx, onClose }: { ctx: LeadContext; onClose: () => void }) {
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done">("idle");
  const toast = useToast();
  const event = conferenceConfig.eventName || "Shoptalk";

  // Close on Escape — standard modal affordance.
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (status === "sending") return;
    setStatus("sending");
    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firstName: first,
          lastName: last,
          company,
          email,
          keyword: ctx.keyword,
          brand: ctx.brand,
        }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Something went wrong.");
      }
      setStatus("done");
    } catch (err) {
      setStatus("idle");
      toast(err instanceof Error ? err.message : "Something went wrong.", "error");
    }
  };

  const done = status === "done";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Meet Nimble at ${event}`}
        className="animate-fade-up relative w-full max-w-md rounded-3xl border border-brand/25 bg-card p-6 shadow-2xl sm:p-7"
      >
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 text-muted-foreground transition hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>

        {done ? (
          <div className="py-2 text-center">
            <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400">
              <CheckCircle2 className="h-7 w-7" />
            </span>
            <h2 className="mt-3 text-xl font-bold tracking-tight">
              Thanks{first ? `, ${first}` : ""}!
            </h2>
            <p className="mx-auto mt-1.5 max-w-xs text-pretty text-sm text-muted-foreground">
              We&apos;ll be in touch to set up time. See you at {event}!
            </p>
            <button
              onClick={onClose}
              className="mt-5 inline-flex items-center justify-center rounded-xl border border-border px-5 py-2 text-sm font-semibold transition hover:border-brand/40"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand">
              Let&apos;s meet at {event}
            </p>
            <h2 className="mt-1.5 text-xl font-bold tracking-tight sm:text-2xl">
              See what Nimble can do for your brand
            </h2>
            <p className="mt-2 text-pretty text-sm text-muted-foreground">
              Leave your details and we&apos;ll set up time at {event} to walk through the
              full live picture for your brand — across every retailer.
            </p>

            <form onSubmit={submit} className="mt-4 space-y-2.5">
              <div className="flex gap-2.5">
                <input
                  value={first}
                  onChange={(e) => setFirst(e.target.value)}
                  required
                  placeholder="First name"
                  aria-label="First name"
                  autoFocus
                  className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-brand/30"
                />
                <input
                  value={last}
                  onChange={(e) => setLast(e.target.value)}
                  required
                  placeholder="Last name"
                  aria-label="Last name"
                  className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-brand/30"
                />
              </div>
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                required
                placeholder="Company"
                aria-label="Company"
                className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-brand/30"
              />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                aria-label="Work email"
                className="h-11 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-brand/30"
              />
              <button
                type="submit"
                disabled={status === "sending"}
                className="inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-xl bg-gold text-sm font-bold text-background transition active:scale-[0.98] disabled:opacity-60"
              >
                {status === "sending" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    Send it to me <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            <p className="mt-3 text-center text-xs text-muted-foreground">
              Prefer email?{" "}
              <a
                href={conferenceConfig.contactUrl}
                className="font-semibold text-brand hover:underline"
              >
                Write to us directly
              </a>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
