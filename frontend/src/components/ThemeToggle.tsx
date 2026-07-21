"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  localStorage.setItem("theme", theme);
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
      <circle cx="12" cy="12" r="4" />
      <path
        strokeLinecap="round"
        d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-3.5 w-3.5">
      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
    </svg>
  );
}

export default function ThemeToggle() {
  // Unknown until mount (the real value was already applied synchronously
  // by the inline head script, before hydration — this just reads it back).
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    // Deliberate exception to react-hooks/set-state-in-effect: this reads
    // DOM state that only exists client-side (set by the pre-hydration head
    // script) and must happen post-hydration to avoid a server/client
    // markup mismatch — the same pattern libraries like next-themes use.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  if (theme === null) {
    return <div className="h-7 w-13" aria-hidden />;
  }

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label="Toggle dark mode"
      onClick={toggle}
      className="relative h-7 w-13 shrink-0 rounded-full border border-neutral-300 bg-neutral-200 transition-colors dark:border-white/15 dark:bg-neutral-800"
    >
      <motion.span
        className="absolute top-0.5 left-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-white text-neutral-600 shadow dark:bg-neutral-950 dark:text-amber-300"
        animate={{ x: isDark ? 24 : 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      >
        {isDark ? <MoonIcon /> : <SunIcon />}
      </motion.span>
    </button>
  );
}
