import { useState, useEffect, useCallback } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Check,
  X,
  RefreshCw,
  Link2,
  AlertTriangle,
  UserCheck,
  Clock,
} from 'lucide-react';
import { getAssumptions, decideAssumption } from '../api/projects';
import type { Assumption, ImpactLevel, AssumptionStatus } from '../types';

interface AssumptionReviewProps {
  projectId: string;
  onDecisionMade?: () => void;
}

function statusConfig(status: AssumptionStatus) {
  switch (status) {
    case 'ACCEPTED':
      return {
        icon: <ShieldCheck className="w-4 h-4" />,
        cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
        label: 'Accepted',
      };
    case 'REJECTED':
      return {
        icon: <ShieldX className="w-4 h-4" />,
        cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
        label: 'Rejected',
      };
    case 'SUPERSEDED':
      return {
        icon: <ShieldAlert className="w-4 h-4" />,
        cls: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
        label: 'Superseded',
      };
    default:
      return {
        icon: <ShieldAlert className="w-4 h-4" />,
        cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
        label: 'Proposed',
      };
  }
}

function impactConfig(impact: ImpactLevel) {
  switch (impact) {
    case 'HIGH':
      return { cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30', label: 'High Risk' };
    case 'MEDIUM':
      return { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30', label: 'Medium Risk' };
    default:
      return { cls: 'bg-slate-500/10 text-slate-400 border-slate-500/30', label: 'Low Risk' };
  }
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}

export default function AssumptionReview({ projectId, onDecisionMade }: AssumptionReviewProps) {
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<'ALL' | AssumptionStatus>('ALL');

  const fetchAssumptions = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getAssumptions(projectId);
      setAssumptions(data);
    } catch {
      // empty
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchAssumptions();
  }, [fetchAssumptions]);

  const handleDecision = async (assumptionId: string, decision: 'accepted' | 'rejected') => {
    setProcessingIds((prev) => new Set(prev).add(assumptionId));
    setActionErrors((prev) => {
      const next = { ...prev };
      delete next[assumptionId];
      return next;
    });

    try {
      const updated = await decideAssumption(projectId, assumptionId, decision);
      setAssumptions((prev) =>
        prev.map((a) => (a.id === assumptionId ? updated : a))
      );
      onDecisionMade?.();
    } catch (err: any) {
      setActionErrors((prev) => ({ ...prev, [assumptionId]: err.message }));
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(assumptionId);
        return next;
      });
    }
  };

  const filtered = filter === 'ALL' ? assumptions : assumptions.filter((a) => a.status === filter);
  const proposedCount = assumptions.filter((a) => a.status === 'PROPOSED').length;

  if (isLoading) {
    return (
      <div className="p-6 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
        <RefreshCw className="w-5 h-5 animate-spin text-brand-400" />
        Loading assumptions...
      </div>
    );
  }

  if (assumptions.length === 0) {
    return (
      <div className="p-6 text-center rounded-xl border border-dashed border-slate-800 flex flex-col items-center gap-2">
        <ShieldCheck className="w-8 h-8 text-emerald-500/30" />
        <p className="text-sm font-medium text-slate-400">No Assumptions</p>
        <p className="text-xs text-slate-600 max-w-sm">
          No assumptions have been generated yet. Run AI Analysis to identify requirement gaps that may require assumptions.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filter Tabs */}
      <div className="flex items-center gap-2 flex-wrap">
        {(['ALL', 'PROPOSED', 'ACCEPTED', 'REJECTED'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg border transition ${
              filter === f
                ? 'bg-brand-600/20 border-brand-500/40 text-brand-300'
                : 'bg-slate-900/40 border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-600'
            }`}
          >
            {f === 'ALL' ? `All (${assumptions.length})` : f === 'PROPOSED' ? `Proposed (${proposedCount})` : f}
          </button>
        ))}
      </div>

      {/* Assumption Cards */}
      <div className="flex flex-col gap-2.5">
        {filtered.length === 0 ? (
          <div className="p-4 text-center text-slate-600 text-xs border border-dashed border-slate-800 rounded-lg">
            No assumptions with status "{filter}".
          </div>
        ) : (
          filtered.map((asm) => {
            const sc = statusConfig(asm.status);
            const ic = impactConfig(asm.impact);
            const isProcessing = processingIds.has(asm.id);
            const error = actionErrors[asm.id];

            return (
              <div
                key={asm.id}
                id={`assumption-card-${asm.id}`}
                className="p-3.5 rounded-xl border border-slate-800/70 bg-slate-900/40 flex flex-col gap-3"
              >
                {/* Header row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono text-slate-600">{asm.id}</span>
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border flex items-center gap-1 ${sc.cls}`}>
                        {sc.icon}
                        {sc.label}
                      </span>
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${ic.cls}`}>
                        {ic.label}
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 leading-snug">{asm.statement}</p>
                  </div>
                </div>

                {/* Rationale */}
                <p className="text-xs text-slate-500 leading-relaxed pl-0.5">
                  <span className="font-semibold text-slate-400">Rationale:</span> {asm.rationale}
                </p>

                {/* Linked Requirements */}
                {asm.linked_requirement_ids.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link2 className="w-3 h-3 text-slate-600" />
                    {asm.linked_requirement_ids.map((rid) => (
                      <span
                        key={rid}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/50 text-slate-400"
                      >
                        {rid}
                      </span>
                    ))}
                  </div>
                )}

                {/* Reviewer Attribution Badge */}
                {(asm.reviewed_by || asm.reviewer_email) && (
                  <div className="flex items-center gap-1.5 text-[11px] text-cyan-300 bg-cyan-950/40 border border-cyan-500/20 px-2.5 py-1 rounded-md w-fit">
                    <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                    <span>
                      Reviewed by{' '}
                      <span className="font-semibold text-white">
                        {asm.reviewer_email || asm.reviewed_by}
                      </span>
                      {asm.reviewed_at && (
                        <span className="text-slate-400 ml-1.5 inline-flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5 text-slate-500" />
                          {formatDate(asm.reviewed_at)}
                        </span>
                      )}
                    </span>
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-[11px]">
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                    {error}
                  </div>
                )}

                {/* Action Buttons — only for PROPOSED */}
                {asm.status === 'PROPOSED' && (
                  <div className="flex items-center gap-2 pt-1 border-t border-slate-800/60">
                    <button
                      id={`btn-accept-${asm.id}`}
                      onClick={() => handleDecision(asm.id, 'accepted')}
                      disabled={isProcessing}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/15 hover:bg-emerald-600/30 border border-emerald-500/30 text-emerald-400 text-xs font-medium transition disabled:opacity-40"
                    >
                      {isProcessing ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <Check className="w-3 h-3" />
                      )}
                      Accept
                    </button>
                    <button
                      id={`btn-reject-${asm.id}`}
                      onClick={() => handleDecision(asm.id, 'rejected')}
                      disabled={isProcessing}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/15 hover:bg-rose-600/30 border border-rose-500/30 text-rose-400 text-xs font-medium transition disabled:opacity-40"
                    >
                      {isProcessing ? (
                        <RefreshCw className="w-3 h-3 animate-spin" />
                      ) : (
                        <X className="w-3 h-3" />
                      )}
                      Reject
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
