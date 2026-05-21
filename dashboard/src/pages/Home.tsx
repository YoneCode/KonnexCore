import type { JSX } from "react";
import { Link } from "react-router-dom";

export function Home(): JSX.Element {
  return (
    <div className="mx-auto max-w-[1200px] px-6 py-20 lg:py-32">
      {/* Hero */}
      <section className="grid gap-16 lg:grid-cols-12">
        <header className="lg:col-span-9">
          <p className="label-eyebrow animate-rise">
            Konnex Builder Grant — Spark Tier
          </p>
          <h1
            className="mt-8 font-display text-display-xl font-light text-ink animate-rise"
            style={{ animationDelay: "60ms" }}
          >
            The validator stack
            <br />
            Konnex <span className="font-bold italic text-hero-accent">specced.</span>
          </h1>
          <p
            className="mt-10 max-w-[54ch] text-body leading-relaxed text-subtext animate-rise"
            style={{ animationDelay: "120ms" }}
          >
            TEE-attested sensor capture. Six-stage deterministic verification.
            Honeypot oracle scoring the validators that score miners. All three
            layers Konnex's docs call for — shipped as working open-source code.
          </p>
          <div
            className="mt-12 flex flex-wrap items-center gap-5 animate-rise"
            style={{ animationDelay: "180ms" }}
          >
            <Link
              to="/full-stack"
              className="group relative overflow-hidden border border-ink bg-ink px-7 py-3.5 font-mono text-label uppercase tracking-wider text-paper transition-transform duration-300 ease-out-quart hover:-translate-y-0.5"
            >
              <span className="relative z-10">Run the demo →</span>
            </Link>
            <Link
              to="/detverify"
              className="font-mono text-label uppercase tracking-wider text-subtext underline-offset-4 transition-colors hover:text-ink hover:underline"
            >
              DetVerify alone
            </Link>
            <a
              href="/docs"
              className="font-mono text-label uppercase tracking-wider text-subtext underline-offset-4 transition-colors hover:text-ink hover:underline"
            >
              API docs
            </a>
          </div>
        </header>

        <aside
          className="self-end lg:col-span-3 animate-rise"
          style={{ animationDelay: "240ms" }}
        >
          <div className="border border-rule bg-surface p-5">
            <dl className="space-y-4 text-small">
              <Stat label="Tests" value="298" />
              <Stat label="Coverage" value="99%" />
              <Stat label="Phases" value="9/9" />
              <Stat label="Crypto" value="SHA-3 + Ed25519" />
            </dl>
          </div>
        </aside>
      </section>

      {/* Three layers */}
      <section className="mt-32">
        <p className="label-eyebrow">Architecture</p>
        <div className="mt-6 grid gap-px bg-rule lg:grid-cols-3">
          <LayerCard
            ord="A"
            title="RootID"
            tagline="Identity & TEE attestation"
            to="/rootid"
            body="Software TEE signs each sensor frame at capture. Monotonic nonces per (job, channel). did:knx: bound to Ed25519 pubkey."
          />
          <LayerCard
            ord="B"
            title="DetVerify"
            tagline="Deterministic Layer-3"
            to="/detverify"
            body="Signature → Temporal → Cross-modal → Replay → Anomaly → Kinematic. Same input → same output, every time. No LLM cost."
          />
          <LayerCard
            ord="C"
            title="Honeynet"
            tagline="Honeypot oracle"
            to="/honeynet"
            body="S(Vᵢ) = α·C + β·H − γ·P. Honest validators separate from lazy by ≥ 0.3 points. The H term catches what consensus can't."
          />
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-dashed border-rule pb-3 last:border-0 last:pb-0">
      <dt className="font-mono text-label uppercase text-subtext">{label}</dt>
      <dd className="font-display text-title font-medium tabular text-ink">{value}</dd>
    </div>
  );
}

interface LayerCardProps {
  ord: string;
  title: string;
  tagline: string;
  body: string;
  to: string;
}

function LayerCard({ ord, title, tagline, body, to }: LayerCardProps): JSX.Element {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-4 bg-paper p-8 transition-colors duration-300 ease-out-quart hover:bg-surface"
    >
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-label uppercase text-subtext">
          Layer {ord}
        </span>
        <span className="font-mono text-label text-subtext transition-transform duration-200 group-hover:translate-x-1">
          →
        </span>
      </div>
      <h2 className="font-display text-display-md font-medium text-ink">
        {title}
      </h2>
      <p className="font-mono text-small uppercase tracking-wide text-signal-deep">
        {tagline}
      </p>
      <p className="mt-auto text-small leading-relaxed text-subtext">{body}</p>
    </Link>
  );
}
