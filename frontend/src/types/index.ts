/**
 * TypeScript domain models and API schemas for the BRD Agent.
 * Synchronized with FastAPI schemas in backend/app/api/schemas_api.py
 * and domain models in backend/app/models/.
 */

export type ProjectStatus =
  | 'DRAFT'
  | 'ANALYZING'
  | 'AWAITING_CLARIFICATION'
  | 'READY_TO_GENERATE'
  | 'GENERATING'
  | 'GENERATED'
  | 'COMPLETED'
  | 'FAILED';

export interface Project {
  id: string;
  title: string;
  idea: string;
  status: ProjectStatus;
  input_revision: number;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
  owner_id?: string | null;
  owner_email?: string | null;
}

export type RequirementType = 'functional' | 'nonfunctional' | 'business' | 'constraint';
export type RequirementPriority = 'MUST' | 'SHOULD' | 'COULD' | 'WONT';

export interface Requirement {
  id: string;
  type: RequirementType;
  title: string;
  statement: string;
  actor?: string | null;
  outcome?: string | null;
  priority: RequirementPriority;
  acceptance_criteria: string[];
  trace_refs: string[];
  confidence: number;
  source_chunk_ids?: string[];
  rationale?: string | null;
}

export type AnswerFormat = 'TEXT' | 'CHOICE' | 'DATE' | 'NUMBER' | 'YES_NO';
export type QuestionStatus = 'open' | 'answered' | 'skipped';

export interface Question {
  id: string;
  project_id: string;
  field_path: string;
  question_text: string;
  why_it_matters: string;
  answer_format: AnswerFormat;
  options?: string[] | null;
  impact: number;
  gap_confidence: number;
  priority: number;
  status: QuestionStatus;
  created_at?: string;
}

export type ImpactLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type AssumptionStatus = 'PROPOSED' | 'ACCEPTED' | 'REJECTED' | 'SUPERSEDED';

export interface Assumption {
  id: string;
  project_id: string;
  statement: string;
  rationale: string;
  impact: ImpactLevel;
  status: AssumptionStatus;
  linked_requirement_ids: string[];
  reviewed_by?: string | null;
  reviewer_email?: string | null;
  reviewed_at?: string | null;
}

export interface BRDVersion {
  id: string;
  project_id: string;
  version_number: number;
  title: string;
  content_json: Record<string, any>;
  status: string;
  created_at?: string | null;
}

export interface SourceDocument {
  id: string;
  project_id: string;
  filename: string;
  file_type: 'pdf' | 'docx' | 'txt' | 'image' | string;
  file_size_bytes?: number | null;
  status: string;
  chunk_count: number;
  created_at?: string | null;
  uploaded_by?: string | null;
  uploader_email?: string | null;
}

export interface ValidationIssue {
  code: string;
  severity: 'blocker' | 'warning';
  field_path: string;
  entity_id?: string | null;
  message: string;
}

export interface ValidationResult {
  issues: ValidationIssue[];
}

export interface ProjectDetailResponse {
  project: Project;
  requirement_count: number;
  open_question_count: number;
  assumption_count: number;
}

export interface CreateProjectResponse {
  project: Project;
}

export interface SourceDocumentListResponse {
  items: SourceDocument[];
}

export interface AnalyzeResponse {
  project: Project;
  requirements: Requirement[];
  validation_result: ValidationResult;
  open_questions: Question[];
  assumptions: Assumption[];
  next_status: ProjectStatus;
}

export interface AnswerSubmissionItem {
  question_id: string;
  value: string;
}

export interface SubmitAnswersRequest {
  answers: AnswerSubmissionItem[];
}

export interface SubmitAnswersResponse {
  project: Project;
  requirements: Requirement[];
  validation_result: ValidationResult;
  open_questions: Question[];
  assumptions: Assumption[];
  next_status: ProjectStatus;
}

export interface BRDGenerateResponse {
  project: Project;
  brd_version: BRDVersion;
  download_url: string;
}

export interface HealthResponse {
  status: string;
}
