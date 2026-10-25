import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

// Font di-bundle saat build, jadi app tetap tampil benar walau laptop offline.
const plex = IBM_Plex_Sans({
  variable: "--font-plex",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "LK Monitoring",
  description: "WA Blast dan Tarik Cutoff – Monitoring Revitalisasi SD 2026",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className={plex.variable}>
      <body>{children}</body>
    </html>
  );
}
