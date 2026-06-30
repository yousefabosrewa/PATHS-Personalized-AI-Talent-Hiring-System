# PATHS — Personalized AI Talent Hiring System
## Graduation Project Presentation

> **Instructions**: Each `---` separator below marks a new slide. Speaker notes are in blockquotes. Layout suggestions are in *italic annotations*. Diagrams are described in `[DIAGRAM: ...]` blocks for you to recreate visually in PowerPoint/Google Slides.

---

## Slide 1 — Title Slide

### Personalized AI Talent Hiring System (PATHS)

**Faculty of Computer Science & Engineering — Galala University**
**Academic Year 2025–2026**

| Team Members | ID |
|---|---|
| Abdelrahman Osheba | 222100946 |
| Ahmed Abouelela | 222100032 |
| Ahmed Abdelghany | 222100123 |
| Osama Khalil | 222100211 |
| Youssef Abousrewa | 221101030 |

**Supervised By**
- Associate Professor **Shaker El-Sappagh**
- Assistant Professor **Amr Hefny**

*Layout: Use the PATHS logo or a hero image of the platform. Large project title centered, team table below, supervisor names at the bottom. Dark gradient background (navy → deep blue).*

> **Speaker Notes**: "Good morning/afternoon. We are presenting PATHS — the Personalized AI Talent Hiring System. This is our graduation project that tackles one of the most pressing challenges in modern recruitment: the fragmentation of hiring tools and workflows."

---

## Slide 2 — The Recruitment Problem

### Why Modern Hiring Is Broken

**4 Critical Pain Points:**

1. 🔧 **Fragmented Tools**
   - Organizations juggle 4–6 disconnected tools (ATS, sourcing, assessment, scheduling)
   - Manual handoffs create data silos and inefficiency

2. ⏱️ **Slow Hiring Cycles**
   - Global median time-to-hire: **~38 days**
   - 92% of Egyptian HR professionals dissatisfied with application quality

3. 📉 **Poor Outreach & Passive Talent Access**
   - First-email reply rates can be **single digits**
   - 70% of the global workforce is passive talent — unreached by traditional methods

4. ⚖️ **Inconsistent & Biased Evaluation**
   - No standardized rubrics across teams
   - Identity-related bias in screening decisions
   - 41% of new hires in Egypt's tech sector leave within 18 months due to lack of growth alignment

**The Core Question:**
> *"How can we design a unified AI-driven agentic system that reduces time-to-hire and cost-per-hire, improves outreach response, and supports fair, auditable, privacy-respecting hiring decisions?"*

*Layout: Use 4 icon cards in a 2×2 grid. Each pain point gets an icon and short description. The core question at the bottom in a highlighted box.*

> **Speaker Notes**: "Modern recruitment is not just slow — it's structurally broken. Companies stitch together 4 to 6 separate tools with manual handoffs, creating data silos. The median time-to-hire is 38 days globally. Outreach response rates are in the low single digits. Evaluation is inconsistent and prone to bias. And in Egypt specifically, 41% of tech hires leave within 18 months because there's no link between hiring decisions and career development. This is the problem PATHS was built to solve."

---

## Slide 3 — Project Goal

### PATHS: One End-to-End AI Hiring System

**From fragmented tools → to a unified intelligent pipeline**

```
Sourcing → Evaluation → Decision → Development Plan
   ↓           ↓            ↓              ↓
 Find the    Assess       Make fair      Convert
 right       skills &     auditable      insights
 candidates  fit fairly   decisions      into growth
```

**Key Design Principles:**

| Principle | How PATHS Implements It |
|---|---|
| 🤖 **AI-Augmented, Human-Controlled** | Human-in-the-loop at every critical checkpoint |
| 🔒 **Privacy-First** | Anonymization before evaluation, RBAC, audit logs |
| 📊 **Evidence-Based** | Explainable scores with rationale, not black-box ranking |
| 🔄 **End-to-End** | Single platform from sourcing through post-hire development |
| 🎯 **Skills-Based** | Focus on demonstrated capabilities, not credentials alone |

*Layout: Large horizontal arrow at the top showing the 4-stage pipeline. Below, a clean table or icon list of the design principles. Use a dark background with accent color highlights.*

