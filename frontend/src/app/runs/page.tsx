"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { AnimatePresence, motion } from "motion/react";
import { api } from "@/lib/api";
import {
  Button,
  Card,
  EmptyState,
  FadeIn,
  PageHeading,
  Label,
  Select,
  StatusBadge,
  TextInput,
} from "@/components/ui";
import type { RunStatus, RunSummary } from "@/lib/types";

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <p className="text-2xl font-semibold text-neutral-900 dark:text-neutral-100">{value}</p>
      <p className="text-xs text-neutral-500 dark:text-neutral-400">{label}</p>
    </Card>
  );
}

function computeStats(runs: RunSummary[] | undefined) {
  const total = runs?.length ?? 0;
  const byStatus = (status: RunStatus) => runs?.filter((r) => r.status === status).length ?? 0;
  return {
    total,
    live: byStatus("active") + byStatus("sleeping") + byStatus("paused"),
    completed: byStatus("completed"),
    terminated: byStatus("terminated"),
  };
}

export default function RunsPage() {
  const {
    data: runs,
    mutate,
    isLoading,
  } = useSWR("runs", api.listRuns, { refreshInterval: 4000 });
  const { data: supervisors } = useSWR("supervisors", api.listSupervisors);

  const [supervisorId, setSupervisorId] = useState("");
  const [orderId, setOrderId] = useState("");
  const [initialInstruction, setInitialInstruction] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stats = computeStats(runs);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!supervisorId) {
      setError("choose a supervisor first");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.createRun({
        supervisor_id: supervisorId,
        order_id: orderId,
        initial_instruction: initialInstruction || null,
      });
      setOrderId("");
      setInitialInstruction("");
      await mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <FadeIn>
        <PageHeading eyebrow="Order Lifecycle" className="text-2xl">
          Runs
        </PageHeading>
        <p className="mt-1.5 text-sm text-neutral-600 dark:text-neutral-300">
          Each run starts one long-running Temporal workflow for a single order.
        </p>
      </FadeIn>

      <FadeIn delay={0.05} className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Total runs" value={stats.total} />
        <StatTile label="Live (active/sleeping/paused)" value={stats.live} />
        <StatTile label="Completed" value={stats.completed} />
        <StatTile label="Terminated" value={stats.terminated} />
      </FadeIn>

      <FadeIn delay={0.1}>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <Label>Supervisor</Label>
                <Select value={supervisorId} onChange={(e) => setSupervisorId(e.target.value)}>
                  <option value="">select…</option>
                  {supervisors?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
                {supervisors?.length === 0 && (
                  <p className="mt-1.5 text-xs text-neutral-500 dark:text-neutral-400">
                    No supervisors yet —{" "}
                    <Link
                      href="/supervisors"
                      className="font-medium text-amber-600 hover:underline dark:text-amber-400"
                    >
                      create one
                    </Link>{" "}
                    first.
                  </p>
                )}
              </div>
              <div>
                <Label>Order ID</Label>
                <TextInput
                  required
                  value={orderId}
                  onChange={(e) => setOrderId(e.target.value)}
                  placeholder="order-123"
                />
              </div>
            </div>
            <div>
              <Label>Initial instruction (optional)</Label>
              <TextInput
                value={initialInstruction}
                onChange={(e) => setInitialInstruction(e.target.value)}
                placeholder="e.g. prioritize speed over cost for this order"
              />
            </div>
            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Starting…" : "Start run"}
            </Button>
          </form>
        </Card>
      </FadeIn>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">All runs</h2>
        {isLoading && (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>
        )}
        {runs?.length === 0 && <EmptyState>No runs yet — start one above.</EmptyState>}
        <ul className="space-y-3">
          <AnimatePresence>
            {runs?.map((run) => (
              <motion.li
                key={run.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Link href={`/runs/${run.id}`}>
                  <Card className="flex items-center justify-between p-4 transition-colors hover:border-amber-500/30 dark:hover:border-amber-400/25 dark:hover:bg-neutral-900/80">
                    <div>
                      <span className="font-medium text-neutral-900 dark:text-neutral-100">
                        {run.order_id}
                      </span>
                      <span className="ml-2 text-xs text-neutral-500 dark:text-neutral-400">
                        {run.temporal_workflow_id}
                      </span>
                    </div>
                    <StatusBadge status={run.status} />
                  </Card>
                </Link>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}
