# ADR 0011 — Forecasting: three models, rolling-origin backtest, simplest champion within tolerance

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

Buyers, finance teams and pricing teams want to know next year's consumer food inflation. Data are annual, about 25 years per country, 27 countries. Short series punish complex models, and a forecast feeds decisions somebody must justify.

## Options considered

| Model | Pros | Cons |
|---|---|---|
| Naive persistence: next year = this year | No parameters; the reference to beat | Always one year late at turning points |
| **Panel distributed-lag regression with country fixed effects** | Coefficients with economic meaning (pass-through per point of farm-gate change); pooling gives stable slopes | Same pass-through everywhere; linear |
| Gradient boosting | Non-linear effects | Overfits short series; hard to explain; cannot extrapolate |

And for choosing between them:

| Selection rule | Pros | Cons |
|---|---|---|
| Lowest error wins | Simple | Rewards complexity for noise-level gains |
| **Champion-challenger: must beat the baseline by 5% of its error; simplest model within 5% of the best wins** | Complexity has to earn its place; decision stays explainable | Two thresholds to govern |

## Decision

All three models run on every refresh (`ml/models.yaml`, `ml/forecast.py`). A **rolling-origin backtest** predicts each year from 2010 on with models trained only on earlier years, so no future data leaks in. Errors are published overall, in shock years (farm-gate change of 10% or more) and over the last three years.

The champion is the simplest model whose error is within 5% of the best, among models that beat the baseline by at least 5%. Intervals are empirical: the 10th and 90th percentiles of each model's backtest errors.

On the first run the regression and gradient boosting tie (MAE 2.41 vs 2.40 pp, both 22% better than the baseline), so **the regression is champion**: same accuracy, and every coefficient can be challenged by the business. Gradient boosting stays as a challenger; it does better in shock years, which is worth watching.

## Consequences

- ✅ The choice is reproducible and auditable: rules in YAML, results in `ml_model_registry`.
- ✅ The champion's coefficients feed the browser simulator (ADR 0009).
- ✅ Drift is monitored by an alert rule: recent error vs long-run error (ADR 0012).
- ⚠️ Annual data limit what any model can do; the 80% interval is about 7 pp wide, and the dashboard shows it.
- 🔁 Revisit with monthly data (Eurostat publishes monthly HICP): more observations would let gradient boosting or state-space models earn their place.
