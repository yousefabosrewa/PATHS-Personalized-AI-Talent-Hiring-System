import { cn } from "@/lib/utils/cn";

interface PathsWordmarkProps {
  /** "nav" = compact bar logo | "hero" = full hero display | "footer" = medium footer */
  variant?: "nav" | "hero" | "footer";
  /** Tailwind className override */
  className?: string;
}

/**
 * PATHS brand wordmark.
 * "nav"    — single-line "PATHS" at nav scale (~32 px cap height).
 * "hero"   — full-sized display logo with tagline, 180–220 px cap height.
 * "footer" — medium size with tagline.
 */
export function PathsWordmark({ variant = "nav", className }: PathsWordmarkProps) {
  if (variant === "nav") {
    return (
      <span
        className={cn(
          "font-display select-none text-[28px] font-light leading-none tracking-[0.06em] text-foreground",
          className,
        )}
        aria-label="PATHS"
      >
        PATHS
      </span>
    );
  }

  /* hero / footer — full wordmark with "NEXT … GENERATION RECRUITMENT" tagline */
  const isHero = variant === "hero";

  return (
    <div
      className={cn("flex select-none flex-col items-start", className)}
      aria-label="PATHS — Next Generation Recruitment"
    >
      <span
        className={cn(
          "font-display font-light leading-none tracking-[0.06em] text-foreground",
          isHero
            ? "text-[clamp(64px,14vw,200px)]"
            : "text-[48px]",
        )}
      >
        PATHS
      </span>

      {/* Thin divider line that spans the full wordmark width */}
      <div
        className={cn(
          "w-full border-t border-foreground/20",
          isHero ? "mt-3 mb-2" : "mt-2 mb-1.5",
        )}
      />

      {/* Tagline row */}
      <div
        className={cn(
          "flex w-full items-center justify-between font-sans font-light tracking-[0.38em] text-foreground/55",
          isHero ? "text-[11px] sm:text-[13px]" : "text-[9px]",
        )}
      >
        <span>NEXT</span>
        <span>GENERATION RECRUITMENT</span>
      </div>
    </div>
  );
}
