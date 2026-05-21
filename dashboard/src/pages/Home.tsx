import type { JSX } from "react";
import { Link } from "react-router-dom";

export function Home(): JSX.Element {
  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16 lg:py-24">
      <section className="grid gap-12 lg:grid-cols-12 lg:gap-16">
        <header className="lg:col-span-8 lg:col-start-1">
          <p className="label-eyebrow animate-rise">
            Konnex builder grant — Spark tier
          </p>
          <h1
            className="mt-6 font-display text-display-xl font-light leading-[1.02] text-ink animate-rise"
            style={{ animationDelay: "70ms" }}
          >
            The validator
            <br />
            stack Konnex
            <span className="font-bold italic text-signal-deep"> specced.</span>
          </h1>
          <p
            className="mt-8 max-w-[58ch] text-body text-subtext animate-rise"
            style={{ animationDelay: "140ms" }}
          >
            KonnexCore implements the three layers Konnex's docs call for but
            don't yet ship as reference code: TEE-attested sensor capture,
            deterministic six-stage verification, and a honeypot oracle that
            scores the validators that score miners.
          </p>
          <div
            className="mt-10 flex flex-wrap items-center gap-4 animate-rise"
            style={{ animationDelay: "210ms" }}
          >
            <Link
              to="/full-stack"
              className="border border-ink bg-ink px-6 py-3 font-mono text-label uppercase tracking-wider text-paper transition-transform duration-300 ease-out-quart hover:-translate-y-px"
            >
              Run the full-stack demo →
            </Link>
            <Link
              to="/detverify"
              className="font-mono text-label uppercase tracking-wider text-subtext underline-offset-4 hover:text-ink hover:underline"
            >
              See the verifier alone
            </Link>
          </div>
        </header>

        <aside className="lg:col-span-4 lg:col-start-9">
          <ul className="border border-rule bg-surface p-6 text-small text-subtext">
            <li className="border-b border-dashed border-rule pb-3">
              <span className="font-mono text-label uppercase text-ink">
                Status
              </span>
              <p className="mt-1">All 6 phases complete; live demo + tests.</p>
            </li>
            <li className="py-3">
              <span className="font-mono text-label uppercase text-ink">
                Schema
              </span>
              <p className="mt-1">
                Konnex AI Verifier <code className="font-mono">ScoreVector</code>{" "}
                — exact mirror.
              </p>
            </li>
            <li className="border-t border-dashed border-rule pt-3">
              <span className="font-mono text-label uppercase text-ink">
                Crypto
              </span>
              <p className="mt-1">SHA-3-256 + Ed25519 (RFC 8032).</p>
            </li>
          </ul>
        </aside>
      </section>

      <section className="mt-24 grid gap-px bg-rule lg:grid-cols-3">
        <LayerCard
          ord="A"
          title="RootID"
          tagline="Identity & TEE attestation"
          to="/rootid"
          body="Software-simulated TEE signs every sensor packet at capture time. Bound to a did:knx: identity and a job nonce that can't be replayed."
        />
        <LayerCard
          ord="B"
          title="DetVerify"
          tagline="Deterministic Layer-3 verifier"
          to="/detverify"
          body="Six closed-form stages (signature, temporal, cross-modal, replay, anomaly, kinematic) catch what GPT-4o reference verifiers miss."
        />
        <LayerCard
          ord="C"
          title="Honeynet"
          tagline="Honeypot oracle"
          to="/honeynet"
          body="Indistinguishable reference tasks compute H(V_i) per validator. Lazy validators that mimic the network median fail honeypot accuracy."
        />
      </section>
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
      className="group flex flex-col gap-3 bg-paper p-8 transition-colors duration-300 ease-out-quart hover:bg-surface"
    >
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-label uppercase text-subtext">
          Layer {ord}
        </span>
        <span className="font-mono text-label uppercase text-subtext transition-transform group-hover:translate-x-1">
          ↗
        </span>
      </div>
      <h2 className="font-display text-display-md font-medium text-ink">
        {title}
      </h2>
      <p className="font-mono text-small uppercase tracking-wide text-signal-deep">
        {tagline}
      </p>
      <p className="mt-2 text-small text-subtext">{body}</p>
    </Link>
  );
}
