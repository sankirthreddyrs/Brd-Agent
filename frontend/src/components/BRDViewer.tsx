import React, { useState, useEffect, useCallback } from 'react';
import {
  FileDown,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  List,
  Link2,
  FileText,
  Clock,
} from 'lucide-react';
import { generateBRD, getBRD, downloadBRDDocx } from '../api/projects';
import type { Project, BRDVersion } from '../types';

interface BRDViewerProps {
  project: Project;
  onProjectUpdated?: (project: Project) => void;
}

type ViewTab = 'summary' | 'sections' | 'traceability';

export default function BRDViewer({ project, onProjectUpdated }: BRDViewerProps) {
  const [brd, setBrd] = useState<BRDVersion | null>(null);
  const [isLoadingBrd, setIsLoadingBrd] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ViewTab>('summary');

  const fetchBrd = useCallback(async () => {
    setIsLoadingBrd(true);
    try {
      const data = await getBRD(project.id);
      setBrd(data);
    } catch {
      // no BRD yet — expected before generation
    } finally {
      setIsLoadingBrd(false);
    }
  }, [project.id]);

  useEffect(() => {
    if (project.status === 'COMPLETED' || project.status === 'GENERATED') {
      fetchBrd();
    }
  }, [project.status, fetchBrd]);

  const handleGenerate = async () => {
    setError(null);
    setIsGenerating(true);
    try {
      const res = await generateBRD(project.id);
      setBrd(res.brd_version);
      onProjectUpdated?.(res.project);
    } catch (err: any) {
      setError(err.message || 'BRD generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const cleanTitle = project.title.replace(/\s+/g, '_');
      await downloadBRDDocx(project.id, `BRD_${cleanTitle}_v${brd?.version_number || 1}.docx`);
    } catch (err: any) {
      setError(err.message || 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  };

  // Extract sections from content_json
  const sections: { key: string; title: string; content: any }[] = [];
  if (brd?.content_json) {
    for (const [key, value] of Object.entries(brd.content_json)) {
      const title = key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
      sections.push({ key, title, content: value });
    }
  }

  // Build traceability data from sections
  const traceabilityRows: { reqId: string; title: string; refs: string[]; grounded: boolean }[] = [];
  if (brd?.content_json) {
    const reqs = brd.content_json.requirements || brd.content_json.functional_requirements || brd.content_json.detailed_requirements;
    if (Array.isArray(reqs)) {
      for (const r of reqs) {
        const refs = r.trace_refs || r.traceability || [];
        traceabilityRows.push({
          reqId: r.id || r.requirement_id || '—',
          title: r.title || r.name || r.statement || '—',
          refs: Array.isArray(refs) ? refs : [String(refs)],
          grounded: Array.isArray(refs) && refs.length > 0,
        });
      }
    }
  }

  // ─── READY_TO_GENERATE: Show generate button ───
  if (project.status === 'READY_TO_GENERATE' || project.status === 'FAILED') {
    return (
      <div className="flex flex-col items-center justify-center gap-5 p-10 rounded-xl border border-dashed border-cyan-800/40 bg-cyan-950/10">
        <div className="h-16 w-16 rounded-2xl bg-gradient-to-tr from-brand-600 via-cyan-500 to-indigo-500 p-0.5 shadow-xl shadow-cyan-500/20 flex items-center justify-center">
          <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
            <FileText className="w-7 h-7 text-cyan-400" />
          </div>
        </div>

        <div className="text-center">
          <h3 className="text-base font-bold text-white">
            {project.status === 'FAILED' ? 'Retry BRD Generation' : 'Generate Final BRD'}
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-md">
            {project.status === 'FAILED'
              ? `Previous generation failed: ${project.last_error || 'Unknown error'}. Click below to retry.`
              : 'All requirements, assumptions, and clarifications are resolved. Generate the structured BRD document and Word export.'}
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/50 border border-rose-500/30 text-rose-300 text-xs max-w-md">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          id="btn-generate-brd"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="flex items-center gap-2.5 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-brand-600 hover:from-cyan-400 hover:to-brand-500 text-white text-sm font-bold shadow-xl shadow-brand-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Compiling & Generating...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Generate Final BRD
            </>
          )}
        </button>
      </div>
    );
  }

  // ─── GENERATING: In-progress state ───
  if (project.status === 'GENERATING') {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-10 rounded-xl border border-dashed border-amber-800/40 bg-amber-950/10">
        <RefreshCw className="w-10 h-10 text-amber-400 animate-spin" />
        <div className="text-center">
          <h3 className="text-base font-bold text-white">Generating BRD...</h3>
          <p className="text-xs text-slate-400 mt-1">
            The AI is compiling requirements, running quality checks, and rendering the Word document.
          </p>
        </div>
      </div>
    );
  }

  // ─── LOADING: Fetching existing BRD ───
  if (isLoadingBrd) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-10 rounded-xl border border-dashed border-slate-800 bg-slate-900/20">
        <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
        <p className="text-xs text-slate-400">Loading BRD document...</p>
      </div>
    );
  }

  // ─── COMPLETED / GENERATED: Show BRD viewer ───
  if ((project.status === 'COMPLETED' || project.status === 'GENERATED') && brd) {
    return (
      <div className="flex flex-col gap-5">
        {/* Header with Download */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-brand-400" />
              {brd.title || project.title}
            </h3>
            <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                v{brd.version_number}
              </span>
              <span>•</span>
              <span>{sections.length} sections</span>
              {brd.created_at && (
                <>
                  <span>•</span>
                  <span>{new Date(brd.created_at).toLocaleString()}</span>
                </>
              )}
            </div>
          </div>

          <button
            id="btn-download-docx"
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-emerald-500/15 transition disabled:opacity-50"
          >
            {isDownloading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <FileDown className="w-3.5 h-3.5" />
                Download Word (.docx)
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-950/50 border border-rose-500/30 text-rose-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="flex items-center gap-1.5">
          {([
            { key: 'summary', label: 'Executive Summary', icon: <BookOpen className="w-3 h-3" /> },
            { key: 'sections', label: 'Full Breakdown', icon: <List className="w-3 h-3" /> },
            { key: 'traceability', label: 'Traceability Matrix', icon: <Link2 className="w-3 h-3" /> },
          ] as { key: ViewTab; label: string; icon: React.ReactNode }[]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-lg border transition ${
                activeTab === tab.key
                  ? 'bg-brand-600/20 border-brand-500/40 text-brand-300'
                  : 'bg-slate-900/40 border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-600'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'summary' && (
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60">
            {brd.content_json.executive_summary ? (
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {typeof brd.content_json.executive_summary === 'string'
                  ? brd.content_json.executive_summary
                  : JSON.stringify(brd.content_json.executive_summary, null, 2)}
              </div>
            ) : sections.length > 0 ? (
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {typeof sections[0].content === 'string'
                  ? sections[0].content
                  : JSON.stringify(sections[0].content, null, 2)}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No executive summary found in the BRD content.</p>
            )}
          </div>
        )}

        {activeTab === 'sections' && (
          <div className="flex flex-col gap-3">
            {sections.map((section, idx) => (
              <details key={section.key} className="group rounded-xl border border-slate-800/60 bg-slate-900/30" open={idx === 0}>
                <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-slate-900/60 transition rounded-xl text-sm font-semibold text-slate-200">
                  <span className="text-[10px] font-bold text-slate-600 bg-slate-800/60 rounded px-1.5 py-0.5 min-w-[20px] text-center">
                    {idx + 1}
                  </span>
                  {section.title}
                </summary>
                <div className="px-4 pb-4 text-xs text-slate-400 leading-relaxed whitespace-pre-wrap border-t border-slate-800/60 pt-3">
                  {typeof section.content === 'string'
                    ? section.content
                    : JSON.stringify(section.content, null, 2)}
                </div>
              </details>
            ))}
          </div>
        )}

        {activeTab === 'traceability' && (
          <div className="rounded-xl border border-slate-800/60 overflow-hidden">
            {traceabilityRows.length === 0 ? (
              <div className="p-6 text-center text-slate-600 text-xs">
                No traceability data found in the BRD content. Requirements may be embedded in a different structure.
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-900/60 text-slate-500 text-[10px] uppercase tracking-wider">
                    <th className="px-4 py-2.5 font-bold">Req ID</th>
                    <th className="px-4 py-2.5 font-bold">Title</th>
                    <th className="px-4 py-2.5 font-bold">Grounding References</th>
                    <th className="px-4 py-2.5 font-bold text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {traceabilityRows.map((row, i) => (
                    <tr
                      key={i}
                      className="border-t border-slate-800/60 hover:bg-slate-900/40 transition"
                    >
                      <td className="px-4 py-2.5 font-mono text-slate-400">{row.reqId}</td>
                      <td className="px-4 py-2.5 text-slate-300 max-w-[250px] truncate">{row.title}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex flex-wrap gap-1">
                          {row.refs.map((ref, j) => (
                            <span key={j} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800/60 border border-slate-700/40 text-slate-400">
                              {ref}
                            </span>
                          ))}
                          {row.refs.length === 0 && (
                            <span className="text-[9px] italic text-slate-600">none</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {row.grounded ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 mx-auto" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-400 mx-auto" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    );
  }

  // ─── Fallback: Not in a BRD-relevant state ───
  return (
    <div className="p-6 text-center rounded-xl border border-dashed border-slate-800 flex flex-col items-center gap-2">
      <FileDown className="w-8 h-8 text-slate-600" />
      <p className="text-sm font-medium text-slate-400">BRD Not Available</p>
      <p className="text-xs text-slate-600 max-w-sm">
        Complete all analysis and clarification steps to unlock BRD generation. Current status: <span className="font-mono text-slate-400">{project.status}</span>
      </p>
    </div>
  );
}
