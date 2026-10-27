import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { IconArrowRight } from "./icons";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/*
 * Skala desain (dipakai konsisten di semua halaman):
 * - radius: kartu rounded-xl, kontrol rounded-lg, badge rounded-md/full
 * - padding kartu: px-5; header kartu py-3.5; isi py-4
 * - tipe: judul halaman text-2xl, judul seksi/kartu text-base semibold, label meta text-xs uppercase
 */

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "aside";
}) {
  return (
    <Tag className={cx("overflow-hidden rounded-xl border border-stone-200 bg-white shadow-xs", className)}>{children}</Tag>
  );
}

export function CardHeader({
  title,
  action,
  subtitle,
  icon,
}: {
  title: string;
  action?: ReactNode;
  subtitle?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-stone-100 px-5 py-3.5">
      <div className="flex min-w-0 items-start gap-2.5">
        {icon ? <span className="mt-0.5 size-5 shrink-0 text-stone-400">{icon}</span> : null}
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-stone-900">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-sm text-stone-500">{subtitle}</p> : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-[15px] text-stone-600">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}

/** Judul seksi di luar kartu, dengan hitungan dan aksi opsional. */
export function SectionHeading({
  id,
  title,
  count,
  action,
}: {
  id?: string;
  title: string;
  count?: number;
  action?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h2 id={id} className="flex items-center gap-2 text-base font-semibold text-stone-900">
        {title}
        {count != null ? (
          <span className="rounded-full bg-stone-200/70 px-2 py-px text-xs font-semibold tabular-nums text-stone-700">{count}</span>
        ) : null}
      </h2>
      {action}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-brand-700 text-white shadow-xs hover:bg-brand-900 disabled:bg-stone-300",
  secondary: "border border-stone-300 bg-white text-stone-800 shadow-xs hover:bg-stone-50 disabled:text-stone-400",
  danger: "border border-red-300 bg-white text-red-700 shadow-xs hover:bg-red-50 disabled:text-red-300",
  ghost: "text-stone-700 hover:bg-stone-100 disabled:text-stone-400",
};

export function Button({
  variant = "secondary",
  className,
  loading,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; loading?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        BUTTON_VARIANT[variant],
        className,
      )}
    >
      {loading ? <Spinner /> : null}
      {children}
    </button>
  );
}

export function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent"
    />
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("animate-pulse rounded-md bg-stone-200/70", className)} />;
}

export function LoadingRows({ rows = 5, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <div role="status" className="space-y-3 p-5">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-9 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      <div aria-hidden="true" className="mb-3 size-10 rounded-full border-2 border-dashed border-stone-300" />
      <p className="font-medium text-stone-800">{title}</p>
      {hint ? <p className="mt-1 max-w-sm text-sm text-stone-500">{hint}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="m-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <p className="font-medium">Couldn’t load data</p>
      <p className="mt-0.5">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="mt-2 font-medium underline underline-offset-2">
          Try again
        </button>
      ) : null}
    </div>
  );
}

/** Penanda jujur untuk bagian yang disimulasikan (pembayaran, kurir, inbound simulator). */
export function SimulatedTag({ label = "Simulated", title }: { label?: string; title?: string }) {
  return (
    <span
      title={title ?? "Simulated for the demo — no real payment or courier is involved"}
      className="inline-flex shrink-0 items-center whitespace-nowrap rounded border border-dashed border-amber-400 bg-amber-50 px-1.5 py-px text-[11px] font-semibold uppercase tracking-wide text-amber-800"
    >
      {label}
    </span>
  );
}

export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-2 text-sm">
      <dt className="shrink-0 text-stone-500">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words text-stone-900">{value}</dd>
    </div>
  );
}

export function MoreLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 rounded text-sm font-medium text-brand-700 underline-offset-2 hover:underline"
    >
      {children}
      <IconArrowRight className="size-4" />
    </Link>
  );
}

/** Statistik ringkas berlabel (dipakai di header detail kasus). */
export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-stone-900">{value}</dd>
    </div>
  );
}
