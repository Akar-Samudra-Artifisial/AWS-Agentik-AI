/**
 * Teks pesan pelanggan untuk preset (data demo, bukan label UI) — dari docs/prd/00-overview.md §7.
 * Sengaja dipisah di satu konstanta agar mudah diganti (mis. versi bahasa Inggris) tanpa menyentuh UI.
 */
export const PRESET_MESSAGES = {
  A: ["Pesanan ORD-1001 saya terlambat 2 hari.", "1"],
  B: ["ORD-1002 belum sampai juga, sudah seminggu.", "Saya pilih refund saja."],
  C: ["ORD-1003 katanya sudah diterima tapi saya tidak terima apa-apa. Saya akan lapor polisi!"],
} as const satisfies Record<string, readonly string[]>;
