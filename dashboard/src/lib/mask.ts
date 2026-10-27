/** `+6281234567789` → `+62812****789` (sesuai konvensi log di CLAUDE.md). */
export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  const p = phone.replace(/\s+/g, "");
  if (p.length <= 8) return `${p.slice(0, 2)}****`;
  return `${p.slice(0, 6)}****${p.slice(-3)}`;
}

/** `rani.demo@example.com` → `ra*******@example.com` */
export function maskEmail(email: string | null | undefined): string {
  if (!email) return "—";
  const at = email.indexOf("@");
  if (at <= 0) return "****";
  const local = email.slice(0, at);
  const keep = local.slice(0, Math.min(2, local.length));
  return `${keep}${"*".repeat(Math.max(3, local.length - keep.length))}${email.slice(at)}`;
}

// Hanya nomor berprefix internasional (+62…) atau lokal 08…; hindari salah tangkap tanggal/ID.
const PHONE_RE = /\+\d{9,15}\b|\b08\d{7,11}\b/g;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

/** Mask nomor telepon/email yang muncul di teks bebas (pesan, JSON event). */
export function maskText(text: string): string {
  return text
    .replace(EMAIL_RE, (m) => maskEmail(m))
    .replace(PHONE_RE, (m) => maskPhone(m.replace(/[\s-]/g, "")));
}
