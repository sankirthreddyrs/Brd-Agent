/**
 * BRD Service Bridge for Lovable UI
 * Connects the Lovable Dashboard components to the verified FastAPI backend and Supabase Auth.
 */

import { apiClient, API_BASE_URL } from '@/api/client';
import { supabase } from '@/api/supabase';
import * as api from '@/api/projects';
import type {
  Project as BackendProject,
  Requirement as BackendRequirement,
  SourceDocument,
  Question,
  Assumption,
  BRDGenerateResponse,
  BRDVersion,
  AnswerSubmissionItem,
} from '@/types';

export type Validation = "Validated" | "Pending" | "Failed";

export interface Requirement {
  id: string;
  name: string;
  type: string;
  source: string;
  validation: Validation;
  added: string;
}

export interface ActivityItem {
  initials: string;
  title: string;
  body: string;
  time: string;
}

export interface NotificationItem {
  title: string;
  time: string;
}

// Re-export core backend API client and base URL for consumers
export { apiClient, API_BASE_URL, supabase };

// ─── Direct Backend Route Mappings ──────────────────────────────

/**
 * Projects: GET /projects
 */
export async function getProjects(limit: number = 20): Promise<BackendProject[]> {
  return api.getProjects(limit);
}

/**
 * Projects: GET /projects/{id}
 */
export async function getProjectDetail(projectId: string) {
  return api.getProjectDetail(projectId);
}

/**
 * Projects: POST /projects
 */
export async function createProject(title: string | undefined, idea: string) {
  return api.createProject(title, idea);
}

/**
 * Source Upload: POST /projects/{id}/sources (supports PDF, DOCX, TXT, Images)
 */
export async function uploadSourceFile(projectId: string, file: File): Promise<SourceDocument> {
  return api.uploadSourceFile(projectId, file);
}

/**
 * Sources: GET /projects/{id}/sources
 */
export async function getSourceDocuments(projectId: string): Promise<SourceDocument[]> {
  return api.getSourceFiles(projectId);
}

export async function getSourceFiles(projectId: string): Promise<SourceDocument[]> {
  return api.getSourceFiles(projectId);
}

/**
 * Analysis: POST /projects/{id}/analyze
 */
export async function analyzeProject(projectId: string) {
  return api.analyzeProject(projectId);
}

/**
 * Questions: GET /projects/{id}/questions
 */
export async function getQuestions(projectId: string): Promise<Question[]> {
  return api.getQuestions(projectId);
}

/**
 * Questions: POST /projects/{id}/answers
 */
export async function submitAnswers(
  projectId: string,
  answers: (AnswerSubmissionItem | { question_id: string; answer_text: string })[]
) {
  const normalized: AnswerSubmissionItem[] = answers.map((a) => ({
    question_id: a.question_id,
    value: "value" in a ? a.value : a.answer_text,
  }));
  return api.submitAnswers(projectId, normalized);
}

/**
 * Assumptions: GET /projects/{id}/assumptions
 */
export async function getAssumptions(projectId: string): Promise<Assumption[]> {
  return api.getAssumptions(projectId);
}

/**
 * Assumptions: POST /projects/{id}/assumptions/{id}/decision
 */
export async function decideAssumption(
  projectId: string,
  assumptionId: string,
  decision: "accepted" | "rejected" | "ACCEPTED" | "REJECTED"
) {
  const dec = decision.toLowerCase() as "accepted" | "rejected";
  return api.decideAssumption(projectId, assumptionId, dec);
}

/**
 * Generation: POST /projects/{id}/generate
 */
export async function generateBRD(projectId: string): Promise<BRDGenerateResponse> {
  return api.generateBRD(projectId);
}

/**
 * BRD Retrieval: GET /projects/{id}/brd
 */
export async function getBRD(projectId: string): Promise<BRDVersion> {
  return api.getBRD(projectId);
}

/**
 * BRD Document Download: GET /projects/{id}/brd/download
 */
export async function downloadBRD(projectId: string, filename?: string): Promise<void> {
  return api.downloadBRDDocx(projectId, filename);
}

export function getBRDDownloadUrl(projectId: string): string {
  return api.getBRDDownloadUrl(projectId);
}

/**
 * Requirements: GET /projects/{id}/requirements
 */
export async function getRequirements(projectId: string): Promise<BackendRequirement[]> {
  return api.getRequirements(projectId);
}

// ─── Shared Types & Fallback Defaults ────────────────────────

export const emptyProject = {
  id: "",
  name: "No project selected",
  status: "IDLE",
  meta: [] as [string, string][],
};

export const defaultFindings: string[] = [];
export const defaultActivity: ActivityItem[] = [];
export const defaultNotifications: NotificationItem[] = [];

/**
 * Execute AI validation on active project
 */
export const runValidation = async (projectId?: string): Promise<void> => {
  if (projectId) {
    await api.analyzeProject(projectId);
  }
};

