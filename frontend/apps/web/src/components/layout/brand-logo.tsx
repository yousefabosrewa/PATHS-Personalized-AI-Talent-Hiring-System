import { cn } from "@/lib/utils/cn";

/**
 * The PATHS brand logo. Single source of truth so every surface (org sidebar,
 * candidate portal, landing page, auth) renders the same asset consistently.
 * Pass height/width via `className` (e.g. "h-14 w-auto max-w-[200px]").
 */
export function BrandLogo({
  className,
  alt = "PATHS — Personalized AI Talent Hiring System",
}: {
  className?: string;
  alt?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/paths-logo.png"
      alt={alt}
      draggable={false}
      className={cn("object-contain select-none", className)}
    />
  );
}
