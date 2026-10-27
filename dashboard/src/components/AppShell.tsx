"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { isApiConfigured, useApprovals, useHealth } from "@/lib/api";
import { TIME_ZONE_HINT } from "@/lib/format";
import { IconInbox, IconOverview, IconSend, IconShieldCheck } from "./icons";
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
    <span
      role="status"
      className={cx(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset",
        state === "live" && "bg-emerald-50 text-emerald-800 ring-emerald-300",
        state === "offline" && "bg-red-50 text-red-800 ring-red-300",
        (state === "checking" || state === "unset") && "bg-stone-100 text-stone-600 ring-stone-300",
      )}
    >
      <span className="relative flex size-2" aria-hidden="true">
        {state === "live" ? (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500 opacity-60" />
        ) : null}
        <span
          className={cx(
            "relative inline-flex size-2 rounded-full",
            state === "live" ? "bg-emerald-600" : state === "offline" ? "bg-red-600" : "bg-stone-400",
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
      className="ml-auto rounded-full bg-amber-400 px-1.5 text-xs font-semibold tabular-nums text-amber-950"
      aria-label={`${n} pending ${n === 1 ? "approval" : "approvals"}`}
    >
      {n}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  return (
    <div className="min-h-screen lg:flex">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="border-b border-stone-200 bg-white lg:w-64 lg:shrink-0 lg:border-r lg:border-b-0">
        {/* aside meregang setinggi konten (latar + border penuh); isinya yang sticky. */}
        <div className="lg:sticky lg:top-0 lg:flex lg:max-h-screen lg:min-h-screen lg:flex-col lg:overflow-y-auto">
          <div className="flex items-center justify-between gap-3 px-5 py-4 lg:block lg:py-5">
            <Link href="/" className="flex items-center gap-2.5 rounded-lg">
              <span aria-hidden="true" className="grid size-9 place-items-center rounded-lg bg-brand-900 text-base font-bold text-white">
                R
              </span>
              <span>
                <span className="block text-base font-semibold leading-tight text-stone-900">ResolveAI</span>
                <span className="block text-xs text-stone-500">Supervisor console</span>
              </span>
            </Link>
            <div className="lg:mt-4">
              <LiveIndicator />
            </div>
          </div>
          <nav aria-label="Main navigation" className="overflow-x-auto px-3 pb-3 lg:pb-0">
            <ul className="flex gap-1 lg:flex-col">
              {NAV.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cx(
                        "flex items-center gap-2.5 rounded-lg px-3 py-2 text-[15px] font-medium whitespace-nowrap transition-colors",
                        active ? "bg-brand-50 text-brand-900" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
                      )}
                    >
                      <Icon className={cx("size-[18px]", active ? "text-brand-700" : "text-stone-400")} />
                      {item.label}
                      {item.href === "/approvals/" ? <PendingCount /> : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="mt-auto hidden space-y-1 border-t border-stone-100 px-5 py-4 text-xs text-stone-500 lg:block">
            <p>All times in {TIME_ZONE_HINT}</p>
            <p>Payments &amp; courier are simulated</p>
            <p>Customer contact data is masked</p>
          </div>
        </div>
      </aside>
      <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
        <div className="mx-auto max-w-[1600px]">
          {!isApiConfigured ? (
            <div role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
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
