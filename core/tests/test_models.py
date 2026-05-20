"""Schema tests for ``core/models.py``.

These tests pin the JSON shape of every Pydantic model defined in
spec Section 5. Any change to a field name, type, or constraint must
be reflected in this file first (TDD) and motivated by an update to
the build spec (design spec Section 8).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core import models


def _now() -> datetime:
    return datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# DIDDocument
# ---------------------------------------------------------------------------


class TestDIDDocument:
    def test_valid_did(self) -> None:
        doc = models.DIDDocument(
            id="did:knx:test:abc-123",
            public_key_hex="aa" * 32,
            auth_key_hex="bb" * 32,
            capabilities=["camera", "imu"],
            created_at=_now(),
        )
        assert doc.id == "did:knx:test:abc-123"

    def test_rejects_non_knx_did(self) -> None:
        with pytest.raises(ValidationError):
            models.DIDDocument(
                id="did:example:abc",
                public_key_hex="aa" * 32,
                auth_key_hex="bb" * 32,
                capabilities=[],
                created_at=_now(),
            )

    def test_rejects_malformed_did(self) -> None:
        with pytest.raises(ValidationError):
            models.DIDDocument(
                id="not-a-did",
                public_key_hex="aa" * 32,
                auth_key_hex="bb" * 32,
                capabilities=[],
                created_at=_now(),
            )

    def test_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            models.DIDDocument(
                id="did:knx:test:abc",
                public_key_hex="aa" * 32,
                auth_key_hex="bb" * 32,
                capabilities=[],
                created_at=_now(),
                evil_field="injection",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# SensorPacket
# ---------------------------------------------------------------------------


class TestSensorPacket:
    def _packet(self, **overrides: object) -> models.SensorPacket:
        defaults: dict[str, object] = {
            "job_id": "j" * 64,
            "robot_did": "did:knx:test:r1",
            "channel": models.SensorChannel.CAMERA,
            "timestamp_ns": 1_700_000_000_000_000_000,
            "nonce": 0,
            "data_b64": "aGVsbG8=",
            "signature_hex": "cc" * 64,
        }
        defaults.update(overrides)
        return models.SensorPacket(**defaults)  # type: ignore[arg-type]

    def test_valid_packet_round_trip(self) -> None:
        packet = self._packet()
        encoded = packet.model_dump_json()
        decoded = models.SensorPacket.model_validate_json(encoded)
        assert decoded == packet

    def test_channel_must_be_known(self) -> None:
        with pytest.raises(ValidationError):
            models.SensorPacket(
                job_id="j" * 64,
                robot_did="did:knx:test:r1",
                channel="ultrasonic",  # type: ignore[arg-type]
                timestamp_ns=1,
                nonce=0,
                data_b64="aGVsbG8=",
                signature_hex="cc" * 64,
            )

    def test_negative_nonce_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._packet(nonce=-1)

    def test_negative_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._packet(timestamp_ns=-1)

    def test_all_six_channels_accepted(self) -> None:
        for ch in models.SensorChannel:
            assert self._packet(channel=ch).channel == ch


# ---------------------------------------------------------------------------
# PolicyTrace + PoPWBundle
# ---------------------------------------------------------------------------


class TestPoPWBundle:
    def test_full_bundle_round_trip(self) -> None:
        packet = models.SensorPacket(
            job_id="j" * 64,
            robot_did="did:knx:test:r1",
            channel=models.SensorChannel.IMU,
            timestamp_ns=1,
            nonce=0,
            data_b64="aGVsbG8=",
            signature_hex="cc" * 64,
        )
        trace = models.PolicyTrace(
            actions=[{"type": "move", "dx": 1}],
            seed=42,
            policy_hash="dd" * 32,
        )
        bundle = models.PoPWBundle(
            job_id="j" * 64,
            robot_did="did:knx:test:r1",
            task_prompt="pick apple",
            policy_trace=trace,
            sensor_packets=[packet],
            bundle_merkle_root="ee" * 32,
            submitted_at=_now(),
        )
        as_json = bundle.model_dump_json()
        again = models.PoPWBundle.model_validate_json(as_json)
        assert again == bundle


# ---------------------------------------------------------------------------
# ScoreVector — Konnex compatibility
# ---------------------------------------------------------------------------


class TestScoreVector:
    def _score(self, **overrides: object) -> models.ScoreVector:
        defaults: dict[str, object] = {
            "accuracy": 90,
            "speed": 80,
            "safety": 95,
            "optimal_track": 70,
            "energy_efficiency": 75,
            "trajectory_stability": 88,
            "final_pct": 84,
            "verdict": "success",
            "reasoning": "all stages passed",
        }
        defaults.update(overrides)
        return models.ScoreVector(**defaults)  # type: ignore[arg-type]

    def test_valid_score(self) -> None:
        score = self._score()
        assert score.verdict == "success"

    def test_score_field_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._score(accuracy=-1)

    def test_score_field_above_hundred_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._score(safety=101)

    @pytest.mark.parametrize("verdict", ["success", "failure", "inconclusive"])
    def test_all_three_verdicts_accepted(self, verdict: str) -> None:
        assert self._score(verdict=verdict).verdict == verdict

    def test_unknown_verdict_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._score(verdict="maybe")

    def test_konnex_field_set_exact(self) -> None:
        # Per spec Section 6 + https://docs.konnex.world/supported-ai-models/verifier
        score = self._score()
        payload = json.loads(score.model_dump_json())
        expected_keys = {
            "accuracy",
            "speed",
            "safety",
            "optimal_track",
            "energy_efficiency",
            "trajectory_stability",
            "final_pct",
            "verdict",
            "reasoning",
        }
        assert set(payload.keys()) == expected_keys


# ---------------------------------------------------------------------------
# DetVerifyResult / StageResult
# ---------------------------------------------------------------------------


class TestDetVerifyResult:
    def _score(self) -> models.ScoreVector:
        return models.ScoreVector(
            accuracy=90,
            speed=80,
            safety=95,
            optimal_track=70,
            energy_efficiency=75,
            trajectory_stability=88,
            final_pct=84,
            verdict="success",
            reasoning="ok",
        )

    def test_minimum_valid_result(self) -> None:
        result = models.DetVerifyResult(
            score=self._score(),
            stage_results=[
                models.StageResult(name="stage1", passed=True, detail="ok"),
            ],
            deterministic_only=True,
        )
        assert result.layers_agree is None
        assert result.llm_comparison is None

    def test_stage_severity_default_info(self) -> None:
        sr = models.StageResult(name="stage1", passed=True, detail="ok")
        assert sr.severity == "info"

    def test_invalid_stage_severity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            models.StageResult(
                name="stage1",
                passed=True,
                detail="ok",
                severity="critical",  # type: ignore[arg-type]
            )

    def test_with_llm_comparison(self) -> None:
        result = models.DetVerifyResult(
            score=self._score(),
            stage_results=[],
            deterministic_only=False,
            llm_comparison=self._score(),
            layers_agree=True,
        )
        assert result.layers_agree is True


# ---------------------------------------------------------------------------
# ValidatorMetascore — α·C + β·H − γ·P
# ---------------------------------------------------------------------------


class TestValidatorMetascore:
    def test_default_weights(self) -> None:
        ms = models.ValidatorMetascore(
            validator_did="did:knx:test:v1",
            consensus_term=0.9,
            honeypot_accuracy=0.95,
            penalty_score=0.05,
            metascore=0.5 * 0.9 + 0.4 * 0.95 - 0.1 * 0.05,
            sample_count=100,
        )
        assert ms.alpha == 0.5
        assert ms.beta == 0.4
        assert ms.gamma == 0.1

    def test_negative_sample_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            models.ValidatorMetascore(
                validator_did="did:knx:test:v1",
                consensus_term=0.5,
                honeypot_accuracy=0.5,
                penalty_score=0.0,
                metascore=0.5,
                sample_count=-1,
            )

    def test_consensus_term_range(self) -> None:
        with pytest.raises(ValidationError):
            models.ValidatorMetascore(
                validator_did="did:knx:test:v1",
                consensus_term=1.5,  # > 1.0 rejected
                honeypot_accuracy=0.5,
                penalty_score=0.0,
                metascore=0.5,
                sample_count=10,
            )


# ---------------------------------------------------------------------------
# ValidatorVote
# ---------------------------------------------------------------------------


class TestValidatorVote:
    def test_round_trip(self) -> None:
        score = models.ScoreVector(
            accuracy=90,
            speed=80,
            safety=95,
            optimal_track=70,
            energy_efficiency=75,
            trajectory_stability=88,
            final_pct=84,
            verdict="success",
            reasoning="ok",
        )
        vote = models.ValidatorVote(
            validator_did="did:knx:test:v1",
            job_id="j" * 64,
            score=score,
            submitted_at=_now(),
        )
        again = models.ValidatorVote.model_validate_json(vote.model_dump_json())
        assert again == vote


# ---------------------------------------------------------------------------
# HoneypotTask
# ---------------------------------------------------------------------------


class TestHoneypotTask:
    def _score(self) -> models.ScoreVector:
        return models.ScoreVector(
            accuracy=90,
            speed=80,
            safety=95,
            optimal_track=70,
            energy_efficiency=75,
            trajectory_stability=88,
            final_pct=84,
            verdict="success",
            reasoning="ok",
        )

    def test_is_honeypot_literal_true(self) -> None:
        task = models.HoneypotTask(
            job_id="j" * 64,
            subnet=models.Subnet.ROBOARM,
            prompt="pick apple",
            deadline_s=120,
            reward_test_knx=1.5,
            ground_truth_score=self._score(),
            ground_truth_hash="ff" * 32,
        )
        assert task.is_honeypot is True

    def test_is_honeypot_false_rejected(self) -> None:
        with pytest.raises(ValidationError):
            models.HoneypotTask(
                job_id="j" * 64,
                subnet=models.Subnet.ROBOARM,
                prompt="pick apple",
                deadline_s=120,
                reward_test_knx=1.5,
                is_honeypot=False,  # type: ignore[arg-type]
                ground_truth_score=self._score(),
                ground_truth_hash="ff" * 32,
            )

    def test_negative_reward_rejected(self) -> None:
        with pytest.raises(ValidationError):
            models.HoneypotTask(
                job_id="j" * 64,
                subnet=models.Subnet.ROBOARM,
                prompt="pick apple",
                deadline_s=120,
                reward_test_knx=-1.0,
                ground_truth_score=self._score(),
                ground_truth_hash="ff" * 32,
            )

    def test_subnet_enum_values(self) -> None:
        # Spec Section 5: Subnet members are drone-navigation, roboarm-vla, slam-3d-map.
        assert models.Subnet.DRONE.value == "drone-navigation"
        assert models.Subnet.ROBOARM.value == "roboarm-vla"
        assert models.Subnet.SLAM.value == "slam-3d-map"
