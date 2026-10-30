import type { ReactNode } from "react";

function Svg({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export const IconRekap = () => (
  <Svg><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></Svg>
);
export const IconHariIni = () => (
  <Svg><path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" /></Svg>
);
export const IconCutoff = () => (
  <Svg><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></Svg>
);
export const IconPanduan = () => (
  <Svg><circle cx="12" cy="12" r="9.5" /><path d="M9.6 9.2a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.7" /><path d="M12 17h.01" /></Svg>
);
export const IconLogo = () => (
  <Svg size={16}><path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 21l2.1-5.6A8.5 8.5 0 1 1 21 11.5z" /></Svg>
);
export const IconTanya = () => (
  <Svg><path d="M20 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" /><path d="M10 8.6a2 2 0 0 1 3.9.6c0 1.3-1.9 1.7-1.9 2.9" /><path d="M12 14.5h.01" /></Svg>
);
export const IconLog = () => (
  <Svg><rect x="3.5" y="4.5" width="17" height="16" rx="2" /><path d="M3.5 9.5h17" /><path d="M8 2.5v4" /><path d="M16 2.5v4" /><path d="M8 14h3" /><path d="M8 17h6" /></Svg>
);
export const IconAdmin = () => (
  <Svg><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z" /><circle cx="12" cy="10.5" r="2.3" /><path d="M8.3 16.2a4.2 4.2 0 0 1 7.4 0" /></Svg>
);
