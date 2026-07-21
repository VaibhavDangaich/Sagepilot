import type { Metadata } from "next";
import Link from "next/link";
import Script from "next/script";
import { Geist, Geist_Mono } from "next/font/google";
import NavLink from "@/components/NavLink";
import ThemeToggle from "@/components/ThemeToggle";
import AuroraBackground from "@/components/AuroraBackground";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Order Supervisor",
  description: "AI supervisor POC for a single order's lifecycle",
};

// Runs before hydration (next/script "beforeInteractive") so the correct
// theme class is on <html> before first paint — otherwise there'd be a
// flash of the wrong theme on every load.
const THEME_INIT_SCRIPT = `
  (function () {
    try {
      var stored = localStorage.getItem("theme");
      var theme = stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      if (theme === "dark") document.documentElement.classList.add("dark");
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
      </head>
      <body className="min-h-full flex flex-col bg-stone-50 text-neutral-900 dark:bg-transparent dark:text-neutral-100">
        <AuroraBackground />
        <header className="sticky top-0 z-10 border-b border-neutral-200 bg-stone-50/80 backdrop-blur-xl dark:border-white/10 dark:bg-neutral-950/70">
          <nav className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
            <Link href="/" className="mr-4 flex items-center gap-2 font-semibold tracking-tight">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500 font-mono text-xs font-bold text-neutral-950 dark:bg-amber-400">
                OS
              </span>
              Order Supervisor
            </Link>
            <NavLink href="/supervisors">Supervisors</NavLink>
            <NavLink href="/runs">Runs</NavLink>
            <NavLink href="/lessons">Lessons</NavLink>
            <div className="ml-auto">
              <ThemeToggle />
            </div>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
