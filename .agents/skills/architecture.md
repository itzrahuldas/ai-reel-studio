# Skill: Architecture

## How to Modify Architecture

### Before Making Changes
1. Read docs/ARCHITECTURE.md fully
2. Read all existing ADRs in docs/DECISIONS/
3. Understand current service boundaries

### ADR Rule
Every non-trivial architectural decision MUST have an ADR:
- New external dependency
- New service boundary
- Change to data storage strategy
- Change to auth strategy
- Choice of provider/library where alternatives exist

ADR template:
`markdown
# ADR-XXXX: Title
**Status:** Proposed | Accepted | Deprecated | Superseded
**Date:** YYYY-MM-DD
**Deciders:** [Agent personas involved]

## Context
## Decision
## Consequences
## Alternatives Considered
`

### Mermaid Diagram Rule
- Update docs/ARCHITECTURE.md system diagram for any service addition/removal
- All diagrams must render in GitHub Markdown
- Test diagrams at https://mermaid.live before committing

### Dependency Rule
- No service should directly access another service's database
- Frontend only communicates with API (never directly with DB, Redis, or S3)
- Worker only communicates via task queue (never directly with API)
- All external integrations go through service adapters
