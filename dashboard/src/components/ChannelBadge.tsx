import type { ReactNode } from "react";
import type { Channel } from "@/lib/api-types";
import { CHANNEL_LABEL } from "@/lib/format";
import { IconMail, IconPhone, IconWhatsApp } from "./icons";
import { cx } from "./ui";

/** Kanal dibedakan lewat ikon + label (netral), agar warna tetap milik status dan aksen. */
export const CHANNEL_ICON: Record<Channel, (p: { className?: string }) => ReactNode> = {
  whatsapp: IconWhatsApp,
  sms: IconPhone,
  email: IconMail,
};

export function ChannelBadge({ channel, size = "md" }: { channel: Channel; size?: "sm" | "md" }) {
  const Icon = CHANNEL_ICON[channel];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md bg-white font-medium text-zinc-700 ring-1 ring-zinc-950/10 ring-inset whitespace-nowrap",
        size === "sm" ? "px-1.5 py-px text-[11px]" : "px-2 py-0.5 text-xs",
      )}
    >
      {Icon ? <Icon className={cx("text-zinc-500", size === "sm" ? "size-3" : "size-3.5")} /> : null}
      {CHANNEL_LABEL[channel] ?? channel}
    </span>
  );
}
