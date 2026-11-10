import type { ReactNode } from "react";
import { OnlineShell } from "@/components/online/OnlineShell";

export default function OnlineLayout({ children }: { children: ReactNode }) {
  return <OnlineShell>{children}</OnlineShell>;
}
