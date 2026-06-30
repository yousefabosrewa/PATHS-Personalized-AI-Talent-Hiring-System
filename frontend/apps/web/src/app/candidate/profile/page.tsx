"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  Edit2, MapPin, Mail, Phone, ExternalLink,
  Globe, GraduationCap, Briefcase, Code2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCandidateProfile } from "@/lib/hooks";
import { createEmptyCandidateProfile } from "@/lib/candidate/portal-profile";

// Display-only casing for skill chips. Skills are stored normalized
// (lowercase) for matching / dedup; this just makes them read nicely.
const SKILL_DISPLAY: Record<string, string> = {
  "aws": "AWS", "gcp": "GCP", "sql": "SQL", "nlp": "NLP", "css": "CSS",
  "html": "HTML", "api": "API", "rest api": "REST API", "ci/cd": "CI/CD",
  "c++": "C++", "c#": "C#", ".net": ".NET", "php": "PHP", "ml": "ML",
  "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB",
  "sqlite": "SQLite", "graphql": "GraphQL", "javascript": "JavaScript",
  "typescript": "TypeScript", "fastapi": "FastAPI", "tensorflow": "TensorFlow",
  "pytorch": "PyTorch", "node.js": "Node.js", "next.js": "Next.js",
  "scikit-learn": "scikit-learn", "github": "GitHub", "gitlab": "GitLab",
  "numpy": "NumPy", "opencv": "OpenCV", "neo4j": "Neo4j", "power bi": "Power BI",
};

