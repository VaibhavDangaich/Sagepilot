"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { AnimatePresence, motion } from "motion/react";
import { api } from "@/lib/api";
import {
  ALL_EVENT_TYPES,
  type ActivityLogKind,
  type FaultSide,
  type TimelineEntry,
} from "@/lib/types";
import {
  Button,
  Card,
  EmptyState,
  FadeIn,
  Label,
  Select,
  StatusBadge,
  TextInput,
} from "@/components/ui";
import RunChatPanel from "@/components/RunChatPanel";
import RunGraphView from "@/components/RunGraphView";

const KIND_META: Record<ActivityLogKind, { label: string; dot: string; glow: string }> = {
  incoming_event: {
    label: "Incoming event",
    dot: "bg-sky-500 dark:bg-sky-400",
    glow: "shadow-sky-500/50",
  },
  wake_decision: {
    label: "Woke up",
    dot: "bg-emerald-500 dark:bg-emerald-400",
    glow: "shadow-emerald-500/50",
  },
  sleep_decision: {
    label: "Went to sleep",
    dot: "bg-slate-500 dark:bg-slate-400",
    glow: "shadow-slate-500/50",
  },
  agent_action: {
    label: "Action taken",
    dot: "bg-amber-500 dark:bg-amber-400",
    glow: "shadow-amber-500/50",
  },
  manual_instruction: {
    label: "Instruction added",
    dot: "bg-rose-500 dark:bg-rose-400",
    glow: "shadow-rose-500/50",
  },
  final_output: {
    label: "Final output",
    dot: "bg-neutral-800 dark:bg-neutral-100",
    glow: "shadow-neutral-800/50",
  },
  system: {
    label: "System",
    dot: "bg-neutral-400 dark:bg-neutral-500",
    glow: "shadow-neutral-400/50",
  },
};

function formatPayload(kind: ActivityLogKind, payload: Record<string, unknown>): string {
  switch (kind) {
    case "incoming_event":
      return `event: ${payload.event_type}`;
    case "wake_decision":
    case "sleep_decision": {
      if ("reasoning_note" in payload) {
        return `${payload.reasoning_note} (sleep ${payload.sleep_seconds}s)`;
      }
      const prefix = payload.is_unknown_event ? "unrecognized event type — " : "";
      return `${prefix}${String(payload.reason ?? "")}`;
    }
    case "agent_action":
      return `${payload.name}: ${payload.message}`;
    case "manual_instruction":
      return String(payload.instruction ?? "");
    case "final_output":
      return String(payload.final_summary ?? "");
    case "system":
      return String(payload.message ?? "");
    default:
      return JSON.stringify(payload);
  }
}

// Entries worth prompting a human to annotate with fault + resolution — a
// custom addition beyond the spec (see README). Deliberately narrow: the
// known problem event types, plus anything outside the built-in catalog
// (a custom/unrecognized trigger), which is exactly what an
// incoming_event's is_unknown_event flag can't itself capture (that lives
// on the wake_decision row, not the incoming_event row).
const PROBLEM_EVENT_TYPES = new Set(["payment_failed", "shipment_delayed", "refund_requested"]);

function isProblemLikeEntry(entry: TimelineEntry): boolean {
  if (entry.kind !== "incoming_event") return false;
  const eventType = String(entry.payload.event_type ?? "");
  return (
    PROBLEM_EVENT_TYPES.has(eventType) ||
    !(ALL_EVENT_TYPES as string[]).includes(eventType)
  );
}

