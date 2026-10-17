import { createFileRoute } from "@tanstack/react-router";
import { DocumentViewer, Card } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";
import { FileText, Download, CheckCircle2, Clock } from "lucide-react";

export const Route = createFileRoute("/documents")({
  head: () => ({
    meta: [
      { title: "Documents — BRD Agent" },
      { name: "description", content: "Grounding source files and compiled Business Requirements Documents." },
    ],
  }),
  component: Page,
});

function Page() {
  const { activeProject, brdVersion, downloadDocx, sources } = useApp();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[20px] font-bold text-foreground">
          {activeProject ? `${activeProject.title} — Documents` : "Documents"}
        </h1>
        <p className="text-[12.5px] text-muted-foreground">
          Manage grounding input files and generated BRD artifacts
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <DocumentViewer />

        {/* Generated Artifacts card */}
        <Card className="flex flex-col p-4">
          <h2 className="text-[13.5px] font-semibold text-foreground mb-1">Generated Deliverables</h2>
          <p className="text-[11.5px] text-muted-foreground mb-3">
            Formal Word (.docx) documents compiled with deterministic verification
          </p>

          <div className="flex-1 min-h-[220px]">
            {brdVersion ? (
              <div className="space-y-3">
                <div className="rounded-lg border border-primary/30 bg-primary/5 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/20 text-primary">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="font-semibold text-[13.5px] text-foreground">{brdVersion.title}</div>
                        <div className="text-[11px] text-muted-foreground mt-0.5">
                          Version {brdVersion.version_number} • {brdVersion.status}
                        </div>
                      </div>
                    </div>
                    <span className="inline-flex items-center gap-1 rounded bg-success/10 text-success border border-success/20 px-2 py-0.5 text-[10.5px] font-semibold">
                      <CheckCircle2 className="h-3 w-3" />
                      COMPILED
                    </span>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                    <span className="text-[11px] text-muted-foreground">
                      Ready for enterprise stakeholder review
                    </span>
                    <button
                      onClick={downloadDocx}
                      className="flex items-center gap-1.5 rounded-md bg-primary px-3.5 py-1.5 text-[12px] font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download .docx</span>
                    </button>
                  </div>
                </div>

                <div className="rounded-lg border border-border p-3 text-[11.5px] text-muted-foreground bg-muted/20">
                  <span className="font-semibold text-foreground">Standard 7-Section BRD Skeleton:</span>
                  <ul className="mt-1 list-disc pl-5 space-y-0.5">
                    <li>Executive Summary &amp; Business Objectives</li>
                    <li>User Personas &amp; Stakeholder Map</li>
                    <li>Functional Requirements Matrix</li>
                    <li>Non-Functional Requirements (NFRs)</li>
                    <li>Business Rules &amp; Constraints</li>
                    <li>Assumptions &amp; Dependencies</li>
                    <li>Data Dictionary &amp; Traceability Matrix</li>
                  </ul>
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center p-8 text-center border-2 border-dashed border-border rounded-lg">
                <Clock className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <div className="text-[13px] font-medium text-foreground">No BRD version generated yet</div>
                <div className="text-[11.5px] text-muted-foreground mt-1 max-w-xs">
                  Run AI analysis and resolve clarification gaps to compile your formal BRD artifact.
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
