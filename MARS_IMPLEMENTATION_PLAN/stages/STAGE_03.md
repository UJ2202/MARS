# Stage 3: Branding & Renaming

**Phase:** 0 - Foundation
**Dependencies:** Stage 2 (AppShell Layout)
**Risk Level:** Low

## Objectives

1. Rename product from CMBAGENT to MARS in all UI-visible locations
2. Update metadata (page title, description, favicon)
3. Create MARS logo/branding assets
4. Update environment banners and config descriptions
5. Update the `not-found.tsx` page with MARS branding
6. Update `package.json` name field

## Current State Analysis

### What We Have
- `layout.tsx`: `title: 'CMBAGENT'`, `description: 'Interactive UI for CMBAgent...'`
- `Header.tsx`: `<h1>CMBAGENT</h1>`, subtitle "Autonomous Research Backend"
- `TopNavigation.tsx`: `<h1>CMBAGENT</h1>`
- Config description: "Configuration for the CMBAgent UI" in `lib/config.ts`
- GitHub link to `github.com/CMBAgents/cmbagent` in Header
- Tasks page header: "IT TASKS" title
- `package.json`: `"name": "cmbagent-ui"`
- No favicon or logo files exist
- Jersey 10 font used for logo styling

### What We Need
- All instances of "CMBAGENT" / "CMBAgent" / "cmbagent" replaced with "MARS" in user-facing text
- New favicon and SVG logo
- Updated meta tags
- Clean brand identity using Inter/system-ui instead of Jersey 10

## Pre-Stage Verification

### Check Prerequisites
1. Stage 2 complete: AppShell with TopBar is rendering
2. TopBar already shows "MARS" (set in Stage 2, Task 3)
3. Build passes: `npm run build`

## Implementation Tasks

### Task 1: Create Favicon and Logo
**Objective:** Create MARS branded assets

**Files to Create:**
- `public/favicon.ico` (or `app/favicon.ico` for Next.js App Router)
- `public/mars-logo.svg`

**Implementation:**

For `app/favicon.ico`, create a simple favicon. Since we can't create binary files from code, use a placeholder approach:

Create `app/icon.tsx` (Next.js dynamic favicon):

```tsx
import { ImageResponse } from 'next/og'

export const size = { width: 32, height: 32 }
export const contentType = 'image/png'

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 20,
          background: '#3B82F6',
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          borderRadius: '6px',
          fontWeight: 700,
          fontFamily: 'system-ui',
        }}
      >
        M
      </div>
    ),
    { ...size }
  )
}
```

Create `public/mars-logo.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 32" fill="none">
  <rect width="32" height="32" rx="8" fill="#3B82F6"/>
  <text x="16" y="22" text-anchor="middle" fill="white" font-family="system-ui, sans-serif" font-weight="700" font-size="18">M</text>
  <text x="76" y="22" text-anchor="middle" fill="currentColor" font-family="system-ui, sans-serif" font-weight="700" font-size="20">MARS</text>
</svg>
```

**Verification:**
- [ ] Favicon appears in browser tab
- [ ] Logo SVG renders correctly

### Task 2: Update Metadata in `layout.tsx`
**Objective:** Ensure all meta tags reference MARS

**Files to Modify:**
- `app/layout.tsx`

**Changes:**

This was partially done in Stage 2. Verify the metadata is:

```typescript
export const metadata: Metadata = {
  title: 'MARS',
  description: 'MARS - Autonomous Research Platform',
}
```

Also remove the Jersey 10 Google Fonts link from `<head>` if not done in Stage 2.

**Verification:**
- [ ] Browser tab shows "MARS"
- [ ] Page description meta tag reads "MARS - Autonomous Research Platform"
- [ ] No Jersey 10 font loading

### Task 3: Update Config Description
**Objective:** Rename in source code comments and config

**Files to Modify:**
- `lib/config.ts`

**Changes:**

```typescript
/**
 * Configuration for MARS UI
 * Uses environment variables with fallbacks for local development
 */
```

**Verification:**
- [ ] Source comment updated

### Task 4: Update `package.json`
**Objective:** Rename package

**Files to Modify:**
- `package.json`

