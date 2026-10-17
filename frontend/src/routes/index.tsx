import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Actions, Activity, DocumentViewer, KeyFindings, KPIs, ProjectHeader, RequirementsTable, ValidationSummary } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";
import { CreateProjectModal } from "@/components/CreateProjectModal";
import { Sparkles, Plus, Loader2 } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — BRD Agent" },
      { name: "description", content: "AI-powered requirements extraction, clarification loop, and BRD document generation." },
    ],
  }),
  component: Index,
});

function Index() {
  const { activeProject, isProjectLoading, projects } = useApp();
  const [createOpen, setCreateOpen] = useState(false);

  if (isProjectLoading && !activeProject) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-[13px] text-muted-foreground">Loading project workspace...</p>
      </div>
    );
  }

  if (!activeProject && projects.length === 0) {
    return (
      <div className="flex min-h-[70vh] flex-col items-center justify-center p-6 text-center">
        <div className="grid h-16 w-16 place-items-center rounded-2xl bg-primary/10 text-primary mb-4 shadow-sm">
          <Sparkles className="h-8 w-8" />
        </div>
        <h1 className="text-[22px] font-bold text-foreground">Welcome to BRD Agent</h1>
        <p className="text-[13.5px] text-muted-foreground max-w-md mt-2 mb-6">
          Transform your business ideas and source documents into rigorous, enterprise-grade Business Requirements Documents.
        </p>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-[14px] font-semibold text-primary-foreground hover:bg-primary/90 transition-all shadow-md"
        >
          <Plus className="h-4 w-4" />
          <span>Create Your First Project</span>
        </button>

        <CreateProjectModal isOpen={createOpen} onClose={() => setCreateOpen(false)} />
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,470px)_1fr]">
          <ProjectHeader />
          <div className="flex flex-col gap-3">
            <Actions />
            <KPIs />
          </div>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          <DocumentViewer />
          <RequirementsTable />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <ValidationSummary />
          <KeyFindings />
          <Activity />
        </div>
      </div>
    </>
  );
}
