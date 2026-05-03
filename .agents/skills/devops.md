# Skill: DevOps

## Docker Rules
- Worker and API must NOT run as root user
- Use multi-stage builds to minimize image size
- Pin base image versions (e.g., python:3.12.3-slim)
- Install FFmpeg in worker image: pt-get install -y ffmpeg
- Health checks defined for all services in docker-compose.yml

## CI Rules
- CI runs on every push to main and every PR
- Jobs: lint ? typecheck ? unit tests ? integration tests
- Fail fast: if lint fails, do not run tests
- Cache dependencies: npm cache, pip cache
- Secrets: use GitHub Actions Secrets only, never in workflow YAML

## Migration Rules
- Migrations run as a pre-deploy step (separate job in CI/CD)
- Test: lembic upgrade head + lembic downgrade -1 in CI
- Never run migrations as part of application startup

## Environment Variable Rules
- All env variables documented in .env.example
- .env.example has no real values — only placeholder strings
- New env variable added = .env.example updated = CHANGELOG entry
- Group variables by category with comments in .env.example

## Deployment Checklist
Before every production deploy:
- [ ] All tests passing in CI
- [ ] CHANGELOG.md updated
- [ ] .env.example updated with any new variables
- [ ] Database migration tested on staging
- [ ] Docker image builds successfully
- [ ] docker compose up --build runs without errors
- [ ] Health endpoint returns 200
- [ ] Sentry/monitoring configured for new service
