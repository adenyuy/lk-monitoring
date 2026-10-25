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

const CHIP: Record<string, string> = {
  ok: "var(--ok-bg)|var(--ok-fg)",
  info: "var(--primary-soft)|var(--primary)",
  muted: "#f2f4f7|#475467",
  warn: "var(--warn-bg)|var(--warn-fg)",
  bad: "var(--bad-bg)|var(--bad-fg)",
  dark: "var(--ink)|#fff",
};

/** Label status kecil berwarna. */
export function Chip({ tone, children }: { tone: keyof typeof CHIP; children: ReactNode }) {
  const [bg, fg] = CHIP[tone].split("|");
  return (
    <span style={{ display: "inline-block", padding: "2px 9px", borderRadius: 999, fontSize: 12, fontWeight: 500,
      whiteSpace: "nowrap", background: bg, color: fg, flex: "none" }}>
      {children}
    </span>
  );
}

/** Warna chip untuk status kirim / chat. */
export function statusTone(status: string): keyof typeof CHIP {
  return ({
    Dibalas: "ok", Dibaca: "info", Terkirim: "muted", Gagal: "bad", Dilewati: "warn",
    Menunggu: "muted", Berikutnya: "info", Dicoba: "info",
  } as Record<string, keyof typeof CHIP>)[status] ?? "muted";
}

/** Warna chip untuk prioritas sekolah. */
export function prioritasTone(p: string): keyof typeof CHIP {
  if (p.endsWith("1")) return "bad";
  if (p.endsWith("2")) return "warn";
  if (p.endsWith("3")) return "info";
  return "ok";
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
