import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { IconAlert, IconArrowRight, IconChevronDown, IconInbox } from "./icons";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/*
 * Skala desain (dipakai konsisten di semua halaman):
 * - permukaan: kartu bg-white + ring 1px zinc-950/6% + shadow-card; radius kartu rounded-xl, kontrol rounded-lg, badge rounded-md
 * - spasi: padding kartu px-5; header kartu py-4; jarak antar-blok gap-6; antar-seksi mt-8
 * - tipe: judul halaman 28px semibold; judul kartu 14px semibold; label meta 11px uppercase tracking-wider; angka tabular-nums
 */

export const SURFACE = "rounded-xl bg-white shadow-card ring-1 ring-zinc-950/[0.06]";

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "aside";
}) {
  return <Tag className={cx("overflow-hidden", SURFACE, className)}>{children}</Tag>;
}

export function CardHeader({
  title,
  action,
  subtitle,
  icon,
  id,
}: {
  title: string;
  action?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  id?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4">
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-zinc-50 text-zinc-500 ring-1 ring-zinc-950/[0.06] [&>svg]:size-4">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h2 id={id} className="text-sm font-semibold text-zinc-900">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-[13px] text-zinc-500">{subtitle}</p> : null}
        </div>
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
  eyebrow,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  eyebrow?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-zinc-200/70 pb-6">
      <div className="min-w-0">
        {eyebrow ? <div className="mb-2">{eyebrow}</div> : null}
        <h1 className="text-[28px] leading-9 font-semibold tracking-[-0.02em] text-zinc-950">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-zinc-500">{description}</p> : null}
      </div>
      {action ? <div className="flex flex-wrap items-center gap-2">{action}</div> : null}
    </header>
  );
}

/** Label kecil uppercase untuk metadata / judul grup. */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500", className)}>{children}</p>;
}

export function CountPill({ value, tone = "neutral" }: { value: number; tone?: "neutral" | "warning" | "accent" }) {
  return (
    <span
      className={cx(
        "inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-px text-[11px] font-semibold tabular-nums",
        tone === "neutral" && "bg-zinc-100 text-zinc-600",
        tone === "warning" && "bg-warning-100 text-warning-800",
        tone === "accent" && "bg-accent-50 text-accent-700",
      )}
    >
      {value}
    </span>
  );
}

