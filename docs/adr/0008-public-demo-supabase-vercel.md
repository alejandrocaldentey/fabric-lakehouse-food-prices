# ADR 0008 — Public demo: Diamond on Supabase, dashboard on Vercel

- **Status:** Accepted — decided by Alejandro Caldentey on 2026-11-23
- **Date:** 2026-11-23

## Context

The Fabric trial ends after 60 days, and Power BI "publish to web" exposes data with no control. A portfolio needs a demo that anyone can open, that stays up, and that costs nothing.

## Options considered

| Option | Interactive | Stays up after the trial | Cost | Control |
|---|---|---|---|---|
| **Diamond in Supabase Postgres (read-only, RLS) + Next.js dashboard on Vercel, refreshed by GitHub Actions** | Yes | Yes | Free tiers | Read-only role, row-level security |
| Power BI publish to web | Yes | Only with capacity | Capacity | None: public URL |
| Static site with charts rendered at build time | Limited | Yes | Free | Full |

## Decision

**Supabase + Vercel.** GitHub Actions runs the pipeline on DuckDB, then upserts `diamond_country_year` and `dim_country` into Supabase. The dashboard reads them through a read-only role with row-level security; no write key ever reaches the browser. Metric labels, units and descriptions come from the metric catalogue ([ADR 0006](0006-diamond-metrics-layer.md)), so the dashboard shows the same definitions as Power BI.

## Consequences

- ✅ The demo survives the Fabric trial and costs nothing.
- ✅ It shows the architecture is platform-independent: Fabric for the enterprise path, open stack for the public path, one metric catalogue.
- ⚠️ Free tiers pause inactive projects; the weekly CI refresh keeps the database active.