function prettySkill(raw: string): string {
  const k = (raw || "").trim().toLowerCase();
  if (SKILL_DISPLAY[k]) return SKILL_DISPLAY[k];
  return (raw || "")
    .trim()
    .split(/\s+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

export default function CandidateProfilePage() {
  const { data: profile = createEmptyCandidateProfile() } = useCandidateProfile();

  return (
    <div className="min-h-screen px-6 py-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 flex items-start justify-between gap-4 flex-wrap"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold text-foreground">My Profile</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Keep your profile up to date for better job matches.
            </p>
          </div>
          <Button size="sm" className="gap-2 glow-blue" asChild>
            <Link href="/candidate/profile/edit">
              <Edit2 className="h-3.5 w-3.5" /> Edit Profile
            </Link>
          </Button>
        </motion.div>

        <div className="space-y-5">
          {/* Identity card */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass gradient-border rounded-2xl p-7"
          >
            <div className="flex items-start gap-5 flex-wrap">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary/20 font-heading text-2xl font-bold text-primary">
                {profile.fullName.charAt(0) || "C"}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="font-heading text-xl font-bold text-foreground">
                  {profile.fullName || "Your name"}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {profile.currentTitle || "—"}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary text-[11px] capitalize">
                    {profile.careerLevel}
                  </Badge>
                  <Badge variant="outline" className="text-[11px] text-muted-foreground">
                    {profile.yearsExperience} yrs experience
                  </Badge>
                  {profile.locationText && (
                    <Badge variant="outline" className="text-[11px] text-muted-foreground flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {profile.locationText}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {profile.summary && (
              <p className="mt-5 text-[13px] leading-relaxed text-muted-foreground">
                {profile.summary}
              </p>
            )}

            {/* Contact */}
            <div className="mt-5 flex flex-wrap gap-4 text-xs text-muted-foreground">
              {profile.email && (
                <span className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5" />{profile.email}</span>
              )}
              {(profile.otherEmails ?? []).map((em) => (
                <span key={em} className="flex items-center gap-1.5 text-muted-foreground/70" title="Other email address">
                  <Mail className="h-3.5 w-3.5" />{em}
                </span>
              ))}
              {profile.phone && (
                <span className="flex items-center gap-1.5"><Phone className="h-3.5 w-3.5" />{profile.phone}</span>
              )}
              {profile.links.linkedin && (
                <a href={profile.links.linkedin} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-primary hover:underline"><ExternalLink className="h-3.5 w-3.5" />LinkedIn</a>
              )}
              {profile.links.github && (
                <a href={profile.links.github} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-primary hover:underline"><ExternalLink className="h-3.5 w-3.5" />GitHub</a>
              )}
              {profile.links.portfolio && (
                <a href={profile.links.portfolio} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-primary hover:underline"><Globe className="h-3.5 w-3.5" />Portfolio</a>
              )}
            </div>
          </motion.div>

          {/* Skills */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass rounded-2xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <Code2 className="h-4 w-4 text-primary" />
              <h3 className="font-heading text-sm font-bold text-foreground">Skills</h3>
            </div>
            {profile.skills.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No skills added yet.{" "}
                <Link href="/candidate/profile/edit" className="text-primary hover:underline">Add skills</Link>
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {profile.skills.map((sk) => (
                  <span
                    key={sk.id}
                    className="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-[11px] font-medium text-foreground"
                  >
                    {prettySkill(sk.name)}
                  </span>
                ))}
              </div>
            )}
          </motion.div>

          {/* Experience */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass rounded-2xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <Briefcase className="h-4 w-4 text-primary" />
              <h3 className="font-heading text-sm font-bold text-foreground">Experience</h3>
            </div>
            {profile.experiences.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No experience added yet.{" "}
                <Link href="/candidate/profile/edit" className="text-primary hover:underline">Add experience</Link>
              </p>
            ) : (
              <div className="space-y-4">
                {profile.experiences.map((exp) => (
                  <div key={exp.id} className="border-l-2 border-primary/20 pl-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-foreground">{exp.title}</p>
                      {exp.isCurrent && (
                        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-400">Current</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {exp.companyName}{exp.location ? ` · ${exp.location}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground/60">
                      {exp.startDate || "—"} – {exp.isCurrent ? "Present" : exp.endDate ?? "—"}
                    </p>
                    {exp.description && (
                      <p className="mt-1.5 text-[13px] text-muted-foreground leading-relaxed">{exp.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Education */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass rounded-2xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <GraduationCap className="h-4 w-4 text-primary" />
              <h3 className="font-heading text-sm font-bold text-foreground">Education</h3>
            </div>
            {profile.education.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No education added yet.{" "}
                <Link href="/candidate/profile/edit" className="text-primary hover:underline">Add education</Link>
              </p>
            ) : (
              <div className="space-y-3">
                {profile.education.map((edu) => (
                  <div key={edu.id} className="border-l-2 border-primary/20 pl-4">
                    <p className="text-sm font-semibold text-foreground">
                      {edu.degree || "Degree"}{edu.fieldOfStudy ? ` · ${edu.fieldOfStudy}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {edu.institution} · {edu.startYear ?? "—"}–{edu.isOngoing ? "Present" : edu.endYear ?? "—"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Job Preferences */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="glass rounded-2xl p-6"
          >
            <h3 className="font-heading text-sm font-bold text-foreground mb-4">Job Preferences</h3>
            {profile.preferences.jobTypes.length === 0 &&
            profile.preferences.workplaceTypes.length === 0 &&
            profile.preferences.desiredRoles.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No preferences set yet.{" "}
                <Link href="/candidate/profile/edit" className="text-primary hover:underline">Set preferences</Link>
              </p>
            ) : (
              <div className="space-y-3 text-sm text-muted-foreground">
                {(profile.preferences.jobTypes.length > 0 ||
                  profile.preferences.workplaceTypes.length > 0) && (
                  <div className="flex flex-wrap gap-1.5">
                    {profile.preferences.jobTypes.map((t) => (
                      <span key={t} className="evidence-pill capitalize">{t.replace(/_/g, " ")}</span>
                    ))}
                    {profile.preferences.workplaceTypes.map((t) => (
                      <span key={t} className="evidence-pill capitalize">{t}</span>
                    ))}
                  </div>
                )}
                {profile.preferences.desiredRoles.length > 0 && (
                  <p>Desired roles: {profile.preferences.desiredRoles.join(", ")}</p>
                )}
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