> **Speaker Notes**: "PATHS is designed as one end-to-end AI hiring system that connects four phases that are currently disconnected: sourcing the right candidates, evaluating their skills fairly, making auditable hiring decisions, and converting interview insights into individual development plans. The system is AI-augmented but human-controlled. Privacy is built in from the start with anonymization. Scoring is explainable — every recommendation comes with evidence and rationale."

---

## Slide 4 — What PATHS Does

### Core Platform Capabilities

**7 Key Capabilities Across the Hiring Lifecycle:**

| # | Capability | Description |
|---|---|---|
| 1 | **Multi-Source Ingestion** | CV upload, LinkedIn profile, GitHub contributions, portfolio, ATS export |
| 2 | **Master Candidate Profile** | Entity resolution + normalization → one unified profile per candidate |
| 3 | **Anonymization** | Identity-sensitive fields hidden during evaluation to reduce bias |
| 4 | **Top-K Shortlisting** | Scoring agent ranks candidates with confidence ratings + rationale |
| 5 | **Technical Assessment** | AI-generated coding/behavioral assessments with rubric-based grading |
| 6 | **Decision Support Packet** | Structured report: scores, strengths, weaknesses, hiring recommendation |
| 7 | **Individual Development Plan (IDP)** | Skill gaps → learning path for accepted & rejected candidates |

```
[DIAGRAM: Layered capability stack]

┌─────────────────────────────────────────────────┐
│          Individual Development Plan (IDP)       │  ← Post-decision
├─────────────────────────────────────────────────┤
│          Decision Support Packet                 │  ← Decision
├─────────────────────────────────────────────────┤
│     Technical Assessment + Interview Prep        │  ← Evaluation
├─────────────────────────────────────────────────┤
│     Top-K Shortlist + Anonymized Ranking          │  ← Screening
├─────────────────────────────────────────────────┤
│  CV · LinkedIn · GitHub · Portfolio · ATS Import  │  ← Ingestion
└─────────────────────────────────────────────────┘
```

*Layout: Stacked layers (bottom-up) showing capabilities building on each other. Each layer in a progressively lighter shade. Number badges on the left.*

> **Speaker Notes**: "Here's what PATHS actually does. It starts with multi-source ingestion — we don't just parse a CV. We pull data from LinkedIn, GitHub, portfolio sites, and ATS exports, then merge them into a single master profile using entity resolution. Before evaluation, the system anonymizes candidates. A scoring agent produces a ranked Top-K shortlist with confidence ratings and explainable rationale. For technical roles, the system generates assessments and provides rubric-based grading. At the end, everything is assembled into a decision support packet for the hiring manager. And uniquely, PATHS generates Individual Development Plans — even for rejected candidates — turning evaluation data into growth opportunities."

---

## Slide 5 — End-to-End Workflow

### The PATHS Hiring Pipeline

```
[DIAGRAM: Full pipeline flow — recreate this as a visual flowchart]

┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────────┐
│   JOB    │───▶│  CANDIDATE   │───▶│   BIAS      │───▶│   SCORING     │
│ CREATION │    │  SOURCING    │    │ GUARDRAILS  │    │  & RANKING    │
│          │    │ (Inbound/    │    │ (Anonymize) │    │  (Top-K)      │
│ • Title  │    │  Outbound)   │    │             │    │ • Fit score   │
│ • Reqs   │    │ • CV upload  │    │ • Hide name │    │ • Evidence    │
│ • Rubric │    │ • LinkedIn   │    │ • Hide age  │    │ • Confidence  │
│ • Skills │    │ • GitHub     │    │ • Hide gender│   │ • Rationale   │
└──────────┘    │ • ATS import │    └─────────────┘    └───────┬───────┘
                └──────────────┘                               │
                                                               ▼
┌──────────┐    ┌──────────────┐    ┌─────────────┐    ┌───────────────┐
│   IDP    │◀───│  DECISION    │◀───│ INTERVIEW   │◀───│   OUTREACH    │
│ & GROWTH │    │  SUPPORT     │    │ & ASSESS    │    │ & SCHEDULING  │
│          │    │              │    │             │    │               │
│ • Gaps   │    │ • Final score│    │ • RAG-based │    │ • Personalized│
│ • Plan   │    │ • Report     │    │   questions │    │   messages    │
│ • Goals  │    │ • Recommend  │    │ • Assessment│    │ • Multi-channel│
│ • Review │    │ • HITL ✓     │    │ • Summary   │    │ • Tracking    │
└──────────┘    └──────────────┘    └─────────────┘    └───────────────┘

                    ▲ Human-in-the-Loop checkpoints at every stage ▲
```

