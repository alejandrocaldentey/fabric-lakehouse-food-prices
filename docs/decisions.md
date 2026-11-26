# Decision layer: alerts and playbooks

Generated from [`decisions/rules.yaml`](../decisions/rules.yaml) and [`decisions/playbooks.yaml`](../decisions/playbooks.yaml) by `python -m decisions.build` ([ADR 0012](adr/0012-decision-layer.md)).

## Rules

| Rule | Category | Tests | High | Medium |
|---|---|---|---|---|
| `farm_gate_shock` Farm-gate price shock | market | `a.producer_price_change_pct` | `ABS(value) >= 20` | `ABS(value) >= 10` |
| `margin_squeeze` Downstream margin squeeze | market | `a.food_price_gap_pp` | `value <= -10` | `value <= -5` |
| `margin_expansion` Shelf prices outrunning farm-gate | market | `a.food_price_gap_pp` | `value >= 10` | `value >= 5` |
| `food_inflation_premium` Food outpacing the basket | market | `a.food_inflation_premium_pp` | `value >= 6` | `value >= 3` |
| `forecast_food_inflation` High food inflation forecast | forecast | `a.forecast_next_pct` | `value >= 6` | `value >= 4` |
| `data_stale` Country data behind the frontier | data | `a.years_behind` | `value >= 2` | `value >= 1` |
| `model_drift` Forecast model drift | model | `m.mae_recent / NULLIF(m.mae, 0)` | `value >= 2` | `value >= 1.5` |

## Roles

- **Head of Data · Food manufacturer** — Protect gross margin when raw-material costs move; give procurement and finance one version of the cost outlook.
- **Head of Data · Retailer or distributor** — Keep shelf prices competitive and defensible; give category teams and negotiators the same numbers suppliers will quote.
- **Procurement analytics lead** — Time contracts, hedges and supplier negotiations with farm-gate price signals.
- **Pricing and revenue analytics lead** — Decide when and how much to move list prices without losing volume or trust.

## When `farm_gate_shock` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | How much margin is at risk if the shock reaches our input costs, and when does it hit COGS? | Join the farm-gate index to the bill of materials by commodity; publish cogs_inflation_pct in the semantic layer with the same one-year lag the model uses. | COGS inflation vs list-price inflation (pp) | 0-3 months | cost |
| Head of Data · Retailer or distributor | Which supplier price-increase requests should we expect in the next two quarters, and how big should they be? | Supplier-request tracker comparing each requested increase with the farm-gate index of the product's inputs. | Requested increase minus input-cost increase (pp) | 3-6 months | cost |
| Procurement analytics lead | Should we lock volume now or keep contracts short? Since 2001, after a farm-gate move of 10% or more, the next year's move was smaller in 77% of 148 cases and reversed in 41%. | Contract-coverage view (volume locked vs forecast need by month) next to the index and the forecast interval. | Share of next 12 months' volume under fixed price | 0-3 months | cost |
| Pricing and revenue analytics lead | How much of this shock will reach our costs next year (about 0.25 points per point of farm-gate inflation), and how much volume would each point of price increase cost? | Simulate pass-through scenarios with the published coefficients against our price-elasticity model. | Volume at risk per point of price increase | 3-6 months | price |

## When `margin_squeeze` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Which SKUs and drivers explain the margin loss, and which can we act on this quarter? | Margin bridge (price, volume, mix, input cost) per SKU, refreshed with every index update. | Gross margin bridge by driver (pp) | 0-3 months | cost |
| Head of Data · Retailer or distributor | Which suppliers are absorbing costs now and most likely to push them through next? | Score suppliers by exposure to the squeezed commodities so negotiators start with the riskiest. | Spend exposed to squeezed categories (%) | 3-6 months | cost |
| Procurement analytics lead | Are supplier quotes below what their inputs justify, and how long can that last? | Should-cost models per category built on the farm-gate index and its one-year lag. | Should-cost vs quoted price (%) | 0-3 months | cost |
| Pricing and revenue analytics lead | Where is a price increase justified by costs and least likely to cost volume? | Rank SKUs by cost gap and price elasticity. | Margin recovered per point of volume lost | 0-3 months | price |

## When `margin_expansion` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Can we justify our next price increase with input-cost evidence when retailers push back? | Evidence pack linking our price changes to input-cost changes, generated from governed metrics, not slides. | Our price change vs input-cost change (pp) | 3-6 months | price |
| Head of Data · Retailer or distributor | Where are shelf prices running ahead of costs, and can we explain each gap to a regulator? | Monitor shelf vs input-cost gaps by category with alerts; keep the lineage auditable. | Shelf vs farm-gate gap by category (pp) | 0-3 months | price |
| Procurement analytics lead | If farm-gate costs do not explain supplier quotes, what does: energy, labour or logistics? | Extend the cost model with energy and labour indices so quotes are decomposed by driver. | Share of quote increase explained by each driver | 3-6 months | cost |
| Pricing and revenue analytics lead | Is there room to invest in price while input costs ease, before competitors do? | Track competitor price indices against ours and the farm-gate index. | Our price index vs competitors (base 100) | 0-3 months | price |

## When `food_inflation_premium` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Are customers trading down to private label in our categories, and how early can we see it? | Add channel and brand tier to the sales model. | Private-label share in our categories (%) | 3-6 months | volume |
| Head of Data · Retailer or distributor | Are we protecting price perception on the products customers remember (key-value items)? | A governed list of key-value items with price-perception tracking. | Basket price index of key-value items | 0-3 months | price |
| Pricing and revenue analytics lead | Have price elasticities changed now that food outpaces other prices? | Re-estimate elasticity models with the food inflation premium as a feature. | Elasticity change vs last estimate | 0-3 months | volume |

## When `forecast_food_inflation` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | What happens to next year's margin at the low and high end of the forecast range? | Feed the 80% interval, not only the point, into the planning model. | Budget margin at both ends of the interval | next budget cycle | cost |
| Head of Data · Retailer or distributor | Which forecast bound does each category plan use, and do all plans cite the same run? | Publish the forecast as a certified metric with its model version. | Plans using the certified forecast (%) | next budget cycle | trust |
| Procurement analytics lead | Is it worth buying ahead of the forecast, given storage capacity and shelf life? | Combine the forecast with storage capacity and shelf life in a buy-timing model. | Cost avoided vs buying at forecast prices | 3-12 months | cost |
| Pricing and revenue analytics lead | Which price changes should trigger automatically if the forecast crosses a threshold? | Encode price triggers as rules on the published forecast, versioned like these alerts. | Time from trigger to price change (days) | 3-12 months | price |

## When `data_stale` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Which decisions this month rest on this country's provisional numbers? | Show freshness next to every metric; fall back to the last complete year with a visible flag. | Decisions taken on stale data (count) | now | trust |
| Head of Data · Retailer or distributor | Are we benchmarking suppliers on numbers that are out of date? | A freshness SLA per source in the data contract; alert the owner, not the consumer. | Sources within freshness SLA (%) | now | trust |

## When `model_drift` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Can we still trust the point forecast, or should plans switch to the interval or the baseline? | Open a model review: feature drift, retrain, re-run champion selection. | Recent vs long-run forecast error (x) | now | trust |
| Head of Data · Retailer or distributor | Do planners know the forecast is under review and which fallback to use? | Route drift alerts to the model owner with the backtest attached; record the decision in an ADR. | Time to resolve a drift alert (days) | now | trust |
