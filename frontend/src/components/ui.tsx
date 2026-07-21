"use client";

import { motion, type HTMLMotionProps } from "motion/react";
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import type { RunStatus } from "@/lib/types";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-lg border border-neutral-200 bg-white/90 shadow-[0_1px_3px_rgba(0,0,0,0.06)] backdrop-blur-xl dark:border-white/10 dark:bg-neutral-900/85 dark:shadow-[0_8px_32px_rgba(0,0,0,0.45)] ${className}`}
    >
      {children}
    </div>
  );
}

export function Label({ children }: { children: ReactNode }) {
  return (
    <label className="mb-1 block text-sm font-medium text-neutral-700 dark:text-neutral-200">
      {children}
    </label>
  );
}

const fieldClasses =
  "w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-amber-500/60 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-colors dark:border-white/15 dark:bg-black/40 dark:text-neutral-50 dark:placeholder:text-neutral-500 dark:focus:border-amber-400/50 dark:focus:ring-amber-400/20";

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
      className={`${fieldClasses} dark:bg-neutral-900 dark:[&>option]:bg-neutral-900 ${props.className ?? ""}`}
    />
  );
}

type ButtonVariant = "primary" | "secondary" | "danger";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-amber-500 text-neutral-950 shadow-[0_0_0_1px_rgba(217,119,6,0.25)] hover:bg-amber-400 hover:shadow-[0_0_16px_rgba(217,119,6,0.25)] disabled:opacity-40 disabled:hover:shadow-none dark:bg-amber-400 dark:shadow-[0_0_0_1px_rgba(251,191,36,0.3)] dark:hover:bg-amber-300 dark:hover:shadow-[0_0_20px_rgba(251,191,36,0.35)]",
  secondary:
    "border border-neutral-300 text-neutral-700 hover:bg-neutral-100 disabled:opacity-40 dark:border-white/12 dark:text-neutral-200 dark:hover:bg-white/5",
  danger:
    "border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-40 dark:border-red-500/30 dark:text-red-400 dark:hover:bg-red-500/10",
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
// idle/asleep, neutral = archived. Same hues in both themes, tuned for
// contrast against a light vs. dark card background.
const STATUS_STYLES: Record<RunStatus, string> = {
  active:
    "border-emerald-600/25 bg-emerald-500/10 text-emerald-700 dark:border-emerald-500/25 dark:text-emerald-300",
  sleeping:
    "border-slate-400/30 bg-slate-400/10 text-slate-600 dark:border-slate-400/25 dark:text-slate-300",
  paused:
    "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:border-amber-400/25 dark:text-amber-300",
  completed:
    "border-neutral-300 bg-neutral-100 text-neutral-500 dark:border-white/10 dark:bg-white/5 dark:text-neutral-400",
  terminated:
    "border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300",
};

const STATUS_DOTS: Record<RunStatus, string> = {
  active: "bg-emerald-500 dark:bg-emerald-400",
  sleeping: "bg-slate-500 dark:bg-slate-400",
  paused: "bg-amber-500 dark:bg-amber-400",
  completed: "bg-neutral-400 dark:bg-neutral-500",
  terminated: "bg-red-500 dark:bg-red-400",
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
    <div className="rounded-lg border border-dashed border-neutral-300 bg-neutral-100/50 p-8 text-center text-sm text-neutral-500 dark:border-white/15 dark:bg-white/[0.02] dark:text-neutral-400">
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
      <p className="mb-1.5 font-mono text-xs tracking-[0.2em] text-amber-600 uppercase dark:text-amber-400/80">
        {eyebrow}
      </p>
      <h1
        className={`font-semibold tracking-tight text-neutral-900 dark:text-neutral-50 ${className}`}
      >
        {children}
      </h1>
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