**Pipeline Stages:**
1. **Job Creation** — Define role, requirements, fairness rubric, skill weights
2. **Candidate Sourcing** — Inbound (CV/ATS) + Outbound (LinkedIn/GitHub search)
3. **Bias Guardrails** — Anonymize identity before evaluation
4. **Scoring & Ranking** — Evidence-based Top-K shortlist with explainable scores
5. **Outreach & Scheduling** — RAG-personalized messages, multi-channel delivery
6. **Interview & Assessment** — RAG-generated questions, rubric-based grading
7. **Decision Support** — Structured report + HITL final approval
8. **IDP & Growth Plan** — Skill gaps → development pathway (hired or rejected)

*Layout: 8-box pipeline in two rows (4 + 4), connected with arrows. Use alternating colors. Add a "Human-in-the-Loop" banner spanning the bottom. This is the most important visual slide — invest in making it look great.*

> **Speaker Notes**: "This is the full PATHS pipeline. It starts when a recruiter creates a job with structured requirements and a fairness rubric. Then sourcing happens — either inbound through CV uploads and ATS imports, or outbound through LinkedIn and GitHub search. Before any evaluation, the system applies bias guardrails by anonymizing candidate profiles. The scoring agent then ranks candidates using evidence-based metrics. After shortlist approval, the outreach agent sends personalized messages using RAG. Interviews are supported by AI-generated questions grounded in the company knowledge base. Finally, a decision support packet is generated for the hiring manager, and whether a candidate is hired or rejected, they receive an Individual Development Plan. Human-in-the-loop checkpoints exist at every critical stage."

---

## Slide 6 — System Architecture

### Technical Architecture

