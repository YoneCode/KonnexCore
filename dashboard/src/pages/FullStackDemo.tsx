import type { JSX } from "react";
import { useEffect, useState } from "react";
import {
  type DemoRunResult,
  type DemoScenario,
  api,
} from "../api/client";
import { ScorePanel } from "../components/ScorePanel";
import { StageRow } from "../components/StageRow";
import { cn } from "../lib/cn";

export function FullStackDemo(): JSX.Element {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [active, setActive] = useState<DemoScenario["key"]>("clean");
  const [result, setResult] = useState<DemoRunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.demo
      .scenarios(ctrl.signal)
      .then(setScenarios)
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(`scenarios: ${String(e)}`);
      });
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    api.demo
      .fullStack({ scenario: active }, ctrl.signal)
      .then((r) => {
        setResult(r);
        setLoading(false);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) {
          setError(String(e));
          setLoading(false);
        }
      });
    return () => ctrl.abort();
  }, [active]);

  const expectedFailure = result?.expected_stage ?? null;

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16">
      <header className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <p className="label-eyebrow">End-to-end demo</p>
          <h1 className="mt-4 font-display text-display-lg font-light tracking-tight text-ink">
            Capture, sign, verify
            <br />
            <span className="font-bold italic text-signal-deep">
              under attack.
            </span>
          </h1>
          <p className="mt-6 max-w-[60ch] text-body text-subtext">
            One scenario at a time. RootID signs, DetVerify scores. The
            adversarial scenarios pass naive structural validation but each
            falls at a precisely-named stage.
          </p>
        </div>
      </header>

      <section className="mt-12 flex flex-wrap items-center gap-2 border-b border-dashed border-rule pb-6">
        {scenarios.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setActive(s.key)}
            className={cn(
              "border px-3 py-2 font-mono text-label uppercase tracking-wider transition-colors duration-200 ease-out-quart",
              active === s.key
                ? "border-ink bg-ink text-paper"
                : "border-rule bg-paper text-subtext hover:border-ink hover:text-ink",
            )}
          >
            {s.title}
          </button>
        ))}
      </section>

      {error && (
        <p className="mt-6 border border-rejected bg-paper p-3 text-small text-rejected">
          {error}
        </p>
      )}

      <section className="mt-10 grid gap-12 lg:grid-cols-12">
        <div className="lg:col-span-12">
          <h2 className="label-eyebrow">DetVerify cascade</h2>
          <div className={cn("mt-4 transition-opacity", loading && "opacity-50")}>
            <StageRow stages={result?.detverify.stage_results ?? []} />
          </div>
        </div>

        {result && (
          <>
            <div className="lg:col-span-7">
              <ScorePanel score={result.detverify.score} />
            </div>
            <aside className="lg:col-span-5">
              {expectedFailure ? (
                <div className="border border-rule bg-surface p-6">
                  <p className="label-eyebrow">Attack outcome</p>
                  <p className="mt-3 font-mono text-small uppercase tracking-wide text-signal-deep">
                    Caught at stage → {result.detverify.stage_results.at(-1)?.name}
                  </p>
                  <p className="mt-3 text-small text-subtext">
                    {result.narrative}
                  </p>
                  <p className="mt-4 border-t border-dashed border-rule pt-4 text-small text-subtext">
                    Konnex's GPT-4o reference verifier passes most of these.
                    The deterministic Layer-3 catches them with a precise
                    failure reason and a final_pct ≤ 30.
                  </p>
                </div>
              ) : (
                <div className="border border-rule bg-surface p-6">
                  <p className="label-eyebrow">Clean run</p>
                  <p className="mt-3 text-small text-subtext">
                    All six stages passed. The RootID-signed bundle resolves
                    to the registered robot, every packet's canonical-bytes
                    signature verifies, and Stage 6 confirms the per-joint
                    torque envelope.
                  </p>
                </div>
              )}
            </aside>
          </>
        )}
      </section>
    </div>
  );
}
