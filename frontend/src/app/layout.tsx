import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import NavLink from "@/components/NavLink";
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
      <body className="min-h-full flex flex-col text-neutral-100">
        <AuroraBackground />
        <header className="sticky top-0 z-10 border-b border-white/10 bg-neutral-950/70 backdrop-blur-xl">
          <nav className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3">
            <Link href="/" className="mr-4 flex items-center gap-2 font-semibold tracking-tight">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-400 font-mono text-xs font-bold text-neutral-950">
                OS
              </span>
              Order Supervisor
            </Link>
            <NavLink href="/supervisors">Supervisors</NavLink>
            <NavLink href="/runs">Runs</NavLink>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
