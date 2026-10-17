import React, { useState } from 'react';
import { useApp } from '@/context/AppContext';
import { Loader2, Plus, Sparkles, X } from 'lucide-react';
import { toast } from 'sonner';

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CreateProjectModal({ isOpen, onClose }: CreateProjectModalProps) {
  const { createProject } = useApp();
  const [title, setTitle] = useState('');
  const [idea, setIdea] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) {
      toast.error('Please enter a business idea or description.');
      return;
    }

    setSubmitting(true);
    try {
      await createProject(title.trim() || undefined, idea.trim());
      setTitle('');
      setIdea('');
      onClose();
    } catch (err: any) {
      toast.error(err.message || 'Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-foreground/30 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-foreground">Create New BRD Project</h2>
              <p className="text-[12px] text-muted-foreground">Describe your business initiative or product vision</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-[12.5px] font-medium text-foreground mb-1">
              Project Title <span className="text-muted-foreground">(Optional)</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Telehealth Video Consultation Platform"
              className="w-full rounded-md border border-input bg-card px-3 py-2 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-[12.5px] font-medium text-foreground mb-1">
              Business Idea &amp; Scope <span className="text-destructive">*</span>
            </label>
            <textarea
              rows={5}
              required
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="Describe the target users, core business problems, key workflows, regulatory requirements, and technical constraints..."
              className="w-full rounded-md border border-input bg-card p-3 text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-md border border-border px-3.5 py-2 text-[12.5px] font-medium text-muted-foreground hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Creating Project...
                </>
              ) : (
                <>
                  <Plus className="h-3.5 w-3.5" />
                  Create Project
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
