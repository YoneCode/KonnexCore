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
}

export function ScorePanel({ score }: Props): JSX.Element {
  const tone = verdictTone(score.verdict);
  return (
    <div className="border border-rule bg-surface p-6">
      <div className="flex items-end justify-between gap-4 border-b border-dashed border-rule pb-4">
        <div>
          <p className="label-eyebrow">Konnex ScoreVector</p>
          <p className="mt-1 font-display text-display-md font-light text-ink tabular">
            {score.final_pct}
            <span className="ml-1 text-subtext">/100</span>
          </p>
        </div>
        <span
          className={cn(
            "pill",
            tone === "ok" && "border-verified text-verified",
            tone === "fail" && "border-rejected text-rejected",
            tone === "warn" && "border-signal text-signal-deep",
          )}
        >
          {score.verdict}
        </span>
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
        {AXES.map(({ key, label }) => (
          <li key={key} className="flex items-baseline justify-between gap-3">
            <span className="font-mono text-label uppercase text-subtext">
              {label}
            </span>
            <span className="text-body tabular">{score[key]}</span>
          </li>
        ))}
      </ul>
      {score.reasoning && (
        <p className="mt-4 border-t border-dashed border-rule pt-4 text-small text-subtext">
          {score.reasoning}
        </p>
      )}
    </div>
  );
}

function verdictTone(v: ScoreVector["verdict"]): "ok" | "warn" | "fail" {
  if (v === "success") return "ok";
  if (v === "inconclusive") return "warn";
  return "fail";
}
