import type { Metadata } from "next";
import { AdminBlastView } from "@/components/blast/AdminBlastView";

export const metadata: Metadata = { title: "Blast admin – LK Monitoring" };

export default function BlastAdminPage() {
  return <AdminBlastView />;
}
