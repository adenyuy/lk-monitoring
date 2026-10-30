import type { Metadata } from "next";
import { AdminView } from "@/components/admin/AdminView";

export const metadata: Metadata = { title: "Admin – LK Monitoring" };

export default function AdminPage() {
  return <AdminView />;
}
