/** Fixed, decorative background glow — pure CSS animation (cheap, no JS
 * driving it), sits behind everything at -z-10. Purely visual, so it's
 * marked aria-hidden. Two restrained glows (warm signal amber + a cool
 * counterpoint), not a multi-color gradient wash — plus a faint technical
 * grid, closer to an instrument panel than a generic "AI app" hero. */
export default function AuroraBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-neutral-950"
    >
      <div className="animate-aurora absolute top-[-25%] left-[-15%] h-[55vw] w-[55vw] rounded-full bg-amber-500/10 blur-[140px]" />
      <div
        className="animate-aurora absolute right-[-20%] bottom-[-25%] h-[50vw] w-[50vw] rounded-full bg-slate-500/10 blur-[140px]"
        style={{ animationDelay: "-11s" }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:56px_56px]" />
    </div>
  );
}
