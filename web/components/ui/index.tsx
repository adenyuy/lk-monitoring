import type { ButtonHTMLAttributes, ReactNode } from "react";
import s from "./ui.module.css";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  size,
  loading,
  children,
  className,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm"; loading?: boolean }) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={[s.btn, s[variant], size ? s[size] : "", className ?? ""].join(" ")}
    >
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ label }: { label?: string }) {
  return <span className={s.spinner} role={label ? "status" : undefined} aria-label={label} />;
}

const ICONS = {
  ok: <path d="M20 6 9 17l-5-5" />,
  warn: (
    <>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </>
  ),
  bad: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="m15 9-6 6M9 9l6 6" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </>
  ),
};

export function Notice({
  tone,
  title,
  children,
}: {
  tone: keyof typeof ICONS;
  title?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className={`${s.notice} ${s[tone]}`} role={tone === "bad" ? "alert" : "status"}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {ICONS[tone]}
      </svg>
      <div>
        {title && <div className={s.noticeTitle}>{title}</div>}
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}
