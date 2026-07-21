"use client";

import { useEffect, useMemo, useState } from "react";
import cytoscape, {
  type Core,
  type ElementDefinition,
  type LayoutOptions,
  type StylesheetJsonBlock,
} from "cytoscape";
import coseBilkent from "cytoscape-cose-bilkent";
import CytoscapeComponent from "react-cytoscapejs";
import type { ActivityLogKind, TimelineEntry } from "@/lib/types";

// Registering an already-registered extension throws — guard for React
// Fast Refresh re-executing this module in dev.
try {
  cytoscape.use(coseBilkent);
} catch {
  // already registered
}

/** Renders an order's timeline as an actual force-directed graph (not a
 * flowchart) — nodes for every activity-log entry, sequential edges
 * following `seq`, plus a dashed branch to any long-term-memory lesson
 * consulted at that turn. Clicking a node or edge opens an inspector panel
 * with its full details. A custom addition beyond the assignment spec (see
 * README); built entirely from data the existing /timeline endpoint
 * already returns, no new backend endpoint needed. */

const KIND_COLORS: Record<ActivityLogKind, string> = {
  incoming_event: "#0ea5e9",
  wake_decision: "#10b981",
  sleep_decision: "#64748b",
  agent_action: "#f59e0b",
  manual_instruction: "#f43f5e",
  final_output: "#78716c",
  system: "#a3a3a3",
};

const LESSON_COLOR = "#8b5cf6";

function shortLabel(entry: TimelineEntry): string {
  switch (entry.kind) {
    case "incoming_event":
      return `event: ${entry.payload.event_type}`;
    case "wake_decision":
    case "sleep_decision":
      if ("reasoning_note" in entry.payload) return String(entry.payload.reasoning_note);
      return String(entry.payload.reason ?? "");
    case "agent_action":
      return `${entry.payload.name}`;
    case "manual_instruction":
      return String(entry.payload.instruction ?? "");
    case "final_output":
      return "final output";
    case "system":
      return String(entry.payload.message ?? "");
    default:
      return "";
  }
}

// Cytoscape styles are plain values, not CSS — they don't pick up our
// dark: Tailwind classes automatically, so the palette is built explicitly
// per theme and swapped when the toggle changes (watched via a
// MutationObserver on <html class="dark">).
function buildStylesheet(isDark: boolean): StylesheetJsonBlock[] {
  const labelBg = isDark ? "#171412" : "#ffffff";
  const labelFg = isDark ? "#e7e2dc" : "#292524";
  const edgeColor = isDark ? "#57534e" : "#a8a29e";

  return [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        "border-width": 3,
        "border-color": "data(color)",
        "border-opacity": 0.5,
        label: "data(label)",
        "text-wrap": "wrap",
        "text-max-width": "100px",
        "font-size": "9px",
        color: labelFg,
        "text-background-color": labelBg,
        "text-background-opacity": 0.92,
        "text-background-padding": "3px",
        "text-background-shape": "roundrectangle",
        width: 40,
        height: 40,
        "text-valign": "bottom",
        "text-margin-y": 8,
      },
    },
    {
      selector: "node[?isLesson]",
      style: {
        shape: "diamond",
        width: 34,
        height: 34,
        "border-style": "dashed",
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 5,
        "border-opacity": 1,
      },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "line-color": edgeColor,
        "target-arrow-color": edgeColor,
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        opacity: 0.8,
      },
    },
    {
      selector: "edge[?isLesson]",
      style: {
        "line-color": LESSON_COLOR,
        "target-arrow-color": LESSON_COLOR,
        "line-style": "dashed",
        width: 1.5,
      },
    },
    {
      selector: "edge:selected",
      style: { width: 4, opacity: 1 },
    },
  ];
}

const LAYOUT = {
  name: "cose-bilkent",
  animate: false,
  fit: true,
  padding: 48,
  nodeRepulsion: 9000,
  idealEdgeLength: 90,
  gravity: 0.4,
  numIter: 2500,
} as unknown as LayoutOptions;

// Recognized payload keys get a friendly label and their own row; anything
// else still shows up, just under its raw key — no information is dropped.
const FIELD_LABELS: Record<string, string> = {
  reasoning_note: "Reasoning",
  sleep_seconds: "Sleep duration (s)",
  next_wake_at: "Next wake-up at",
  memory_summary: "Memory summary",
  wake_policy: "Wake policy",
  event_type: "Event type",
  data: "Event data",
  name: "Action",
  message: "Message",
  reason: "Reason",
  wake_now: "Wake now",
  is_unknown_event: "Unrecognized event type",
  instruction: "Instruction",
  final_summary: "Final summary",
};

function formatFieldValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return JSON.stringify(value);
}

interface SelectedNode {
  kind: "node";
  id: string;
  label: string;
  isLesson: boolean;
  seq?: number;
  entryKind?: string;
  createdAt?: string;
  payload?: Record<string, unknown>;
  lessonText?: string;
}

interface SelectedEdge {
  kind: "edge";
  id: string;
  sourceLabel: string;
  targetLabel: string;
  isLesson: boolean;
}

type Selected = SelectedNode | SelectedEdge;

function useIsDarkTheme(): boolean {
  // Safe as a lazy initializer (not deferred to an effect): this component
  // is only ever mounted once run/timeline data has loaded client-side, so
  // it's never part of the server-rendered HTML — no hydration mismatch to
  // avoid here, unlike ThemeToggle.
  const [isDark, setIsDark] = useState(
    () => typeof document !== "undefined" && document.documentElement.classList.contains("dark")
  );

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => setIsDark(root.classList.contains("dark")));
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

