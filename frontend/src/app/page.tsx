import Link from "next/link";
import { Card, FadeIn, PageHeading } from "@/components/ui";

export default function Home() {
  return (
    <div className="space-y-10">
      <FadeIn>
        <PageHeading eyebrow="AI Supervisor POC" className="text-3xl sm:text-4xl">
          Order Supervisor
        </PageHeading>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-300">
          A long-running AI supervisor that watches a single order&apos;s lifecycle end to
          end — reasoning at workflow start, on incoming events, and on scheduled
          wake-ups, then sleeping in between rather than polling continuously.
        </p>
      </FadeIn>
      <div className="grid gap-4 sm:grid-cols-2">
        <FadeIn delay={0.08}>
          <Link href="/supervisors" className="group block h-full">
            <Card className="h-full p-5 transition-colors group-hover:border-amber-400/25 group-hover:bg-neutral-900/80">
              <h2 className="font-medium text-neutral-100">Supervisors →</h2>
              <p className="mt-1.5 text-sm text-neutral-300">
                Configure a supervisor template: base instruction, available actions, wake
                policy, and model.
              </p>
            </Card>
          </Link>
        </FadeIn>
        <FadeIn delay={0.16}>
          <Link href="/runs" className="group block h-full">
            <Card className="h-full p-5 transition-colors group-hover:border-amber-400/25 group-hover:bg-neutral-900/80">
              <h2 className="font-medium text-neutral-100">Runs →</h2>
              <p className="mt-1.5 text-sm text-neutral-300">
                Start a run for an order, inject events, inspect the timeline and memory, and
                control a live run.
              </p>
            </Card>
          </Link>
        </FadeIn>
      </div>
    </div>
  );
}