function getConsultedLessons(entry: TimelineEntry): string[] {
  const value = entry.payload.consulted_lessons;
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function LessonLogger({
  runId,
  defaultProblem,
  onClose,
}: {
  runId: string;
  defaultProblem: string;
  onClose: () => void;
}) {
  const [fault, setFault] = useState<FaultSide>("internal");
  const [problem, setProblem] = useState(defaultProblem);
  const [resolution, setResolution] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      await api.logLesson(runId, { fault, problem, resolution });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-3 space-y-3 border-t border-neutral-200 pt-3 dark:border-white/10">
      <div>
        <Label>Whose side was this?</Label>
        <div className="flex gap-2">
          {(["internal", "client"] as const).map((side) => (
            <button
              key={side}
              type="button"
              onClick={() => setFault(side)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                fault === side
                  ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:border-amber-400/40 dark:bg-amber-400/10 dark:text-amber-300"
                  : "border-neutral-300 text-neutral-600 hover:bg-neutral-100 dark:border-white/10 dark:text-neutral-300 dark:hover:bg-white/5"
              }`}
            >
              {side === "internal" ? "Our side" : "Client side"}
            </button>
          ))}
        </div>
      </div>
      <div>
        <Label>Problem</Label>
        <TextInput value={problem} onChange={(e) => setProblem(e.target.value)} />
      </div>
      <div>
        <Label>
          {fault === "internal" ? "How we fixed it" : "Notes (optional)"}
        </Label>
        <TextInput value={resolution} onChange={(e) => setResolution(e.target.value)} />
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex gap-2">
        <Button
          disabled={submitting || !problem.trim()}
          onClick={submit}
          className="px-3 py-1.5 text-xs"
        >
          {submitting ? "Saving…" : "Save to long-term memory"}
        </Button>
        <Button
          variant="secondary"
          disabled={submitting}
          onClick={onClose}
          className="px-3 py-1.5 text-xs"
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}

const CUSTOM_EVENT_OPTION = "__custom__";

// `now` only ever changes from the interval's own tick callback (an event,
// not a synchronous setState-in-effect-body), so the derived label below
// is computed at render time rather than stored as its own state.
function useCountdown(target: string | null): string | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!target) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [target]);

  if (!target) return null;
  const diff = new Date(target).getTime() - now;
  if (diff <= 0) return "any moment now";
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

export default function RunDetailClient({ runId }: { runId: string }) {
  const { data: run, mutate: mutateRun } = useSWR(["run", runId], () => api.getRun(runId), {
    refreshInterval: 3000,
  });
  const { data: timeline } = useSWR(["timeline", runId], () => api.getTimeline(runId), {
    refreshInterval: 3000,
  });

  const [eventType, setEventType] = useState<string>(ALL_EVENT_TYPES[0]);
  const [customEventType, setCustomEventType] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loggingSeq, setLoggingSeq] = useState<number | null>(null);
  const [view, setView] = useState<"timeline" | "graph">("timeline");

  const countdown = useCountdown(run?.next_wake_at ?? null);

  async function withBusy(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await mutateRun();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!run) {
    return <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>;
  }

  const isTerminal = run.status === "completed" || run.status === "terminated";
  const ordered = timeline?.slice().reverse();

  return (
    <div className="space-y-6">
      <FadeIn>
        <Card className="flex items-start justify-between p-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">
              Order {run.order_id}
            </h1>
            <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
              {run.temporal_workflow_id}
            </p>
            {countdown && !isTerminal && (
              <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-300">
                Next wake-up in{" "}
                <span className="font-mono font-medium text-amber-700 dark:text-amber-300">
                  {countdown}
                </span>
              </p>
            )}
          </div>
          <StatusBadge status={run.status} />
        </Card>
      </FadeIn>

      {error && (
        <p className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="grid gap-6 md:grid-cols-3">
        <div className="space-y-3 md:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              {view === "timeline" ? "Timeline" : "Graph"}
            </h2>
            <div className="flex gap-1 rounded-md border border-neutral-300 p-0.5 dark:border-white/10">
              {(["timeline", "graph"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setView(v)}
                  className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                    view === v
                      ? "bg-amber-500/15 text-amber-700 dark:bg-amber-400/15 dark:text-amber-300"
                      : "text-neutral-500 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-white/5"
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          {ordered?.length === 0 && <EmptyState>No activity yet.</EmptyState>}
          {view === "graph" && ordered && ordered.length > 0 && (
            <RunGraphView timeline={ordered} />
          )}
          <ol
            className={`relative space-y-4 border-l border-neutral-300 pl-6 dark:border-white/10 ${
              view === "graph" ? "hidden" : ""
            }`}
          >
            <AnimatePresence initial={false}>
              {ordered?.map((entry) => {
                const meta = KIND_META[entry.kind];
                return (
                  <motion.li
                    key={entry.seq}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3 }}
                    className="relative"
                  >
                    <span
                      className={`absolute top-1.5 -left-[1.6rem] h-2.5 w-2.5 rounded-full shadow-[0_0_8px] ${meta.dot} ${meta.glow}`}
                    />
                    <Card className="p-3">
                      <div className="flex items-center justify-between text-xs text-neutral-500 dark:text-neutral-400">
                        <span className="font-medium text-neutral-600 dark:text-neutral-300">
                          {meta.label}
                        </span>
                        <span>{new Date(entry.created_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="mt-1 text-sm text-neutral-800 dark:text-neutral-200">
                        {formatPayload(entry.kind, entry.payload)}
                      </p>
                      {getConsultedLessons(entry).length > 0 && (
                        <details className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">
                          <summary className="cursor-pointer font-medium text-violet-600 dark:text-violet-300">
                            Consulted {getConsultedLessons(entry).length} past lesson
                            {getConsultedLessons(entry).length > 1 ? "s" : ""} from long-term
                            memory
                          </summary>
                          <ul className="mt-1 space-y-1.5">
                            {getConsultedLessons(entry).map((lesson, i) => (
                              <li
                                key={i}
                                className="rounded border border-violet-500/20 bg-violet-500/5 p-2 whitespace-pre-wrap"
                              >
                                {lesson}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                      {isProblemLikeEntry(entry) &&
                        (loggingSeq === entry.seq ? (
                          <LessonLogger
                            runId={runId}
                            defaultProblem={formatPayload(entry.kind, entry.payload)}
                            onClose={() => setLoggingSeq(null)}
                          />
                        ) : (
                          <button
                            type="button"
                            onClick={() => setLoggingSeq(entry.seq)}
                            className="mt-2 text-xs font-medium text-amber-600 hover:underline dark:text-amber-400"
                          >
                            Log outcome →
                          </button>
                        ))}
                      <details className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">
                        <summary className="cursor-pointer hover:text-neutral-700 dark:hover:text-neutral-200">
                          Raw details
                        </summary>
                        <pre className="mt-1 overflow-x-auto rounded bg-black/5 p-2 whitespace-pre-wrap dark:bg-white/5">
                          {JSON.stringify(entry.payload, null, 2)}
                        </pre>
                      </details>
                    </Card>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ol>
        </div>

        <div className="space-y-4">
          <RunChatPanel runId={runId} />
          <Card className="p-4">
            <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              Memory summary
            </h2>
            <p className="mt-1.5 text-sm whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
              {run.memory_summary || "(empty — no turns yet)"}
            </p>
          </Card>
          <Card className="p-4">
            <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              Wake policy
            </h2>
            <p className="mt-1.5 text-sm whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
              {run.wake_policy || "(using default classifier rules)"}
            </p>
          </Card>

          {isTerminal && (run.final_summary || run.final_learnings) && (
            <Card className="space-y-3 p-4">
              <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
                Final output
              </h2>
              <div>
                <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                  Summary
                </p>
                <p className="text-sm text-neutral-800 dark:text-neutral-200">
                  {run.final_summary}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                  Key learnings
                </p>
                <p className="text-sm text-neutral-800 dark:text-neutral-200">
                  {run.final_learnings}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                  Feedback
                </p>
                <p className="text-sm text-neutral-800 dark:text-neutral-200">
                  {run.final_feedback}
                </p>
              </div>
            </Card>
          )}

          {!isTerminal && (
            <Card className="space-y-5 p-4">
              <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
                Controls
              </h2>

              <div>
                <Label>Inject event</Label>
                <div className="flex gap-2">
                  <Select
                    value={eventType}
                    onChange={(e) => setEventType(e.target.value)}
                    className="flex-1"
                  >
                    {ALL_EVENT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                    <option value={CUSTOM_EVENT_OPTION}>custom…</option>
                  </Select>
                  <Button
                    disabled={
                      busy || (eventType === CUSTOM_EVENT_OPTION && !customEventType.trim())
                    }
                    onClick={() =>
                      withBusy(() =>
                        api.injectEvent(
                          runId,
                          eventType === CUSTOM_EVENT_OPTION ? customEventType.trim() : eventType
                        )
                      )
                    }
                  >
                    Send
                  </Button>
                </div>
                {eventType === CUSTOM_EVENT_OPTION && (
                  <>
                    <TextInput
                      value={customEventType}
                      onChange={(e) => setCustomEventType(e.target.value)}
                      placeholder="e.g. carrier_lost_package"
                      className="mt-2"
                    />
                    <p className="mt-1 text-xs text-neutral-500 dark:text-neutral-400">
                      Not one of the built-in types — the classifier will treat it as
                      unrecognized and always escalate it for the agent to interpret.
                    </p>
                  </>
                )}
              </div>

              <div>
                <Label>Add instruction</Label>
                <div className="flex gap-2">
                  <TextInput
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder="e.g. escalate immediately if delayed"
                    className="flex-1"
                  />
                  <Button
                    disabled={busy || !instruction}
                    onClick={() =>
                      withBusy(async () => {
                        await api.addInstruction(runId, instruction);
                        setInstruction("");
                      })
                    }
                  >
                    Add
                  </Button>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 border-t border-neutral-200 pt-4 dark:border-white/10">
                {run.status === "paused" ? (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => withBusy(() => api.resumeRun(runId))}
                  >
                    Resume
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => withBusy(() => api.interruptRun(runId))}
                  >
                    Pause
                  </Button>
                )}
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() => {
                    if (confirm("Terminate this run? This ends the workflow.")) {
                      void withBusy(() => api.terminateRun(runId));
                    }
                  }}
                >
                  Terminate
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
