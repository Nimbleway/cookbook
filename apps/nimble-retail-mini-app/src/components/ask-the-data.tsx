"use client";

import { useRef, useState } from "react";
import { Send, Sparkles, Loader2, MessageSquare, ArrowRight } from "lucide-react";
import type { InsightPayload } from "@/lib/types";

const SUGGESTED = [
  "Who's buying the shelf vs earning it?",
  "Which retailer is mine to win?",
  "Where is the category leader exposed?",
  "What would my weekly report miss?",
];

type Turn = { role: "user" | "assistant"; text: string };

// Feels like chatting with a retail analyst. Streams Claude Sonnet token-by-
// token. Entirely separate from insight rendering — nothing here blocks the
// page; insights are already on screen before a question is ever asked.
export function AskTheData({ insights }: { insights: InsightPayload }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    setInput("");
    setTurns((t) => [...t, { role: "user", text: q }, { role: "assistant", text: "" }]);
    setBusy(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "ask", question: q, payload: insights }),
      });
      if (!res.ok || !res.body) {
        throw new Error(await res.text().catch(() => "Ask failed"));
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setTurns((t) => {
          const next = [...t];
          next[next.length - 1] = {
            role: "assistant",
            text: next[next.length - 1].text + chunk,
          };
          return next;
        });
        scrollRef.current?.scrollTo({ top: 999999, behavior: "smooth" });
      }
    } catch (err) {
      setTurns((t) => {
        const next = [...t];
        next[next.length - 1] = {
          role: "assistant",
          text:
            err instanceof Error && err.message.includes("ANTHROPIC")
              ? "Add ANTHROPIC_API_KEY to enable Ask-the-Data."
              : "Sorry — couldn't reach the analyst. Try again.",
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-3xl border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border bg-gradient-to-r from-brand/10 to-transparent px-5 py-3.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gold">
          <MessageSquare className="h-4 w-4 text-background" />
        </div>
        <div>
          <h3 className="font-semibold tracking-tight">Ask a follow-up</h3>
          <p className="text-xs text-muted-foreground">
            Anything about this shelf — answer, why it matters, what to do
          </p>
        </div>
      </div>

      <div ref={scrollRef} className="max-h-80 space-y-3 overflow-y-auto p-5">
        {turns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Ask anything about{" "}
            <span className="font-medium text-foreground">{insights.keyword}</span>{" "}
            {`across ${insights.retailers.length} retailers`} — you&apos;ll get a
            straight answer and why it&apos;s interesting.
          </p>
        ) : (
          turns.map((t, i) => (
            <div
              key={i}
              className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`${
                  t.role === "user"
                    ? "max-w-[85%] rounded-2xl bg-foreground px-3.5 py-2 text-sm leading-relaxed text-background"
                    : "w-full rounded-2xl border border-border bg-secondary px-3.5 py-3 text-sm"
                }`}
              >
                {t.role === "assistant" ? (
                  !t.text && busy ? (
                    <span className="inline-flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" /> thinking…
                    </span>
                  ) : (
                    <Answer text={t.text} />
                  )
                ) : (
                  <span className="leading-relaxed">{t.text}</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Suggested questions */}
      <div className="flex flex-wrap gap-2 px-5 pb-3">
        {SUGGESTED.map((s) => (
          <button
            key={s}
            onClick={() => ask(s)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground transition hover:border-brand/40 disabled:opacity-50"
          >
            <Sparkles className="h-3 w-3 text-brand" />
            {s}
          </button>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="flex items-center gap-2 border-t border-border p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about this shelf…"
          className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-brand/30"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold text-background transition active:scale-95 disabled:opacity-50"
          aria-label="Send"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </form>
    </div>
  );
}

type AskShape = {
  finding?: string;
  whyItMatters?: string;
  action?: string;
};

// Renders the structured decision answer: Answer · Why It Matters · Evidence ·
// Recommended Action. Input is the streamed JSON object; while it's still
// accumulating (not yet valid JSON) we show a thinking state, never raw JSON.
function Answer({ text }: { text: string }) {
  const trimmed = text.trim();
  let parsed: AskShape | null = null;
  try {
    parsed = JSON.parse(trimmed) as AskShape;
  } catch {
    parsed = null;
  }

  if (!parsed) {
    // Mid-stream JSON → thinking; a non-JSON fallback (rare) → show as text.
    if (trimmed.startsWith("{") || !trimmed) {
      return (
        <span className="inline-flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> thinking…
        </span>
      );
    }
    return <p className="leading-relaxed">{trimmed}</p>;
  }

  return (
    <div className="space-y-3">
      {parsed.finding && (
        <p className="text-[15px] font-bold leading-snug tracking-tight text-foreground">
          {parsed.finding}
        </p>
      )}
      {parsed.whyItMatters && (
        <div>
          <AskLabel>Why it matters</AskLabel>
          <p className="mt-0.5 leading-snug text-muted-foreground">{parsed.whyItMatters}</p>
        </div>
      )}
      {parsed.action && (
        <div className="flex items-start gap-2 rounded-xl border border-brand/25 bg-brand/10 p-2.5">
          <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
          <div>
            <AskLabel tone="brand">Do this</AskLabel>
            <p className="mt-0.5 font-medium leading-snug text-foreground">{parsed.action}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function AskLabel({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: "brand";
}) {
  return (
    <span
      className={`text-[10px] font-semibold uppercase tracking-wide ${
        tone === "brand" ? "text-brand" : "text-muted-foreground/70"
      }`}
    >
      {children}
    </span>
  );
}
