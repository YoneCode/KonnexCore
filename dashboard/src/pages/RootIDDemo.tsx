import type { JSX } from "react";
import { useState } from "react";
import { type DIDDocument, api } from "../api/client";

export function RootIDDemo(): JSX.Element {
  const [doc, setDoc] = useState<DIDDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createIdentity(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const result = await api.identity.create({ network: "testnet" });
      setDoc(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1200px] px-6 py-16">
      <header className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <p className="label-eyebrow">Layer A — RootID</p>
          <h1 className="mt-4 font-display text-display-lg font-light tracking-tight text-ink">
            Hardware-rooted identity,
            <br />
            <span className="font-bold italic text-signal-deep">
              software-simulated TEE.
            </span>
          </h1>
          <p className="mt-6 max-w-[58ch] text-body leading-relaxed text-subtext">
            The TEE simulator generates an isolated Ed25519 keypair and binds
            it to a <code className="font-mono">did:knx:</code> identifier.
            Production swaps in ARM PSA Crypto API or Apple Secure Enclave.
            Same interface, hardware-backed key.
          </p>
        </div>
      </header>

      <section className="mt-12 grid gap-px bg-rule lg:grid-cols-3">
        <Step
          ord="01"
          title="Generate keypair"
          body="OS CSPRNG via cryptography.hazmat. Private bytes never leave the simulated TEE."
        />
        <Step
          ord="02"
          title="Compose did:knx:"
          body="Identifier = first 16 hex chars of SHA-3-256(public_bytes). Deterministic, collision-resistant."
        />
        <Step
          ord="03"
          title="Register on-chain mock"
          body="IdentityRegistry refuses to attach a different pubkey to a registered DID."
        />
      </section>

      <section className="mt-12 grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <button
            type="button"
            onClick={createIdentity}
            disabled={loading}
            className="border border-ink bg-ink px-6 py-3 font-mono text-label uppercase tracking-wider text-paper transition-transform duration-300 ease-out-quart hover:-translate-y-px disabled:opacity-50"
          >
            {loading ? "Generating…" : "Create identity"}
          </button>
          {error && (
            <p className="mt-4 border border-rejected bg-paper p-3 text-small text-rejected">
              {error}
            </p>
          )}
        </div>

        <aside className="lg:col-span-5">
          {doc ? (
            <DIDCard doc={doc} />
          ) : (
            <p className="border border-dashed border-rule bg-surface p-6 text-small text-subtext">
              Click <em>Create identity</em> to mint a fresh{" "}
              <code className="font-mono">did:knx:testnet:</code> document.
            </p>
          )}
        </aside>
      </section>
    </div>
  );
}

function Step({
  ord,
  title,
  body,
}: {
  ord: string;
  title: string;
  body: string;
}): JSX.Element {
  return (
    <div className="bg-paper p-8">
      <span className="font-mono text-label uppercase text-subtext">{ord}</span>
      <h3 className="mt-3 font-display text-subtitle text-ink">
        {title}
      </h3>
      <p className="mt-2 text-small text-subtext">{body}</p>
    </div>
  );
}

function DIDCard({ doc }: { doc: DIDDocument }): JSX.Element {
  return (
    <div className="border border-rule bg-surface p-6 animate-rise">
      <p className="label-eyebrow">DID document</p>
      <dl className="mt-4 grid gap-4 text-small">
        <div>
          <dt className="font-mono text-label uppercase text-subtext">id</dt>
          <dd className="mt-1 break-all font-mono text-small text-ink">
            {doc.id}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-label uppercase text-subtext">
            public_key_hex
          </dt>
          <dd className="mt-1 break-all font-mono text-small text-ink">
            {doc.public_key_hex}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-label uppercase text-subtext">
            capabilities
          </dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {doc.capabilities.map((c) => (
              <span key={c} className="pill">
                {c}
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </div>
  );
}
