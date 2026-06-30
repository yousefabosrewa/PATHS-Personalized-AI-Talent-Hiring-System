"""PATHS Assessment Agent service (fix5.md).

Generates job-level assessment drafts. The agent uses the existing
:pyfunc:`app.services.llm.openrouter_client.generate_json_response`
abstraction so the same free-model fallback chain is reused. Every
assessment type has its own schema and instruction block, and every
generated question gets ``agent_reason`` + ``measures`` + (when
applicable) ``mapped_job_requirements`` so HR can see why the agent
chose it.

If the agent fails we return a deterministic, clearly-labelled fallback
draft so the UI never crashes; the caller persists it with
``agent_metadata.used_fallback = True`` so HR knows to regenerate.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from app.db.models.job import Job
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

logger = logging.getLogger(__name__)


# ── Public types ─────────────────────────────────────────────────────────────


AssessmentType = Literal[
    "technical_assessment",
    "hr_assessment",
    "iq_test",
    "problem_solving_coding",
    "problem_solving_thinking",
    "quiz",
]


ASSESSMENT_TYPES: tuple[AssessmentType, ...] = (
    "technical_assessment",
    "hr_assessment",
    "iq_test",
    "problem_solving_coding",
    "problem_solving_thinking",
    "quiz",
)

ASSESSMENT_TYPE_LABELS: dict[str, str] = {
    "technical_assessment":      "Technical Assessment",
    "hr_assessment":             "HR Assessment",
    "iq_test":                   "IQ Test",
    "problem_solving_coding":    "Problem Solving: Coding",
    "problem_solving_thinking":  "Problem Solving: Thinking",
    "quiz":                      "Quiz",
}


_VALID_DIFFICULTIES = ("junior", "intermediate", "senior", "expert")


# ── Per-type schemas ────────────────────────────────────────────────────────


_TECHNICAL_SCHEMA = """{
  "title": "<short assessment title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int, usually 100>,
  "questions": [
    {
      "question": "<concrete role-specific question>",
      "type": "technical_written",
      "difficulty": "junior|intermediate|senior|expert",
      "estimated_time_minutes": <int>,
      "score": <int>,
      "expected_answer": "<what a strong answer covers>",
      "rubric": [
        { "criterion": "<criterion>", "points": <int> }
      ],
      "agent_reason": "<one sentence on why this question>",
      "measures": ["<skill>", ...],
      "mapped_job_requirements": ["<requirement>", ...]
    }, ...
  ]
}"""


_HR_SCHEMA = """{
  "title": "<short title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int>,
  "questions": [
    {
      "question": "<behavioural / cultural question>",
      "type": "hr_behavioural",
      "competency_measured": "<one competency>",
      "score": <int>,
      "rubric": [
        { "criterion": "<criterion>", "points": <int> }
      ],
      "strong_answer_indicators": ["<bullet>", ...],
      "weak_answer_indicators":   ["<bullet>", ...],
      "agent_reason": "<one sentence>"
    }, ...
  ]
}"""


_IQ_SCHEMA = """{
  "title": "<short title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int>,
  "questions": [
    {
      "question": "<cognitive question>",
      "type": "iq_mcq|iq_numeric|iq_pattern|iq_verbal",
      "options": ["<a>", "<b>", "<c>", "<d>"],
      "correct_answer": "<exact match of one option, or a number/string>",
      "explanation": "<why this is correct>",
      "skill_measured": "<reasoning type>",
      "difficulty": "junior|intermediate|senior|expert",
      "score": <int>,
      "agent_reason": "<one sentence>"
    }, ...
  ]
}"""


_CODING_SCHEMA = """{
  "title": "<short title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int>,
  "questions": [
    {
      "question": "<problem statement>",
      "type": "coding_problem",
      "difficulty": "junior|intermediate|senior|expert",
      "score": <int>,
      "input_output_examples": [
        { "input": "<sample input>", "output": "<expected output>" }
      ],
      "constraints": ["<bullet>", ...],
      "expected_solution_approach": "<high-level approach>",
      "hidden_test_ideas": ["<bullet>", ...],
      "rubric": [
        { "criterion": "<criterion>", "points": <int> }
      ],
      "agent_reason": "<one sentence>",
      "measures": ["<skill>", ...],
      "mapped_job_requirements": ["<requirement>", ...]
    }, ...
  ]
}"""


_THINKING_SCHEMA = """{
  "title": "<short title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int>,
  "questions": [
    {
      "scenario": "<real-world scenario relevant to the role>",
      "question": "<the task / question to answer>",
      "type": "thinking_scenario",
      "difficulty": "junior|intermediate|senior|expert",
      "score": <int>,
      "expected_reasoning_path": ["<step>", ...],
      "rubric": [
        { "criterion": "<criterion>", "points": <int> }
      ],
      "agent_reason": "<one sentence>",
      "measures": ["<skill>", ...],
      "mapped_job_requirements": ["<requirement>", ...]
    }, ...
  ]
}"""


_QUIZ_SCHEMA = """{
  "title": "<short title>",
  "description": "<2 sentence overview>",
  "duration_minutes": <int>,
  "total_score": <int>,
  "questions": [
    {
      "question": "<quiz question>",
      "type": "mcq|true_false|short_answer|multi_select",
      "options": ["<a>", "<b>", ...],
      "correct_answer": "<exact match(es)>",
      "explanation": "<why this is correct>",
      "skill_measured": "<topic>",
      "difficulty": "junior|intermediate|senior|expert",
      "score": <int>,
      "agent_reason": "<one sentence>"
    }, ...
  ]
}"""


_SCHEMAS: dict[AssessmentType, str] = {
    "technical_assessment":     _TECHNICAL_SCHEMA,
    "hr_assessment":            _HR_SCHEMA,
    "iq_test":                  _IQ_SCHEMA,
    "problem_solving_coding":   _CODING_SCHEMA,
    "problem_solving_thinking": _THINKING_SCHEMA,
    "quiz":                     _QUIZ_SCHEMA,
}


_TYPE_INSTRUCTIONS: dict[AssessmentType, str] = {
    "technical_assessment": (
        "Generate a job-relevant technical assessment that tests the must-have "
        "skills for this role. Each question must be realistic, gradable, and "
        "include a rubric. Avoid leetcode trivia unless the role explicitly "
        "requires algorithms — prefer real-world API design, system design, "
        "data modelling, and debugging. Map each question to one or more of "
        "the job's required skills or responsibilities."
    ),
    "hr_assessment": (
        "Generate behavioural / cultural-fit questions strictly from the HR "
        "instructions, company values, role-specific competencies, or "
        "uploaded HR material provided below. NEVER ask about protected "
        "attributes (gender, age, religion, race, marital status, "
        "disability, nationality, political affiliation). NEVER invent "
        "competencies the HR user did not request. If no HR guidance is "
        "available, fall back to widely-accepted behavioural competencies "
        "such as ownership, communication, and prioritisation."
    ),
    "iq_test": (
        "Generate cognitive reasoning questions suitable for professional "
        "recruitment. Mix pattern recognition, numerical reasoning, logical "
        "reasoning, and verbal reasoning. Avoid childish riddles. Every "
        "question must have an unambiguous correct answer and a short "
        "explanation."
    ),
    "problem_solving_coding": (
        "Generate practical coding problems closely tied to the role. Each "
        "problem includes a clear statement, input/output examples where "
        "applicable, constraints, a high-level expected approach, and a few "
        "hidden test ideas. Avoid pure leetcode unless the role explicitly "
        "needs algorithm work."
    ),
    "problem_solving_thinking": (
        "Generate scenario-based reasoning problems testing structured "
        "thinking, debugging mindset, system-design reasoning, or analytical "
        "decision-making relevant to the role. Each question includes a "
        "scenario, a precise question, an expected reasoning path, and a "
        "rubric."
    ),
    "quiz": (
        "Generate a clean quiz that mixes MCQ, true/false, short answer and "
        "multi-select where appropriate. Tie every question to the job "
        "requirements, HR instructions, or the uploaded reference material. "
        "Each question must have an unambiguous correct answer."
    ),
}


_SYSTEM_PROMPT = (
    "You are the PATHS Assessment Generation Agent.\n\n"
    "You generate JOB-LEVEL assessments that HR will review as drafts "
    "before any candidate sees them.\n\n"
    "Rules:\n"
    "  • Never produce questions that target protected attributes (gender, "
    "race, age, religion, marital status, disability, nationality, political "
    "affiliation).\n"
    "  • Never invent skills, technologies, employers, or requirements that "
    "are not visible in the provided context.\n"
    "  • Avoid vague, duplicate, unmeasurable, or generic motivational "
    "questions in technical / coding / IQ assessments.\n"
    "  • Every question must be unambiguous and gradable.\n"
    "  • Output ONLY a single JSON object that matches the requested schema; "
    "no Markdown, no preamble, no trailing prose."
)


# ── Context builder ─────────────────────────────────────────────────────────


def _job_context(job: Job) -> dict[str, Any]:
    """Anonymized but rich job context for the agent."""
    return {
        "title":            getattr(job, "title", "") or "",
        "seniority_level":  getattr(job, "seniority_level", "") or "",
        "department":       getattr(job, "department", "") or "",
        "workplace_type":   getattr(job, "workplace_type", "") or "",
        "summary":          (getattr(job, "summary", "") or "")[:800],
        "description":      (getattr(job, "description_text", "") or "")[:2000],
        "requirements":     (getattr(job, "requirements", "") or "")[:1500],
        "required_skills":  list(getattr(job, "required_skills", None) or [])[:30],
        "nice_to_have":     list(getattr(job, "nice_to_have_skills", None) or [])[:30],
        "responsibilities": (getattr(job, "responsibilities", "") or "")[:1500],
    }


# ── Main entry point ────────────────────────────────────────────────────────


def generate_assessment_draft(
    *,
    job: Job,
    assessment_type: str,
    difficulty: str | None = None,
    question_count: int | None = None,
    duration_minutes: int | None = None,
    hr_instructions: str | None = None,
    source_file_text: str | None = None,
    source_file_name: str | None = None,
) -> dict[str, Any]:
    """Return a draft dict — never raises, but flags ``used_fallback=True``
    when the agent could not produce valid JSON.

    The shape mirrors the per-type schema with these additions:

      * ``title``, ``description``, ``duration_minutes``, ``total_score``
      * ``questions``: list of per-type question objects
      * ``agent_metadata``: ``{used_fallback, model_chain, reason, ...}``
    """
    if assessment_type not in ASSESSMENT_TYPES:
        raise ValueError(f"unknown_assessment_type: {assessment_type}")
    if difficulty and difficulty not in _VALID_DIFFICULTIES:
        raise ValueError(f"invalid_difficulty: {difficulty}")

    diff = (difficulty or "intermediate").strip()
    qc = max(1, min(int(question_count or _default_question_count(assessment_type)), 25))
    dur = max(5, min(int(duration_minutes or _default_duration(assessment_type)), 240))

    job_block = _job_context(job)
    type_label = ASSESSMENT_TYPE_LABELS[assessment_type]  # type: ignore[index]

    parts: list[str] = [
        f"Assessment type: {type_label}",
        f"Difficulty: {diff}",
        f"Target number of questions: {qc}",
        f"Target total duration (minutes): {dur}",
        "",
        f"Type-specific instructions:\n{_TYPE_INSTRUCTIONS[assessment_type]}",  # type: ignore[index]
        "",
        f"Job context (JSON):\n{job_block}",
    ]
    if hr_instructions and hr_instructions.strip():
        parts.append(f"\nHR custom instructions:\n{hr_instructions.strip()[:2000]}")
    if source_file_text and source_file_text.strip():
        parts.append(
            f"\nReference material from uploaded file"
            f"{' (' + source_file_name + ')' if source_file_name else ''}:\n"
            f"{source_file_text.strip()[:6000]}"
        )

    parts.append(
        "\nReturn ONLY a JSON object matching this schema:\n"
        + _SCHEMAS[assessment_type]  # type: ignore[index]
    )

    user_prompt = "\n".join(parts)

    try:
        payload = generate_json_response(
            _SYSTEM_PROMPT, user_prompt, temperature=0.25, max_tokens=4096,
        )
        if not isinstance(payload, dict):
            raise OpenRouterClientError("agent returned non-object")
        normalized = _normalize_payload(payload, assessment_type, diff, dur, qc)
        normalized["agent_metadata"] = {
            "used_fallback": False,
            "assessment_type": assessment_type,
            "difficulty": diff,
            "question_count_target": qc,
            "duration_target_minutes": dur,
            "source_file_used": bool(source_file_text),
            "source_file_name": source_file_name,
            "hr_instructions_used": bool(hr_instructions and hr_instructions.strip()),
        }
        return normalized
    except OpenRouterClientError as exc:
        return _agent_fallback(
            assessment_type, job_block, diff, dur, qc,
            reason=str(exc)[:200],
            hr_instructions=hr_instructions,
            source_file_name=source_file_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[AssessmentAgent] generation failed (%s)", exc)
        return _agent_fallback(
            assessment_type, job_block, diff, dur, qc,
            reason=f"{type(exc).__name__}: {exc}"[:200],
            hr_instructions=hr_instructions,
            source_file_name=source_file_name,
        )


# ── Defaults + normalisation ────────────────────────────────────────────────


def _default_question_count(assessment_type: str) -> int:
    return {
        "technical_assessment":     5,
        "hr_assessment":            5,
        "iq_test":                  10,
        "problem_solving_coding":   2,
        "problem_solving_thinking": 3,
        "quiz":                     10,
    }.get(assessment_type, 5)


def _default_duration(assessment_type: str) -> int:
    return {
        "technical_assessment":     60,
        "hr_assessment":            30,
        "iq_test":                  20,
        "problem_solving_coding":   90,
        "problem_solving_thinking": 45,
        "quiz":                     25,
    }.get(assessment_type, 45)


def _normalize_payload(
    raw: dict[str, Any],
    assessment_type: str,
    difficulty: str,
    duration: int,
    qc_target: int,
) -> dict[str, Any]:
    """Coerce the agent's JSON into the shape the rest of the system expects."""
    title = str(raw.get("title") or "").strip() or ASSESSMENT_TYPE_LABELS.get(  # type: ignore[arg-type]
        assessment_type, "Assessment",
    )
    description = str(raw.get("description") or "").strip()

    questions_raw = raw.get("questions") or []
    if not isinstance(questions_raw, list):
        questions_raw = []

    questions: list[dict[str, Any]] = []
    total_score_from_questions = 0
    for i, q in enumerate(questions_raw, start=1):
        if not isinstance(q, dict):
            continue
        normalized_q = dict(q)
        normalized_q.setdefault("id", f"Q{i}")
        score = normalized_q.get("score")
        if not isinstance(score, (int, float)) or score <= 0:
            normalized_q["score"] = max(1, round(100 / max(1, len(questions_raw))))
        # Enforce difficulty default per-question.
        if assessment_type in (
            "technical_assessment",
            "problem_solving_coding",
            "problem_solving_thinking",
            "iq_test",
            "quiz",
        ):
            normalized_q.setdefault("difficulty", difficulty)
        total_score_from_questions += int(normalized_q["score"])
        questions.append(normalized_q)

    duration_minutes = raw.get("duration_minutes")
    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        duration_minutes = duration

    total_score = raw.get("total_score")
    if not isinstance(total_score, int) or total_score <= 0:
        total_score = total_score_from_questions or 100

    return {
        "title": title,
        "description": description,
        "duration_minutes": int(duration_minutes),
        "total_score": int(total_score),
        "questions": questions,
    }


