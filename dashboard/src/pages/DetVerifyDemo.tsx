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

export function DetVerifyDemo(): JSX.Element {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [active, setActive] = useState<DemoScenario["key"]>("clean");
  const [result, setResult] = useState<DemoRunResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.demo
      .scenarios(ctrl.signal)
      .then(setScenarios)
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(`load scenarios: ${String(e)}`);
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

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16">
      <header className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <p className="label-eyebrow">Layer B — DetVerify</p>
          <h1 className="mt-4 font-display text-display-lg font-light tracking-tight text-ink">
            Six deterministic stages,
            <br />
            <span className="font-bold italic text-signal-deep">
              one named failure
            </span>{" "}
            per attack.
          </h1>
          <p className="mt-6 max-w-[60ch] text-body text-subtext">
            Pick a scenario. The clean run scores ≥ 80 with all six stages
            passing. Each adversarial run drops below 30 with a precisely
            named stage at fault.
          </p>
        </div>
      </header>

      <section className="mt-12 flex flex-wrap gap-2 border-b border-dashed border-rule pb-6">
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
        <p className="mt-6 border border-rejected bg-paper p-4 text-small text-rejected">
          {error}
        </p>
      )}

      <section className="mt-10">
        <h2 className="label-eyebrow">Stage cascade</h2>
        <div className={cn("mt-4 transition-opacity", loading && "opacity-50")}>
          {result ? (
            <StageRow stages={result.detverify.stage_results} />
          ) : (
            <StageRow stages={[]} />
          )}
        </div>
      </section>

      {result && (
        <section className="mt-12 grid gap-8 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <ScorePanel score={result.detverify.score} />
          </div>
          <aside className="lg:col-span-5">
            {result.expected_stage && (
              <div className="border border-rule bg-surface p-6 text-small">
                <p className="label-eyebrow">Attack narrative</p>
                <p className="mt-3 font-mono text-small uppercase tracking-wide text-signal-deep">
                  Expected stage → {result.expected_stage}
                </p>
                <p className="mt-3 text-subtext">{result.narrative}</p>
              </div>
            )}
          </aside>
        </section>
      )}
    </div>
  );
}
