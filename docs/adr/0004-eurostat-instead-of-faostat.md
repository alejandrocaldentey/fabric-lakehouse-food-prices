# ADR 0004 — Eurostat replaces FAOSTAT as the price source

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

FAOSTAT was the first choice for global producer and consumer food prices. In practice its API answered cloud runners with HTTP 521 (origin down behind Cloudflare) or hung until timeout, across several days of CI runs. A pipeline whose main source is unreachable from the cloud cannot run in Fabric either.

## Options considered

| Option | Coverage | Reliability from cloud | Fit with the question |
|---|---|---|---|
| **Eurostat Statistics API** (`apri_pi_outa`, `prc_hicp_aind`) | EU, EFTA, candidates | Good, no key | Producer index and HICP food from one harmonised source |
| FAOSTAT bulk CSV downloads | Global | Untested; same provider | Same data, heavier files |
| OECD / IMF SDMX APIs | OECD / global | Good | Consumer prices strong; farm-gate prices weak |

## Decision

**Eurostat** for both producer and consumer food prices. World Bank stays as the global context series (consumer inflation, all items).

## Consequences

- ✅ One harmonised methodology for both sides of the transmission: same country codes, same base years.
- ✅ Eurostat also publishes a food-price monitoring tool by product chain (agricultural → industrial → consumer), a natural next step for a multi-stage model.
- ⚠️ Scope narrows from global to Europe. The architecture is source-agnostic (source registry + staging), so adding a global source later is a configuration change, not a redesign.
- The live CI check is blocking again: if Eurostat is unreachable, we want to know.

## When we would revisit

FAOSTAT's API becomes reliable from cloud runners, or the question needs non-European countries.
