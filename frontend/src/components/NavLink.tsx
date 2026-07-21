"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export default function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const pathname = usePathname();
  const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <Link
      href={href}
      className={`relative rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        isActive
          ? "text-amber-700 dark:text-amber-300"
          : "text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-100"
      }`}
    >
      {isActive && (
        <span className="absolute inset-0 -z-10 rounded-md bg-amber-500/10 ring-1 ring-amber-500/20 dark:bg-amber-400/10 dark:ring-amber-400/20" />
      )}
      {children}
    </Link>
  );
}
