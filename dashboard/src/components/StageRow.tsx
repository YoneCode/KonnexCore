import type { JSX } from "react";
import type { StageResult } from "../api/client";
import { cn } from "../lib/cn";

interface StageRowProps {
  stages: StageResult[];
  /** Optional placeholder names to render in greyed-out state when stages haven't run yet. */
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
  // Map runtime stage results onto the expected canonical order. Stages
  // that haven't run yet (early-exit) render greyed-out.
  const byName = new Map(stages.map((s) => [s.name, s]));
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
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
        tone === "idle" && "border-dashed opacity-60",
        tone === "fail" && "border-rejected",
        tone === "warning" && "border-signal",
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
          tone === "idle" ? "text-subtext" : "text-ink",
        )}
      >
        {stage ? stage.detail : "not reached"}
      </p>
    </div>
  );
}

function Dot({ tone }: { tone: "idle" | "ok" | "warning" | "fail" }): JSX.Element {
  const colour = {
    idle: "bg-rule-strong",
    ok: "bg-verified",
    warning: "bg-signal",
    fail: "bg-rejected",
  }[tone];
  return <span className={cn("size-2 rounded-full", colour)} aria-hidden />;
}

function cascadeDelay(name: string): number {
  const index = _STAGE_NAMES.indexOf(name as (typeof _STAGE_NAMES)[number]);
  return Math.max(0, index) * 70;
}