export default function RunGraphView({ timeline }: { timeline: TimelineEntry[] }) {
  const [selected, setSelected] = useState<Selected | null>(null);
  const isDark = useIsDarkTheme();
  const stylesheet = useMemo(() => buildStylesheet(isDark), [isDark]);

  const elements = useMemo<ElementDefinition[]>(() => {
    const nodes: ElementDefinition[] = [];
    const edges: ElementDefinition[] = [];

    timeline.forEach((entry, i) => {
      const id = `entry-${entry.seq}`;
      nodes.push({
        data: {
          id,
          label: `#${entry.seq} ${shortLabel(entry).slice(0, 40)}`,
          color: KIND_COLORS[entry.kind],
          seq: entry.seq,
          entryKind: entry.kind,
          createdAt: entry.created_at,
          payload: entry.payload,
        },
      });
      if (i > 0) {
        edges.push({
          data: { id: `e-${entry.seq}`, source: `entry-${timeline[i - 1].seq}`, target: id },
        });
      }

      const consultedLessons = entry.payload.consulted_lessons;
      if (Array.isArray(consultedLessons)) {
        consultedLessons.forEach((lesson, li) => {
          const lessonId = `lesson-${entry.seq}-${li}`;
          nodes.push({
            data: {
              id: lessonId,
              label: `Lesson: ${String(lesson).slice(0, 40)}…`,
              color: LESSON_COLOR,
              isLesson: true,
              lessonText: String(lesson),
            },
          });
          edges.push({
            data: { id: `e-${lessonId}`, source: lessonId, target: id, isLesson: true },
          });
        });
      }
    });

    return [...nodes, ...edges];
  }, [timeline]);

  function attachHandlers(cy: Core) {
    // cy() fires again on every re-render — clear first so handlers never
    // stack up as new elements arrive via polling.
    cy.removeAllListeners();
    cy.on("tap", "node", (evt) => {
      const d = evt.target.data();
      setSelected({
        kind: "node",
        id: d.id,
        label: d.label,
        isLesson: Boolean(d.isLesson),
        seq: d.seq,
        entryKind: d.entryKind,
        createdAt: d.createdAt,
        payload: d.payload,
        lessonText: d.lessonText,
      });
    });
    cy.on("tap", "edge", (evt) => {
      const d = evt.target.data();
      setSelected({
        kind: "edge",
        id: d.id,
        sourceLabel: String(evt.target.source().data("label")),
        targetLabel: String(evt.target.target().data("label")),
        isLesson: Boolean(d.isLesson),
      });
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });
  }

  const payloadEntries = selected?.kind === "node" ? Object.entries(selected.payload ?? {}) : [];

  return (
    <div className="relative h-[600px] w-full overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-white/10 dark:bg-neutral-950">
      <CytoscapeComponent
        elements={elements}
        stylesheet={stylesheet}
        layout={LAYOUT}
        style={{ width: "100%", height: "100%" }}
        minZoom={0.3}
        maxZoom={2.5}
        cy={attachHandlers}
      />

      {selected && (
        <div className="absolute top-3 right-3 max-h-[calc(100%-1.5rem)] w-80 overflow-y-auto rounded-lg border border-neutral-200 bg-white/97 p-4 text-xs shadow-lg backdrop-blur dark:border-white/10 dark:bg-neutral-900/97">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-mono font-semibold tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
              {selected.kind === "node" ? "Node details" : "Edge details"}
            </h3>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {selected.kind === "node" && selected.isLesson && (
            <div>
              <p className="mb-1.5 font-medium text-violet-600 dark:text-violet-300">
                Long-term memory lesson
              </p>
              <p className="text-sm whitespace-pre-wrap text-neutral-700 dark:text-neutral-200">
                {selected.lessonText}
              </p>
            </div>
          )}

          {selected.kind === "node" && !selected.isLesson && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px] font-medium text-neutral-700 dark:bg-white/10 dark:text-neutral-200">
                  #{selected.seq}
                </span>
                <span className="text-neutral-500 dark:text-neutral-400">
                  {selected.entryKind}
                </span>
              </div>
              {selected.createdAt && (
                <p className="text-neutral-500 dark:text-neutral-400">
                  {new Date(selected.createdAt).toLocaleString()}
                </p>
              )}
              <div className="space-y-2.5 border-t border-neutral-200 pt-2.5 dark:border-white/10">
                {payloadEntries.map(([key, value]) => (
                  <div key={key}>
                    <p className="text-[10px] font-medium tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
                      {FIELD_LABELS[key] ?? key}
                    </p>
                    <p className="text-sm whitespace-pre-wrap text-neutral-800 dark:text-neutral-200">
                      {formatFieldValue(value)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selected.kind === "edge" && (
            <div className="space-y-2 text-neutral-700 dark:text-neutral-200">
              <div>
                <p className="text-[10px] font-medium tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
                  From
                </p>
                <p className="text-sm">{selected.sourceLabel}</p>
              </div>
              <div>
                <p className="text-[10px] font-medium tracking-wide text-neutral-500 uppercase dark:text-neutral-400">
                  To
                </p>
                <p className="text-sm">{selected.targetLabel}</p>
              </div>
              {selected.isLesson && (
                <p className="mt-1 text-violet-600 dark:text-violet-300">
                  Long-term memory link — this turn consulted that lesson.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
