import React, { useState, useEffect } from 'react';
import {
  User,
  Briefcase,
  Mail,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Shield,
  Sparkles,
} from 'lucide-react';
import { updateUserProfile } from '../api/projects';
import type { UserProfileResponse } from '../types';

interface UserProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentProfile: UserProfileResponse | null;
  currentUserEmail?: string | null;
  onProfileUpdated: (updated: UserProfileResponse) => void;
}

export default function UserProfileModal({
  isOpen,
  onClose,
  currentProfile,
  currentUserEmail,
  onProfileUpdated,
}: UserProfileModalProps) {
  const [fullName, setFullName] = useState('');
  const [roleTitle, setRoleTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFullName(currentProfile?.full_name || '');
      setRoleTitle(currentProfile?.role_title || '');
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  }, [isOpen, currentProfile]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const updated = await updateUserProfile({
        full_name: fullName.trim() || undefined,
        role_title: roleTitle.trim() || undefined,
      });
      setSuccessMessage('Profile updated successfully!');
      onProfileUpdated(updated);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update profile.');
    } finally {
      setIsSaving(false);
    }
  };

  const emailDisplay = currentProfile?.email || currentUserEmail || 'user@example.com';
  const initialLetter = fullName.trim()
    ? fullName.trim()[0].toUpperCase()
    : emailDisplay[0].toUpperCase();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative w-full max-w-md rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl shadow-cyan-500/10 overflow-hidden flex flex-col">
        {/* Glow accent */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-500 via-brand-500 to-indigo-500" />

        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-brand-500/20">
              {initialLetter}
            </div>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                Profile Settings
                <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              </h3>
              <p className="text-xs text-slate-400">
                Update your identity & collaborative role
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMessage && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Email (Read-only) */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-3 w-4 h-4 text-slate-500" />
              <input
                type="email"
                disabled
                value={emailDisplay}
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 text-slate-400 text-sm cursor-not-allowed select-none font-mono"
              />
              <Shield className="absolute right-3.5 top-3 w-4 h-4 text-slate-600" />
            </div>
            <p className="text-[11px] text-slate-500">
              Account email authenticated via Supabase Auth
            </p>
          </div>

          {/* Full Name */}
          <div className="space-y-1.5">
            <label
              htmlFor="profile-full-name"
              className="block text-xs font-semibold text-slate-300 uppercase tracking-wider"
            >
              Full Name
            </label>
            <div className="relative">
              <User className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
              <input
                id="profile-full-name"
                type="text"
                placeholder="e.g. Alex Morgan"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                maxLength={80}
                className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700/80 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 placeholder-slate-500 transition"
              />
            </div>
          </div>

          {/* Role Title */}
          <div className="space-y-1.5">
            <label
              htmlFor="profile-role-title"
              className="block text-xs font-semibold text-slate-300 uppercase tracking-wider"
            >
              Professional Role Title
            </label>
            <div className="relative">
              <Briefcase className="absolute left-3.5 top-3 w-4 h-4 text-slate-400" />
              <input
                id="profile-role-title"
                type="text"
                placeholder="e.g. Product Manager, Systems Architect"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                maxLength={60}
                className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700/80 text-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 placeholder-slate-500 transition"
              />
            </div>
            <p className="text-[11px] text-slate-500">
              Visible to teammates during multi-user clarification chat
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              id="btn-save-profile"
              type="submit"
              disabled={isSaving}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-brand-600 hover:from-cyan-400 hover:to-brand-500 text-white text-xs font-semibold shadow-md shadow-brand-500/20 flex items-center gap-2 transition disabled:opacity-50"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
