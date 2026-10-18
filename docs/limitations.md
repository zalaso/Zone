# Scope and scientific limitations

Version 1.0 finishes the reusable open-source application and distribution, rather than opening a centrally managed SaaS. All six web modes, CLI, benchmark, world generation, scientific scoring, accounts, personal connections and operational tools are included.

## Deliberate boundaries

- **Worlds:** generator version 1 supports levels 1–5. Levels 6–9 are explicitly non-generatable research interfaces, not unfinished buttons in the application. No contact, floor, collision or arbitrary-code physics engine is provided.
- **Numerics:** RK4 and bounded stability checks are tested but are not a certified numerical solver or global error bound. Failed launches provide no fabricated partial observations.
- **Identification:** candidate laws use a restricted AST. Equivalence is empirical on the private evaluation grid, not a general symbolic theorem prover. There is no arbitrary formula execution.
- **Benchmark:** four conditions remain separate; active learning is compared primarily against sequential passive learning. Batch passive is diagnostic. Probe categories and costs/calls are not combined into a single score. Compatibility checks reject unfair pairs; descriptive uncertainty is not a claim of statistical superiority.
- **Agents:** external model identity and costs are declared, not cryptographically attested. Readable model messages are not private chain of thought. Real-world model quality and exact reply reproducibility are not guaranteed.
- **Credentials:** API and local connector paths are separate. Direct hosted ChatGPT plan usage is subject to OpenAI's requirements and is not implied by publishing the repository.
- **Hosting:** one trusted application process with SQLite is the supported scope. HTTPS, backups, policy and capacity remain the instance operator's responsibility. There is no distributed cluster, email recovery or centrally operated service.
- **UX:** the interface is currently Italian; the primary installation and deployment guides are English, with an Italian README and in-app explanations. Native MathML requires a modern browser. Reduced motion and numeric tables are supported, without claiming a complete accessibility certification.

## What has been validated

Automated tests cover simulator dynamics, seeded generation, message validation, public/private payloads, state transitions, human confirmation, scoring, benchmark pairing, ownership, quotas, revocation, migrations, recovery and packaging. Browser scenarios exercise real local HTTP, SQLite and the numerical offline agent. Provider adapters are tested with simulated transports, without paid inference. Release evidence distinguishes these checks from any historical model pilot.

A small earlier real-model investigation showed the protocol can complete; it does not validate scientific discovery across worlds, model families or adversarial participants. Any research claim needs an explicit study design and authorized independent trials. Example worlds, demo scripts and revealed cases are unsuitable as blind evaluation material.

Future experiments can be proposed through issues. They are optional research extensions, not required setup steps for the shipped application.
