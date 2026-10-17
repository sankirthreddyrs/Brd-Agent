import { createFileRoute } from "@tanstack/react-router";
import { Actions, RequirementsTable } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";

export const Route = createFileRoute("/requirements")({
  head: () => ({
    meta: [
      { title: "Requirements — BRD Agent" },
      { name: "description", content: "Extracted and structured requirements with MoSCoW prioritization." },
    ],
  }),
  component: Page,
});

function Page() {
  const { activeProject } = useApp();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-bold text-foreground">
            {activeProject ? `${activeProject.title} — Requirements` : "Requirements"}
          </h1>
          <p className="text-[12.5px] text-muted-foreground">
            Full requirements matrix with actors, outcomes, acceptance criteria, and confidence scores
          </p>
        </div>
        <Actions />
      </div>

      <RequirementsTable full />
    </div>
  );
}
