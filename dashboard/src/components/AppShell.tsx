"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { POLL_MS, isApiConfigured, useApprovals, useHealth } from "@/lib/api";
import { TIME_ZONE_HINT } from "@/lib/format";
import { IconClock, IconInbox, IconLock, IconOverview, IconSend, IconShieldCheck, IconWallet } from "./icons";
import { cx } from "./ui";

const NAV = [
  { href: "/", label: "Overview", icon: IconOverview },
  { href: "/cases/", label: "Cases", icon: IconInbox },
  { href: "/approvals/", label: "Approvals", icon: IconShieldCheck },
  { href: "/simulator/", label: "Simulator", icon: IconSend },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  const base = href.replace(/\/$/, "");
  return pathname === base || pathname.startsWith(`${base}/`) || (base === "/cases" && pathname.startsWith("/case"));
}

function LiveIndicator() {
  const { data, error, isLoading } = useHealth();
  const state = !isApiConfigured ? "unset" : error ? "offline" : data ? "live" : isLoading ? "checking" : "offline";
  const label = { live: "Live · API connected", offline: "Offline", checking: "Connecting…", unset: "API not configured" }[state];
  return (
    <span role="status" className="inline-flex items-center gap-2 text-xs font-medium text-zinc-600">
      <span className="relative flex size-2" aria-hidden="true">
        {state === "live" ? (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-success-500 opacity-50" />
        ) : null}
        <span
          className={cx(
            "relative inline-flex size-2 rounded-full",
            state === "live" ? "bg-success-500" : state === "offline" ? "bg-danger-500" : "bg-zinc-300",
          )}
        />
      </span>
      {label}
    </span>
  );
}

function PendingCount() {
  const { data } = useApprovals("pending");
  const n = data?.length ?? 0;
  if (!n) return null;
  return (
    <span
      className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-warning-500 px-1.5 text-[11px] font-semibold tabular-nums text-white"
      aria-label={`${n} pending ${n === 1 ? "approval" : "approvals"}`}
    >
      {n}
    </span>
  );
}

function LogoMark() {
  return (
    <span
      aria-hidden="true"
      className="grid size-8 place-items-center rounded-[9px] bg-accent-600 text-white shadow-sm ring-1 ring-accent-700/50 ring-inset"
    >
      <svg viewBox="0 0 24 24" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 12.5 9 17.5 20 6.5" />
      </svg>
    </span>
  );
}

const FOOTNOTES = [
  { icon: IconClock, text: `All times in ${TIME_ZONE_HINT}` },
  { icon: IconWallet, text: "Payments & courier are simulated" },
  { icon: IconLock, text: "Customer contact data is masked" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  return (
    <div className="min-h-screen lg:flex">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:shadow-raised"
      >
        Skip to content
      </a>
      <aside className="border-b border-zinc-200/80 bg-white lg:w-60 lg:shrink-0 lg:border-r lg:border-b-0">
        {/* aside meregang setinggi konten (latar + border penuh); isinya sticky setinggi viewport.
            Status & catatan menempel di dasar viewport (mt-auto). */}
        <div className="lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:overflow-y-auto">
          <div className="flex items-center justify-between gap-3 px-4 py-3.5 lg:px-5 lg:pt-5 lg:pb-6">
            <Link href="/" className="flex items-center gap-2.5 rounded-lg">
              <LogoMark />
              <span className="leading-tight">
                <span className="block text-[15px] font-semibold tracking-[-0.01em] text-zinc-950">ResolveAI</span>
                <span className="block text-[11px] font-medium text-zinc-500">Supervisor console</span>
              </span>
            </Link>
            <div className="lg:hidden">
              <LiveIndicator />
            </div>
          </div>

          <nav aria-label="Main navigation" className="overflow-x-auto px-3 pb-3 lg:pb-0">
            <p className="mb-1.5 hidden px-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-400 lg:block">Workspace</p>
            <ul className="flex gap-0.5 lg:flex-col">
              {NAV.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium whitespace-nowrap transition-colors",
                        active
                          ? "bg-zinc-100 text-zinc-950"
                          : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
                      )}
                    >
                      {active ? (
                        <span aria-hidden="true" className="absolute top-2 bottom-2 -left-3 hidden w-[3px] rounded-r-full bg-accent-600 lg:block" />
                      ) : null}
                      <Icon className={cx("size-[18px]", active ? "text-accent-600" : "text-zinc-400")} />
                      {item.label}
                      {item.href === "/approvals/" ? <PendingCount /> : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="mt-auto hidden border-t border-zinc-200/80 px-3 pt-5 pb-4 lg:block">
            <div className="rounded-xl bg-zinc-50 p-3 ring-1 ring-zinc-950/[0.05] ring-inset">
              <LiveIndicator />
              <p className="mt-1 text-[11px] text-zinc-500">Auto-refresh every {POLL_MS / 1000} s</p>
            </div>
            <ul className="mt-4 space-y-2 px-2">
              {FOOTNOTES.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2 text-[11.5px] text-zinc-500">
                  <Icon className="size-3.5 shrink-0 text-zinc-400" />
                  {text}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </aside>
      <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[1360px]">
          {!isApiConfigured ? (
            <div role="alert" className="mb-6 rounded-lg bg-warning-50 px-4 py-3 text-sm text-warning-800 ring-1 ring-warning-200 ring-inset">
              <strong>API not configured.</strong> Set <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> and{" "}
              <code className="font-mono">NEXT_PUBLIC_API_KEY</code> in <code className="font-mono">.env.local</code>, then rebuild.
            </div>
          ) : null}
          {children}
        </div>
      </main>
    </div>
  );
}
