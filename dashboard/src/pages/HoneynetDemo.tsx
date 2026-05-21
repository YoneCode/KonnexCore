import type { JSX } from "react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type ValidatorMetascore, api } from "../api/client";
import { cn } from "../lib/cn";

export function HoneynetDemo(): JSX.Element {
  const [rows, setRows] = useState<ValidatorMetascore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    api.honeypot
      .leaderboard(ctrl.signal)
      .then((r) => {
        setRows(r);
        setLoading(false);
      })
      .catch((e) => {
        if (!ctrl.signal.aborted) {
          setError(String(e));
          setLoading(false);
        }
      });
    return () => ctrl.abort();
  }, []);

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16">
      <header className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <p className="label-eyebrow">Layer C — Honeynet</p>
          <h1 className="mt-4 font-display text-display-lg font-light tracking-tight text-ink">
            Honeypots reveal validators
            <br />
            <span className="font-bold italic text-signal-deep">
              the consensus can't.
            </span>
          </h1>
          <p className="mt-6 max-w-[58ch] text-body leading-relaxed text-subtext">
            Lazy validators copy the network median and pass consensus
            checks. They fail the H(V_i) term — honeypot accuracy — because
            they never actually verify anything. Run the demo CLI
            (<code className="font-mono">make demo</code>) to see honest beat
            lazy by ≥ 0.3 metascore points on a 100 + 10 task batch.
          </p>
        </div>
      </header>

      <section className="mt-12 grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <h2 className="label-eyebrow">Leaderboard (live oracle state)</h2>
          {error && (
            <p className="mt-4 border border-rejected bg-paper p-3 text-small text-rejected">
              {error}
            </p>
          )}
          {!error && (
            <div
              className={cn(
                "mt-4 border border-rule bg-surface p-4 transition-opacity",
                loading && "is-loading",
              )}
            >
              {rows.length === 0 ? (
                <EmptyState />
              ) : (
                <Leaderboard rows={rows} />
              )}
            </div>
          )}
        </div>

        <aside className="lg:col-span-5">
          <Formula />
        </aside>
      </section>
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div className="border border-dashed border-rule bg-paper p-8 text-center">
      <p className="font-mono text-label uppercase text-subtext">
        no validators yet
      </p>
      <p className="mt-3 text-small text-subtext">
        Submit votes via{" "}
        <code className="font-mono">POST /api/honeypot/submit-vote</code> or
        run{" "}
        <code className="font-mono">python examples/05_honeypot_demo.py</code>{" "}
        on the server.
      </p>
    </div>
  );
}

function Leaderboard({ rows }: { rows: ValidatorMetascore[] }): JSX.Element {
  const data = rows.map((r) => ({
    name: r.validator_did.replace(/^did:knx:[^:]+:/, ""),
    metascore: Number(r.metascore.toFixed(3)),
    consensus: Number(r.consensus_term.toFixed(3)),
    honeypot: Number(r.honeypot_accuracy.toFixed(3)),
  }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 56)}>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 24 }}>
          <CartesianGrid stroke="var(--color-rule)" strokeDasharray="2 4" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} tick={{ fontFamily: "IBM Plex Mono", fontSize: 11, fill: "var(--color-subtext)" }} />
          <YAxis dataKey="name" type="category" width={120} tick={{ fontFamily: "IBM Plex Mono", fontSize: 11, fill: "var(--color-ink)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--color-paper)",
              border: "1px solid var(--color-rule-strong)",
              fontFamily: "IBM Plex Mono",
              fontSize: 12,
            }}
            cursor={{ fill: "var(--color-rule)" }}
          />
          <Bar dataKey="metascore" fill="var(--color-signal)" radius={[0, 1, 1, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Formula(): JSX.Element {
  return (
    <div className="border border-rule bg-surface p-6">
      <p className="label-eyebrow">Validator metascore formula</p>
      <p className="mt-3 font-mono text-body tabular text-ink">
        S(Vᵢ) = α·C + β·H − γ·P
      </p>
      <ul className="mt-4 space-y-3 text-small text-subtext">
        <li>
          <span className="font-mono text-label uppercase text-ink">C</span> —
          consensus alignment with network
        </li>
        <li>
          <span className="font-mono text-label uppercase text-ink">H</span> —
          honeypot accuracy (this is what catches lazy validators)
        </li>
        <li>
          <span className="font-mono text-label uppercase text-ink">P</span> —
          operational penalty (timeouts, abstentions)
        </li>
      </ul>
      <p className="mt-4 border-t border-dashed border-rule pt-4 text-small text-subtext">
        Spec defaults α=0.5, β=0.4, γ=0.1. The leaderboard above uses the
        H-only weights from <code className="font-mono">make demo</code> so
        the discriminator stands out.
      </p>
    </div>
  );
}