```
[DIAGRAM: 4-tier architecture — recreate as a layered diagram]

┌─────────────────────────────────────────────────────────┐
│                    FRONTEND                              │
│              Next.js + TypeScript + React                │
│     Dashboard · Job Management · Candidate Portal        │
│     Interview UI · Assessment UI · Admin Panel           │
└───────────────────────┬─────────────────────────────────┘
                        │ REST API
┌───────────────────────▼─────────────────────────────────┐
│                    BACKEND                               │
│                FastAPI (Python)                           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Jobs    │ │Candidates│ │Interview │ │  Screening  │ │
│  │ Module  │ │ Module   │ │ Module   │ │   Module    │ │
│  ├─────────┤ ├──────────┤ ├──────────┤ ├─────────────┤ │
│  │Sourcing │ │ Outreach │ │Decision  │ │    Auth     │ │
│  │ Module  │ │ Module   │ │ Support  │ │   Module    │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
│                                                          │
│  Security: JWT + Argon2 | RBAC | Structured Logging      │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                  AI / MODEL LAYER                        │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────┐  │
│  │   Ollama   │  │  AI Agents │  │  MCP Providers    │  │
│  │  (LLaMA /  │  │ (6 agents) │  │ • LinkedIn MCP    │  │
│  │  Mistral / │  │ • Scoring  │  │ • Skill Evidence  │  │
│  │  DeepSeek) │  │ • Outreach │  │ • Calendar/Gmail  │  │
│  │            │  │ • RAG Prep │  │                   │  │
│  └────────────┘  │ • Assess   │  └───────────────────┘  │
│                  │ • Decision │                          │
│                  │ • Ingestion│                          │
│                  └────────────┘                          │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│               POLYGLOT PERSISTENCE                       │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ PostgreSQL   │  │  Apache AGE  │  │    Qdrant    │   │
│  │              │  │  (Graph DB)  │  │ (Vector DB)  │   │
│  │ Structured   │  │              │  │              │   │
│  │ records:     │  │ Knowledge    │  │ Semantic     │   │
│  │ users, jobs, │  │ graph:       │  │ search:      │   │
│  │ candidates,  │  │ candidates ↔ │  │ CV ↔ JD      │   │
│  │ applications,│  │ skills ↔     │  │ similarity,  │   │
│  │ assessments, │  │ jobs ↔       │  │ knowledge    │   │
│  │ decisions,   │  │ evidence ↔   │  │ base         │   │
│  │ audit logs   │  │ companies    │  │ retrieval    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Technology Stack Summary:**

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js, TypeScript, React, Tailwind CSS |
| **Backend** | FastAPI (Python), Pydantic, SQLAlchemy |
| **AI/LLM** | Ollama (LLaMA / Mistral / DeepSeek), LangChain |
| **Data** | PostgreSQL, Apache AGE (Graph), Qdrant (Vector) |
| **Security** | JWT, Argon2, RBAC, Structured Audit Logs |
| **Integration** | MCP Protocol (LinkedIn, Calendar, Gmail, Skill Evidence) |
| **Deployment** | Docker, Docker Compose |

*Layout: 4-tier layered diagram (Frontend → Backend → AI Layer → Data Layer). Color-code each tier. Technology logos alongside names. Clean and professional.*

> **Speaker Notes**: "PATHS uses a four-tier architecture. The frontend is built with Next.js, TypeScript, and React. The backend is a modular monolithic FastAPI application with separate modules for jobs, candidates, interviews, screening, sourcing, outreach, and decision support. The AI layer runs through Ollama for local LLM inference — we support LLaMA, Mistral, and DeepSeek models. Six specialized AI agents handle different tasks. We also use the Model Context Protocol for external integrations like LinkedIn sourcing, Calendar, and Gmail. The data layer is polyglot: PostgreSQL for structured data, Apache AGE for graph relationships between candidates, skills, and jobs, and Qdrant for vector-based semantic search."

---

## Slide 7 — Key AI Components

### AI-Powered Intelligence

**1. Agentic AI Architecture (6 Specialized Agents)**

| Agent | Role |
|---|---|
| 🔍 **Sourcing Agent** | Find candidates from LinkedIn, GitHub, and external sources |
| 📊 **Scoring/Ranking Agent** | Evaluate fit-to-role with evidence-based scoring and Top-K ranking |
| 📧 **Outreach Agent** | Generate RAG-personalized engagement messages |
| 📝 **Assessment Agent** | Create rubric-aligned assessments and grade submissions |
| 🤝 **Interview Prep Agent** | Generate RAG-grounded HR + technical interview questions |
| 📋 **Decision Support Agent** | Compile final report with scores, strengths, and recommendation |

**2. RAG (Retrieval-Augmented Generation)**
- Grounds all AI outputs in **organization knowledge base** (company docs, job context, candidate evidence)
- Uses **Qdrant vector search** for semantic retrieval
- Prevents hallucination — AI generates from retrieved evidence, not imagination

**3. Candidate Scoring Pipeline**
- **Evidence gating**: Skills scored only when backed by CV/GitHub/portfolio proof
- **Hybrid scoring**: Content-based similarity + graph-based matching signals
- **Explainable output**: Every score includes rationale and confidence rating

**4. Human-in-the-Loop (HITL)**
- Shortlist approval before outreach
- De-anonymization request approval
- Final hiring decision requires human sign-off
- AI recommends — humans decide

**5. Bias Guardrails**
- Candidate anonymization before evaluation
- Scoring excludes protected attributes (age, gender, location) unless explicitly job-relevant
- Fairness rubric defined at job creation
- Audit trail for all decisions

*Layout: Use a central hub diagram with the 6 agents radiating outward. Below, 4 feature cards for RAG, Scoring, HITL, and Bias Guardrails. Use icons and short descriptions.*

> **Speaker Notes**: "The AI in PATHS is not a single model — it's an agentic architecture with six specialized agents. The Sourcing Agent discovers candidates. The Scoring Agent evaluates fit. The Outreach Agent writes personalized messages. The Assessment Agent creates and grades tests. The Interview Prep Agent generates contextual questions. And the Decision Support Agent compiles everything into a structured report. All agents use RAG — Retrieval-Augmented Generation — which means every output is grounded in the organization's actual knowledge base through Qdrant vector search. The scoring pipeline uses evidence gating: a skill is only scored if there's proof from a CV, GitHub, or portfolio. And critically, humans remain in the loop at every checkpoint — the AI recommends, but humans decide."

---

## Slide 8 — Evaluation Design

### What We Tested & How

**7 Evaluation Metrics Across 3 Categories:**

| Category | Metric | What It Measures |
|---|---|---|
| **Coverage** | Process Coverage | How many of the 16 recruitment stages does PATHS cover? |
| **Functional** | Functional Success Rate (E2E) | Do Playwright end-to-end tests pass? |
| **Functional** | Backend Test Pass Rate | Do pytest unit/integration tests pass? |
| **Accuracy** | Matching Accuracy (Band-Hit) | Does scoring place candidates in the correct quality band? |
| **Accuracy** | Matching Accuracy (Relevance-Consistent) | Are top-ranked candidates actually more relevant? |
| **Quality** | RAG Retrieval Relevance | Does the system retrieve the right context? (Hit Rate, MRR, NDCG) |
| **Quality** | Generated Output Quality | Are AI-generated outputs (outreach, questions, reports) high quality? |

**Testing Approach:**

```
[DIAGRAM: Testing pyramid]

         ┌──────────┐
         │  E2E     │  ← Playwright (48 scenarios)
         │  Tests   │
         ├──────────┤
         │ Backend  │  ← pytest (174 tests)
         │  Tests   │
         ├──────────┤
         │   AI /   │  ← RAG retrieval metrics
         │   RAG    │    (8 queries, Hit Rate, MRR, NDCG)
         │  Quality │
         ├──────────┤
         │ Process  │  ← Coverage mapping
         │ Coverage │    (16 recruitment stages)
         └──────────┘
