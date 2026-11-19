# ADR 0002 — CI/CD: GitHub Actions + fabric-cicd

- **Status:** Accepted
- **Date:** 2026-11-19
- **Deciders:** Alejandro Caldentey

## Context

Fabric items (notebooks, lakehouses, semantic models, pipelines) must move from a dev workspace to prod reproducibly. Fabric offers Git integration and built-in deployment pipelines; the open-source `fabric-cicd` Python library deploys item definitions from a repo through the Fabric REST APIs.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| **GitHub Actions + fabric-cicd** | Code lives where the portfolio is public; free for public repos; parameterised per environment | Service principal and secrets to manage |
| Azure DevOps Pipelines + fabric-cicd | Common in enterprise Microsoft shops | Pipelines are not visible next to the public code |
| Fabric deployment pipelines (UI) | Low-code, native | Manual steps; hard to review and test |

## Decision

**GitHub Actions + fabric-cicd.** Dev workspace synced through Fabric Git integration; test and prod deployed by `fabric-cicd` from `main`.

## Consequences

- ✅ Every deployment is reviewable in a pull request and visible in the public Actions log.
- ⚠️ Requires a service principal with workspace permissions, stored as GitHub secrets.
- The same `fabric-cicd` deployment script runs unchanged on Azure DevOps; switching is a pipeline-file change, not a redesign.

## When we would revisit

A client mandates Azure DevOps, or needs approval gates tied to Azure Boards.
