# Skill: Frontend Engineering

## Next.js Conventions
- Use App Router (src/app/) not Pages Router
- Server Components by default; Client Components only when needed ('use client')
- Layout components in layout.tsx; page data in page.tsx
- API route handlers in src/app/api/ (only for BFF patterns)

## Feature Folder Convention
`
src/features/{feature-name}/
  index.ts           # public exports
  {Feature}Page.tsx  # page-level component
  {Feature}Form.tsx  # form component
  use{Feature}.ts    # TanStack Query hooks
  {feature}.schema.ts  # Zod schemas
  {feature}.types.ts   # feature-specific types
  README.md
`

## Component Standards
- Components in src/components/ui/ are purely presentational
- All props typed explicitly (no inferred props from JSX)
- Use orwardRef for form controls
- Accessibility: all interactive elements must have ria-label or visible label
- Loading state: show Skeleton component, not blank space
- Error state: show error message + retry button
- Empty state: show descriptive empty illustration + CTA

## Form Validation Standards
`	sx
// Always use React Hook Form + Zod
const schema = z.object({
  prompt: z.string().min(10).max(2000),
  language: z.enum(['en', 'hi', 'es', 'fr']),
})
const form = useForm<z.infer<typeof schema>>({
  resolver: zodResolver(schema),
})
`

## API Client Standards
- All API calls go through src/lib/api-client.ts
- All requests include Authorization header
- All responses typed with shared types from packages/shared
- Use TanStack Query for server state (never fetch in useEffect)
- Error responses normalized to ApiError type

## UI Loading/Error/Empty States
- Every query must handle: isLoading, isError, isEmpty, data
- Use <Suspense> boundaries for async server components
- Never render undefined — always provide fallback
