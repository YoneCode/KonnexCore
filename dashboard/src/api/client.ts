// Typed wrappers around the Phase 6 backend (api/main.py).
// All responses come from the FastAPI Pydantic models — types here mirror them.

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";

async function request<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    signal,
    ...init,
  });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const error = new Error(`HTTP ${response.status} on ${path}`) as Error & {
      status: number;
      detail: unknown;
    };
    error.status = response.status;
    error.detail = detail;
    throw error;
  }
  return (await response.json()) as T;
}

// ---------------------------------------------------------------------------
// Types — kept small; mirror only the fields the UI consumes.
// ---------------------------------------------------------------------------

export type SensorChannel = "camera" | "imu" | "lidar" | "gps" | "torque" | "thermal";
export type Verdict = "success" | "failure" | "inconclusive";

export interface DIDDocument {
  id: string;
  public_key_hex: string;
  auth_key_hex: string;
  capabilities: string[];
  created_at: string;
}

export interface ScoreVector {
  accuracy: number;
  speed: number;
  safety: number;
  optimal_track: number;
  energy_efficiency: number;
  trajectory_stability: number;
  final_pct: number;
  verdict: Verdict;
  reasoning: string;
}

export interface StageResult {
  name: string;
  passed: boolean;
  detail: string;
  severity: "info" | "warning" | "fail";
}

export interface DetVerifyResult {
  score: ScoreVector;
  stage_results: StageResult[];
  deterministic_only: boolean;
  llm_comparison: ScoreVector | null;
  layers_agree: boolean | null;
}

export interface SensorPacket {
  job_id: string;
  robot_did: string;
  channel: SensorChannel;
  timestamp_ns: number;
  nonce: number;
  data_b64: string;
  signature_hex: string;
}

export interface PolicyTrace {
  actions: Array<Record<string, unknown>>;
  seed: number;
  policy_hash: string;
}

export interface PoPWBundle {
  job_id: string;
  robot_did: string;
  task_prompt: string;
  policy_trace: PolicyTrace;
  sensor_packets: SensorPacket[];
  bundle_merkle_root: string;
  submitted_at: string;
}

export interface HoneypotTask {
  job_id: string;
  subnet: "drone-navigation" | "roboarm-vla" | "slam-3d-map";
  prompt: string;
  deadline_s: number;
  reward_test_knx: number;
  is_honeypot: true;
  ground_truth_score: ScoreVector;
  ground_truth_hash: string;
}

export interface ValidatorMetascore {
  validator_did: string;
  consensus_term: number;
  honeypot_accuracy: number;
  penalty_score: number;
  alpha: number;
  beta: number;
  gamma: number;
  metascore: number;
  sample_count: number;
}

export interface DemoScenario {
  key: "clean" | "deepfake" | "replay" | "gps_spoof" | "frame_skip" | "torque_mismatch";
  title: string;
  expected_verdict: Verdict;
}

export interface DemoRunResult {
  scenario: string;
  detverify: DetVerifyResult;
  expected_stage: string | null;
  narrative: string | null;
}

export interface AttackResponse {
  bundle: PoPWBundle;
  expected_stage: string;
  narrative: string;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export const api = {
  health: (signal?: AbortSignal) =>
    request<{ status: string; version: string }>("/health", { method: "GET" }, signal),

  identity: {
    create: (
      body: { network?: string; capabilities?: string[] },
      signal?: AbortSignal,
    ) =>
      request<DIDDocument>(
        "/identity/create",
        { method: "POST", body: JSON.stringify(body) },
        signal,
      ),
    resolve: (did: string, signal?: AbortSignal) =>
      request<DIDDocument>(
        `/identity/${encodeURIComponent(did)}`,
        { method: "GET" },
        signal,
      ),
  },

  verify: {
    bundle: (bundle: PoPWBundle, signal?: AbortSignal) =>
      request<DetVerifyResult>(
        "/verify",
        { method: "POST", body: JSON.stringify(bundle) },
        signal,
      ),
  },

  honeypot: {
    leaderboard: (signal?: AbortSignal) =>
      request<ValidatorMetascore[]>("/honeypot/leaderboard", { method: "GET" }, signal),
  },

  attack: {
    generate: (
      type: "deepfake" | "replay" | "gps_spoof" | "frame_skip" | "torque_mismatch",
      signal?: AbortSignal,
    ) =>
      request<AttackResponse>(
        `/attack/generate/${type}`,
        { method: "POST" },
        signal,
      ),
  },

  demo: {
    scenarios: (signal?: AbortSignal) =>
      request<DemoScenario[]>("/demo/scenarios", { method: "GET" }, signal),
    fullStack: (
      body: { scenario: DemoScenario["key"]; seed?: number },
      signal?: AbortSignal,
    ) =>
      request<DemoRunResult>(
        "/demo/full-stack",
        { method: "POST", body: JSON.stringify(body) },
        signal,
      ),
  },
};
