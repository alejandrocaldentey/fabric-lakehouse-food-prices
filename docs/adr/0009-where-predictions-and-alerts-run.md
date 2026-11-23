# ADR 0009 — Where forecasts and alerts are computed: in the pipeline, with a governed browser simulator

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

The product adds a forecast of next year's consumer food inflation, alerts on KPI thresholds and a what-if simulator. Each of these can be computed in the pipeline, in the browser or by an API on demand. The choice decides which numbers are governed, who can audit them and what the platform costs.

## Options considered

| Option | Pros | Cons | When it fits |
|---|---|---|---|
| **Batch in the pipeline** | One definition; contracts, tests and lineage apply; reproducible (versioned data + model); near-zero serving cost | Fresh only at the refresh cadence; only pre-computed scenarios | Numbers somebody signs off: KPIs, official forecasts, alerts |
| In the browser | Full interactivity; no backend | Logic duplicated in TypeScript, so two implementations drift; no contracts or lineage; not auditable; no heavy models | Presentation only, never definitions |
| API on demand (edge function or model endpoint) | One implementation; unlimited scenarios | Infrastructure to run and secure; cost and cold starts | Many scenarios or heavy models, at enterprise scale |
| **Hybrid: pipeline computes, browser applies published coefficients** | Governed outputs plus interactive what-if; still one definition | The browser formula must match the pipeline exactly | This product |

## Decision

**Hybrid.** The pipeline trains the models, scores them, picks the champion, evaluates the alert rules and publishes everything as tables with contracts and lineage. The browser never trains or decides anything: the shock simulator only applies the regression coefficients the pipeline published.

A **parity test** guards the boundary. In this repo, `tests/test_ml.py::test_published_coefficients_reproduce_the_forecast` proves the published coefficients rebuild every published forecast. In the dashboard, the build fails if its formula, applied to the published inputs, does not reproduce the published forecast for every country.

Rule of thumb: compute where the definition is governed; the closer to the user, the less logic it should own.

## Consequences

- ✅ Every number on screen, including alerts, has a contract, a lineage and a run id.
- ✅ The what-if stays interactive at zero backend cost.
- ⚠️ A new model family the browser cannot apply (for example gradient boosting) stays pipeline-only; the simulator always uses the explainable model.
- 🔁 Revisit when scenarios multiply (many products, monthly data) or models get heavier: move the simulator behind an API endpoint backed by the same model registry.
