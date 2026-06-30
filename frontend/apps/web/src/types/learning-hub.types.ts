/**
 * PATHS — Candidate Learning Hub types.
 *
 * Mirrors the backend `LearningHubResponse` contract served by
 * GET /api/v1/candidates/{id}/learning-hub.
 */

export type RecommendationType = "role" | "skill" | "project" | "best_practice";
export type RecommendationPriority = "high" | "medium" | "low";
export type RecommendationDifficulty = "beginner" | "intermediate" | "advanced";

export interface LearningRecommendation {
  id: string;
  title: string;
  type: RecommendationType;
  priority: RecommendationPriority;
  difficulty: RecommendationDifficulty;
  /** 0..1 personalisation score from the recommendation engine. */
  score: number;
  /** Plain-language explanation of why this item was recommended. */
  reason: string;
  relatedSkills: string[];
  /** External roadmap.sh link. */
  url: string;
}

export interface LearningHubSummary {
  recommendedRole: string | null;
  topSkillGap: string | null;
  recommendedProjectLevel: string;
  totalRecommendations: number;
}

export interface TargetOption {
  id: string;
  label: string;
}

export interface LearningHubResponse {
  candidateId: string;
  candidateName: string;
  currentPosition: string | null;
  targetRole: string | null;
  /** Role id currently driving recommendations (chosen or auto-detected). */
  targetRoleId: string | null;
  /** Roles the candidate can pick as their learning target. */
  availableTargets: TargetOption[];
  summary: LearningHubSummary;
  recommendations: LearningRecommendation[];
}
