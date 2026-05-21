# Submission Checklist

Run through every item below before clicking "Submit" on the Konnex builder form.

## Repository

- [ ] GitHub repo is **public** (`Settings → General → Danger Zone → Visibility`).
- [ ] MIT license file present at root (`LICENSE`).
- [ ] README has demo URL, "Run locally" section, test count, and GitHub Actions badge.
- [ ] No secrets committed (`grep -r 'BEGIN.*PRIVATE KEY' . --include='*.py'` returns nothing).
- [ ] No `.env` or `.env.local` committed (`.gitignore` covers them).
- [ ] `make test` passes from a clean checkout (clone fresh on another machine to verify).
- [ ] `make lint` passes (ruff + black + mypy strict).
- [ ] CI passing on `main` branch (GitHub Actions green badge).

## Live demo URL

- [ ] URL accessible from incognito browser (not your dev session, not localhost).
- [ ] Home page loads — hero headline visible.
- [ ] `/full-stack` page runs: clean scenario → verdict "success", final_pct ≥ 80.
- [ ] `/full-stack` page runs: deepfake scenario → verdict "failure", stage 1 short-circuits.
- [ ] `/rootid` page: "Create identity" returns a DID document.
- [ ] `/honeynet` page: leaderboard renders (may be empty if demo hasn't run on server; note this is acceptable — the bar chart appears with an empty-state message).
- [ ] `/docs` (Swagger UI) loads and lists all 14 endpoints.
- [ ] No browser console errors on any page (open DevTools → Console → navigate all 5 pages).
- [ ] Mobile-responsive at 768px width (the review may happen on a tablet).

## Demo video

- [ ] Duration ≤ 60 seconds.
- [ ] Uploaded to YouTube as **unlisted**.
- [ ] Video shows the *live* demo URL (not localhost).
- [ ] Audio is clear; no background noise.
- [ ] Captions or voiceover explain every transition.
- [ ] Final frame shows the GitHub URL.

## Application form

- [ ] One-line pitch ≤ 140 characters (copy-paste from `docs/APPLICATION.md`).
- [ ] Demo link points to the live URL that works when reviewers click it.
- [ ] GitHub link points to the public repo.
- [ ] "Subnet category" is "Sensor fusion & PoPW validation".
- [ ] "Stage" is "Working demo".
- [ ] No claims about features that aren't implemented (re-read the "What we do NOT claim" section in APPLICATION.md).

## Final gut-check

- [ ] If a reviewer opens the URL cold — is the value obvious in 10 seconds?
- [ ] If a reviewer clones the repo — does `make test` pass on the first try?
- [ ] If a reviewer reads the README — do they understand what this builds and why Konnex?
- [ ] If a reviewer watches the video at 2× speed — is the story still clear?

---

Once every box is checked, submit at: **https://subnets.testnet.konnex.world/builders**
