import { useState } from 'react';
import {
  Table2,
  ChevronDown,
  ChevronUp,
  User,
  CheckSquare,
  ExternalLink,
} from 'lucide-react';
import type { Requirement, RequirementType, RequirementPriority } from '../types';

interface RequirementsTableProps {
  requirements: Requirement[];
}

type TabFilter = 'ALL' | RequirementType;

function priorityBadge(priority: RequirementPriority) {
  switch (priority) {
    case 'MUST':
      return { cls: 'bg-rose-500/15 text-rose-400 border-rose-500/30', label: 'MUST' };
    case 'SHOULD':
      return { cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30', label: 'SHOULD' };
    case 'COULD':
      return { cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30', label: 'COULD' };
    case 'WONT':
      return { cls: 'bg-slate-500/15 text-slate-400 border-slate-500/30', label: "WON'T" };
    default:
      return { cls: 'bg-slate-500/15 text-slate-400 border-slate-500/30', label: priority };
  }
}

function typeBadge(type: RequirementType) {
  switch (type) {
    case 'functional':
      return { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Functional' };
    case 'nonfunctional':
      return { cls: 'bg-purple-500/10 text-purple-400 border-purple-500/20', label: 'Non-Func.' };
    case 'business':
      return { cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', label: 'Business' };
    case 'constraint':
      return { cls: 'bg-orange-500/10 text-orange-400 border-orange-500/20', label: 'Constraint' };
    default:
      return { cls: 'bg-slate-500/10 text-slate-400 border-slate-500/20', label: type };
  }
}

function traceTagStyle(ref: string) {
  if (ref.startsWith('CHUNK:') || ref.startsWith('DOC:'))
    return 'bg-blue-950/30 text-blue-400 border-blue-500/20';
  if (ref.startsWith('ANS-') || ref.startsWith('ANSWER:'))
    return 'bg-violet-950/30 text-violet-400 border-violet-500/20';
  if (ref === 'IDEA')
    return 'bg-amber-950/30 text-amber-400 border-amber-500/20';
  if (ref.startsWith('ASSUMPTION:') || ref.startsWith('ASM-'))
    return 'bg-orange-950/30 text-orange-400 border-orange-500/20';
  return 'bg-slate-900/30 text-slate-400 border-slate-700/30';
}

const TABS: { key: TabFilter; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'functional', label: 'Functional' },
  { key: 'nonfunctional', label: 'Non-Functional' },
  { key: 'business', label: 'Business' },
  { key: 'constraint', label: 'Constraint' },
];

export default function RequirementsTable({ requirements }: RequirementsTableProps) {
  const [activeTab, setActiveTab] = useState<TabFilter>('ALL');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<'priority' | 'id'>('priority');
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = activeTab === 'ALL'
    ? requirements
    : requirements.filter((r) => r.type === activeTab);

  const priorityOrder: Record<RequirementPriority, number> = {
    MUST: 0,
    SHOULD: 1,
    COULD: 2,
    WONT: 3,
  };

  const sorted = [...filtered].sort((a, b) => {
    let cmp: number;
    if (sortField === 'priority') {
      cmp = priorityOrder[a.priority] - priorityOrder[b.priority];
    } else {
      cmp = a.id.localeCompare(b.id);
    }
    return sortAsc ? cmp : -cmp;
  });

  const handleSort = (field: 'priority' | 'id') => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === 'id');
    }
  };

  const tabCounts: Record<TabFilter, number> = {
    ALL: requirements.length,
    functional: requirements.filter((r) => r.type === 'functional').length,
    nonfunctional: requirements.filter((r) => r.type === 'nonfunctional').length,
    business: requirements.filter((r) => r.type === 'business').length,
    constraint: requirements.filter((r) => r.type === 'constraint').length,
  };

  if (requirements.length === 0) {
    return (
      <div className="p-6 text-center rounded-xl border border-dashed border-slate-800 flex flex-col items-center gap-2">
        <Table2 className="w-8 h-8 text-slate-600" />
        <p className="text-sm font-medium text-slate-400">No Requirements Extracted</p>
        <p className="text-xs text-slate-600 max-w-sm">
          Run AI Analysis on your project to extract structured requirements from the business idea and uploaded source documents.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Category Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg border whitespace-nowrap transition ${
              activeTab === tab.key
                ? 'bg-brand-600/20 border-brand-500/40 text-brand-300'
                : 'bg-slate-900/40 border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-600'
            }`}
          >
            {tab.label} ({tabCounts[tab.key]})
          </button>
        ))}
      </div>

      {/* Requirements Table Header */}
      <div className="hidden md:grid grid-cols-12 gap-2 px-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
        <button
          onClick={() => handleSort('id')}
          className="col-span-1 flex items-center gap-1 hover:text-slate-300 transition"
        >
          ID
          {sortField === 'id' && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
        </button>
        <span className="col-span-4">Title & Statement</span>
        <button
          onClick={() => handleSort('priority')}
          className="col-span-1 flex items-center gap-1 hover:text-slate-300 transition"
        >
          Priority
          {sortField === 'priority' && (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
        </button>
        <span className="col-span-1">Type</span>
        <span className="col-span-2">Actor</span>
        <span className="col-span-3">Traceability</span>
      </div>

      {/* Rows */}
      <div className="flex flex-col gap-1.5">
        {sorted.map((req) => {
          const pb = priorityBadge(req.priority);
          const tb = typeBadge(req.type);
          const isExpanded = expandedId === req.id;

          return (
            <div key={req.id} id={`req-row-${req.id}`}>
              {/* Main row */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : req.id)}
                className="w-full grid grid-cols-1 md:grid-cols-12 gap-2 p-3 rounded-xl border border-slate-800/60 bg-slate-900/30 hover:bg-slate-900/60 hover:border-slate-700 transition text-left items-start"
              >
                {/* ID */}
                <span className="col-span-1 text-[11px] font-mono text-slate-500 flex items-center gap-1">
                  {req.id}
                </span>

                {/* Title & Statement */}
                <div className="col-span-4 min-w-0">
                  <p className="text-xs font-semibold text-slate-200 truncate">{req.title}</p>
                  <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">{req.statement}</p>
                </div>

                {/* Priority */}
                <div className="col-span-1">
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${pb.cls}`}>
                    {pb.label}
                  </span>
                </div>

                {/* Type */}
                <div className="col-span-1">
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${tb.cls}`}>
                    {tb.label}
                  </span>
                </div>

                {/* Actor */}
                <div className="col-span-2 flex items-center gap-1 text-[11px] text-slate-400">
                  {req.actor && <User className="w-3 h-3 text-slate-600" />}
                  <span className="truncate">{req.actor || '—'}</span>
                </div>

                {/* Traceability Tags */}
                <div className="col-span-3 flex flex-wrap gap-1">
                  {req.trace_refs.slice(0, 3).map((ref, i) => (
                    <span
                      key={i}
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${traceTagStyle(ref)}`}
                    >
                      {ref.length > 20 ? ref.slice(0, 20) + '…' : ref}
                    </span>
                  ))}
                  {req.trace_refs.length > 3 && (
                    <span className="text-[9px] text-slate-600">+{req.trace_refs.length - 3}</span>
                  )}
                  {req.trace_refs.length === 0 && (
                    <span className="text-[9px] text-slate-700 italic">ungrounded</span>
                  )}
                </div>
              </button>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="ml-2 mr-2 -mt-1 p-4 rounded-b-xl border border-t-0 border-slate-800/60 bg-slate-900/50 flex flex-col gap-3">
                  {/* Full statement */}
                  <div>
                    <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      Full Statement
                    </h5>
                    <p className="text-xs text-slate-300 leading-relaxed">{req.statement}</p>
                  </div>

                  {/* Outcome */}
                  {req.outcome && (
                    <div>
                      <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                        Expected Outcome
                      </h5>
                      <p className="text-xs text-slate-400">{req.outcome}</p>
                    </div>
                  )}

                  {/* Acceptance Criteria */}
                  {req.acceptance_criteria.length > 0 && (
                    <div>
                      <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <CheckSquare className="w-3 h-3" />
                        Acceptance Criteria ({req.acceptance_criteria.length})
                      </h5>
                      <ul className="space-y-1">
                        {req.acceptance_criteria.map((ac, i) => (
                          <li key={i} className="text-xs text-slate-400 flex items-start gap-2">
                            <span className="text-emerald-500 mt-0.5">✓</span>
                            <span>{ac}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* All Trace Refs */}
                  {req.trace_refs.length > 0 && (
                    <div>
                      <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <ExternalLink className="w-3 h-3" />
                        Traceability References
                      </h5>
                      <div className="flex flex-wrap gap-1.5">
                        {req.trace_refs.map((ref, i) => (
                          <span key={i} className={`text-[10px] font-mono px-2 py-0.5 rounded border ${traceTagStyle(ref)}`}>
                            {ref}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Confidence */}
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 pt-1 border-t border-slate-800/60">
                    <span>Confidence: <span className="text-slate-300 font-semibold">{(req.confidence * 100).toFixed(0)}%</span></span>
                    {req.rationale && (
                      <span className="text-slate-600">• {req.rationale}</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
