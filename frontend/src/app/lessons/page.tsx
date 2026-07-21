"use client";

import useSWR from "swr";
import { api } from "@/lib/api";
import { Card, EmptyState, FadeIn, PageHeading, Pill } from "@/components/ui";
import type { FaultSide, LessonSource } from "@/lib/types";

const SOURCE_STYLES: Record<LessonSource, string> = {
  agent: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300",
  human: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
};

const FAULT_STYLES: Record<FaultSide, string> = {
  internal: "border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300",
  client: "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-300",
};

export default function LessonsPage() {
  const { data: lessons, isLoading } = useSWR("lessons", api.listLessons, {
    refreshInterval: 5000,
  });

  return (
    <div className="space-y-8">
      <FadeIn>
        <PageHeading eyebrow="Custom addition" className="text-2xl">
          Long-term memory
        </PageHeading>
        <p className="mt-1.5 max-w-2xl text-sm text-neutral-600 dark:text-neutral-300">
          Cross-run lessons learned — not scoped to any single order. When a run hits a
          notable problem, the wrap-up agent can flag it automatically; a human can also
          log one directly against a timeline entry. New runs semantically search this
          store for similar past issues before deciding how to act.
        </p>
      </FadeIn>

      <div className="space-y-3">
        {isLoading && (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>
        )}
        {lessons?.length === 0 && (
          <EmptyState>
            No lessons recorded yet — they accumulate as runs hit (and resolve) notable
            problems.
          </EmptyState>
        )}
        <ul className="space-y-3">
          {lessons?.map((lesson) => (
            <li key={lesson.id}>
              <Card className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill className={SOURCE_STYLES[lesson.source]}>{lesson.source}</Pill>
                    {lesson.fault && (
                      <Pill className={FAULT_STYLES[lesson.fault]}>
                        {lesson.fault === "internal" ? "our side" : "client side"}
                      </Pill>
                    )}
                    <span className="text-xs text-neutral-500 dark:text-neutral-400">
                      order {lesson.order_id}
                    </span>
                  </div>
                  <span className="text-xs text-neutral-500 dark:text-neutral-400">
                    {new Date(lesson.created_at).toLocaleString()}
                  </span>
                </div>
                <div>
                  <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                    Problem
                  </p>
                  <p className="text-sm text-neutral-800 dark:text-neutral-200">
                    {lesson.problem}
                  </p>
                </div>
                {lesson.resolution && (
                  <div>
                    <p className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
                      Resolution
                    </p>
                    <p className="text-sm text-neutral-800 dark:text-neutral-200">
                      {lesson.resolution}
                    </p>
                  </div>
                )}
              </Card>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
