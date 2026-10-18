# English interface and presentation

Zone 1.1 uses English for product controls, onboarding, all six modes, account,
connections, help and staff tools. User notes, existing world/challenge names and
real model messages are not automatically translated. The scientific protocol,
benchmark v0.3 and database schema 4 are unchanged.

## Readable scientific screens

Experiments, hypotheses and final test states have readable numbered references.
Raw identifiers stay in technical details and API records for traceability.
Internal status codes are presented as actionable English states. Model/provider
identifiers remain meaningful configuration fields, rather than invented names.

Displayed measurements use English decimal points, at most four decimal places
for ordinary values, and scientific notation for very small or large values.
The actual numerical records and submissions retain their original precision.
Nonfinite values are not presented as measurements. Useful event order, budgets,
times, coordinates and units remain visible.

The numerical offline baseline describes its limited linear hypothesis without
printing long coefficient arrays. Its fitting and numerical predictions are
unchanged; it remains explicitly labelled **not an LLM**. Real model content is
rendered as received, with safe display-only mathematics. Zone does not promise
to rewrite arbitrary model output into plain language.

## Installation difficulty

For the local offline application, install Python 3.11 or later, then run the
three commands in [Getting started](getting-started.md). The published wheel
includes the English website; users do not need Node, Git, Docker or an AI key.
Keep the server terminal open and visit its loopback URL. On first use, create
an account, save the recovery code and choose **Start without AI**.

Connecting an API requires a provider extra and credentials. ChatGPT and Ollama
require the separate local connector terminal; this is documented setup, not a
one-click browser connection. A public server additionally needs HTTPS, backups
and an operator. [AI setup](ai-connections.md), [self-hosting](self-hosting.md).

## Video and screenshot

The README image is a capture of the English application. Its landing example is
explicitly illustrative. The [42-second introduction](https://github.com/zalaso/Zone/releases/download/v1.1.0/zone-introduction-en.mp4)
is a silent 1920 × 1080 MP4 with English captions, actual local product screens
and a numerical offline trial. It contains no credentials, provider inference,
music or invented research findings. Release media is separate from the small
installation wheel.

To reproduce the captures, build the frontend, start a new loopback workspace
on port 8770 and, from `frontend`, run:

```sh
node scripts/capture-presentation.mjs
```

Requires Playwright's browser and FFmpeg on PATH. Use
`ZONE_SMOKE_BASE_URL`, `ZONE_MEDIA_OUT` or `ZONE_FFMPEG` to override the local
URL, output directory or FFmpeg executable. Output defaults to ignored
`benchmark_data/english-presentation`. The script creates a synthetic local
account, explicitly authorizes one simulation and uses only the numerical
offline baseline. Use a disposable workspace and wait between full browser
scenarios to respect real quotas. No recovery or connector key screen is captured.

## Verification scope

Local verification covers Python and UI regression tests, TypeScript/build,
public bundle guards, real browser flows on desktop/mobile, explicit approval,
modified settings before prediction, mathematical rendering, history without
future observations and offline comparison completion. A clean installed wheel
is exercised outside the checkout for launch, account creation, persistence,
restart and restore. Release CI repeats the applicable checks on Linux/Windows.

For 1.1.0, the local regression suite passed **298 Python tests, 39 UI tests
and 2 frontend guard tests**. The browser checks completed a modified experiment
with a preregistered prediction, Human vs AI and a personal offline Arena trial,
including mobile/tablet layouts, reduced motion and history replay. The
experience scenario observed no external product requests or CSP violations.

These are engineering checks, not a user study, accessibility certification or
new validation of real model scientific ability. This update performs no real
provider calls, model downloads or production-server deployment.
