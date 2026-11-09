import type { Metadata } from "next";
import { Suspense } from "react";
import { ForumView } from "@/components/forum/ForumView";

export const metadata: Metadata = { title: "Forum tim – LK Monitoring" };

export default function ForumPage() {
  return (
    <Suspense>
      <ForumView />
    </Suspense>
  );
}
