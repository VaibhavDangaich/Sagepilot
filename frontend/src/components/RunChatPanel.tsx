"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, Label, TextInput } from "@/components/ui";

interface ChatMessage {
  question: string;
  answer: string;
}

/** Stateless per-order Q&A — a custom addition beyond the assignment spec
 * (see README). Each question is answered fresh from this order's current
 * timeline/memory (no server-side chat history); the messages shown here
 * are just this browser session's local transcript. Kept deliberately
 * separate from the order-supervisor agent itself — read-only, never acts
 * on the order. */
export default function RunChatPanel({ runId }: { runId: string }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    const q = question.trim();
    if (!q) return;
    setAsking(true);
    setError(null);
    try {
      const { answer } = await api.chatAboutRun(runId, { question: q });
      setMessages((prev) => [...prev, { question: q, answer }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAsking(false);
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div>
        <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
          Ask about this order
        </h2>
        <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
          Grounded only in this order&apos;s own timeline and memory — a separate,
          read-only tool, not the supervisor agent itself.
        </p>
      </div>

      {messages.length > 0 && (
        <div className="max-h-64 space-y-3 overflow-y-auto border-t border-neutral-200 pt-3 dark:border-white/10">
          {messages.map((m, i) => (
            <div key={i} className="space-y-1">
              <p className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                Q: {m.question}
              </p>
              <p className="text-sm text-neutral-800 dark:text-neutral-200">{m.answer}</p>
            </div>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div>
        <Label>Question</Label>
        <div className="flex gap-2">
          <TextInput
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void ask();
              }
            }}
            placeholder="e.g. why did the agent escalate this order?"
            className="flex-1"
          />
          <Button disabled={asking || !question.trim()} onClick={() => void ask()}>
            {asking ? "Asking…" : "Ask"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
