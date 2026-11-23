# ADR 0010 — Chain-link index bases and rebase to 2020 = 100

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

Eurostat publishes the agricultural output price index in five bases (2000, 2005, 2010, 2015 and 2020 = 100). Each base covers only some years: the 2020 base starts in 2020. Using one base cut the story to 2020-2025, which hides the 2008 and 2011 commodity spikes. Levels from different bases cannot be mixed: 110 in base 2015 and 110 in base 2020 are different prices. The consumer index (HICP) has a single current base, which is not 2020.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Keep only the 2020 base | Simple, no transformation | Six years of history; no crisis to learn from; too short to backtest a model |
| Splice growth rates from each base | Easy | Levels are lost; cumulative comparisons impossible |
| **Backward ratio chain-linking, newest base first, rebased to 2020 = 100** | Keeps each base's own growth rates; one continuous level; producer and consumer levels comparable | Rule to document; link years must exist |

## Decision

**Chain-link in silver** (`transform/sql/02_silver_price_index_chained.sql`), in portable SQL:

1. The newest base wins every year it covers.
2. An older base only fills years before every newer base starts; a base that starts later than a newer one adds nothing and is dropped.
3. Each older base is multiplied by the ratio of the newer base to the older one at the year the newer base starts.
4. If that year is missing in the older base, the chain stops there. No value is interpolated.
5. Every series, producer and consumer, is rebased so 2020 = 100.

Each published value keeps its `source_unit`, `source_value`, `rebase_factor` and `link_year`, so any number can be traced back to the figure Eurostat published.

## Consequences

- ✅ History from 2000 for 25 of 27 countries (Croatia from 2005, Estonia from 2015, where a link year is missing), and 424 out-of-sample points to backtest the models.
- ✅ Producer and consumer levels share a base, so "since 2000, farm-gate +X% vs shelf +Y%" is a valid comparison.
- ✅ Growth rates in each year equal those Eurostat published in that year's base.
- ⚠️ Chain-linked levels are not additive across countries; aggregates must be built from weights, not by summing.
- 🔁 Revisit when Eurostat moves to a 2025 base: add `I25` with priority 1 in `seed_index_base.csv` and the chain re-links itself.
