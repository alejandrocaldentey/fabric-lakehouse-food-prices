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
| Head of Data · Food manufacturer | Re-run the COGS forecast and brief finance on the margin at risk before the next budget cycle. | Join this index to the bill of materials by commodity; publish cogs_inflation_pct in the semantic layer with the same lag the regression uses. | COGS inflation vs list-price inflation (pp) | 0-3 months |
| Head of Data · Retailer or distributor | Expect supplier price-increase requests within two quarters; prepare category baselines now. | Build a supplier-request tracker that compares each requested increase with the farm-gate index of the product's inputs. | Requested increase minus input-cost increase (pp) | 3-6 months |
| Procurement analytics lead | Decide whether to lock volume or shorten contracts; a shock this size usually partly reverses. | Add a contract-coverage view (volume locked vs forecast need by month) next to the index and the forecast interval. | Share of next 12 months' volume under fixed price | 0-3 months |
| Pricing and revenue analytics lead | Plan staged price moves instead of one jump; consumers react to step changes more than to the total. | Simulate pass-through scenarios with the published coefficients against your price-elasticity model. | Volume at risk per point of price increase | 3-6 months |

## When `margin_squeeze` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Prioritise cost-to-serve and mix actions; list prices are lagging input costs. | Ship a margin bridge (price, volume, mix, input cost) at SKU level, refreshed with every index update. | Gross margin bridge by driver (pp) | 0-3 months |
| Head of Data · Retailer or distributor | Suppliers are absorbing costs now and will push them through; anticipate a wave of renegotiations. | Score suppliers by exposure to the squeezed commodities so negotiators start with the riskiest. | Spend exposed to squeezed categories (%) | 3-6 months |
| Procurement analytics lead | Use the squeeze in negotiations; suppliers' costs rose more than their prices. | Provide should-cost models per category built on the farm-gate index and the lag structure. | Should-cost vs quoted price (%) | 0-3 months |
| Pricing and revenue analytics lead | Identify where a price move is justified by costs and defensible to buyers and consumers. | Rank SKUs by cost gap and elasticity to target increases where volume risk is lowest. | Margin recovered per point of volume lost | 0-3 months |

## When `margin_expansion` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Downstream margins are widening; expect retailers to push back on your next increase. | Evidence pack linking your price changes to input-cost changes, generated from governed metrics, not slides. | Your price change vs input-cost change (pp) | 3-6 months |
| Head of Data · Retailer or distributor | Shelf prices are running ahead of costs; reputational and regulatory risk rises. | Monitor shelf-price vs input-cost gaps by category with alerts, and keep the lineage auditable for regulators. | Shelf vs farm-gate gap by category (pp) | 0-3 months |
| Procurement analytics lead | Farm-gate costs are not the driver; look at energy, labour and logistics in supplier quotes. | Extend the cost model with energy and labour indices so quotes are decomposed by driver. | Share of quote increase explained by each driver | 3-6 months |
| Pricing and revenue analytics lead | Room for promotions or price investment without hurting margin; competitors may move first. | Track competitor price indices against your own and the farm-gate index. | Price index vs competitors (base 100) | 0-3 months |

## When `food_inflation_premium` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Food is outpacing household budgets; expect trading down to private label. | Add channel and brand-tier mix to the sales model to catch trading down early. | Private-label share in your categories (%) | 3-6 months |
| Head of Data · Retailer or distributor | Price perception becomes the battleground; protect key-value items. | Maintain a governed list of key-value items with price-perception tracking. | Basket price index of key-value items | 0-3 months |
| Pricing and revenue analytics lead | Elasticities shift when food outpaces income; re-estimate before the next price round. | Re-train elasticity models with the inflation premium as a feature. | Elasticity change vs last estimate | 0-3 months |

## When `forecast_food_inflation` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Build next year's budget on the forecast range, not a single number. | Feed the 80% interval, not only the point, into the planning model and show it in the budget pack. | Budget margin at the low and high end of the interval | next budget cycle |
| Head of Data · Retailer or distributor | Agree with category teams which interval bound each plan uses. | Publish the forecast as a certified metric with its model version, so every plan cites the same run. | Plans using the certified forecast (%) | next budget cycle |
| Procurement analytics lead | Front-load purchases where storage allows and prices are still below the forecast. | Combine the forecast with storage capacity and shelf life in a buy-timing model. | Cost avoided vs buying at forecast prices | 3-12 months |
| Pricing and revenue analytics lead | Prepare the price architecture for the forecast level, with triggers rather than dates. | Encode price triggers as rules on the published forecast, versioned like these alerts. | Time from trigger to price change (days) | 3-12 months |

## When `data_stale` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Treat this country's numbers as provisional in any decision. | Show freshness next to every metric and fall back to the regional aggregate with a visible flag. | Decisions taken on stale data (count) | now |
| Head of Data · Retailer or distributor | Do not benchmark this country's suppliers on these numbers until the data catch up. | Add a freshness SLA per source to the data contract and alert the owner, not the consumer. | Sources within freshness SLA (%) | now |

## When `model_drift` fires

| Role | Business action | Data action | KPI | Horizon |
|---|---|---|---|---|
| Head of Data · Food manufacturer | Pause decisions that rely on the point forecast; use the interval or the baseline. | Open a model review - check feature drift, retrain, and re-run the champion selection. | Recent vs long-run forecast error (x) | now |
| Head of Data · Retailer or distributor | Tell planners the forecast is under review and which fallback to use. | Route drift alerts to the model owner with the backtest attached; record the decision in an ADR. | Time to resolve a drift alert (days) | now |
