# Product Specification — AI Reel Studio

**Version:** 0.1.0 (Bootstrap)
**Status:** Draft
**Owner:** Product Manager (AI Agent)
**Last Updated:** 2026-05-03

---

## 1. Problem Statement

Creating high-quality Instagram Reels requires:
- Professional scriptwriting skills
- Video production tools
- Graphic design capabilities
- Consistent branding knowledge
- Knowledge of Instagram content strategy

This is inaccessible to most small business owners, solopreneurs, content creators, and agencies working at scale. Existing tools either require manual effort across multiple apps or produce low-quality outputs.

**AI Reel Studio solves this by providing an end-to-end pipeline:** from a text idea + one image → to a published Instagram Reel — in minutes, with human approval at each step.

---

## 2. Target Users

| Persona            | Description                                                   |
|--------------------|---------------------------------------------------------------|
| Solopreneur        | One-person business wanting professional social content       |
| Small Business     | Local shops, restaurants, service providers                   |
| Content Creators   | Influencers managing multiple brand deals                     |
| Social Media Agency| Agencies managing 10–100 client accounts                     |
| E-commerce Brand   | Product-focused brands needing product showcase Reels         |

---

## 3. MVP Scope

### In Scope (MVP)
- Text prompt + image input
- AI-generated script, storyboard, caption, hashtags
- AI voiceover (TTS)
- Subtitle generation
- FFmpeg-rendered vertical MP4 (9:16)
- AI video provider adapter (pluggable)
- Manual review and approval UI
- Instagram Reels publish via Meta Graph API
- Single workspace per user
- Basic account management

### Not in Scope (MVP)
- Multi-platform publishing (TikTok, YouTube Shorts)
- Real-time collaboration editing
- Custom brand kit builder
- Scheduled publishing queue (Phase 2)
- Analytics dashboard
- White-label / reseller mode
- Video template library
- Multi-step human approval with comments

---

## 4. Non-Goals

- We are NOT building a general-purpose video editor
- We are NOT providing social media analytics
- We are NOT replacing professional videographers
- We are NOT hosting user media permanently (S3 with TTL strategy)
- We are NOT building a TikTok or YouTube integration (V2+)

---

## 5. User Stories

### Core Generation Flow
```
US-001: As a user, I can submit a text prompt + image so the AI generates a complete Reel concept.
US-002: As a user, I can see the generated script, storyboard, caption, and hashtags.
US-003: As a user, I can regenerate individual sections (script, caption, hashtags) independently.
US-004: As a user, I can preview the generated video before approving.
US-005: As a user, I can edit the caption and hashtags before publishing.
```

### Review & Approval
```
US-006: As a user, I can approve a reel version for publishing.
US-007: As a user, I can reject a reel version and request regeneration.
US-008: As a user, I can see the current status of my reel (generating, ready, failed, published).
```

### Instagram Publishing
```
US-009: As a user, I can connect my Instagram Business account via OAuth.
US-010: As a user, I can publish an approved reel to my connected Instagram account.
US-011: As a user, I can see the publish status (processing, published, failed).
US-012: As a user, I am notified when my Instagram token needs renewal.
```

### Account & Settings
```
US-013: As a user, I can manage my workspace settings.
US-014: As a user, I can view all my reel projects in a dashboard.
US-015: As a user, I can see which Instagram accounts are connected.
```

---

## 6. Success Metrics

| Metric                              | MVP Target   |
|-------------------------------------|--------------|
| Time from prompt → video ready      | < 3 minutes  |
| Time from prompt → published        | < 5 minutes  |
| Video generation success rate       | > 90%        |
| Instagram publish success rate      | > 95%        |
| User approval rate (accept reel)    | > 60%        |
| Regeneration request rate           | < 40%        |
| Platform uptime                     | > 99.5%      |

---

## 7. Product Risks

| Risk                              | Severity | Mitigation                                        |
|-----------------------------------|----------|---------------------------------------------------|
| AI video provider downtime        | High     | FFmpeg fallback renderer built-in                 |
| Instagram API rate limits         | High     | Exponential backoff, per-account rate tracking    |
| Meta App Review delay             | High     | Use test users during development; plan 4–6 weeks |
| AI-generated content moderation   | Medium   | Built-in moderation step in AI pipeline           |
| Token expiry / reconnect friction | Medium   | Token refresh monitoring + reconnect UI           |
| User uploads malicious files      | High     | Strict MIME/type validation, virus scan adapter   |
| LLM output quality variance       | Medium   | Output schema validation + retry with feedback    |
| GDPR / privacy compliance         | Medium   | Data retention TTL, no PII in logs                |

---

## 8. Open Questions

- [ ] Should we support scheduling (future date/time publishing) in MVP?
- [ ] Should caption editing be a rich text editor or plain textarea?
- [ ] Do we need multi-image input (carousel support) in MVP?
- [ ] What is the video duration range? (15s / 30s / 60s / 90s)
- [ ] Do we charge per generation or per seat (pricing model)?

---

*This spec must be reviewed and approved before major feature work begins. See `.agents/workflows/02-implement-feature.md` for the approval loop.*