```

*Layout: Clean table at the top. Testing pyramid diagram below. Use professional colors and clear labels.*

> **Speaker Notes**: "We designed a rigorous evaluation covering seven metrics across three categories. First, process coverage — does PATHS actually cover the full recruitment lifecycle? Second, functional correctness — do the frontend and backend actually work? We used Playwright for end-to-end testing and pytest for backend tests. Third, AI quality — does the RAG system retrieve the right context, and are the generated outputs actually useful? We measured retrieval with Hit Rate, MRR, and NDCG, and evaluated generation quality through structured rubrics."

---

## Slide 9 — Result 1: Process Coverage

### PATHS Covers 93.75% of the Recruitment Lifecycle

**15 out of 16 stages fully covered**

| Stage | Status |
|---|---|
| 1. Job Posting & Requirement Definition | ✅ Covered |
| 2. Inbound Candidate Collection | ✅ Covered |
| 3. Outbound Candidate Sourcing | ✅ Covered |
| 4. Candidate Profile Unification | ✅ Covered |
| 5. Candidate Anonymization | ✅ Covered (basic — names/photos) |
| 6. Candidate Scoring & Ranking | ✅ Covered |
| 7. Shortlist Approval (HITL) | ✅ Covered |
| 8. Contact Enrichment | ⚠️ Partial (scaffolded, not productionized) |
| 9. Personalized Outreach | ✅ Covered |
| 10. Interview Scheduling | ✅ Covered |
| 11. Interview Preparation (RAG) | ✅ Covered |
| 12. Technical Assessment | ✅ Covered |
| 13. Interview Summary & Analysis | ✅ Covered |
| 14. Decision Support & HITL Decision | ✅ Covered |
| 15. Acceptance/Rejection Feedback | ✅ Covered |
| 16. Individual Development Plan (IDP) | ✅ Covered |

**Partial Areas:**
- **Anonymization**: Covers name/photo removal; deeper attribute anonymization (e.g., university name, company) is future work
- **Contact Enrichment**: Architecture scaffolded via MCP but not deployed to production data sources

**Coverage Score: 15/16 = 93.75%**

*Layout: Two-column table with green checkmarks and yellow warning icons. Large percentage at the bottom in a highlighted callout. Clean and data-driven.*

> **Speaker Notes**: "PATHS covers 15 out of 16 recruitment stages, which is 93.75% coverage. The only stage that's partially covered is contact enrichment — the architecture is scaffolded through the Model Context Protocol, but it's not connected to production data sources yet. Anonymization is implemented but currently covers basic fields like names and photos. Deeper attribute anonymization — like hiding university or company names — is planned as future work. Every other stage, from job posting through individual development plans, is fully functional."

---

## Slide 10 — Result 2: Testing Results

### Functional Correctness: Near-Perfect Pass Rates

**End-to-End Testing (Playwright)**

| Metric | Result |
|---|---|
| Total E2E Scenarios | **48** |
| Passed | **48** |
| Failed | **0** |
| **Pass Rate** | **100%** ✅ |

**Backend Testing (pytest)**

| Metric | Result |
|---|---|
| Total Backend Tests | **174** |
| Passed | **168** |
| Failed | **6** |
| **Pass Rate** | **96.6%** ✅ |

```
[DIAGRAM: Two large circular progress indicators side by side]

   ┌─────────────────┐        ┌─────────────────┐
   │   E2E TESTS     │        │  BACKEND TESTS  │
   │                  │        │                  │
   │     100%         │        │     96.6%        │
   │    48 / 48       │        │   168 / 174      │
   │                  │        │                  │
   │   Playwright     │        │     pytest       │
   └─────────────────┘        └─────────────────┘
