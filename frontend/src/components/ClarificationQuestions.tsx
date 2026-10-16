import { useState, useEffect, useCallback } from 'react';
import {
  MessageCircleQuestion,
  Send,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CircleDot,
  CheckCircle2,
  Info,
  Zap,
} from 'lucide-react';
import { getQuestions, submitAnswers } from '../api/projects';
import type { Question, AnswerSubmissionItem, SubmitAnswersResponse } from '../types';

interface ClarificationQuestionsProps {
  projectId: string;
  onAnswersSubmitted?: (response: SubmitAnswersResponse) => void;
}

function impactBadge(impact: number) {
  switch (impact) {
    case 3:
      return { label: 'High Impact', cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' };
    case 2:
      return { label: 'Medium', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' };
    default:
      return { label: 'Low', cls: 'bg-slate-500/10 text-slate-400 border-slate-500/30' };
  }
}

export default function ClarificationQuestions({
  projectId,
  onAnswersSubmitted,
}: ClarificationQuestionsProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const fetchQuestions = useCallback(async () => {
    setIsLoading(true);
    try {
      const qs = await getQuestions(projectId);
      // Sort by priority descending (impact * gap_confidence)
      qs.sort((a, b) => b.priority - a.priority);
      setQuestions(qs);
      // Auto-expand first 3
      setExpandedIds(new Set(qs.slice(0, 3).map((q) => q.id)));
    } catch {
      // empty list is fine
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const setAnswer = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const answeredCount = Object.values(answers).filter((v) => v.trim().length > 0).length;

  const handleSubmit = async () => {
    const items: AnswerSubmissionItem[] = Object.entries(answers)
      .filter(([, v]) => v.trim().length > 0)
      .map(([question_id, value]) => ({ question_id, value: value.trim() }));

    if (items.length === 0) {
      setSubmitError('Please answer at least one question before submitting.');
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const response = await submitAnswers(projectId, items);
      setAnswers({});
      onAnswersSubmitted?.(response);
      // Refresh the questions (re-analysis may produce new ones or mark answered)
      await fetchQuestions();
    } catch (err: any) {
      setSubmitError(err.message || 'Failed to submit answers');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-6 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
        <RefreshCw className="w-5 h-5 animate-spin text-brand-400" />
        Loading clarification questions...
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="p-6 text-center rounded-xl border border-dashed border-slate-800 flex flex-col items-center gap-2">
        <CheckCircle2 className="w-8 h-8 text-emerald-500/40" />
        <p className="text-sm font-medium text-slate-400">No Open Questions</p>
        <p className="text-xs text-slate-600 max-w-sm">
          All clarification gaps have been resolved, or analysis has not yet generated questions.
          Run AI Analysis to detect any remaining gaps.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header summary */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageCircleQuestion className="w-4 h-4 text-violet-400" />
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Open Questions ({questions.length})
          </span>
        </div>
        <span className="text-xs text-slate-500">
          {answeredCount} / {questions.length} answered
        </span>
      </div>

      {/* Question Cards */}
      <div className="flex flex-col gap-2.5">
        {questions.map((q, idx) => {
          const expanded = expandedIds.has(q.id);
          const badge = impactBadge(q.impact);
          const currentAnswer = answers[q.id] || '';

          return (
            <div
              key={q.id}
              id={`question-card-${q.id}`}
              className={`rounded-xl border transition-all ${
                currentAnswer.trim().length > 0
                  ? 'border-emerald-500/30 bg-emerald-950/10'
                  : 'border-slate-800/70 bg-slate-900/40'
              }`}
            >
              {/* Question header */}
              <button
                onClick={() => toggleExpand(q.id)}
                className="w-full flex items-start gap-3 p-3.5 text-left"
              >
                <span className="text-[10px] font-bold text-slate-500 bg-slate-800/60 rounded px-1.5 py-0.5 mt-0.5 min-w-[24px] text-center">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 leading-snug">
                    {q.question_text}
                  </p>
                  <div className="flex flex-wrap items-center gap-2 mt-1.5">
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${badge.cls}`}>
                      {badge.label}
                    </span>
                    <span className="text-[10px] text-slate-600 font-mono">{q.field_path}</span>
                    <span className="text-[10px] text-slate-600 flex items-center gap-0.5">
                      <Zap className="w-2.5 h-2.5" />
                      {q.gap_confidence.toFixed(2)} confidence
                    </span>
                  </div>
                </div>
                {expanded ? (
                  <ChevronUp className="w-4 h-4 text-slate-500 flex-shrink-0 mt-1" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0 mt-1" />
                )}
              </button>

              {/* Expanded section */}
              {expanded && (
                <div className="px-3.5 pb-3.5 flex flex-col gap-3 border-t border-slate-800/60 pt-3">
                  {/* Why it matters */}
                  <div className="flex gap-2 p-2.5 rounded-lg bg-indigo-950/20 border border-indigo-500/15 text-xs text-slate-400">
                    <Info className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0 mt-0.5" />
                    <span>{q.why_it_matters}</span>
                  </div>

                  {/* Answer input */}
                  {q.answer_format === 'CHOICE' && q.options && q.options.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {q.options.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => setAnswer(q.id, opt)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                            currentAnswer === opt
                              ? 'bg-brand-600/20 border-brand-500/50 text-brand-300 shadow-sm shadow-brand-500/10'
                              : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-600'
                          }`}
                        >
                          {currentAnswer === opt && (
                            <CircleDot className="w-3 h-3 inline mr-1 -mt-0.5" />
                          )}
                          {opt}
                        </button>
                      ))}
                    </div>
                  ) : q.answer_format === 'YES_NO' ? (
                    <div className="flex gap-2">
                      {['Yes', 'No'].map((opt) => (
                        <button
                          key={opt}
                          onClick={() => setAnswer(q.id, opt)}
                          className={`px-4 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                            currentAnswer === opt
                              ? 'bg-brand-600/20 border-brand-500/50 text-brand-300'
                              : 'bg-slate-900/50 border-slate-800 text-slate-400 hover:border-slate-600'
                          }`}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <textarea
                      value={currentAnswer}
                      onChange={(e) => setAnswer(q.id, e.target.value)}
                      rows={2}
                      placeholder={
                        q.answer_format === 'NUMBER'
                          ? 'Enter a numeric value...'
                          : q.answer_format === 'DATE'
                          ? 'Enter a date (YYYY-MM-DD)...'
                          : 'Type your answer...'
                      }
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-white placeholder-slate-600 text-xs focus:outline-none focus:border-brand-500 transition resize-none"
                    />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Submit Error */}
      {submitError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/50 border border-rose-500/30 text-rose-300 text-xs">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{submitError}</span>
        </div>
      )}

      {/* Submit Button */}
      <button
        id="btn-submit-answers"
        onClick={handleSubmit}
        disabled={isSubmitting || answeredCount === 0}
        className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-brand-600 hover:from-violet-500 hover:to-brand-500 text-white text-xs font-semibold shadow-lg shadow-violet-500/15 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isSubmitting ? (
          <>
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            Submitting & Re-analyzing...
          </>
        ) : (
          <>
            <Send className="w-3.5 h-3.5" />
            Submit Answers & Re-analyze ({answeredCount})
          </>
        )}
      </button>
    </div>
  );
}
