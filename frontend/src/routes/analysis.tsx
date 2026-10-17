import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Card, ValidationSummary } from "@/components/brd/Panels";
import { useApp } from "@/context/AppContext";
import {
  BrainCircuit, Play, Loader2, CheckCircle2, XCircle, HelpCircle, AlertCircle,
  Send, Sparkles, ShieldAlert
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/analysis")({
  head: () => ({
    meta: [
      { title: "BRD Analysis — BRD Agent" },
      { name: "description", content: "Interactive clarification questions and assumption decisions." },
    ],
  }),
  component: Page,
});

function Page() {
  const {
    activeProject,
    questions,
    assumptions,
    triggerAnalyze,
    isAnalyzing,
    submitQuestionAnswers,
    decideAssumption,
    generateBRD,
  } = useApp();

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submittingQ, setSubmittingQ] = useState<string | null>(null);

  const handleAnswerSubmit = async (questionId: string) => {
    const val = (answers[questionId] || "").trim();
    if (!val) {
      toast.error("Please enter an answer before submitting.");
      return;
    }
    setSubmittingQ(questionId);
    try {
      await submitQuestionAnswers([{ question_id: questionId, value: val }]);
      setAnswers((prev) => ({ ...prev, [questionId]: "" }));
    } finally {
      setSubmittingQ(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-bold text-foreground">
            {activeProject ? `${activeProject.title} — AI Analysis & Gaps` : "BRD Analysis"}
          </h1>
          <p className="text-[12.5px] text-muted-foreground">
            Resolve clarification questions and accept/reject synthesized assumptions to progress toward BRD generation
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={triggerAnalyze}
            disabled={isAnalyzing || !activeProject}
            className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {isAnalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            <span>{isAnalyzing ? "Analyzing Project..." : "Run AI Analysis"}</span>
          </button>

          {activeProject?.status === "READY_TO_GENERATE" && (
            <button
              onClick={generateBRD}
              className="flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-[12.5px] font-medium text-white hover:bg-emerald-500 transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              <span>Generate Formal BRD</span>
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ValidationSummary />
        </div>

        {/* Assumptions Review */}
        <div className="lg:col-span-2">
          <Card className="flex flex-col p-4 h-full">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-[14px] font-semibold text-foreground">Explicit Assumptions ({assumptions.length})</h2>
                <p className="text-[11.5px] text-muted-foreground">AI-synthesized defaults requiring business stakeholder sign-off</p>
              </div>
            </div>

            <div className="mt-2 flex-1 overflow-y-auto max-h-[360px] space-y-2.5">
              {assumptions.length === 0 ? (
                <div className="p-8 text-center text-[12.5px] text-muted-foreground">
                  No assumptions generated yet. Run AI Analysis to evaluate project assumptions.
                </div>
              ) : (
                assumptions.map((a) => {
                  const isAccepted = a.status.toUpperCase() === "ACCEPTED";
                  const isRejected = a.status.toUpperCase() === "REJECTED";

                  return (
                    <div
                      key={a.id}
                      className={`p-3 rounded-lg border text-[12px] transition-colors ${
                        isAccepted
                          ? "border-emerald-500/30 bg-emerald-500/5"
                          : isRejected
                          ? "border-destructive/30 bg-destructive/5"
                          : "border-border bg-card"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="font-medium text-foreground">{a.statement}</div>
                          <div className="text-[11px] text-muted-foreground mt-1">
                            <span className="font-medium text-foreground/80">Rationale:</span> {a.rationale}
                          </div>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">
                              Impact: {a.impact}
                            </span>
                            <span
                              className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded border ${
                                isAccepted
                                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                                  : isRejected
                                  ? "bg-destructive/10 text-destructive border-destructive/20"
                                  : "bg-warning/10 text-warning border-warning/20"
                              }`}
                            >
                              {a.status}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            onClick={() => decideAssumption(a.id, "accepted")}
                            title="Accept Assumption"
                            className={`p-1.5 rounded border transition-colors ${
                              isAccepted
                                ? "bg-emerald-600 text-white border-emerald-600"
                                : "hover:bg-emerald-500/10 text-emerald-600 border-emerald-500/30"
                            }`}
                          >
                            <CheckCircle2 className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => decideAssumption(a.id, "rejected")}
                            title="Reject Assumption"
                            className={`p-1.5 rounded border transition-colors ${
                              isRejected
                                ? "bg-destructive text-white border-destructive"
                                : "hover:bg-destructive/10 text-destructive border-destructive/30"
                            }`}
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Clarification Questions Section */}
      <Card className="p-4">
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-foreground">Clarification Questions ({questions.length})</h2>
          <p className="text-[12px] text-muted-foreground">
            Targeted questions automatically generated by AI to resolve incomplete or ambiguous requirements
          </p>
        </div>

        {questions.length === 0 ? (
          <div className="p-10 text-center border-2 border-dashed border-border rounded-lg">
            <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
            <h3 className="text-[13.5px] font-semibold text-foreground">No Open Clarification Gaps</h3>
            <p className="text-[12px] text-muted-foreground mt-1 max-w-sm mx-auto">
              All identified requirements are grounded. You are ready to generate your formal BRD document!
            </p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {questions.map((q) => {
              const currentAnswer = answers[q.id] || "";
              const isSubmitting = submittingQ === q.id;

              return (
                <div key={q.id} className="p-3.5 rounded-lg border border-border bg-card flex flex-col justify-between">
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <span className="font-medium text-[13px] text-foreground">{q.question_text}</span>
                      <span className="shrink-0 text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                        Priority {q.priority}
                      </span>
                    </div>
                    {q.why_it_matters && (
                      <p className="text-[11.5px] text-muted-foreground mb-3 italic">
                        Why it matters: {q.why_it_matters}
                      </p>
                    )}
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      value={currentAnswer}
                      onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleAnswerSubmit(q.id);
                      }}
                      placeholder="Type stakeholder decision or answer..."
                      className="flex-1 rounded-md border border-input bg-card px-3 py-1.5 text-[12.5px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                    <button
                      onClick={() => handleAnswerSubmit(q.id)}
                      disabled={isSubmitting || !currentAnswer.trim()}
                      className="flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-[12px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {isSubmitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                      <span>Submit</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