```

**What the 6 failed backend tests cover:**
- Edge cases in concurrent assessment submissions
- Timing-sensitive scheduling operations
- Non-critical and documented for future fixes

*Layout: Two large donut/circle charts dominating the slide — one for E2E (green, 100%) and one for Backend (green, 96.6%). Numbers large and bold. Brief note about the 6 failures below.*

> **Speaker Notes**: "Our testing results show strong functional correctness. All 48 end-to-end test scenarios passed using Playwright — that's a 100% pass rate covering the full user journey from job creation to hiring decisions. On the backend, 168 out of 174 pytest tests passed, giving us 96.6%. The 6 failures are edge cases in concurrent submissions and timing-sensitive operations — they're documented and non-critical."

---

## Slide 11 — Result 3: AI/RAG/Generated Output Quality

### AI Quality Metrics

**RAG Retrieval Performance:**

| Metric | Score |
|---|---|
| **Hit Rate @ 5** | **100%** — every query found relevant context in top 5 |
| **Top-1 Relevance** | **87.5%** — the #1 retrieved document was relevant 87.5% of the time |
| **MRR (Mean Reciprocal Rank)** | **0.9375** |
| **NDCG @ 5** | **0.9575** |

**Generated Output Quality (Overall):**

| Output Type | Quality Score |
|---|---|
| Outreach messages | High — personalized and contextually grounded |
| Interview questions | High — role-specific and rubric-aligned |
| Assessment content | High — appropriate difficulty and coverage |
| Decision summaries | High — structured with evidence |
| **Overall Generation Quality** | **88.6%** |

```
[DIAGRAM: Bar chart showing metrics]

Hit Rate@5      ████████████████████ 100%
NDCG@5          ███████████████████  95.75%
MRR             ███████████████████  93.75%
Top-1 Relevance ██████████████████   87.5%
Gen. Quality    ██████████████████   88.6%
```

*Layout: Metrics table at top. Horizontal bar chart visualization in the center. Key insight callout at the bottom.*

> **Speaker Notes**: "Our RAG system performs very well. Hit Rate at 5 is 100% — meaning every query found relevant context within the top 5 retrieved documents. The top-1 relevance is 87.5%, and our NDCG score is 0.9575, indicating strong ranking quality. For generated outputs — including outreach messages, interview questions, assessments, and decision summaries — the overall quality score is 88.6%. These outputs are not generic; they're grounded in actual company knowledge and candidate evidence through RAG."

---

## Slide 12 — Discussion: Why PATHS Is Different

### Not Just an ATS. Not Just an Assessment Tool.

**What existing tools do (in isolation):**

| Tool Type | What It Does | What It Misses |
|---|---|---|
| **ATS** (Greenhouse, Workable) | Track applications | No sourcing, no AI evaluation, no development |
| **Sourcing** (SeekOut, LinkedIn Recruiter) | Find candidates | No evaluation, no scheduling, no decisions |
| **Assessment** (HackerRank, Codility) | Test technical skills | No profile context, no outreach, no growth plans |
| **Chatbot** (Paradox/Olivia) | Automate Q&A | No deep evaluation, no decision support |
| **Talent CRM** (Beamery) | Manage talent pools | Complex, expensive, enterprise-only |

**What PATHS does differently:**

```
[DIAGRAM: Bridge diagram]

   Sourcing ──────┐
                   │
   Evaluation ─────┼──── PATHS ────── Unified, AI-driven,
                   │                   evidence-based,
   Decision ───────┤                   human-controlled
                   │
   Development ────┘
