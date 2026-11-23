import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Level } from "@/lib/api";

const LEVEL: Record<Level, string> = {
  low: "border-border text-muted-foreground",
  medium: "border-amber/40 text-amber",
  high: "border-danger/50 text-danger",
};

export function LevelBadge({ label, level }: { label: string; level: Level | null }) {
  if (!level) return <span className="font-mono text-xs text-muted-foreground">-</span>;
  return (
    <Badge variant="outline" className={cn("font-mono text-[11px] font-normal", LEVEL[level])}>
      {label} {level}
    </Badge>
  );
}

export function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[13px]", className)}>{children}</span>;
}

/** Terminal-style block for commands and quoted test output. */
export function Terminal({ title, children, tone }: { title?: string; children: React.ReactNode; tone?: "fail" | "pass" }) {
  return (
    <div className="overflow-hidden rounded-md border border-border bg-[#101a17]">
      {title && (
        <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
          <span className="text-sage">&gt;_</span>
          {title}
        </div>
      )}
      <pre
        className={cn(
          "overflow-x-auto px-3 py-2 font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap break-words",
          tone === "fail" && "text-danger",
          tone === "pass" && "text-sage",
        )}
      >
        {children}
      </pre>
    </div>
  );
}

export function Section({ eyebrow, title, children }: { eyebrow: string; title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="mb-2 font-mono text-xs text-sage">{eyebrow}</div>
      <h2 className="font-serif text-3xl leading-tight text-foreground">{title}</h2>
      {children && <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{children}</p>}
    </div>
  );
}
