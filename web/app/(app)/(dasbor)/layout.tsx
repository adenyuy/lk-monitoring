import type { ReactNode } from "react";
import { SubMenu } from "@/components/dasbor/SubMenu";

/** Dashboard, Ranking, Paparan, dan Log (Bimtek punya menu sendiri): satu menu Dashboard dengan tab di atasnya. */
export default function DasborLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SubMenu />
      {children}
    </>
  );
}