# ── Fallback drafts (deterministic, no LLM) ────────────────────────────────


def _agent_fallback(
    assessment_type: str,
    job_block: dict[str, Any],
    difficulty: str,
    duration: int,
    qc: int,
    *,
    reason: str,
    hr_instructions: str | None,
    source_file_name: str | None,
) -> dict[str, Any]:
    """Last-ditch deterministic draft so the UI never crashes.

    The fallback intentionally produces a small set of generic but
    role-aware placeholder questions and flags ``used_fallback=True`` so
    HR can regenerate when the agent is back.
    """
    role = job_block.get("title") or "the role"
    skills = job_block.get("required_skills") or []
    primary_skill = skills[0] if skills else "the core required skill"

    if assessment_type == "technical_assessment":
        questions = [
            {
                "id": "Q1",
                "question": (
                    f"Walk us through how you would design a small service related "
                    f"to {role}. Cover API contract, validation, persistence, error "
                    f"handling, and observability."
                ),
                "type": "technical_written",
                "difficulty": difficulty,
                "estimated_time_minutes": 15,
                "score": 50,
                "expected_answer": (
                    "Endpoint shape, validation strategy, persistence layer, error "
                    "handling, and operational signals."
                ),
                "rubric": [
                    {"criterion": "API design clarity", "points": 15},
                    {"criterion": "Validation and security", "points": 15},
                    {"criterion": "Persistence and schema", "points": 10},
                    {"criterion": "Observability", "points": 10},
                ],
                "agent_reason": (
                    "Fallback draft — covers the breadth of skills a backend "
                    "engineer typically needs."
                ),
                "measures": ["API design", "validation", "data modelling"],
                "mapped_job_requirements": skills[:3],
            },
            {
                "id": "Q2",
                "question": (
                    f"Describe a difficult bug you debugged in a system that "
                    f"used {primary_skill}. How did you isolate it, and what "
                    f"would you do differently next time?"
                ),
                "type": "technical_written",
                "difficulty": difficulty,
                "estimated_time_minutes": 12,
                "score": 50,
                "expected_answer": (
                    "Structured debugging approach with measurable outcomes "
                    "and reflection."
                ),
                "rubric": [
                    {"criterion": "Systematic isolation", "points": 25},
                    {"criterion": "Communication", "points": 15},
                    {"criterion": "Reflection / lessons", "points": 10},
                ],
                "agent_reason": "Fallback draft — measures real-world debugging.",
                "measures": ["debugging", "ownership", "communication"],
                "mapped_job_requirements": skills[:3],
            },
        ]
    elif assessment_type == "hr_assessment":
        questions = [
            {
                "id": "Q1",
                "question": (
                    "Tell us about a time you had to handle conflicting priorities "
                    "under a tight deadline."
                ),
                "type": "hr_behavioural",
                "competency_measured": "Prioritization and communication",
                "score": 50,
                "rubric": [
                    {"criterion": "Clear situation and context", "points": 15},
                    {"criterion": "Decision-making process", "points": 15},
                    {"criterion": "Stakeholder communication", "points": 10},
                    {"criterion": "Outcome and reflection", "points": 10},
                ],
                "strong_answer_indicators": [
                    "Explains trade-offs clearly",
                    "Communicates with stakeholders",
                    "Shows ownership and reflection",
                ],
                "weak_answer_indicators": [
                    "Blames others",
                    "No clear prioritization method",
                    "No measurable outcome",
                ],
                "agent_reason": (
                    "Fallback draft — universal prioritization / communication "
                    "scenario."
                ),
            },
            {
                "id": "Q2",
                "question": (
                    "Describe a project where you took ownership of an outcome "
                    "that was not strictly part of your job description."
                ),
                "type": "hr_behavioural",
                "competency_measured": "Ownership",
                "score": 50,
                "rubric": [
                    {"criterion": "Initiative", "points": 20},
                    {"criterion": "Impact", "points": 20},
                    {"criterion": "Reflection", "points": 10},
                ],
                "strong_answer_indicators": [
                    "Initiative without being asked",
                    "Clear, measurable impact",
                ],
                "weak_answer_indicators": [
                    "Generic 'I helped' statements",
                    "No measurable outcome",
                ],
                "agent_reason": "Fallback draft — universal ownership signal.",
            },
        ]
    elif assessment_type == "iq_test":
        questions = [
            {
                "id": "Q1",
                "question": "What number comes next in the series: 2, 6, 12, 20, 30, ?",
                "type": "iq_pattern",
                "options": ["36", "40", "42", "48"],
                "correct_answer": "42",
                "explanation": (
                    "Differences are 4, 6, 8, 10, 12 — the next difference is 12, "
                    "so 30 + 12 = 42."
                ),
                "skill_measured": "Pattern recognition",
                "difficulty": difficulty,
                "score": 50,
                "agent_reason": "Fallback — classic pattern-recognition question.",
            },
            {
                "id": "Q2",
                "question": (
                    "A team finishes a feature in 6 weeks with 3 engineers. "
                    "Assuming the work scales linearly, how many weeks would it "
                    "take 5 engineers?"
                ),
                "type": "iq_numeric",
                "options": ["3.0", "3.6", "4.5", "5.0"],
                "correct_answer": "3.6",
                "explanation": "6 × 3 / 5 = 3.6 weeks.",
                "skill_measured": "Numerical reasoning",
                "difficulty": difficulty,
                "score": 50,
                "agent_reason": "Fallback — practical numerical reasoning.",
            },
        ]
    elif assessment_type == "problem_solving_coding":
        questions = [
            {
                "id": "Q1",
                "question": (
                    f"Implement a function that, given a list of candidate "
                    f"records, returns the top N candidates ranked by a "
                    f"weighted sum of skill-match score and years of experience. "
                    f"Tie-break alphabetically by alias."
                ),
                "type": "coding_problem",
                "difficulty": difficulty,
                "score": 100,
                "input_output_examples": [
                    {
                        "input": "candidates=[{alias:'A',skill:80,yrs:5},...], n=3, weights=(0.7,0.3)",
                        "output": "[<top 3 candidates>]",
                    },
                ],
                "constraints": ["O(n log n) acceptable", "n up to 10,000"],
                "expected_solution_approach": (
                    "Compute weighted score, sort with stable tie-breaker, "
                    "slice top N."
                ),
                "hidden_test_ideas": [
                    "Two candidates with identical weighted scores — verify alphabetical tiebreak.",
                    "n larger than the input list — return everyone.",
                ],
                "rubric": [
                    {"criterion": "Correctness", "points": 40},
                    {"criterion": "Edge cases", "points": 25},
                    {"criterion": "Readability", "points": 20},
                    {"criterion": "Complexity awareness", "points": 15},
                ],
                "agent_reason": "Fallback — practical ranking task close to the role.",
                "measures": ["sorting", "weighted scoring", "edge cases"],
                "mapped_job_requirements": skills[:3],
            },
        ]
    elif assessment_type == "problem_solving_thinking":
        questions = [
            {
                "id": "Q1",
                "scenario": (
                    "A production service that the team owns has just started "
                    "returning intermittent 500s, but only for a subset of "
                    "users. Logs show no clear pattern; the dashboard is green."
                ),
                "question": (
                    "Walk us through how you would approach the investigation "
                    "and what hypotheses you would prioritise."
                ),
                "type": "thinking_scenario",
                "difficulty": difficulty,
                "score": 100,
                "expected_reasoning_path": [
                    "Confirm scope: which users, requests, regions, versions?",
                    "Diff recent deploys, feature flags, dependencies.",
                    "Correlate with infra signals (latency, retries, saturation).",
                    "Reproduce locally / in staging; bisect if needed.",
                    "Communicate status + mitigations to stakeholders.",
                ],
                "rubric": [
                    {"criterion": "Structured triage", "points": 30},
                    {"criterion": "Hypothesis prioritisation", "points": 25},
                    {"criterion": "Stakeholder communication", "points": 20},
                    {"criterion": "Reflection on systemic causes", "points": 25},
                ],
                "agent_reason": "Fallback — universal incident-response scenario.",
                "measures": ["debugging mindset", "communication", "ownership"],
                "mapped_job_requirements": skills[:3],
            },
        ]
    else:  # quiz
        questions = [
            {
                "id": "Q1",
                "question": (
                    f"Which of these is most relevant to the {role} role?"
                ),
                "type": "mcq",
                "options": skills[:4] or ["Communication", "Ownership", "Curiosity", "Resilience"],
                "correct_answer": (skills[:1] or ["Communication"])[0],
                "explanation": "Picked because it's listed first in the job's required skills.",
                "skill_measured": "Job awareness",
                "difficulty": difficulty,
                "score": 50,
                "agent_reason": "Fallback — placeholder quiz item.",
            },
            {
                "id": "Q2",
                "question": "True or false: assessments should be reviewed by HR before being released to candidates.",
                "type": "true_false",
                "options": ["true", "false"],
                "correct_answer": "true",
                "explanation": "The PATHS workflow requires HR approval before release.",
                "skill_measured": "Process awareness",
                "difficulty": difficulty,
                "score": 50,
                "agent_reason": "Fallback — process check.",
            },
        ]

    return {
        "title": f"{ASSESSMENT_TYPE_LABELS.get(assessment_type, 'Assessment')} (fallback draft)",  # type: ignore[arg-type]
        "description": (
            "This draft was produced by the deterministic fallback because the "
            "LLM agent was unavailable. HR should regenerate or edit before "
            "approval."
        ),
        "duration_minutes": duration,
        "total_score": sum(int(q.get("score", 0)) for q in questions) or 100,
        "questions": questions,
        "agent_metadata": {
            "used_fallback": True,
            "fallback_reason": reason,
            "assessment_type": assessment_type,
            "difficulty": difficulty,
            "question_count_target": qc,
            "duration_target_minutes": duration,
            "source_file_used": bool(source_file_name),
            "source_file_name": source_file_name,
            "hr_instructions_used": bool(hr_instructions and hr_instructions.strip()),
        },
    }


