"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

type ToastTone = "success" | "error" | "info";
type Toast = { id: number; tone: ToastTone; message: string };

type ToastApi = (message: string, tone?: ToastTone) => void;

const ToastContext = createContext<ToastApi | null>(null);

// Zero-dependency toast system. `useToast()` returns a push function; toasts
// auto-dismiss and animate in via the `toast-in` keyframe (no slide under
// reduced-motion — handled in globals.css).
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback<ToastApi>(
    (message, tone = "info") => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, tone, message }]);
      setTimeout(() => remove(id), 5000);
    },
    [remove],
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 sm:bottom-auto sm:right-5 sm:top-20 sm:items-end"
      >
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  // No-op fallback if used outside a provider — never throws in the demo.
  return ctx ?? (() => {});
}

const toneStyle: Record<ToastTone, { ring: string; icon: React.ReactNode }> = {
  success: {
    ring: "border-emerald-500/30",
    icon: <CheckCircle2 className="h-5 w-5 text-emerald-500" />,
  },
  error: {
    ring: "border-rose-500/30",
    icon: <AlertTriangle className="h-5 w-5 text-rose-500" />,
  },
  info: {
    ring: "border-brand/30",
    icon: <Info className="h-5 w-5 text-brand" />,
  },
};

function ToastCard({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const s = toneStyle[toast.tone];
  return (
    <div
      className={`animate-toast-in pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-2xl border ${s.ring} bg-card/95 p-3.5 shadow-lg backdrop-blur`}
    >
      <span className="mt-0.5 shrink-0">{s.icon}</span>
      <p className="flex-1 text-sm font-medium leading-snug text-foreground">
        {toast.message}
      </p>
      <button
        onClick={onClose}
        className="shrink-0 rounded-md p-0.5 text-muted-foreground transition hover:bg-muted"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
