import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  FileText,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Plus,
  FolderOpen,
  Clock,
  Layers,
  AlertTriangle,
  Database,
  Cpu,
  Upload,
  MessageCircleQuestion,
  ShieldCheck,
  FileDown,
  Table2,
  LogOut,
} from 'lucide-react';
import type { User as SupabaseUser } from '@supabase/supabase-js';
import { supabase } from './api/supabase';
import {
  checkHealth,
  getProjects,
  createProject,
  analyzeProject,
  getQuestions,
  getAssumptions,
} from './api/projects';
import type {
  Project,
  ProjectStatus,
  Requirement,
  Question,
  Assumption,
  AnalyzeResponse,
  SubmitAnswersResponse,
} from './types';

import DocumentUploader from './components/DocumentUploader';
import ClarificationQuestions from './components/ClarificationQuestions';
import AssumptionReview from './components/AssumptionReview';
import RequirementsTable from './components/RequirementsTable';
import BRDViewer from './components/BRDViewer';
import AuthModal from './components/AuthModal';

// ─── Shared Status Badge Utility ───────────────────────────────
function getStatusBadge(status: ProjectStatus) {
  switch (status) {
    case 'COMPLETED':
      return { bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-400', label: 'Completed' };
    case 'READY_TO_GENERATE':
      return { bg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30', dot: 'bg-cyan-400', label: 'Ready to Generate' };
    case 'ANALYZING':
    case 'GENERATING':
      return { bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30', dot: 'bg-amber-400 animate-pulse', label: status === 'ANALYZING' ? 'Analyzing...' : 'Generating...' };
    case 'AWAITING_CLARIFICATION':
      return { bg: 'bg-violet-500/10 text-violet-400 border-violet-500/30', dot: 'bg-violet-400', label: 'Clarification Needed' };
    case 'FAILED':
      return { bg: 'bg-rose-500/10 text-rose-400 border-rose-500/30', dot: 'bg-rose-400', label: 'Failed' };
    case 'DRAFT':
    default:
      return { bg: 'bg-slate-500/10 text-slate-300 border-slate-500/30', dot: 'bg-slate-400', label: 'Draft' };
  }
}

// ─── Tab Definitions ───────────────────────────────────────────
type WorkspaceTab = 'inputs' | 'analysis' | 'clarification' | 'brd';

interface TabDef {
  key: WorkspaceTab;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

// ─── Main Application ──────────────────────────────────────────
export default function App() {
  // Auth
  const [currentUser, setCurrentUser] = useState<SupabaseUser | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  // Health
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  // Projects
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  // Active project data
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [openQuestions, setOpenQuestions] = useState<Question[]>([]);
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Workspace tab
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('inputs');

  // New Project Modal
  const [isCreating, setIsCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newIdea, setNewIdea] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Toast Notification
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  // ─── Health ──────────────────────────────────────────────────
  const pingHealth = useCallback(async () => {
    setIsCheckingHealth(true);
    setHealthError(null);
    try {
      const data = await checkHealth();
      setIsBackendHealthy(data?.status === 'ok');
    } catch (err: any) {
      setIsBackendHealthy(false);
      setHealthError(err.message || 'Connection failed');
    } finally {
      setIsCheckingHealth(false);
    }
  }, []);

  // ─── Project List ────────────────────────────────────────────
  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    try {
      const data = await getProjects(20);
      setProjects(data);
    } catch {
      // silently ignore
    } finally {
      setIsLoadingProjects(false);
    }
  }, []);

  // ─── Supabase Auth Listener ──────────────────────────────────
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setCurrentUser(session?.user ?? null);
      setIsAuthLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      const newUser = session?.user ?? null;
      setCurrentUser(newUser);
      setIsAuthLoading(false);
      if (!newUser) {
        // Clear project state cleanly on logout / user switch
        setSelectedProject(null);
        setProjects([]);
        setRequirements([]);
        setOpenQuestions([]);
        setAssumptions([]);
      } else {
        fetchProjects();
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [fetchProjects]);

  // ─── Load project-specific entity state ──────────────────────
  const loadProjectData = useCallback(async (projectId: string) => {
    try {
      const [qs, asms] = await Promise.all([
        getQuestions(projectId).catch(() => [] as Question[]),
        getAssumptions(projectId).catch(() => [] as Assumption[]),
      ]);
      setOpenQuestions(qs);
      setAssumptions(asms);
    } catch {
      // silently ignore
    }
  }, []);

  // ─── Sync data when selection changes ────────────────────────
  useEffect(() => {
    if (selectedProject) {
      setRequirements([]);
      setOpenQuestions([]);
      setAssumptions([]);
      loadProjectData(selectedProject.id);
    }
  }, [selectedProject?.id, loadProjectData]);

  // ─── Initial load & heartbeat ────────────────────────────────
  useEffect(() => {
    pingHealth();
    if (currentUser) {
      fetchProjects();
    }
    const interval = setInterval(pingHealth, 30000);
    return () => clearInterval(interval);
  }, [pingHealth, fetchProjects, currentUser]);

  // ─── Update helpers ──────────────────────────────────────────
  const updateProject = (updated: Project) => {
    setSelectedProject(updated);
    setProjects((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };

  const handleAnalyzeResult = (res: AnalyzeResponse) => {
    updateProject(res.project);
    setRequirements(res.requirements);
    setOpenQuestions(res.open_questions);
    setAssumptions(res.assumptions);
    // Auto-switch to appropriate tab
    if (res.next_status === 'AWAITING_CLARIFICATION') {
      setActiveTab('clarification');
    } else if (res.next_status === 'READY_TO_GENERATE') {
      setActiveTab('brd');
    } else {
      setActiveTab('analysis');
    }
  };

  // ─── Handlers ────────────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!selectedProject) return;
    setIsAnalyzing(true);
    showNotification('success', `Initiating AI analysis for "${selectedProject.title}"...`);
    try {
      const res = await analyzeProject(selectedProject.id);
      handleAnalyzeResult(res);
      showNotification('success', `Analysis complete! Status: ${res.next_status}`);
    } catch (err: any) {
      showNotification('error', `Analysis failed: ${err.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAnswersSubmitted = (res: SubmitAnswersResponse) => {
    updateProject(res.project);
    setRequirements(res.requirements);
    setOpenQuestions(res.open_questions);
    setAssumptions(res.assumptions);
    showNotification('success', `Answers merged & re-analyzed. Status: ${res.next_status}`);
    if (res.next_status === 'READY_TO_GENERATE') {
      setActiveTab('brd');
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIdea || newIdea.trim().length < 10) {
      setCreateError('Business idea must be at least 10 characters long.');
      return;
    }
    setCreateError(null);
    setIsSubmitting(true);
    try {
      const res = await createProject(newTitle, newIdea);
      const created = res.project;
      setProjects((prev) => [created, ...prev]);
      setSelectedProject(created);
      setActiveTab('inputs');
      setNewTitle('');
      setNewIdea('');
      setIsCreating(false);
      showNotification('success', `Project "${created.title}" created!`);
    } catch (err: any) {
      setCreateError(err.message || 'Failed to create project');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Tab Definitions with dynamic badge counts ───────────────
  const proposedCount = assumptions.filter((a) => a.status === 'PROPOSED').length;

  const tabs: TabDef[] = [
    { key: 'inputs', label: 'Inputs & Sources', icon: <Upload className="w-3.5 h-3.5" /> },
    { key: 'analysis', label: 'Analysis & Requirements', icon: <Table2 className="w-3.5 h-3.5" />, badge: requirements.length || undefined },
    { key: 'clarification', label: 'Clarification & Assumptions', icon: <MessageCircleQuestion className="w-3.5 h-3.5" />, badge: (openQuestions.length + proposedCount) || undefined },
    { key: 'brd', label: 'Final BRD & Export', icon: <FileDown className="w-3.5 h-3.5" /> },
  ];

  // ─── Render ──────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-brand-500/30 selection:text-brand-200">
      {/* Background glows */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl" />
        <div className="absolute top-1/3 -right-40 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
      </div>

      {/* ═══════════════════ HEADER ═══════════════════ */}
      <header id="app-header" className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-6 py-3.5 backdrop-blur-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3.5">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-brand-600 via-cyan-500 to-indigo-500 p-0.5 shadow-lg shadow-brand-500/20 flex items-center justify-center">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <FileText className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                BRD Agent
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-400 border border-brand-500/30">
                  v1.0
                </span>
              </h1>
              <p className="text-xs text-slate-400">AI Requirements Workspace</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Connection badge */}
            <div
              id="backend-connection-badge"
              className={`flex items-center space-x-2.5 px-3.5 py-1.5 rounded-full text-xs font-medium border transition-all duration-300 ${
                isBackendHealthy === true
                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/30 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]'
                  : isBackendHealthy === false
                  ? 'bg-rose-950/60 text-rose-300 border-rose-500/30 shadow-[0_0_15px_-3px_rgba(244,63,94,0.2)]'
                  : 'bg-slate-900/60 text-slate-400 border-slate-700/50'
              }`}
            >
              <div className="relative flex items-center justify-center">
                <span className={`h-2.5 w-2.5 rounded-full ${
                  isBackendHealthy === true ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                    : isBackendHealthy === false ? 'bg-rose-500' : 'bg-amber-400 animate-pulse'
                }`} />
                {isBackendHealthy === true && <span className="absolute h-4 w-4 rounded-full bg-emerald-400/20 animate-ping" />}
              </div>
              <span className="tracking-wide">
                {isCheckingHealth ? 'Checking...' : isBackendHealthy === true ? 'API Online' : isBackendHealthy === false ? 'Disconnected' : 'Connecting...'}
              </span>
              <button onClick={pingHealth} title="Retry" className="ml-1 text-slate-400 hover:text-white transition-colors p-0.5 rounded">
                <RefreshCw className={`w-3.5 h-3.5 ${isCheckingHealth ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <button
              id="btn-new-project-header"
              onClick={() => setIsCreating(true)}
              className="hidden sm:inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-brand-600 hover:from-cyan-400 hover:to-brand-500 text-white text-xs font-semibold shadow-md shadow-brand-500/20 transition-all active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" />
              New Project
            </button>

            {/* Logged in User Profile & Sign Out */}
            {currentUser && (
              <div className="flex items-center gap-2 pl-3 border-l border-slate-800">
                <div
                  id="user-profile-badge"
                  className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs text-slate-300"
                >
                  <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-500 flex items-center justify-center text-white text-[10px] font-bold">
                    {currentUser.email ? currentUser.email[0].toUpperCase() : 'U'}
                  </div>
                  <span
                    className="max-w-[120px] sm:max-w-[180px] truncate font-medium text-slate-200"
                    title={currentUser.email || ''}
                  >
                    {currentUser.email}
                  </span>
                </div>
                <button
                  id="btn-sign-out"
                  onClick={async () => {
                    await supabase.auth.signOut();
                    showNotification('success', 'Signed out successfully');
                  }}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 border border-transparent hover:border-rose-500/30 transition-all cursor-pointer"
                  title="Sign out of workspace"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ═══════════════════ AUTH MODAL ═══════════════════ */}
      {!isAuthLoading && !currentUser && (
        <AuthModal
          isOpen={true}
          onSuccess={() => {
            showNotification('success', 'Authenticated successfully! Loading workspace...');
            fetchProjects();
          }}
        />
      )}

      {/* ═══════════════════ TOAST ═══════════════════ */}
      {notification && (
        <div
          id="toast-notification"
          className={`fixed top-16 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl border text-sm font-medium shadow-2xl backdrop-blur-md transition-all duration-300 ${
            notification.type === 'success'
              ? 'bg-emerald-950/90 text-emerald-200 border-emerald-500/40'
              : 'bg-rose-950/90 text-rose-200 border-rose-500/40'
          }`}
        >
          {notification.type === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-rose-400" />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* ═══════════════════ MAIN ═══════════════════ */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 z-10 flex flex-col gap-6">
        {/* Offline banner */}
        {isBackendHealthy === false && (
          <div id="connection-warning-banner" className="flex items-center justify-between p-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-200 text-sm">
            <div className="flex items-center gap-3">
              <XCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
              <div>
                <p className="font-semibold text-rose-300">Cannot connect to backend at http://localhost:8000</p>
                {healthError && <p className="text-xs text-rose-300/80 mt-0.5 font-mono">Detail: {healthError}</p>}
                <p className="text-xs text-rose-400/90 mt-0.5">
                  Run: <code className="px-1.5 py-0.5 bg-rose-900/40 rounded text-rose-200 font-mono">uvicorn app.main:app --reload --port 8000</code>
                </p>
              </div>
            </div>
            <button onClick={pingHealth} className="px-3 py-1.5 rounded-lg bg-rose-900/50 hover:bg-rose-800/60 border border-rose-700/50 text-xs font-semibold transition">
              Retry
            </button>
          </div>
        )}

        {/* Stats row */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-4 rounded-xl border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider">Projects</p>
              <h3 className="text-2xl font-bold text-white mt-1">{projects.length}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
              <FolderOpen className="w-5 h-5" />
            </div>
          </div>
          <div className="glass-card p-4 rounded-xl border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider">Active</p>
              <h3 className="text-sm font-semibold text-slate-200 mt-1 truncate max-w-[200px]">
                {selectedProject ? selectedProject.title : 'None Selected'}
              </h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="glass-card p-4 rounded-xl border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 uppercase font-semibold tracking-wider">AI Engine</p>
              <h3 className="text-sm font-semibold text-slate-200 mt-1 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-400" />
                Groq · Llama 3.3 70B
              </h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Cpu className="w-5 h-5" />
            </div>
          </div>
        </section>

        {/* ═══════════════ Two-column layout ═══════════════ */}
        <div id="project-container" className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1">
          {/* ─── Left: Project Sidebar ─── */}
          <aside className="lg:col-span-3 flex flex-col gap-4">
            <div className="glass-panel p-4 rounded-2xl border border-slate-800/80 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Database className="w-4 h-4 text-cyan-400" />
                  Projects
                </h2>
                <button onClick={() => setIsCreating(true)} className="p-1.5 rounded-lg bg-brand-600/20 hover:bg-brand-600/40 text-brand-300 border border-brand-500/30 text-xs font-medium flex items-center gap-1 transition">
                  <Plus className="w-3.5 h-3.5" /> New
                </button>
              </div>

              <div className="flex flex-col gap-2 mt-2 max-h-[600px] overflow-y-auto pr-1">
                {isLoadingProjects ? (
                  <div className="p-8 text-center text-slate-500 text-xs flex flex-col items-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-brand-400" />
                    <span>Loading...</span>
                  </div>
                ) : projects.length === 0 ? (
                  <div className="p-6 text-center text-slate-500 text-xs rounded-xl border border-dashed border-slate-800">
                    No projects yet. Create your first project!
                  </div>
                ) : (
                  projects.map((proj) => {
                    const badge = getStatusBadge(proj.status);
                    const isSelected = selectedProject?.id === proj.id;
                    return (
                      <div
                        key={proj.id}
                        onClick={() => { setSelectedProject(proj); setActiveTab('inputs'); }}
                        className={`p-3 rounded-xl border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-slate-800/80 border-brand-500/50 shadow-md shadow-brand-500/10'
                            : 'bg-slate-900/40 border-slate-800/60 hover:bg-slate-900/80 hover:border-slate-700/80'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-sm font-semibold text-white line-clamp-1">{proj.title}</h4>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border whitespace-nowrap flex items-center gap-1 ${badge.bg}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                            {badge.label}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{proj.idea}</p>
                        <div className="flex items-center justify-between text-[11px] text-slate-500 mt-2.5 pt-2 border-t border-slate-800/60">
                          <span>Rev {proj.input_revision}</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(proj.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </aside>

          {/* ─── Right: Workspace Canvas ─── */}
          <section className="lg:col-span-9 flex flex-col gap-4">
            {selectedProject ? (
              <div id="selected-project-panel" className="glass-panel p-5 rounded-2xl border border-slate-800/80 flex flex-col gap-5">
                {/* Project header bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-xl font-bold text-white tracking-tight">{selectedProject.title}</h2>
                      {(() => {
                        const b = getStatusBadge(selectedProject.status);
                        return (
                          <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full border flex items-center gap-1.5 ${b.bg}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${b.dot}`} />
                            {b.label}
                          </span>
                        );
                      })()}
                    </div>
                    <p className="text-xs text-slate-400 mt-1 font-mono">
                      ID: {selectedProject.id} • Rev {selectedProject.input_revision}
                    </p>
                  </div>
                  <button
                    id="btn-analyze-project"
                    onClick={handleAnalyze}
                    disabled={isAnalyzing}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-brand-500/20 flex items-center gap-2 transition disabled:opacity-50"
                  >
                    {isAnalyzing ? (
                      <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Analyzing...</>
                    ) : (
                      <><Sparkles className="w-3.5 h-3.5 text-cyan-300" /> Run Analysis</>
                    )}
                  </button>
                </div>

                {/* ─── Workspace Tabs ─── */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
                  {tabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={`flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-lg border whitespace-nowrap transition ${
                        activeTab === tab.key
                          ? 'bg-brand-600/20 border-brand-500/40 text-brand-300'
                          : 'bg-slate-900/40 border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-600'
                      }`}
                    >
                      {tab.icon}
                      {tab.label}
                      {tab.badge !== undefined && tab.badge > 0 && (
                        <span className="ml-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-brand-500/20 text-brand-400 border border-brand-500/30 min-w-[18px] text-center">
                          {tab.badge}
                        </span>
                      )}
                    </button>
                  ))}
                </div>

                {/* ─── Tab Content ─── */}
                <div className="min-h-[300px]">
                  {/* Tab 1: Inputs & Sources */}
                  {activeTab === 'inputs' && (
                    <div className="flex flex-col gap-5">
                      <div>
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Business Idea
                        </h3>
                        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 text-sm text-slate-300 leading-relaxed">
                          {selectedProject.idea}
                        </div>
                      </div>
                      <div>
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                          Source Documents
                        </h3>
                        <DocumentUploader
                          projectId={selectedProject.id}
                          onUploadComplete={() => {
                            showNotification('success', 'Document uploaded and parsed successfully!');
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Tab 2: Analysis & Requirements */}
                  {activeTab === 'analysis' && (
                    <div className="flex flex-col gap-5">
                      {requirements.length === 0 && !isAnalyzing ? (
                        <div className="p-8 text-center rounded-xl border border-dashed border-slate-800 flex flex-col items-center gap-3">
                          <Table2 className="w-10 h-10 text-slate-600" />
                          <div>
                            <p className="text-sm font-medium text-slate-400">No Requirements Yet</p>
                            <p className="text-xs text-slate-600 mt-1 max-w-md">
                              Click "Run Analysis" above to extract structured requirements from the business idea and uploaded source documents.
                            </p>
                          </div>
                        </div>
                      ) : isAnalyzing ? (
                        <div className="p-8 text-center flex flex-col items-center gap-3">
                          <RefreshCw className="w-8 h-8 text-brand-400 animate-spin" />
                          <p className="text-sm font-medium text-slate-300">AI is analyzing your project...</p>
                          <p className="text-xs text-slate-500">Extracting requirements, detecting gaps, validating completeness</p>
                        </div>
                      ) : (
                        <RequirementsTable requirements={requirements} />
                      )}
                    </div>
                  )}

                  {/* Tab 3: Clarification & Assumptions */}
                  {activeTab === 'clarification' && (
                    <div className="flex flex-col gap-6">
                      <div>
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <MessageCircleQuestion className="w-4 h-4 text-violet-400" />
                          Clarification Questions
                          {openQuestions.length > 0 && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-violet-500/15 text-violet-400 border border-violet-500/25">
                              {openQuestions.length} open
                            </span>
                          )}
                        </h3>
                        <ClarificationQuestions
                          projectId={selectedProject.id}
                          onAnswersSubmitted={handleAnswersSubmitted}
                        />
                      </div>

                      <div className="border-t border-slate-800/80 pt-5">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-amber-400" />
                          Assumptions
                          {proposedCount > 0 && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25">
                              {proposedCount} pending
                            </span>
                          )}
                        </h3>
                        <AssumptionReview
                          projectId={selectedProject.id}
                          onDecisionMade={() => {
                            loadProjectData(selectedProject.id);
                            showNotification('success', 'Assumption decision recorded.');
                          }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Tab 4: Final BRD & Export */}
                  {activeTab === 'brd' && (
                    <BRDViewer
                      project={selectedProject}
                      onProjectUpdated={(updated) => {
                        updateProject(updated);
                        showNotification('success', 'BRD generated successfully!');
                      }}
                    />
                  )}
                </div>
              </div>
            ) : (
              /* No project selected */
              <div className="glass-panel p-12 rounded-2xl border border-slate-800/80 text-center flex flex-col items-center justify-center gap-4">
                <FileText className="w-12 h-12 text-slate-600" />
                <div>
                  <h3 className="text-base font-semibold text-slate-300">No Project Selected</h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm">
                    Select a project from the sidebar or create a new one to start building requirements.
                  </p>
                </div>
                <button
                  onClick={() => setIsCreating(true)}
                  className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md transition"
                >
                  Create Project
                </button>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* ═══════════════════ MODAL: New Project ═══════════════════ */}
      {isCreating && (
        <div id="modal-create-project" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-panel w-full max-w-lg p-6 rounded-2xl border border-slate-700/80 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                Initialize BRD Project
              </h3>
              <button onClick={() => setIsCreating(false)} className="text-slate-400 hover:text-white p-1 rounded-lg">✕</button>
            </div>

            <form onSubmit={handleCreateProject} className="flex flex-col gap-4 mt-4">
              <div>
                <label htmlFor="project-title" className="block text-xs font-semibold text-slate-300 mb-1">
                  Project Title (Optional)
                </label>
                <input
                  id="project-title"
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g., Enterprise Procurement Portal"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-brand-500 transition"
                />
              </div>
              <div>
                <label htmlFor="project-idea" className="block text-xs font-semibold text-slate-300 mb-1">
                  Business Idea & Core Requirements *
                </label>
                <textarea
                  id="project-idea"
                  rows={5}
                  value={newIdea}
                  onChange={(e) => setNewIdea(e.target.value)}
                  placeholder="Describe the product vision, users, pain points, features, integrations (min 10 chars)..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-brand-500 transition resize-none"
                  required
                />
              </div>
              {createError && (
                <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  <span>{createError}</span>
                </div>
              )}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button type="button" onClick={() => setIsCreating(false)} className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-cyan-600 hover:from-brand-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-md shadow-brand-500/20 flex items-center gap-2 transition disabled:opacity-50"
                >
                  {isSubmitting ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Creating...</> : <><Plus className="w-3.5 h-3.5" /> Create Project</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
