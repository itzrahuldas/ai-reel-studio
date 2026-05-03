# Workflow 01: Bootstrap Project

## Trigger
Run this workflow when starting a new project or initializing a new service.

## Steps

### 1. Read Existing Context
- Read README.md (root)
- Read docs/ARCHITECTURE.md
- Read docs/PRODUCT_SPEC.md
- Read .agents/agents.md

### 2. Create Folder Structure
- Create all directories as defined in ARCHITECTURE.md
- Create placeholder README.md in each meaningful folder
- Create IMPLEMENTATION_LOG.md in each package

### 3. Install Dependencies
`ash
# Frontend
cd apps/web && npm install

# Backend
cd apps/api && pip install -e ".[dev]"

# Worker
cd apps/worker && pip install -e ".[dev]"
`

### 4. Validate
- Run 
pm run typecheck in apps/web
- Run uff check . in apps/api
- Run docker compose config to validate compose file

### 5. Initial Documentation
- Update docs/CHANGELOG.md with bootstrap entry
- Create initial ADRs
- Create .env.example with all required variables

### 6. Git Init
`ash
git init
git add .
git commit -m "Bootstrap production-grade AI Reel Studio foundation"
`

### 7. Report
- Print list of created files
- Print how to run locally
- Identify any missing credentials or blockers
