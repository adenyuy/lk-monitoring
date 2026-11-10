import type { NextConfig } from "next";

// Dibangun jadi file statis (web/out) lalu disajikan oleh backend Python di :8787.
// Rewrites/proxy tidak didukung di mode export, jadi saat `next dev` web memanggil
// API langsung lewat NEXT_PUBLIC_API_BASE (lihat lib/api.ts dan scripts/dev.bat).
//
// LKM_ONLINE=1: build dashboard online (Vercel). Hanya file rute berakhiran .online.tsx yang dipakai
// (app/layout.online.tsx, app/(online)/...), jadi halaman blast/LK/forum/admin tidak ikut ter-build sama sekali.
const online = process.env.LKM_ONLINE === "1";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  ...(online ? { pageExtensions: ["online.tsx", "online.ts"] } : {}),
};

export default nextConfig;
