import type { JSX } from "react";
import type { StageResult } from "../api/client";
import { cn } from "../lib/cn";

interface StageRowProps {
  stages: StageResult[];
  expected?: string[];
}

const _STAGE_NAMES = [
  "signature",
  "temporal",
  "crossmodal",
  "replay",
  "anomaly",
  "kinematic",
] as const;

const STAGE_LABELS: Record<string, string> = {
  signature: "01 — Signature",
  temporal: "02 — Temporal",
  crossmodal: "03 — Cross-modal",
  replay: "04 — Replay",
  anomaly: "05 — Anomaly",
  kinematic: "06 — Kinematic",
};

export function StageRow({ stages, expected = [..._STAGE_NAMES] }: StageRowProps): JSX.Element {
  const byName = new Map(stages.map((s) => [s.name, s]));
  return (
    <div
      className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6"
      style={{ viewTransitionName: "stage-cascade" }}
    >
      {expected.map((name) => {
        const stage = byName.get(name);
        return <StageTile key={name} name={name} stage={stage} />;
      })}
    </div>
  );
}

function StageTile({
  name,
  stage,
}: {
  name: string;
  stage: StageResult | undefined;
}): JSX.Element {
  const tone = !stage
    ? "idle"
    : stage.severity === "fail"
      ? "fail"
      : stage.severity === "warning"
        ? "warning"
        : "ok";

  return (
    <div
      className={cn(
        "stage-tile animate-rise",
        tone === "idle" && "border-dashed opacity-50",
        tone === "fail" && "stage-tile--fail",
        tone === "ok" && "stage-tile--ok",
        tone === "warning" && "stage-tile--warning",
      )}
      style={{ animationDelay: `${cascadeDelay(name)}ms` }}
    >
      <div className="flex items-center justify-between">
        <span className="label-eyebrow">{STAGE_LABELS[name] ?? name}</span>
        <Dot tone={tone} />
      </div>
      <p
        className={cn(
          "min-h-[3rem] text-small leading-snug",
          tone === "idle" && "text-subtext",
          tone === "fail" && "text-rejected",
          tone === "ok" && "text-ink",
          tone === "warning" && "text-signal-deep",
        )}
      >
        {stage ? truncateDetail(stage.detail) : "—"}
      </p>
    </div>
  );
}

function Dot({ tone }: { tone: "idle" | "ok" | "warning" | "fail" }): JSX.Element {
  const styles = {
    idle: "bg-rule-strong",
    ok: "bg-verified shadow-[0_0_6px_var(--color-verified-glow)]",
    warning: "bg-signal shadow-[0_0_6px_var(--color-signal-glow)]",
    fail: "bg-rejected shadow-[0_0_6px_var(--color-rejected-glow)]",
  }[tone];
  return <span className={cn("size-2.5 rounded-full transition-all duration-300", styles)} aria-hidden />;
}

function cascadeDelay(name: string): number {
  const index = _STAGE_NAMES.indexOf(name as (typeof _STAGE_NAMES)[number]);
  return Math.max(0, index) * 70;
}

const MAX_DETAIL_LEN = 80;

function truncateDetail(detail: string): string {
  // Collapse repetitive joint violations into a summary.
  const jointMatch = detail.match(/torque\[\d+\]\.joint\[\d+\]=[\d.]+ exceeds \|limit\|=([\d.]+)/g);
  if (jointMatch && jointMatch.length > 1) {
    const limit = detail.match(/\|limit\|=([\d.]+)/)?.[1] ?? "320.0";
    return `${jointMatch.length} joints exceed ${limit} N·m limit`;
  }
  // Humanize temporal failure: "camera[1] timestamp_ns=X not after prev=Y"
  const temporalMatch = detail.match(/(\w+)\[\d+\] timestamp_ns=\d+ not after prev=\d+/);
  if (temporalMatch) {
    const channel = temporalMatch[1];
    return `${channel} timestamps out of order (non-monotonic)`;
  }
  if (detail.length <= MAX_DETAIL_LEN) return detail;
  return detail.slice(0, MAX_DETAIL_LEN) + "…";
}
