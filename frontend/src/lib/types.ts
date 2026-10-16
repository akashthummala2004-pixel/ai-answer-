export type Verdict = 'supported' | 'contradicted' | 'unsupported' | 'uncertain';
export type Engine = 'auto' | 'live' | 'offline';
export type EngineUsed = 'live' | 'offline-heuristic';

export const VERDICTS: Verdict[] = ['supported', 'contradicted', 'uncertain', 'unsupported'];

export interface Health {
  status: string;
  app: string;
  ai_mode: 'live' | 'offline';
  storage: 'supabase' | 'local';
  auth_required: boolean;
  default_model: string;
  models: string[];
  vision_supported: boolean | null;
  web_search: boolean;
}

export interface EvidenceInput {
  title: string;
  content: string;
  source_url?: string;
}

export interface Evidence extends EvidenceInput {
  id: string;
}

export interface EvidenceMatch {
  evidence_id: string;
  evidence_title: string;
  quote: string;
  quote_verified: boolean;
  quote_match?: 'exact' | 'near' | 'not_found';
}

export interface ClaimReview {
  verdict: Verdict;
  note: string;
  reviewer: string | null;
  reviewed_at: string;
}

export interface Claim {
  id: string;
  text: string;
  verdict: Verdict;
  confidence: number;
  explanation: string;
  evidence: EvidenceMatch[];
  review: ClaimReview | null;
}

export interface Summary {
  total_claims: number;
  counts: Record<Verdict, number>;
  reliability_score: number | null;
  reviewed_claims: number;
  needs_review: number;
}

export type Status = 'needs_review' | 'reviewed' | 'complete';

export interface VerificationListItem {
  id: string;
  created_at: string;
  title: string;
  engine_used: EngineUsed;
  model: string | null;
  status: Status;
  summary: Summary | SmartSummary;
  fallback_reason: string | null;
  is_sample: boolean;
  version: 1 | 2;
  content_type?: ContentType;
  input_kinds?: InputKind[];
}

export interface Verification extends VerificationListItem {
  version: 1;
  summary: Summary;
  question: string | null;
  answer: string;
  evidence: Evidence[];
  engine_requested: Engine;
  claims: Claim[];
  duration_ms: number;
  verified_at: string;
}

export interface Stats {
  total_verifications: number;
  smart_verifications: number;
  last_7_days: number;
  total_claims: number;
  assessment_counts: Record<Assessment, number>;
  verdict_counts: Record<Verdict, number>;
  pending_reviews: number;
  reviewed_claims: number;
  last_verification_at: string | null;
}

export interface QueueItem {
  verification_id: string;
  verification_title: string;
  version: 1 | 2;
  engine_used: EngineUsed;
  created_at: string;
  claim: Claim | SmartClaim;
}

// ---- Smart Verification (version 2) ---------------------------------------------------------
export type Assessment = 'supported_by_evidence' | 'contradicted_by_evidence' | 'not_independently_verified' | 'requires_human_review';
export const ASSESSMENTS: Assessment[] = ['supported_by_evidence', 'contradicted_by_evidence', 'requires_human_review', 'not_independently_verified'];
export type RiskLevel = 'low' | 'moderate' | 'elevated' | 'high';
export type ContentType = 'ai_answer' | 'email' | 'business_message' | 'document' | 'screenshot' | 'web_content' | 'other';
export type InputKind = 'text' | 'pdf' | 'scanned_pdf' | 'image';

export interface SmartInput {
  id: string;
  kind: InputKind;
  name: string;
  mime: string;
  size: number;
  pages: number | null;
  chars: number;
  images_sent: number;
  notes: string[];
}

export interface SmartEvidence {
  input_id: string;
  label: string;
  quote: string;
  match: 'exact' | 'near';
}

export interface SmartClaim {
  id: string;
  text: string;
  source: string | null;
  assessment: Assessment;
  explanation: string;
  evidence: SmartEvidence[];
  review: { verdict: Assessment; note: string; reviewer: string | null; reviewed_at: string } | null;
}

export interface SmartSummary {
  total_claims: number;
  counts: Record<Assessment, number>;
  risk_level: RiskLevel;
  risk_count: number;
  reviewed_claims: number;
  needs_review: number;
  reliability_score: null;
}

export interface SmartAnalysis {
  title: string;
  content_type: ContentType;
  summary: string;
  overall_assessment: string;
  risk_level: RiskLevel;
  key_findings: { label: string; detail: string; source: string | null }[];
  detected_details: { type: string; value: string; source: string }[];
  risks: { title: string; detail: string; severity: 'low' | 'medium' | 'high'; source: string | null }[];
  next_steps: string[];
}

export interface SmartVerification {
  id: string;
  created_at: string;
  updated_at: string;
  version: 2;
  title: string;
  inputs: SmartInput[];
  submitted_text: string | null;
  analysis: SmartAnalysis;
  claims: SmartClaim[];
  limitations: string[];
  engine_used: 'live';
  model: string;
  duration_ms: number;
  verified_at: string;
  status: Status;
  summary: SmartSummary;
  is_sample: boolean;
}
