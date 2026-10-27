import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResolveAI — Konsol Supervisor",
  description: "Pemantauan agen AI pemulihan keluhan pelanggan.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
