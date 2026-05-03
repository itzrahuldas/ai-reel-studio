# ADR-0001: Technology Stack Selection

**Status:** Accepted
**Date:** 2026-05-03
**Deciders:** System Architect, Backend Engineer, Frontend Engineer

---

## Context

We need to select a technology stack for the AI Reel Studio platform that is:
- Production-ready and well-supported
- Familiar to AI agents and human engineers
- Capable of handling async AI/video workloads
- Deployable to commodity cloud infrastructure

## Decision

**Frontend:** Next.js 15 + React + TypeScript + Tailwind CSS
- Industry-standard React framework with App Router
- TypeScript for type safety across the codebase
- Tailwind for utility-first styling consistency
- TanStack Query for server state management
- Zustand for client state management

**Backend:** FastAPI + Python 3.12 + Pydantic v2 + SQLAlchemy 2
- FastAPI: modern, fast, auto-generates OpenAPI docs
- Python 3.12: best ecosystem for AI/ML integration
- Pydantic v2: fast validation, matches our schema needs
- SQLAlchemy 2 async: non-blocking DB queries

**Queue:** Celery + Redis
- Proven async task queue for Python
- Redis: fast, reliable broker + result backend
- Supports priority queues per task type (generation/rendering/publishing)

**Database:** PostgreSQL 16
- Best-in-class relational DB for complex queries
- JSONB for flexible AI output storage
- UUID primary keys for distributed uniqueness

**Storage:** S3-compatible (MinIO local, AWS S3 production)
- Industry-standard object storage API
- Provider-agnostic via boto3 abstraction

## Consequences

**Positive:**
- Strong typing throughout (TypeScript frontend, Pydantic backend)
- AI agent-friendly: all technologies have strong training data
- Fast local setup via Docker Compose
- Clear separation of concerns

**Negative:**
- Two language runtimes (Node.js + Python) increases operational complexity
- Celery requires Redis as an additional service
- SQLAlchemy async can be complex for new contributors

## Alternatives Considered

- **tRPC**: rejected — requires full TypeScript stack end-to-end
- **Django**: rejected — heavier than needed, slower auto-docs
- **BullMQ (Node.js)**: rejected — Python ecosystem better for AI/ML tasks
- **MongoDB**: rejected — relational schema with JSONB is better fit
