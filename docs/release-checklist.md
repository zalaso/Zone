# Release verification

## Version 1.1

The English-interface update preserves the scientific protocol, benchmark v0.3
and SQLite schema 4. The [experience record](english-experience.md) describes the
readability changes, current installation instructions, presentation and local
verification scope. Local checks passed 298 Python tests, 39 UI tests and two
frontend guard tests, TypeScript/build, publication/archive checks and offline
browser scenarios. Release assets include the compiled English UI. No real
model calls or production-server deployment are part of this update.

The [1.1.0 release](https://github.com/zalaso/Zone/releases/tag/v1.1.0) links its
commit, CI and checksummed wheel/source/video assets. The following section is
the historical 1.0 verification record, not a substitute for the current CI run.

## Version 1.0

This is the release record for the public open-source application, not a claim of centrally hosted service availability. Benchmark v0.3, Forge v1, Arena v1, Integrity v1 and SQLite schema 4 are retained.

Required gates:

- [x] Full Python suite and Ruff: 298 tests passed locally.
- [x] Frontend tests, TypeScript/build, AST lint and public bundle checks: 35 UI tests and 2 guard tests passed.
- [x] Full offline operational demo: four benchmark conditions, Arena, aggregation/report and verified backup/restore.
- [x] Clean installed wheel outside the checkout: bundled UI, official workspace launcher, private-file exclusion, registration, persistence, restart and restore.
- [x] Linux/Windows Python 3.11/3.12 CI and Docker build/runtime: [all six jobs passed](https://github.com/zalaso/Zone/actions/runs/39110042893).
- [x] Offline browser: all modes, real local observations, predictions, final scores, account lifecycle, desktop/mobile and reduced motion.
- [x] Publishable worktree, reachable Git history and release archives scanned without secret values in reports.
- [x] README, operator/developer guides, license/notices and local documentation links checked. GitHub Discussions, private vulnerability reporting and dependency alerts enabled and verified; no dependency advisories open at verification time.
- [x] Public GitHub repository and README readable without authentication; wheel/source archives and SHA256SUMS generated and audited.

Release assets: [Zone v1.0.0](https://github.com/zalaso/Zone/releases/tag/v1.0.0). The final publication check downloads both assets and compares their hashes with SHA256SUMS. The linked implementation run passed before final documentation consolidation and tightening the daily-world browser assertion; the tagged release repeats the six CI jobs after those changes. No application code changes are introduced by that consolidation.

No real provider inference, model download or production VPS change is part of these gates. The publisher must not upload databases, backup files, OAuth stores, personal API keys or private benchmark suites. Standard GitHub-hosted runners are used only; workflow artifacts containing data are not uploaded.

Local verification date: 2026-10-18 (Windows, Python 3.14). Clean installation also confirms no provider SDKs in the offline environment. Dependency checks cover both production and development packages; the CI rejects moderate or higher frontend advisories. These checks are not a security certification. The published tag, CI and release notes are the final source of release evidence.

## Reproduce

```sh
python -m pip install -c constraints-ci.txt -e '.[workspace,all-llm,dev]'
python -m ruff check hidden_lab tests tools
python -m unittest discover -s tests -q
python -m hidden_lab ops demo --out benchmark_data/release-demo
cd frontend
pnpm install --frozen-lockfile
pnpm audit --audit-level moderate
pnpm test --maxWorkers=2
pnpm lint
pnpm test:quality
cd ..
python tools/build_release.py --out dist
python tools/check_publication.py --history --archives dist
python tools/verify_distribution.py --mode wheel --wheel dist/hidden_physics_lab-1.0.0-py3-none-any.whl --out benchmark_data/installed-release
```

Use a fresh output directory for each run. The release builder compiles and includes the UI, checks archive boundaries and writes SHA256SUMS. Docker and CI repeat the applicable gates on Linux. Browser tests use a running loopback instance; wait at least 60 seconds between full scenarios on one server to respect the shared IP limiter. On Windows use the virtual environment’s Scripts/python.exe.
