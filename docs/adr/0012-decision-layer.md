# ADR 0012 — Decision layer: alert rules as code, playbooks per role

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

A dashboard that only describes leaves the hard part to the reader: "so what do I do?". The product should flag what matters and tell each role what to do, without turning thresholds into hidden logic in a BI tool.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Thresholds as conditional formatting in the dashboard | Fast | Invisible, unversioned, different in every report |
| Alerts in the BI tool (Power BI data alerts, Fabric Activator) | Native notifications | Per-user, not reviewable as code, not portable |
| **Rules and playbooks as versioned YAML, compiled to SQL, published as data** | Reviewed in pull requests; same rules in every consumer; testable; linked to actions | A generator to maintain |

## Decision

- `decisions/rules.yaml` holds every rule: the metric it tests, its severity levels and a message. `python -m decisions.build` compiles it to `transform/sql/09_decision_alert.sql`. The pipeline evaluates it after the forecast, so rules can test certified metrics, the champion forecast, data freshness and model drift.
- Four categories: **market** (shocks, margin squeeze or expansion, food vs basket), **forecast** (high forecast inflation), **data** (country behind the frontier), **model** (champion drift).
- `decisions/playbooks.yaml` maps each rule to four technical roles: Head of Data at a manufacturer, Head of Data at a retailer, procurement analytics lead, and pricing analytics lead. Each play pairs the **business question** the alert forces with the **data work** that answers it, a KPI, a horizon and the P&L line it touches (cost, price, volume) or trust in the numbers. The decision stays with the business owner; the data team owns the evidence. (Revised on 2026-11-26: plays first prescribed business actions; framing them as questions keeps each role accountable for its own decision.)
- In Fabric, the same `decision_alert` table feeds Activator for notifications. In the public demo, the dashboard reads it.

## Consequences

- ✅ Thresholds are reviewed like code and identical in every consumer.
- ✅ Each alert says which question to answer and what data work makes the answer repeatable.
- ⚠️ Playbooks are expert judgement, not learned. They are versioned so they can be challenged.
- 🔁 Revisit when alerts need routing to people (owners, channels): add a subscription table and send from Activator or a webhook.
