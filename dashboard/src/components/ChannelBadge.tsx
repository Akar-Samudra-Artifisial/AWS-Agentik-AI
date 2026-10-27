import type { Channel } from "@/lib/api-types";
import { CHANNEL_LABEL } from "@/lib/format";
import { cx } from "./ui";

const STYLE: Record<Channel, string> = {
  whatsapp: "bg-wa-50 text-wa-700 ring-wa-600/25",
  sms: "bg-sms-50 text-sms-700 ring-sms-600/25",
  email: "bg-mail-50 text-mail-700 ring-mail-600/25",
};

const DOT: Record<Channel, string> = {
  whatsapp: "bg-wa-600",
  sms: "bg-sms-600",
  email: "bg-mail-600",
};

export const CHANNEL_COLOR: Record<Channel, string> = {
  whatsapp: "#16a34a",
  sms: "#2563eb",
  email: "#6b6489",
};

export function ChannelBadge({ channel, size = "md" }: { channel: Channel; size?: "sm" | "md" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset whitespace-nowrap",
        size === "sm" ? "px-2 py-px text-[11px]" : "px-2.5 py-0.5 text-xs",
        STYLE[channel] ?? "bg-stone-100 text-stone-700 ring-stone-300",
      )}
    >
      <span aria-hidden="true" className={cx("size-1.5 rounded-full", DOT[channel] ?? "bg-stone-500")} />
      {CHANNEL_LABEL[channel] ?? channel}
    </span>
  );
}
