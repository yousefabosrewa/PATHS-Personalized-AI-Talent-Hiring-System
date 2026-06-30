"""
PATHS Backend — OutreachAgent.

Generates a personalized outreach email subject + body via OpenRouter.

Falls back to a deterministic template when:
  * OPENROUTER_API_KEY is not configured, or
  * the LLM call fails for any reason, or
  * the response cannot be parsed as JSON.

The output always contains exactly one ``{{SCHEDULING_LINK}}`` placeholder,
which the caller replaces with the candidate's signed scheduling URL after
the email is composed (never before — see brief).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.services.llm.openrouter_client import (
    OpenRouterClientError,
    generate_json_response,
)

logger = logging.getLogger(__name__)
settings = get_settings()


_SYSTEM_PROMPT = (
    "You are an HR outreach assistant for PATHS. Generate concise, "
    "professional, personalized outreach emails inviting a candidate to "
    "schedule an interview or offer discussion. Never overpromise. Never "
    "mention private AI scoring details directly. Explain fit in a positive, "
    "human way. The HR will review before sending. Reply ONLY with a single "
    "JSON object matching this schema and nothing else:\n"
    "{\n"
    '  "subject": "string",\n'
    '  "body":    "string"\n'
    "}\n"
    "Rules:\n"
    "- 120-180 words maximum.\n"
    "- Warm and professional tone.\n"
    "- Mention 1-2 candidate strengths related to the job.\n"
    "- Include a clear call to action.\n"
    "- Do not mention exact AI score unless explicitly told to.\n"
    "- Do not say the candidate is hired unless this is explicitly a final offer.\n"
    "- Include {{SCHEDULING_LINK}} exactly once in the body.\n"
)


# How the email should be framed for each interview type. The whole point of
# letting HR pick a type is that the draft reads differently for each one.
_INTERVIEW_FOCUS = {
    "hr": (
        "an HR / culture-fit conversation — the candidate's background, "
        "motivation, expectations and how they'd fit the team. Keep it warm "
        "and people-focused; do not promise a technical deep-dive."
    ),
    "technical": (
        "a technical interview — a hands-on discussion of the candidate's "
        "technical skills and problem-solving for this specific role. Signal "
        "they'll dig into their technical experience and how they build things."
    ),
    "mixed": (
        "a mixed interview that BOTH explores technical ability AND gets to "
        "know the candidate as a person — including how well they would adapt "
        "to and thrive in the company's environment and culture. Convey that "
        "this is a holistic, two-sided get-to-know-you conversation."
    ),
}


def _canon_interview_type(value: str | None) -> str:
    """Map any free-text interview type to hr | technical | mixed."""
    v = (value or "").strip().lower()
    if "mix" in v or "both" in v:
        return "mixed"
    if "tech" in v:
        return "technical"
    return "hr"


@dataclass
class GeneratedEmail:
    subject: str
    body: str
    model: str | None = None
    fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "body": self.body,
            "model": self.model,
            "fallback": self.fallback,
        }


def generate_outreach_email(
    *,
    candidate_profile: dict[str, Any],
    job_details: dict[str, Any],
    organization: dict[str, Any],
    hr_name: str | None = None,
    interview_type: str | None = None,
    match_context: dict[str, Any] | None = None,
    is_final_offer: bool = False,
    disclose_ai_score: bool = False,
    extra_instructions: str | None = None,
) -> GeneratedEmail:
    """Return a GeneratedEmail. Always contains {{SCHEDULING_LINK}}."""

    user_prompt = _build_user_prompt(
        candidate_profile=candidate_profile,
        job_details=job_details,
        organization=organization,
        hr_name=hr_name,
        interview_type=interview_type,
        match_context=match_context or {},
        is_final_offer=is_final_offer,
        disclose_ai_score=disclose_ai_score,
        extra_instructions=extra_instructions,
    )

    if not settings.openrouter_api_key:
        return _fallback_email(
            candidate_profile=candidate_profile,
            job_details=job_details,
            organization=organization,
            hr_name=hr_name,
            is_final_offer=is_final_offer,
            interview_type=interview_type,
        )

    try:
        data = generate_json_response(
            _SYSTEM_PROMPT,
            user_prompt,
            model=settings.outreach_agent_model,
            temperature=float(settings.outreach_agent_temperature),
            max_tokens=int(settings.outreach_agent_max_tokens),
        )
    except OpenRouterClientError as exc:
        logger.warning("[OutreachAgent] LLM call failed: %s", exc)
        return _fallback_email(
            candidate_profile=candidate_profile,
            job_details=job_details,
            organization=organization,
            hr_name=hr_name,
            is_final_offer=is_final_offer,
            interview_type=interview_type,
        )

    subject = _coerce_str(data.get("subject")) or _default_subject(
        job_details, is_final_offer,
    )
    body = _coerce_str(data.get("body")) or _default_body(
        candidate_profile, job_details, organization, hr_name,
    )
    body = _ensure_single_placeholder(body)
    return GeneratedEmail(
        subject=subject[:255],
        body=body,
        model=settings.outreach_agent_model,
        fallback=False,
    )


# ── Prompt construction ──────────────────────────────────────────────────


def _build_user_prompt(
    *,
    candidate_profile: dict[str, Any],
    job_details: dict[str, Any],
    organization: dict[str, Any],
    hr_name: str | None,
    interview_type: str | None,
    match_context: dict[str, Any],
    is_final_offer: bool,
    disclose_ai_score: bool,
    extra_instructions: str | None,
) -> str:
    cand_name = candidate_profile.get("full_name") or "Candidate"
    cand_title = candidate_profile.get("current_title") or "—"
    cand_skills = ", ".join(candidate_profile.get("skills") or [])[:300] or "—"
    cand_summary = (candidate_profile.get("summary") or "").strip()[:600] or "—"
    cand_years = candidate_profile.get("years_experience") or "—"

    job_title = job_details.get("title") or "the open role"
    job_summary = (job_details.get("summary") or job_details.get("description_text") or "").strip()[:600] or "—"
    job_seniority = job_details.get("seniority_level") or "—"
    job_workplace = job_details.get("workplace_type") or job_details.get("location_mode") or "—"
    job_location = job_details.get("location_text") or "—"

    org_name = organization.get("name") or "our team"
    org_industry = organization.get("industry") or "—"

    matched_skills = ", ".join(match_context.get("matched_skills") or [])[:300] or "—"
    strengths = ", ".join(match_context.get("strengths") or [])[:300] or "—"

    score_line = ""
    if disclose_ai_score and match_context.get("score") is not None:
        score_line = f"AI match score (HR-disclosed): {match_context.get('score')}/100\n"

    final_offer_line = (
        "This email is a final-offer discussion. The candidate may be told the role is offered."
        if is_final_offer
        else "This email is an interview invitation. Do NOT say the candidate is hired."
    )
    canon = _canon_interview_type(interview_type)
    label = (interview_type or "HR interview").strip()
    interview_line = (
        f"Interview type: {label}. This invitation is for {_INTERVIEW_FOCUS[canon]} "
        "Tailor the email's framing, the strengths you highlight, and the "
        "call-to-action to THIS interview type so the candidate clearly knows "
        "what kind of conversation to expect."
    )

    parts = [
        f"Organization: {org_name} (industry: {org_industry})",
        f"HR contact: {hr_name or 'the hiring team'}",
        f"Job: {job_title} (seniority: {job_seniority}, workplace: {job_workplace}, location: {job_location})",
        f"Job summary: {job_summary}",
        "",
        f"Candidate: {cand_name}",
        f"Current title: {cand_title} (years: {cand_years})",
        f"Candidate skills: {cand_skills}",
        f"Candidate summary: {cand_summary}",
        "",
        f"Matched skills (positive context): {matched_skills}",
        f"Candidate strengths: {strengths}",
        score_line,
        final_offer_line,
        interview_line,
    ]
    if extra_instructions:
        parts.append("")
        parts.append(f"Extra HR instructions: {extra_instructions[:500]}")
    parts.append("")
    parts.append(
        "Generate a JSON object with subject and body following the system rules. "
        "Include {{SCHEDULING_LINK}} exactly once in the body."
    )
    return "\n".join(parts)


# ── Fallback template (no-LLM path) ──────────────────────────────────────


def _fallback_email(
    *,
    candidate_profile: dict[str, Any],
    job_details: dict[str, Any],
    organization: dict[str, Any],
    hr_name: str | None,
    is_final_offer: bool,
    interview_type: str | None = None,
) -> GeneratedEmail:
    return GeneratedEmail(
        subject=_default_subject(job_details, is_final_offer, interview_type),
        body=_default_body(
            candidate_profile, job_details, organization, hr_name, interview_type,
        ),
        model=None,
        fallback=True,
    )


def _default_subject(
    job_details: dict[str, Any], is_final_offer: bool, interview_type: str | None = None,
) -> str:
    title = job_details.get("title") or "open role"
    if is_final_offer:
        return f"Offer Letter Discussion – {title}"
    kind = {
        "hr": "HR Interview",
        "technical": "Technical Interview",
        "mixed": "Interview",
    }[_canon_interview_type(interview_type)]
    return f"{kind} Invitation – {title}"


# The middle paragraph differs by interview type so the candidate knows what
# kind of conversation to expect even when the LLM is unavailable.
_FALLBACK_INVITE_LINE = {
    "hr": (
        "We'd love to set up a short conversation to learn more about your "
        "experience and what you're looking for, and to tell you about the role "
        "and our team."
    ),
    "technical": (
        "We'd love to set up a technical conversation to explore your hands-on "
        "skills and how you approach real problems for this role."
    ),
    "mixed": (
        "We'd love to set up a conversation to get to know you better — both "
        "your technical strengths and how you'd fit and adapt to our team and "
        "company culture."
    ),
}


def _default_body(
    candidate: dict[str, Any],
    job: dict[str, Any],
    org: dict[str, Any],
    hr_name: str | None,
    interview_type: str | None = None,
) -> str:
    cand_name = candidate.get("full_name") or "there"
    title = job.get("title") or "the open role"
    org_name = org.get("name") or "our team"
    skills = (candidate.get("skills") or [])[:3]
    skills_line = (
        f"Your background in {', '.join(skills)} stood out to us. "
        if skills else
        "Your background looks like a strong fit. "
    )
    invite_line = _FALLBACK_INVITE_LINE[_canon_interview_type(interview_type)]
    closing = f"Best regards,\n{hr_name or 'Hiring Team'}\n{org_name}"
    return (
        f"Hi {cand_name},\n\n"
        f"I'm reaching out from {org_name} regarding the {title} position. "
        f"{skills_line}"
        f"{invite_line}\n\n"
        "Please pick a time that works for you using the link below:\n"
        "{{SCHEDULING_LINK}}\n\n"
        "Looking forward to speaking with you.\n\n"
        f"{closing}"
    )


# ── Small helpers ────────────────────────────────────────────────────────


def _coerce_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _ensure_single_placeholder(body: str) -> str:
    """Guarantee the body contains exactly one {{SCHEDULING_LINK}}."""
    placeholder = "{{SCHEDULING_LINK}}"
    if not body:
        body = (
            "Please pick a time that works for you using the link below:\n"
            f"{placeholder}\n"
        )
        return body
    count = body.count(placeholder)
    if count == 1:
        return body
    if count == 0:
        return body.rstrip() + "\n\n" + placeholder + "\n"
    # count > 1 — keep only the first occurrence.
    first = body.find(placeholder) + len(placeholder)
    return body[:first] + body[first:].replace(placeholder, "")
