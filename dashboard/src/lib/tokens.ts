import type { Channel } from "./api-types";

/**
 * Cermin hex dari design tokens di `app/globals.css` untuk Recharts (atribut SVG tidak
 * membaca kelas Tailwind). Ubah bersamaan dengan globals.css.
 */
export const TOKENS = {
  accent50: "#eef2ff",
  accent200: "#c7d2fe",
  accent300: "#a5b4fc",
  accent400: "#818cf8",
  accent500: "#6366f1",
  accent600: "#4f46e5",
  success500: "#10b981",
  warning500: "#f59e0b",
  danger500: "#ef4444",
  info500: "#0ea5e9",
  zinc100: "#f4f4f5",
  zinc200: "#e4e4e7",
  zinc400: "#a1a1aa",
  zinc500: "#71717a",
  zinc900: "#18181b",
} as const;

/** Kanal digambar dengan gradasi aksen tunggal (monokrom), bukan warna merek tiap kanal. */
export const CHANNEL_CHART_COLOR: Record<Channel, string> = {
  whatsapp: TOKENS.accent600,
  sms: TOKENS.accent400,
  email: TOKENS.accent200,
};
