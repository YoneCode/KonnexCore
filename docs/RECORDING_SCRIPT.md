# Demo Video Recording Script (60 seconds)

> OBS Studio · 1080p · 30 fps · MP4 · Browser zoom 110%
> Upload to YouTube as **unlisted** and paste URL into the application form.

---

## Setup before recording

1. Backend running: `venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000`
2. Dashboard built and served (either `make dashboard` or Nginx in production).
3. Browser open at the dashboard root, incognito mode, no extensions.
4. OBS capturing the browser window only (crop out taskbar/dock).
5. Mic ready, quiet environment.

---

## Shot list

| Time | Screen | Voiceover |
|------|--------|-----------|
| **00:00–00:05** | Title card (black BG, white text: "KonnexCore — the validator stack Konnex specced.") | *Silence or light music sting.* |
| **00:05–00:12** | Open `docs.konnex.world/supported-ai-models/verifier` in browser. Highlight the GPT-4o reference code. | "Konnex's reference verifier is GPT-4o on 6 frames. We built the missing layers." |
| **00:12–00:22** | Navigate to dashboard `/rootid`. Click **Create identity**. Show the DID document card appearing with the hex public key. | "Each sensor packet is signed at capture by a TEE-simulated key, bound to a did:knx: identity." |
| **00:22–00:38** | Navigate to `/full-stack`. The **clean** scenario loads automatically — show the six green stage tiles + ScoreVector at 100. Then click **Deepfake video**. Show the cascade: stage 1 fails red, pipeline short-circuits, score drops to 0. | "Same bundle shape. Their LLM verifier passes. Our deterministic Layer 3 catches it — stage 1, signature mismatch." |
| **00:38–00:50** | Click through **Frame skip** → stage 2 (temporal) fails. Click **Torque mismatch** → stage 6 (kinematic) fails. Quick montage — each click flips the verdict to failure with a different named stage. | "Five adversarial attacks, three distinct stage failures. Deterministic, repeatable, no LLM cost." |
| **00:50–00:57** | Navigate to `/honeynet`. Show the bar chart (pre-populated by running `make demo` beforehand). Honest validator at the top; lazy/collusion/stake-pump below. | "Honeypots inject reference tasks. The H term catches lazy validators that fool consensus." |
| **00:57–01:00** | Return to home `/`. Hold on the hero headline. Fade to black. | "KonnexCore. Open-source. github.com/YoneCode/KonnexCore." |

---

## Post-production checklist

- [ ] Total runtime ≤ 60 seconds (hard cap per spec §12).
- [ ] No background noise or long silences.
- [ ] Browser shows the live demo URL (not localhost) if deploying publicly.
- [ ] No secrets visible (no `.env` files, no terminal with API keys).
- [ ] Upload as **unlisted** YouTube — paste URL into APPLICATION.md + the form.
- [ ] Watch once at 2× speed — still comprehensible? If not, tighten.

---

## Tips

- **Record in one take.** The dashboard responds in < 1 s; don't pause.
- **Emphasize the cascade.** The six tiles animating is the visual signature — hold the camera on it for 2–3 seconds each time.
- **Contrast.** Always say "their LLM verifier passes; our deterministic Layer 3 catches it." The reviewers care about the gap.
- **End with the repo URL.** That's what they'll click after the video.
