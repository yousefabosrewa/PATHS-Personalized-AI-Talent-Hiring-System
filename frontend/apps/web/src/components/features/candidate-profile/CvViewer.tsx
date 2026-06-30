"use client";

import { Briefcase, GraduationCap, Wrench, Award } from "lucide-react";
import type { CandidateDetail } from "@/types";

interface Props {
  cv: CandidateDetail["cv"];
}

function SectionTitle({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
    </div>
  );
}

export function CvViewer({ cv }: Props) {
  return (
    <div className="space-y-6">
      {/* Experience */}
      {cv.experience.length > 0 && (
        <section>
          <SectionTitle icon={Briefcase} title="Experience" />
          <div className="space-y-4">
            {cv.experience.map((exp, i) => (
              <div key={i} className="relative pl-4 border-l-2 border-border">
                <p className="font-medium text-sm">{exp.title}</p>
                <p className="text-xs text-muted-foreground">{exp.company}</p>
                {(exp.startDate || exp.endDate) && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {exp.startDate ?? "?"} – {exp.endDate ?? "Present"}
                  </p>
                )}
                {exp.description && (
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed line-clamp-3">
                    {exp.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Education */}
      {cv.education.length > 0 && (
        <section>
          <SectionTitle icon={GraduationCap} title="Education" />
          <div className="space-y-3">
            {cv.education.map((edu, i) => (
              <div key={i} className="pl-4 border-l-2 border-border">
                <p className="font-medium text-sm">{edu.institution}</p>
                {edu.degree && (
                  <p className="text-xs text-muted-foreground">
                    {edu.degree}{edu.field ? `, ${edu.field}` : ""}
                    {edu.graduationYear ? ` · ${edu.graduationYear}` : ""}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Skills */}
      {cv.skills.length > 0 && (
        <section>
          <SectionTitle icon={Wrench} title="Skills" />
          <div className="flex flex-wrap gap-1.5">
            {cv.skills.map((s) => (
              <span
                key={s.skillId}
                className="inline-flex items-center rounded-md border border-border bg-muted px-2 py-0.5 text-xs"
              >
                {s.skillId}
                {s.proficiency != null && (
                  <span className="ml-1 text-muted-foreground">·{s.proficiency}</span>
                )}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Certifications */}
      {cv.certifications.length > 0 && (
        <section>
          <SectionTitle icon={Award} title="Certifications" />
          <div className="space-y-1.5">
            {cv.certifications.map((cert, i) => (
              <div key={i} className="text-xs">
                <span className="font-medium">{cert.name}</span>
                {cert.issuer && (
                  <span className="text-muted-foreground"> · {cert.issuer}</span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
