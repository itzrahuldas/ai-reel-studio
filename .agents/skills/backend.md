# Skill: Backend Engineering

## FastAPI Conventions
- Routers registered in pp/api/v1/ — one file per resource
- All routes use dependency injection for DB session and current user
- Always return typed Pydantic response models
- Never return raw SQLAlchemy objects from routes

## Router / Service / Repository Separation
`
Router     ? validates HTTP request, calls service, returns HTTP response
Service    ? business logic, calls repository, calls external services
Repository ? database access only (queries, inserts, updates)
`

## Pydantic Schema Rules
- Separate schemas for Create / Update / Response
- Response schemas must not include sensitive fields (passwords, raw tokens)
- Use model_config = ConfigDict(from_attributes=True) for ORM mode
- Validate all string fields: min/max length, pattern where needed

## SQLAlchemy Model Rules
- All models inherit from Base (declarative)
- All PKs are UUID: id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
- All timestamps: created_at, updated_at with server defaults
- updated_at auto-updated via onupdate=func.now()
- Status fields use Python Enum mapped to VARCHAR

## Migration Rules
- Always use lembic revision --autogenerate -m "description"
- Test both upgrade and downgrade before committing
- Never DROP columns without a data migration plan
- Run migrations before deploying new API version

## Error Handling Rules
- Raise HTTPException with specific status codes from routers
- Raise custom exceptions from services (mapped to HTTP in exception handlers)
- Never bare except Exception — always catch specific exceptions or re-raise
- All exceptions log with logger.exception() including correlation_id