```

**PATHS connects what others keep separate:**
- ✅ Sourcing intelligence feeds into evaluation context
- ✅ Evaluation evidence feeds into decision support
- ✅ Decision outcomes feed into development plans
- ✅ All grounded by a shared knowledge graph and RAG

*Layout: Comparison table at top. Bridging diagram in the center showing PATHS connecting the 4 pillars. Key differentiators as bullet points below.*

> **Speaker Notes**: "This is why PATHS is fundamentally different. Existing tools solve pieces of the puzzle but not the whole thing. An ATS tracks applications but doesn't source or evaluate. A sourcing tool finds candidates but doesn't assess them. An assessment platform tests skills but has no context about the candidate's full profile. PATHS connects sourcing, evaluation, decision support, and development into one unified system. Sourcing intelligence feeds directly into evaluation context. Evaluation evidence feeds into the decision packet. And decision outcomes — whether hire or reject — feed into individual development plans. This is possible because all components share the same knowledge graph and RAG infrastructure."

---

## Slide 13 — Discussion: Strengths

### Key Strengths of PATHS

**1. 🔄 Unified End-to-End Workflow**
- Single platform replacing 4–6 disconnected tools
- No manual handoffs or data re-entry
- One candidate profile across the entire lifecycle

**2. 📊 Explainable, Evidence-Based Scoring**
- Every score backed by CV/GitHub/portfolio evidence
- Hybrid scoring: content similarity + graph signals
- Confidence ratings and textual rationale for every ranking

**3. 👤 Human-in-the-Loop at Critical Points**
- Shortlist approval before outreach
- De-anonymization requires approval
- Final hiring decision is always human
- AI augments — never replaces — human judgment

**4. 📋 Full Auditability**
- Structured audit logs for every action
- Decision trails from sourcing through hiring
- Supports compliance with data protection requirements

**5. 🎓 Post-Hire Development Plans**
- Evaluation insights converted to growth pathways
- Skill gap analysis → learning recommendations
- Rejected candidates also receive development feedback
- Supports long-term retention (targeting >90% at 18 months)

*Layout: 5 strength cards in a single column or 2+3 grid. Each with an icon, bold title, and 2–3 bullet points. Use subtle gradient backgrounds per card.*

> **Speaker Notes**: "Let me highlight five key strengths. First, the unified workflow — one platform replaces multiple disconnected tools. Second, every score is explainable with evidence backing. Third, humans remain in control at every critical checkpoint. Fourth, full auditability — every action is logged and traceable. And fifth, the development plan feature — this is unique to PATHS. We don't just hire or reject; we convert evaluation insights into growth pathways. Even rejected candidates receive actionable development feedback. This supports long-term retention by ensuring new hires come in with clear growth plans."

---

## Slide 14 — Limitations + Risks

### Honest Assessment of Current Limitations

| Category | Limitation | Impact | Mitigation |
|---|---|---|---|
| **Performance** | LLM inference latency | Longer wait times for AI-generated outputs | Async processing, caching, model quantization |
| **Tuning** | Scoring threshold sensitivity | Threshold changes can shift shortlist composition | Calibration with recruiter feedback loops |
| **Data Quality** | CV/profile data variability | Inconsistent or incomplete input affects scoring | Multi-source fusion, validation checks |
| **Deduplication** | Duplicate candidate detection | Same person may appear with different data | Entity resolution implemented; edge cases remain |
| **Deployment** | Resource-intensive infrastructure | Requires significant compute (LLM, vector DB) | Docker containerization, cloud scaling path |
| **Bias/Fairness** | LLM may encode biases | Risk of unfair outcomes despite guardrails | Anonymization, fairness rubrics, HITL oversight |
| **Integration** | OAuth/external API limitations | LinkedIn, Calendar, Gmail integration complexity | MCP architecture designed for extensibility |

**Key Risks Acknowledged:**
- ⚠️ LLM hallucination risk (mitigated by RAG grounding)
- ⚠️ Scoring model is not yet calibrated on large-scale production data
- ⚠️ Anonymization is basic (name/photo); deeper demographic masking needed
- ⚠️ System not yet tested under high-concurrency production load

*Layout: Clean limitation table dominating the slide. Risk callouts at the bottom with warning icons. Honest and professional tone.*

> **Speaker Notes**: "We want to be transparent about limitations. LLM inference latency means some operations take longer than ideal — we mitigate this with async processing and caching. Scoring thresholds are sensitive and need calibration with real recruiter feedback. CV data quality varies widely and affects scoring accuracy. Duplicate detection works but has edge cases. Deployment is resource-intensive. And while we have bias guardrails, LLMs can encode biases that our anonymization may not fully catch. These are documented limitations with clear mitigation paths."

---

## Slide 15 — Future Work + Final Conclusion

### Roadmap & Conclusion

**Strategic Development Roadmap:**

| Horizon | Timeline | Focus Areas |
|---|---|---|
| 🔵 **Short Term** | 0–6 months | • Improve UI/UX polish and error handling |
| | | • Scoring calibration with recruiter feedback |
| | | • Deeper anonymization (university, company) |
| | | • Performance optimization (caching, model quantization) |
| 🟢 **Medium Term** | 6–18 months | • ATS integration (Greenhouse, Workable, BambooHR) |
| | | • Calendar + email automation (Google, Outlook) |
| | | • Advanced analytics dashboard |
| | | • Multi-language support for MENA markets |
| 🟣 **Long Term** | 18+ months | • Enterprise talent intelligence platform |
| | | • Predictive analytics (turnover risk, team fit) |
| | | • Internal mobility and succession planning |
| | | • White-label SaaS deployment model |

---

### Conclusion

> **PATHS demonstrates that an integrated, AI-driven hiring system can unify the entire recruitment lifecycle — from sourcing through development — while maintaining fairness, explainability, and human control.**

**Key Takeaways:**
- ✅ **93.75%** process coverage across 16 recruitment stages
- ✅ **100%** end-to-end test pass rate (Playwright)
- ✅ **96.6%** backend test pass rate (pytest)
- ✅ **100%** RAG Hit Rate @ 5
- ✅ **88.6%** overall generated output quality
- ✅ Human-in-the-loop at every critical decision
- ✅ Development plans for hired AND rejected candidates

**PATHS transforms recruitment from a fragmented, reactive process into a strategic, AI-augmented, evidence-based talent acquisition system.**

---

### Thank You

**Questions?**

| | Contact |
|---|---|
| 📧 | [Team email / university email] |
| 🔗 | [GitHub repository link] |
| 📄 | [Full report reference] |

*Layout: Roadmap table at the top (use colored timeline). Conclusion box with key metrics. Large "Thank You" with team names and contact info at the bottom. Professional dark gradient background.*

> **Speaker Notes**: "Looking forward, our short-term focus is on UI polish, scoring calibration, and deeper anonymization. In the medium term, we plan to integrate with production ATS systems, calendar, and email. Long-term, PATHS can evolve into an enterprise talent intelligence platform with predictive analytics and internal mobility features. In conclusion, PATHS demonstrates that it's possible to unify the entire recruitment lifecycle with AI while maintaining fairness, explainability, and human control. Our results show strong coverage at 93.75%, perfect end-to-end test pass rates, and 88.6% AI output quality. Thank you — we're happy to take questions."

---

## Appendix: Design Tips for PowerPoint/Google Slides

### Recommended Slide Design:
- **Color Palette**: Dark navy (#0F172A) background with blue (#3B82F6) and teal (#14B8A6) accents
- **Font**: Inter or Outfit for headings, regular weight for body text
- **Slide dimensions**: 16:9 widescreen
- **Animations**: Subtle fade-in for bullet points, none for diagrams
- **Consistency**: Use the same header style and accent color on every slide

### Icon Sources (Free):
- [Heroicons](https://heroicons.com/)
- [Phosphor Icons](https://phosphoricons.com/)
- [Lucide](https://lucide.dev/)

### Diagram Recreation Priority (most visual impact):
1. **Slide 5** — End-to-End Workflow (most important, invest time here)
2. **Slide 6** — System Architecture (layered diagram)
3. **Slide 7** — AI Components (hub-and-spoke agent diagram)
4. **Slide 10** — Testing Results (donut charts)
5. **Slide 11** — RAG Metrics (bar chart)
