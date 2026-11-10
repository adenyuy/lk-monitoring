import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

// Root layout untuk build online (LKM_ONLINE=1). Build laptop memakai app/layout.tsx.
const plex = IBM_Plex_Sans({
  variable: "--font-plex",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "LK Monitoring – Dashboard",
  description: "Dashboard Monitoring Revitalisasi SD 2026",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className={plex.variable}>
      <body>{children}</body>
    </html>
  );
}
