import { createFileRoute } from "@tanstack/react-router";
import { Activity } from "@/components/brd/Panels";

export const Route = createFileRoute("/audit-log")({
  head: () => ({
    meta: [
      { title: "Audit Log — BRD Agent" },
      { name: "description", content: "Deterministic analysis and pipeline audit log in BRD Agent." },
      { property: "og:title", content: "Audit Log — BRD Agent" },
      { property: "og:description", content: "Deterministic analysis and pipeline audit log in BRD Agent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <div className="space-y-3">
      <h1 className="text-[18px] font-semibold">Audit Log</h1>
      <Activity />
    </div>
  );
}
