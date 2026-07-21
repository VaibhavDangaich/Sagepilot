"use client";

import { motion, type HTMLMotionProps } from "motion/react";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import type { RunStatus } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-lg border border-white/10 bg-neutral-900/85 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-xl ${className}`}
    >
      {children}
    </div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1 block text-sm font-medium text-neutral-200">{children}</label>
  );
}

const fieldClasses =
  "w-full rounded-md border border-white/15 bg-black/40 px-3 py-2 text-sm text-neutral-50 placeholder:text-neutral-500 focus:border-amber-400/50 focus:outline-none focus:ring-2 focus:ring-amber-400/20 transition-colors";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${fieldClasses} ${props.className ?? ""}`} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${fieldClasses} ${props.className ?? ""}`} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`${fieldClasses} bg-neutral-900 [&>option]:bg-neutral-900 ${props.className ?? ""}`}
    />
  );
}

type ButtonVariant = "primary" | "secondary" | "danger";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-amber-400 text-neutral-950 shadow-[0_0_0_1px_rgba(251,191,36,0.3)] hover:bg-amber-300 hover:shadow-[0_0_20px_rgba(251,191,36,0.35)] disabled:opacity-40 disabled:hover:shadow-none",
  secondary: "border border-white/12 text-neutral-200 hover:bg-white/5 disabled:opacity-40",
  danger: "border border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-40",
};

export function Button({
  variant = "primary",
  className = "",
  disabled,
  ...props
}: HTMLMotionProps<"button"> & { variant?: ButtonVariant }) {
  return (
    <motion.button
      {...props}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      whileHover={disabled ? undefined : { scale: 1.015 }}
      transition={{ duration: 0.12 }}
      className={`rounded-md px-4 py-2 text-sm font-semibold transition-[box-shadow,background-color] disabled:cursor-not-allowed ${buttonVariants[variant]} ${className}`}
    />
  );
}

export function Pill({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 font-mono text-xs font-medium ${className}`}
    >
      {children}
    </span>
  );
}

// Traffic-light semantics, deliberately: green = go, amber = caution/paused
// (which doubles as this app's own signal color), red = stopped, slate =
// idle/asleep, neutral = archived.
const STATUS_STYLES: Record<RunStatus, string> = {
  active: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  sleeping: "border-slate-400/25 bg-slate-400/10 text-slate-300",
  paused: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  completed: "border-white/10 bg-white/5 text-neutral-400",
  terminated: "border-red-500/25 bg-red-500/10 text-red-300",
};

const STATUS_DOTS: Record<RunStatus, string> = {
  active: "bg-emerald-400",
  sleeping: "bg-slate-400",
  paused: "bg-amber-400",
  completed: "bg-neutral-500",
  terminated: "bg-red-400",
};

// Only "active"/"sleeping" get the live pulse — a run that's paused or over
// shouldn't visually read as "something is happening right now".
const PULSING_STATUSES: ReadonlySet<RunStatus> = new Set(["active", "sleeping"]);

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <Pill className={STATUS_STYLES[status]}>
      <span className="relative flex h-2 w-2">
        {PULSING_STATUSES.has(status) && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${STATUS_DOTS[status]}`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${STATUS_DOTS[status]}`} />
      </span>
      {status}
    </Pill>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 bg-white/[0.02] p-8 text-center text-sm text-neutral-400">
      {children}
    </div>
  );
}

/** A small monospace "signal" label + solid heading — an instrument-panel
 * eyebrow, not another gradient-text hero (deliberately avoiding the
 * indigo/violet gradient-text look that reads as generic AI-app template). */
export function PageHeading({
  eyebrow,
  children,
  className = "",
}: {
  eyebrow: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div>
      <p className="mb-1.5 font-mono text-xs tracking-[0.2em] text-amber-400/80 uppercase">
        {eyebrow}
      </p>
      <h1 className={`font-semibold tracking-tight text-neutral-50 ${className}`}>{children}</h1>
    </div>
  );
}

export function FadeIn({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