**Changes:**

```json
{
  "name": "mars-ui",
  ...
}
```

**Verification:**
- [ ] Package name updated to "mars-ui"

### Task 5: Update `not-found.tsx`
**Objective:** Brand the 404 page

**Files to Modify:**
- `app/not-found.tsx`

**Changes:**

Update any "cmbagent" references to "MARS" and apply MARS styling tokens.

**Verification:**
- [ ] 404 page shows MARS branding

### Task 6: Search and Replace Remaining References
**Objective:** Find all remaining "CMBAGENT" / "CMBAgent" / "cmbagent" in user-facing strings

**Process:**

```bash
grep -rn "CMBAGENT\|CMBAgent\|cmbagent" --include="*.tsx" --include="*.ts" --include="*.css" --include="*.json" \
  /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui/app/ \
  /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui/components/ \
  /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui/lib/ \
  /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui/types/
```

For each match:
- If it's user-facing text (titles, labels, descriptions): rename to "MARS"
- If it's a technical identifier (directory name, env variable prefix): leave unchanged to avoid breaking backend contracts
- If it's a GitHub URL: leave unchanged (still valid repository)

**Important:** Do NOT rename:
- `NEXT_PUBLIC_CMBAGENT_WORK_DIR` env variable (backend contract)
- The project directory name `cmbagent-ui` (filesystem path)
- Any API endpoint paths that include "cmbagent"
- Import paths that reference the project directory

**Verification:**
- [ ] No user-facing instances of "CMBAGENT" remain
- [ ] Technical identifiers (env vars, paths) are preserved
- [ ] Build still passes

### Task 7: Update Tasks Page Header
**Objective:** Update the tasks page branding

**Files to Modify:**
- `app/tasks/page.tsx`

**Changes:**

The existing "IT TASKS" header and "AI-Powered Development Automation" subtitle should be updated to align with MARS branding. However, the specific content on the Tasks page will be overhauled in Stage 6. For now, just ensure it doesn't say "CMBAGENT" anywhere.

**Verification:**
- [ ] Tasks page doesn't reference CMBAGENT

## Files to Create (Summary)

```
cmbagent-ui/
├── app/
│   └── icon.tsx              # Dynamic favicon
└── public/
    └── mars-logo.svg         # Logo asset
```

## Files to Modify

- `app/layout.tsx` - Metadata (if not done in Stage 2), remove Jersey 10 font
- `lib/config.ts` - Update source comments
- `package.json` - Update package name
- `app/not-found.tsx` - MARS branding
- `app/tasks/page.tsx` - Remove any CMBAGENT references
- Any other files found by grep search

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] Browser tab shows "MARS" title
- [ ] Favicon renders in browser tab
- [ ] No user-facing instance of "CMBAGENT" remains in the UI
- [ ] All routes still work (/, /tasks, /sessions)
- [ ] Backend connection still works (no API contract changes)

### Should Pass
- [ ] Logo SVG renders correctly
- [ ] 404 page is MARS branded
- [ ] Package name is "mars-ui"

## Common Issues and Solutions

### Issue 1: Dynamic Favicon Not Rendering
**Symptom:** No favicon in browser tab
**Solution:** Next.js App Router uses `app/icon.tsx` for dynamic favicons. Ensure it exports `size`, `contentType`, and a default function returning `ImageResponse`.

### Issue 2: Breaking Backend References
**Symptom:** API calls fail after renaming
**Solution:** Only rename user-facing strings. Never rename env variables, API paths, or directory names.

## Rollback Procedure

If Stage 3 causes issues:
1. Revert metadata in `layout.tsx` to "CMBAGENT"
2. Delete `app/icon.tsx` and `public/mars-logo.svg`
3. Revert `package.json` name
4. Revert `lib/config.ts` comment
5. Run `npm run build` to confirm

## Success Criteria

Stage 3 is complete when:
1. Product name is "MARS" in all user-facing locations
2. Favicon and logo assets exist
3. Meta tags reflect MARS branding
4. No backend contracts are affected
5. Build passes with no errors

## Next Stage

Once Stage 3 is verified complete, proceed to:
**Stage 4: Core Component Library**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
