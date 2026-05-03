# Skill: AI Pipeline

## Provider Abstraction Rules
- Every AI provider implements the abstract base class
- Constructor takes only config (API keys via env, not constructor args)
- All methods are async
- All external calls have timeout configured
- Providers registered in a factory function:
  `python
  def get_llm_provider() -> LLMProvider:
      provider = settings.AI_PROVIDER
      if provider == 'openai': return OpenAIProvider()
      if provider == 'gemini': return GeminiProvider()
      if provider == 'mock': return MockLLMProvider()
      raise ValueError(f'Unknown AI provider: {provider}')
  `

## Prompt File Rules
- Prompts live in packages/prompts/
- Each prompt file has a version header: <!-- version: 1.0.0 -->
- Prompt files use {{variable}} placeholders for injection
- Never hardcode prompts in Python code
- Changing a prompt = bump version in the file header

## JSON Output Validation Rules
- All LLM outputs expected as JSON must be validated against a Pydantic schema
- If JSON parse fails: log the raw output + retry once with explicit JSON instruction
- If schema validation fails: log the diff + raise PipelineValidationError
- Never use unvalidated LLM output in downstream logic

## Retry / Fallback Rules
| Step              | Retries | Fallback                        |
|-------------------|---------|---------------------------------|
| LLM generation    | 3       | Return FAILED_SCRIPT            |
| Image analysis    | 2       | Proceed without image context   |
| TTS synthesis     | 3       | Silent video (no audio)         |
| AI video gen      | 2       | FFmpeg fallback render          |
| FFmpeg render     | 1       | Return FAILED_RENDER            |

## Moderation Rules
- Moderation check runs AFTER generation, BEFORE saving
- Any True moderation flag ? reject + log AuditEntry
- Moderation results always stored in GenerationJob.output_payload
- Never expose raw moderation details to frontend users
