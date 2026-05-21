import type { JSX } from "react";
import { useEffect, useState } from "react";
import { type DemoRunResult, type DemoScenario, api } from "../api/client";
import { ScorePanel } from "../components/ScorePanel";
import { StageRow } from "../components/StageRow";
import { cn } from "../lib/cn";
import { withViewTransition } from "../lib/viewTransition";

export function FullStackDemo(): JSX.Element {
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [active, setActive] = useState<DemoScenario["key"]>("clean");
  const [result, setResult] = useState<DemoRunResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [animateScore, setAnimateScore] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    api.demo.scenarios(ctrl.signal).then(setScenarios).catch(() => {});
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    setAnimateScore(false);
    api.demo
      .fullStack({ scenario: active }, ctrl.signal)
      .then((r) => {
        withViewTransition(() => {
          setResult(r);
          setLoading(false);
          setAnimateScore(true);
        });
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
      <header>
        <p className="label-eyebrow">End-to-end demo</p>
        <h1 className="mt-4 font-display text-display-lg font-light tracking-tight text-ink">
          Capture · Sign · Verify ·{" "}
          <span className="font-bold italic text-hero-accent">Under attack.</span>
        </h1>
        <p className="mt-6 max-w-[58ch] text-body text-subtext">
          Pick a scenario. Clean bundles score 100. Adversarial bundles drop to 0
          with a precisely named stage at fault. View Transitions morph between states.
        </p>
      </header>

      <nav className="mt-10 flex flex-wrap items-center gap-2 border-b border-dashed border-rule pb-6">
        {scenarios.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => withViewTransition(() => setActive(s.key))}
            className={cn(
              "border px-3 py-2 font-mono text-label uppercase tracking-wider transition-all duration-200 ease-out-quart",
              active === s.key
                ? "border-ink bg-ink text-paper shadow-lift"
                : "border-rule bg-paper text-subtext hover:border-ink hover:text-ink",
            )}
          >
            {s.title}
          </button>
        ))}
      </nav>

      {error && (
        <p className="mt-6 border border-rejected bg-paper p-4 text-small text-rejected">
          {error}
        </p>
      )}

      <section className="mt-10">
        <h2 className="label-eyebrow">DetVerify cascade</h2>
        <div className={cn("mt-4 transition-opacity duration-200", loading && "opacity-40")}>
          <StageRow stages={result?.detverify.stage_results ?? []} />
        </div>
      </section>

      {result && (
        <section className="mt-12 grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <ScorePanel score={result.detverify.score} animate={animateScore} />
          </div>
          <aside className="lg:col-span-5">
            {result.expected_stage ? (
              <div className="border border-rule bg-surface p-6">
                <p className="label-eyebrow">Attack caught</p>
                <p className="mt-3 font-mono text-title font-medium text-rejected">
                  Stage → {result.detverify.stage_results.at(-1)?.name}
                </p>
                <p className="mt-4 text-small leading-relaxed text-subtext">
                  {result.narrative}
                </p>
                <p className="mt-4 border-t border-dashed border-rule pt-4 text-small italic text-subtext">
                  "Their LLM verifier passes. Our deterministic Layer 3 catches it."
                </p>
              </div>
            ) : (
              <div className="border border-rule bg-surface p-6">
                <p className="label-eyebrow">Clean run</p>
                <p className="mt-3 font-mono text-title font-medium text-verified">
                  All 6 stages passed
                </p>
                <p className="mt-4 text-small leading-relaxed text-subtext">
                  RootID-signed bundle verified end-to-end. Every packet's
                  canonical-bytes signature resolves against the registered
                  robot identity. Per-joint torques within the kinematic envelope.
                </p>
              </div>
            )}
          </aside>
        </section>
      )}
    </div>
  );
}
