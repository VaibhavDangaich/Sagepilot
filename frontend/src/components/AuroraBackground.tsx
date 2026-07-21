/** Fixed, decorative background glow — pure CSS animation (cheap, no JS
 * driving it), sits behind everything at -z-10. Purely visual, so it's
 * marked aria-hidden. Two restrained glows (warm signal amber + a cool
 * counterpoint) rather than a multi-color gradient wash, plus a faint
 * technical grid — closer to an instrument panel than a generic "AI app"
 * hero. Dark mode gets the full glow; light mode keeps it barely-there so
 * it doesn't wash out page content on a bright background. */
export default function AuroraBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-stone-50 dark:bg-neutral-950"
    >
      <div className="animate-aurora absolute top-[-25%] left-[-15%] h-[55vw] w-[55vw] rounded-full bg-amber-400/[0.07] blur-[140px] dark:bg-amber-500/10" />
      <div
        className="animate-aurora absolute right-[-20%] bottom-[-25%] h-[50vw] w-[50vw] rounded-full bg-slate-400/[0.06] blur-[140px] dark:bg-slate-500/10"
        style={{ animationDelay: "-11s" }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(0,0,0,0.03)_1px,transparent_1px),linear-gradient(to_bottom,rgba(0,0,0,0.03)_1px,transparent_1px)] bg-[size:56px_56px] dark:bg-[linear-gradient(to_right,rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.025)_1px,transparent_1px)]" />
    </div>
  );
}
