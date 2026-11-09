import type { ReactNode } from "react";
import { SubMenu } from "@/components/dasbor/SubMenu";

/** Dashboard, Paparan, dan Log: satu menu Dashboard dengan tab di atasnya. */
export default function DasborLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SubMenu />
      {children}
    </>
  );
}
