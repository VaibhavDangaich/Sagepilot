"use client";

import { useState } from "react";
import useSWR from "swr";
import { AnimatePresence, motion } from "motion/react";
import { api } from "@/lib/api";
import { ALL_ACTIONS, type ActionName, type WakeAggressiveness } from "@/lib/types";
import {
  Button,
  Card,
  EmptyState,
  FadeIn,
  Label,
  PageHeading,
  Select,
  TextArea,
  TextInput,
} from "@/components/ui";

const PRESETS: Array<{ name: string; base_instruction: string }> = [
  {
    name: "Standard Order Watcher",
    base_instruction:
      "Watch this order from creation to delivery. Escalate payment failures and shipment delays promptly, keep the customer informed, and don't over-communicate for routine updates.",
  },
  {
    name: "High-Touch VIP Order",
    base_instruction:
      "This is a VIP customer's order. Prioritize speed over cost, proactively message the customer on any status change, and escalate to a human immediately on any anomaly.",
  },
];

export default function SupervisorsPage() {
  const { data: supervisors, mutate, isLoading } = useSWR("supervisors", api.listSupervisors);
  const [name, setName] = useState("");
  const [baseInstruction, setBaseInstruction] = useState("");
  const [actions, setActions] = useState<ActionName[]>(ALL_ACTIONS);
  const [aggressiveness, setAggressiveness] = useState<WakeAggressiveness>("balanced");
  const [defaultWakePolicy, setDefaultWakePolicy] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function applyPreset(preset: (typeof PRESETS)[number]) {
    setName(preset.name);
    setBaseInstruction(preset.base_instruction);
  }

  function toggleAction(action: ActionName) {
    setActions((prev) =>
      prev.includes(action) ? prev.filter((a) => a !== action) : [...prev, action]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createSupervisor({
        name,
        base_instruction: baseInstruction,
        available_actions: actions,
        wake_aggressiveness: aggressiveness,
        default_wake_policy: defaultWakePolicy,
      });
      setName("");
      setBaseInstruction("");
      setDefaultWakePolicy("");
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
        <PageHeading eyebrow="Configuration" className="text-2xl">
          Supervisors
        </PageHeading>
        <p className="mt-1.5 text-sm text-neutral-300">
          A supervisor is a reusable template — base instruction, allowed actions, and
          wake behavior — applied when starting a run for a specific order.
        </p>
      </FadeIn>

      <FadeIn delay={0.05}>
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className="rounded-full border border-white/10 px-3 py-1 text-xs font-medium text-neutral-300 transition-colors hover:border-amber-400/40 hover:bg-amber-400/10 hover:text-amber-300"
                >
                  Use preset: {preset.name}
                </button>
              ))}
            </div>

            <div>
              <Label>Name</Label>
              <TextInput
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Standard Order Watcher"
              />
            </div>

            <div>
              <Label>Base instruction</Label>
              <TextArea
                required
                value={baseInstruction}
                onChange={(e) => setBaseInstruction(e.target.value)}
                rows={3}
                placeholder="Watch this order and act if needed..."
              />
            </div>

            <div>
              <Label>Available actions</Label>
              <div className="flex flex-wrap gap-2">
                {ALL_ACTIONS.map((action) => {
                  const checked = actions.includes(action);
                  return (
                    <label
                      key={action}
                      className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                        checked
                          ? "border-amber-400/40 bg-amber-400/10 text-amber-300"
                          : "border-white/10 text-neutral-300 hover:bg-white/5"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAction(action)}
                        className="sr-only"
                      />
                      {action}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <Label>Wake aggressiveness</Label>
                <Select
                  value={aggressiveness}
                  onChange={(e) => setAggressiveness(e.target.value as WakeAggressiveness)}
                >
                  <option value="conservative">conservative</option>
                  <option value="balanced">balanced</option>
                  <option value="aggressive">aggressive</option>
                </Select>
              </div>
              <div>
                <Label>Default wake policy (optional)</Label>
                <TextInput
                  value={defaultWakePolicy}
                  onChange={(e) => setDefaultWakePolicy(e.target.value)}
                  placeholder="e.g. wake immediately on any payment issue"
                />
              </div>
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create supervisor"}
            </Button>
          </form>
        </Card>
      </FadeIn>

      <div className="space-y-3">
        <h2 className="text-sm font-medium text-neutral-400">Existing supervisors</h2>
        {isLoading && <p className="text-sm text-neutral-400">Loading…</p>}
        {supervisors?.length === 0 && <EmptyState>No supervisors yet.</EmptyState>}
        <ul className="space-y-3">
          <AnimatePresence>
            {supervisors?.map((s) => (
              <motion.li
                key={s.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <Card className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-neutral-100">{s.name}</span>
                    <span className="text-xs text-neutral-400">
                      {s.model_config.model} · {s.wake_aggressiveness}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-neutral-300">{s.base_instruction}</p>
                  <p className="mt-2 text-xs text-neutral-400">
                    actions: {s.available_actions.join(", ")}
                  </p>
                </Card>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      </div>
    </div>
  );
}
