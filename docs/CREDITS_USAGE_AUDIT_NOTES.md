# Credits, Plans & Usage Limits — Audit Notes

**Date:** 2026-05-04
**Branch:** `feature/credits-usage-limits`
**Auditor:** Antigravity (automated)

---

## 1. Database Tables

| Table | In `models.py` | In Alembic migration | Notes |
|---|---|---|---|
| `workspace_subscriptions` | ✅ `models.py:372` | ✅ `0006` line 30 | `UNIQUE` on `workspace_id` |
| `usage_counters` | ✅ `models.py:388` | ✅ `0006` line 47 | Index on `workspace_id` |
| `usage_events` | ✅ `models.py:405` | ✅ `0006` line 64 | Index on `workspace_id` |

**Result: ✅ All 3 tables present in both models and migration.**

---

## 2. Default FREE Subscription on Registration

- ✅ `apps/api/app/services/auth.py` — `create_default_workspace()` creates a `WorkspaceSubscription` row with `plan_key="FREE"`, `status=ACTIVE`, and correct `current_period_start/end` on every new registration.

---

## 3. Usage Enforcement Points

| Action | File | Line | Event Type | Status |
|---|---|---|---|---|
| Create reel | `services/reel_project.py` | 69 | `AI_GENERATION` | ✅ Enforced |
| Regenerate reel | `services/reel_project.py` | 271 | `AI_GENERATION` | ✅ Enforced |
| Render reel | `services/render_service.py` | 104 | `RENDER` | ✅ Enforced |
| Publish now | `services/publish_service.py` | 149 | `PUBLISH` | ✅ Enforced |
| Schedule publish | `services/publish_service.py` | 305 | `SCHEDULED_PUBLISH` | ✅ Enforced |

All five enforcement points call `consume_usage()`, which internally calls `check_usage_limit()` first and raises `HTTP 402` if the quota is exceeded.

---

## 4. HTTP 402 Error Structure

**Location:** `services/usage_service.py:155–163`

```python
raise HTTPException(status_code=402, detail={
    "code": "USAGE_LIMIT_EXCEEDED",
    "message": "...",
    "plan_key": plan.key.value,
    "limit": limit,
    "used": used,
    "upgrade_required": True
})
```

✅ Structure matches the required contract exactly.

---

## 5. Dev Routes Guard

**Location:** `api/v1/routers/billing.py:92–101`

```python
def _require_dev_env() -> None:
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, ...)
```

Applied via `DevEnv = Depends(_require_dev_env)` on both:
- `POST /billing/dev/set-plan`
- `POST /billing/dev/grant-usage`

✅ Both routes are blocked when `APP_ENV != development`.

---

## 6. Idempotency / Refund

| Scenario | Implementation | Status |
|---|---|---|
| Retry does not double-charge | `consume_usage` checks `related_job_id` in `usage_events` before inserting | ✅ |
| Cancel schedule frees slot | `cancel_scheduled_publish_job` calls `refund_usage(SCHEDULED_PUBLISH)` | ✅ (`publish_service.py:399`) |
| Render failure refund | Not called — render counter is NOT refunded on pipeline failure | ⚠️ Minor gap |

---

## 7. Frontend 402 Error Handling

### What exists

| File | What's there |
|---|---|
| `lib/api-client.ts:318` | `isUsageLimitError()` type guard defined |
| `lib/api-client.ts:355–359` | Axios interceptor detects status `402`, sets `_isUsageLimitError: true` |
| `lib/api-client.ts:307–325` | `UsageLimitError` interface defined |

### What is MISSING ❌

| Page | Problem | Impact |
|---|---|---|
| `dashboard/create/page.tsx:117` | Catches all errors as `ApiError` and calls `setApiError(apiErr?.message)`. For 402, `apiErr` is a `UsageLimitError` — `message` field exists so it does display, **but there is no upgrade CTA, no plan info, no link to `/dashboard/billing`** | Medium — user sees error text but no guidance |
| `dashboard/reels/[id]/page.tsx` | `renderMutation.onError` and `publishMutation.onError` use `alert()` only — 402 errors crash into a plain browser alert with no structured info | High — terrible UX on limit hit |
| `dashboard/reels/[id]/edit/page.tsx` | Same — `renderMutation.onError` uses `alert()` | High |
| **All pages** | `isUsageLimitError` is **never imported or called** in any `.tsx` file | The type guard exists but is completely unused |

---

## 8. Summary

| Check | Result |
|---|---|
| DB tables exist | ✅ |
| Default FREE plan on registration | ✅ |
| Create reel gated | ✅ |
| Regenerate reel gated | ✅ |
| Render gated | ✅ |
| Publish now gated | ✅ |
| Schedule publish gated | ✅ |
| 402 error format correct | ✅ |
| Dev routes blocked in production | ✅ |
| Frontend `isUsageLimitError` defined | ✅ |
| Frontend `isUsageLimitError` **used** in pages | ❌ |
| Upgrade CTA shown on 402 | ❌ |
| Render failure refund | ⚠️ Minor |

---

## 9. Files That Need Changes

### Priority 1 — Frontend 402 UX (currently broken UX, no crash)

1. **`apps/web/src/app/dashboard/create/page.tsx`**
   - Import `isUsageLimitError` from `@/lib/api-client`
   - In `onSubmit` catch block: check `isUsageLimitError(err)` first
   - If true: set a `usageLimitError` state with plan info and render a banner with upgrade link
   - Change: ~15 lines

2. **`apps/web/src/app/dashboard/reels/[id]/page.tsx`**
   - `renderMutation` and `publishMutation` `onError` callbacks currently use `alert()`
   - Replace with state-based error display that checks `isUsageLimitError`
   - Show: limit hit message + current plan + "View Plans →" link to `/dashboard/billing`
   - Change: ~30 lines

3. **`apps/web/src/app/dashboard/reels/[id]/edit/page.tsx`**
   - Same as above for `saveMutation` and `renderMutation`
   - Change: ~15 lines

### Priority 2 — Minor backend gap

4. **`apps/api/app/services/render_service.py`**
   - In `_run_render_pipeline_inline` exception handler (line 373–398): call `refund_usage(RENDER)` on failure
   - Currently a failed render silently keeps the render count incremented
   - Change: ~5 lines

### Priority 3 — No action needed

- `billing.py` dev guard — ✅ already correct
- `models.py` + migration — ✅ already correct
- `consume_usage` idempotency — ✅ already correct

---

## 10. Recommended Next Patch

```
fix(billing/frontend): surface 402 usage-limit errors with upgrade CTA

- create/page.tsx: detect isUsageLimitError, show plan limit banner
- reels/[id]/page.tsx: replace alert() with 402-aware error state on render/publish
- reels/[id]/edit/page.tsx: same for render mutation
- render_service.py: refund RENDER usage on pipeline failure
```

**After this patch:** the system will be fully enforced end-to-end.
**Safe to proceed to Stripe?** Yes — backend enforcement and DB schema are production-ready. The frontend UX gap is cosmetic (errors display as text, not crash), not a security issue.
