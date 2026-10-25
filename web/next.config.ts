import type { NextConfig } from "next";

// Dibangun jadi file statis (web/out) lalu disajikan oleh backend Python di :8787.
// Rewrites/proxy tidak didukung di mode export, jadi saat `next dev` web memanggil
// API langsung lewat NEXT_PUBLIC_API_BASE (lihat lib/api.ts dan scripts/dev.bat).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
