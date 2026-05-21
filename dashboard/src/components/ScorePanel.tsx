import type { JSX } from "react";
import type { ScoreVector } from "../api/client";
import { cn } from "../lib/cn";

const AXES = [
  { key: "accuracy", label: "Accuracy" },
  { key: "speed", label: "Speed" },
  { key: "safety", label: "Safety" },
  { key: "optimal_track", label: "Optimal track" },
  { key: "energy_efficiency", label: "Energy" },
  { key: "trajectory_stability", label: "Trajectory" },
] as const;

interface Props {
  score: ScoreVector;
  animate?: boolean;
}

export function ScorePanel({ score, animate }: Props): JSX.Element {
  const tone = verdictTone(score.verdict);
  return (
    <div
      className={cn(
        "border border-rule bg-surface p-6",
        animate && "verdict-pulse",
        animate && tone === "fail" && "verdict-pulse--fail",
      )}
      style={{ viewTransitionName: "score-panel" }}
    >
      <div className="flex items-end justify-between gap-4 border-b border-dashed border-rule pb-4">
        <div>
          <p className="label-eyebrow">Konnex ScoreVector</p>
          <p
            className={cn(
              "mt-1 font-display score-number tabular",
              tone === "ok" && "score-number--success",
              tone === "fail" && "score-number--failure",
              tone === "warn" && "score-number--inconclusive",
            )}
          >
            {score.final_pct}
          </p>
        </div>
        <span
          className={cn(
            "pill",
            score.verdict === "success" && "pill--success",
            score.verdict === "failure" && "pill--failure",
            score.verdict === "inconclusive" && "pill--inconclusive",
          )}
          style={{ viewTransitionName: "verdict" }}
        >
          {score.verdict}
        </span>
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        {AXES.map(({ key, label }) => {
          const value = score[key];
          return (
            <li key={key} className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-label uppercase text-subtext">
                {label}
              </span>
              <span
                className={cn(
                  "font-display text-title tabular font-medium",
                  value >= 80 && "text-verified",
                  value > 30 && value < 80 && "text-signal-deep",
                  value <= 30 && "text-rejected",
                )}
              >
                {value}
              </span>
            </li>
          );
        })}
      </ul>
      {score.reasoning && (
        <p className="mt-4 border-t border-dashed border-rule pt-4 text-small text-subtext">
          {truncateReasoning(score.reasoning)}
        </p>
      )}
    </div>
  );
}

function truncateReasoning(text: string): string {
  // Same joint-violation collapse as StageRow.
  const jointMatch = text.match(/torque\[\d+\]\.joint\[\d+\]=[\d.]+ exceeds \|limit\|=([\d.]+)/g);
  if (jointMatch && jointMatch.length > 1) {
    const limit = text.match(/\|limit\|=([\d.]+)/)?.[1] ?? "320.0";
    const prefix = text.split("torque[")[0] ?? "";
    return `${prefix}${jointMatch.length} joints exceed ${limit} N·m limit`;
  }
  if (text.length <= 120) return text;
  return text.slice(0, 120) + "…";
}

function verdictTone(v: ScoreVector["verdict"]): "ok" | "warn" | "fail" {
  if (v === "success") return "ok";
  if (v === "inconclusive") return "warn";
  return "fail";
}