/** Judul seksi di luar kartu, dengan hitungan dan aksi opsional. */
export function SectionHeading({
  id,
  title,
  count,
  description,
  action,
}: {
  id?: string;
  title: string;
  count?: number;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 id={id} className="flex items-center gap-2 text-[15px] font-semibold text-zinc-900">
          {title}
          {count != null ? <CountPill value={count} /> : null}
        </h2>
        {description ? <p className="mt-0.5 text-[13px] text-zinc-500">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary:
    "bg-accent-600 text-white shadow-sm ring-1 ring-accent-700/40 ring-inset hover:bg-accent-700 disabled:bg-zinc-200 disabled:text-zinc-500 disabled:ring-zinc-200 disabled:shadow-none",
  secondary: "bg-white text-zinc-800 shadow-xs ring-1 ring-zinc-950/10 ring-inset hover:bg-zinc-50 disabled:text-zinc-400",
  danger: "bg-white text-danger-700 shadow-xs ring-1 ring-danger-200 ring-inset hover:bg-danger-50 disabled:text-danger-200",
  ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 disabled:text-zinc-400",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  loading,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed [&>svg]:size-4",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-9 px-3.5 text-sm",
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
  return <div aria-hidden="true" className={cx("animate-pulse rounded-md bg-zinc-100", className)} />;
}

export function LoadingRows({ rows = 5, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <div role="status" className="divide-y divide-zinc-100">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3.5">
          <Skeleton className="size-8 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
  icon,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <span
        aria-hidden="true"
        className="mb-4 grid size-11 place-items-center rounded-xl bg-white text-zinc-400 shadow-card ring-1 ring-zinc-950/[0.06] [&>svg]:size-5"
      >
        {icon ?? <IconInbox />}
      </span>
      <p className="text-sm font-semibold text-zinc-900">{title}</p>
      {hint ? <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-zinc-500">{hint}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="m-4 flex items-start gap-3 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger-800 ring-1 ring-danger-200 ring-inset">
      <IconAlert className="mt-0.5 size-4 shrink-0 text-danger-600" />
      <div className="min-w-0">
        <p className="font-semibold">Couldn’t load data</p>
        <p className="mt-0.5 text-danger-700">{message}</p>
        {onRetry ? (
          <button type="button" onClick={onRetry} className="mt-2 font-medium underline underline-offset-2">
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Penanda jujur untuk bagian yang disimulasikan (pembayaran, kurir, inbound simulator). */
export function SimulatedTag({ label = "Simulated", title }: { label?: string; title?: string }) {
  return (
    <span
      title={title ?? "Simulated for the demo — no real payment or courier is involved"}
      className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-dashed border-warning-300 bg-warning-50 px-1.5 py-px text-[10.5px] font-semibold uppercase tracking-[0.06em] text-warning-800"
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-warning-500" />
      {label}
    </span>
  );
}

export function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5 text-[13px]">
      <dt className="shrink-0 text-zinc-500">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words text-zinc-900">{value}</dd>
    </div>
  );
}

export function MoreLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="group inline-flex items-center gap-1 rounded-md text-[13px] font-medium text-accent-700 hover:text-accent-800"
    >
      {children}
      <IconArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

/** Statistik ringkas berlabel (dipakai di header detail kasus). */
export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-semibold uppercase tracking-[0.08em] text-zinc-500">{label}</dt>
      <dd className="mt-1 truncate text-sm font-medium text-zinc-900">{value}</dd>
    </div>
  );
}

/** Kontrol tersegmentasi (radio group native agar dapat dinavigasi keyboard). */
export function SegmentedControl<T extends string>({
  name,
  label,
  value,
  options,
  onChange,
}: {
  name: string;
  label: string;
  value: T;
  options: ReadonlyArray<{ value: T; label: string; count?: number }>;
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">{label}</legend>
      <div className="inline-flex h-9 max-w-full gap-0.5 overflow-x-auto rounded-lg bg-zinc-100 p-0.5 ring-1 ring-zinc-950/[0.04] ring-inset">
        {options.map((o) => {
          const active = o.value === value;
          return (
            <label
              key={o.value}
              className={cx(
                "inline-flex cursor-pointer items-center gap-1.5 rounded-md px-3 text-[13px] font-medium whitespace-nowrap transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent-500",
                active ? "bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-950/[0.06]" : "text-zinc-500 hover:text-zinc-800",
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={active}
                onChange={() => onChange(o.value)}
                className="sr-only"
              />
              {o.label}
              {o.count != null ? (
                <span className={cx("tabular-nums text-[11px]", active ? "text-zinc-500" : "text-zinc-400")}>{o.count}</span>
              ) : null}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** Kelas dasar kontrol form satu baris; samakan tinggi/ring/focus dengan input pencarian & Button md. */
export const CONTROL =
  "h-9 rounded-lg bg-white text-sm text-zinc-900 shadow-xs ring-1 ring-zinc-950/10 ring-inset transition-shadow placeholder:text-zinc-400 focus:ring-2 focus:ring-accent-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400 disabled:shadow-none";

/** Dropdown native bergaya token: panah browser disembunyikan, chevron SVG di kanan. */
export function Select({
  label,
  hideLabel,
  className,
  children,
  id,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hideLabel?: boolean; id: string }) {
  return (
    <div className={cx("flex min-w-0 items-center gap-2", className)}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : "shrink-0 text-[13px] font-medium text-zinc-500"}>
        {label}
      </label>
      <div className="group relative min-w-0 flex-1">
        <select
          id={id}
          {...rest}
          className={cx(
            CONTROL,
            "w-full min-w-40 cursor-pointer appearance-none truncate pr-9 pl-3 hover:bg-zinc-50 hover:ring-zinc-950/15 focus:hover:bg-white",
          )}
        >
          {children}
        </select>
        <IconChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-zinc-400 group-focus-within:text-accent-600 group-has-[:disabled]:text-zinc-300" />
      </div>
    </div>
  );
}

/** Avatar inisial netral untuk nama pelanggan. */
export function Avatar({ name, size = "md" }: { name: string | null | undefined; size?: "sm" | "md" }) {
  const initials = (name ?? "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span
      aria-hidden="true"
      className={cx(
        "grid shrink-0 place-items-center rounded-full bg-zinc-100 font-semibold text-zinc-600 ring-1 ring-zinc-950/[0.06]",
        size === "sm" ? "size-6 text-[10px]" : "size-8 text-[11px]",
      )}
    >
      {initials || "?"}
    </span>
  );
}