# ── Grading agent (candidate submissions) ────────────────────────────────────


_GRADER_SYSTEM = (
    "You are PATHS, a fair and rigorous assessment grader. You receive "
    "assessment questions (each with an expected answer and a points rubric) "
    "and a candidate's answers. Grade each answer ONLY on its merits against "
    "the rubric and expected answer, awarding partial credit per criterion. "
    "Never reward empty, irrelevant, or copied-prompt answers. Be objective "
    "and unbiased (ignore any personal attributes). Reply with a SINGLE valid "
    "JSON object and nothing else:\n"
    "{\n"
    '  "grades": [\n'
    '    {"question_id": "<id>", "awarded": <number 0..max>, '
    '"feedback": "1-2 sentences of specific, constructive feedback"}\n'
    "  ],\n"
    '  "summary": "2-3 sentence overall summary of performance",\n'
    '  "strengths": ["..."],\n'
    '  "areas_to_improve": ["..."]\n'
    "}"
)


def _safe_str_list(value: Any, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        s = str(item).strip()
        if s:
            out.append(s[:240])
        if len(out) >= limit:
            break
    return out


def grade_submission(
    *,
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    job_title: str | None = None,
) -> dict[str, Any]:
    """Grade a candidate's assessment answers against each question's rubric.

    Returns a report dict::

        {total_score, max_score, score_percent, summary, strengths,
         areas_to_improve, per_question: [{question_id, question, answer,
         awarded, max, feedback}], used_fallback}

    Uses the OpenRouter grader in one batched call, with a deterministic
    partial-credit fallback so a submission always produces a score.
    """
    qlist = [q for q in (questions or []) if isinstance(q, dict)]

    # Per-question max points (fall back to an even split of 100).
    maxes: dict[str, float] = {}
    for i, q in enumerate(qlist):
        qid = str(q.get("id") or i)
        try:
            maxes[qid] = float(q.get("score") or 0)
        except (TypeError, ValueError):
            maxes[qid] = 0.0
    if not any(maxes.values()) and qlist:
        each = round(100.0 / len(qlist), 2)
        maxes = {str(q.get("id") or i): each for i, q in enumerate(qlist)}
    max_score = round(sum(maxes.values()), 2)

    def _answer_for(qid: str, idx: int) -> str:
        return str(answers.get(qid) or answers.get(str(idx)) or "").strip()

    graded: dict[str, dict[str, Any]] | None = None
    meta = {"summary": "", "strengths": [], "areas_to_improve": []}
    try:
        items = []
        for i, q in enumerate(qlist):
            qid = str(q.get("id") or i)
            items.append({
                "question_id": qid,
                "question": str(q.get("question") or "")[:1500],
                "max": maxes.get(qid, 0.0),
                "expected_answer": str(q.get("expected_answer") or "")[:1200],
                "rubric": q.get("rubric") if isinstance(q.get("rubric"), list) else [],
                "candidate_answer": _answer_for(qid, i)[:2500],
            })
        user_prompt = (
            f"Role: {job_title or 'the role'}\n\n"
            f"Grade these {len(items)} answers. For each, award 0..max points.\n\n"
            f"{json.dumps(items, ensure_ascii=False)}\n\nReturn the JSON now."
        )
        data = generate_json_response(
            _GRADER_SYSTEM, user_prompt, temperature=0.1, max_tokens=2000,
        )
        grades = data.get("grades") if isinstance(data, dict) else None
        if isinstance(grades, list):
            graded = {
                str(g["question_id"]): g
                for g in grades
                if isinstance(g, dict) and g.get("question_id") is not None
            }
            meta["summary"] = str(data.get("summary") or "").strip()[:1500]
            meta["strengths"] = _safe_str_list(data.get("strengths"))
            meta["areas_to_improve"] = _safe_str_list(data.get("areas_to_improve"))
    except OpenRouterClientError as exc:
        logger.warning("[AssessmentGrader] LLM grading failed: %s", exc)
    except Exception:  # noqa: BLE001
        logger.exception("[AssessmentGrader] unexpected grading error")

    used_fallback = graded is None
    per_question: list[dict[str, Any]] = []
    total = 0.0
    for i, q in enumerate(qlist):
        qid = str(q.get("id") or i)
        mx = maxes.get(qid, 0.0)
        ans = _answer_for(qid, i)
        if graded is not None and qid in graded:
            try:
                awarded = float(graded[qid].get("awarded") or 0)
            except (TypeError, ValueError):
                awarded = 0.0
            awarded = max(0.0, min(mx, awarded))
            feedback = str(graded[qid].get("feedback") or "").strip()[:500]
        else:
            awarded = round(mx * 0.5, 2) if len(ans) >= 40 else (round(mx * 0.2, 2) if ans else 0.0)
            feedback = (
                "Answer received — automatic grading was temporarily unavailable, "
                "so this is a provisional score pending reviewer confirmation."
                if ans else "No answer was provided for this question."
            )
        total += awarded
        per_question.append({
            "question_id": qid,
            "question": str(q.get("question") or ""),
            "answer": ans,
            "awarded": round(awarded, 2),
            "max": mx,
            "feedback": feedback,
        })

    total = round(total, 2)
    percent = round((total / max_score) * 100.0, 1) if max_score else 0.0
    if used_fallback and not meta["summary"]:
        meta["summary"] = (
            "Provisional auto-grade — the AI grader was temporarily unavailable. "
            "A reviewer will confirm the final score."
        )
    return {
        "total_score": total,
        "max_score": max_score,
        "score_percent": percent,
        "summary": meta["summary"],
        "strengths": meta["strengths"],
        "areas_to_improve": meta["areas_to_improve"],
        "per_question": per_question,
        "used_fallback": used_fallback,
    }
