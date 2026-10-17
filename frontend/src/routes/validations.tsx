import { createFileRoute } from "@tanstack/react-router";
import { KeyFindings, RequirementsTable, ValidationSummary } from "@/components/brd/Panels";

export const Route = createFileRoute("/validations")({
  head: () => ({
    meta: [
      { title: "AI Validations — BRD Agent" },
      { name: "description", content: "AI Validations and requirements quality metrics in BRD Agent." },
      { property: "og:title", content: "AI Validations — BRD Agent" },
      { property: "og:description", content: "AI Validations and requirements quality metrics in BRD Agent." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <div className="space-y-3">
      <h1 className="text-[18px] font-semibold">AI Validations</h1>
      <div className="grid gap-3 md:grid-cols-2"><ValidationSummary /><KeyFindings /></div>
      <RequirementsTable full />
    </div>
  );
}
