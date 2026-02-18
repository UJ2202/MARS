# Stage 1: Global CSS & Design Tokens

**Phase:** 0 - Foundation
**Dependencies:** None (first stage)
**Risk Level:** Low

## Objectives

1. Create `styles/mars.css` as the single source of truth for all design tokens
2. Define CSS custom properties for colors, spacing, typography, radii, shadows, z-index, and motion
3. Implement dark and light theme support via `[data-theme]` attribute
4. Add a modern CSS reset and base typographic styles
5. Provide utility classes for layout, flex, and visibility
6. Update `tailwind.config.js` to reference MARS tokens
7. Update `globals.css` to import `mars.css`

## Current State Analysis

### What We Have
- `app/globals.css` with Tailwind directives, basic CSS variables (`--foreground-rgb`, `--background-start-rgb`), console scrollbar styles, and typing animation
- `tailwind.config.js` with custom `primary.*` color scale, `console.*` colors, and `mono` font family
- Inline Tailwind classes throughout all components (no CSS modules or styled-components)
- Hardcoded colors in JSX: `bg-black/20`, `border-white/10`, `text-gray-400`, `from-slate-900`, etc.

### What We Need
- Centralized design token system via CSS custom properties
- Dark/light theme switching capability
- Consistent spacing, typography, and shadow scales
- Utility classes that complement Tailwind
- CSS reset for cross-browser consistency

## Pre-Stage Verification

### Check Prerequisites
1. Confirm `cmbagent-ui/` directory exists and project builds cleanly
2. Confirm `tailwind.config.js` and `app/globals.css` are accessible

### Test Current State
```bash
cd /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui
npm run build
```

## Implementation Tasks

### Task 1: Create `styles/mars.css`
**Objective:** Define all design tokens as CSS custom properties

**Files to Create:**
- `styles/mars.css`

**Implementation:**

```css
/* ==========================================================================
   MARS Design System - Global Tokens & Utilities
   Single source of truth for all visual properties.
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. CSS Reset (Modern)
   -------------------------------------------------------------------------- */
*, *::before, *::after {
  box-sizing: border-box;
}

* {
  margin: 0;
}

html {
  -webkit-text-size-adjust: 100%;
  -moz-text-size-adjust: 100%;
  text-size-adjust: 100%;
  scroll-behavior: smooth;
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

body {
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

img, picture, video, canvas, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
}

p, h1, h2, h3, h4, h5, h6 {
  overflow-wrap: break-word;
}

/* --------------------------------------------------------------------------
   2. Design Tokens (Dark Theme - Default)
   -------------------------------------------------------------------------- */
:root,
[data-theme="dark"] {
  /* --- Colors --- */
  --mars-color-primary: #3B82F6;
  --mars-color-primary-hover: #2563EB;
  --mars-color-primary-active: #1D4ED8;
  --mars-color-primary-subtle: rgba(59, 130, 246, 0.15);
  --mars-color-primary-text: #93C5FD;

  --mars-color-accent: #22C55E;
  --mars-color-accent-hover: #16A34A;
  --mars-color-accent-subtle: rgba(34, 197, 94, 0.15);

  --mars-color-surface: #0B1220;
  --mars-color-surface-raised: #111827;
  --mars-color-surface-overlay: #1F2937;
  --mars-color-surface-sunken: #060A12;

  --mars-color-bg: #0B1220;
  --mars-color-bg-secondary: #111827;
  --mars-color-bg-tertiary: #1F2937;
  --mars-color-bg-hover: rgba(255, 255, 255, 0.05);
  --mars-color-bg-active: rgba(255, 255, 255, 0.08);

  --mars-color-text: #F9FAFB;
  --mars-color-text-secondary: #9CA3AF;
  --mars-color-text-tertiary: #6B7280;
  --mars-color-text-disabled: #4B5563;
  --mars-color-text-inverse: #111827;

  --mars-color-border: rgba(255, 255, 255, 0.1);
  --mars-color-border-strong: rgba(255, 255, 255, 0.2);
  --mars-color-border-subtle: rgba(255, 255, 255, 0.05);

  --mars-color-success: #22C55E;
  --mars-color-success-subtle: rgba(34, 197, 94, 0.15);
  --mars-color-warning: #F59E0B;
  --mars-color-warning-subtle: rgba(245, 158, 11, 0.15);
  --mars-color-danger: #EF4444;
  --mars-color-danger-subtle: rgba(239, 68, 68, 0.15);
  --mars-color-info: #3B82F6;
  --mars-color-info-subtle: rgba(59, 130, 246, 0.15);

  /* Console-specific */
  --mars-color-console-bg: #0D1117;
  --mars-color-console-text: #E5E5E5;

  /* --- Spacing Scale (4px base) --- */
  --mars-space-0: 0;
  --mars-space-1: 0.25rem;   /* 4px */
  --mars-space-2: 0.5rem;    /* 8px */
  --mars-space-3: 0.75rem;   /* 12px */
  --mars-space-4: 1rem;      /* 16px */
  --mars-space-5: 1.25rem;   /* 20px */
  --mars-space-6: 1.5rem;    /* 24px */
  --mars-space-8: 2rem;      /* 32px */
  --mars-space-10: 2.5rem;   /* 40px */
  --mars-space-12: 3rem;     /* 48px */
  --mars-space-16: 4rem;     /* 64px */
  --mars-space-20: 5rem;     /* 80px */

  /* --- Typography --- */
  --mars-font-sans: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
  --mars-font-mono: 'JetBrains Mono', 'Consolas', 'Monaco', 'Courier New', monospace;

  --mars-text-xs: 0.75rem;    /* 12px */
  --mars-text-sm: 0.875rem;   /* 14px */
  --mars-text-base: 1rem;     /* 16px */
  --mars-text-lg: 1.125rem;   /* 18px */
  --mars-text-xl: 1.25rem;    /* 20px */
  --mars-text-2xl: 1.5rem;    /* 24px */
  --mars-text-3xl: 1.875rem;  /* 30px */
  --mars-text-4xl: 2.25rem;   /* 36px */

  --mars-leading-tight: 1.25;
  --mars-leading-normal: 1.5;
  --mars-leading-relaxed: 1.75;

  --mars-font-normal: 400;
  --mars-font-medium: 500;
  --mars-font-semibold: 600;
  --mars-font-bold: 700;

  /* --- Border Radius --- */
  --mars-radius-sm: 4px;
  --mars-radius-md: 8px;
  --mars-radius-lg: 12px;
  --mars-radius-xl: 16px;
  --mars-radius-full: 9999px;

  /* --- Shadows --- */
  --mars-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --mars-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -2px rgba(0, 0, 0, 0.3);
  --mars-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.4);
  --mars-shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4);

  /* --- Z-Index Layers --- */
  --mars-z-base: 0;
  --mars-z-dropdown: 100;
  --mars-z-sticky: 200;
  --mars-z-nav: 300;
  --mars-z-modal-backdrop: 400;
  --mars-z-modal: 500;
  --mars-z-toast: 600;
  --mars-z-tooltip: 700;
  --mars-z-max: 9999;

  /* --- Motion --- */
  --mars-ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --mars-ease-in: cubic-bezier(0.4, 0, 1, 1);
  --mars-ease-out: cubic-bezier(0, 0, 0.2, 1);
  --mars-ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);

  --mars-duration-instant: 50ms;
  --mars-duration-fast: 150ms;
  --mars-duration-normal: 200ms;
  --mars-duration-slow: 300ms;
  --mars-duration-slower: 500ms;

  /* --- Layout --- */
  --mars-sidenav-width: 240px;
  --mars-sidenav-collapsed-width: 64px;
  --mars-topbar-height: 56px;
  --mars-content-max-width: 1536px;
}

/* --------------------------------------------------------------------------
   3. Light Theme Override
   -------------------------------------------------------------------------- */
[data-theme="light"] {
  --mars-color-primary: #2563EB;
  --mars-color-primary-hover: #1D4ED8;
  --mars-color-primary-active: #1E40AF;
  --mars-color-primary-subtle: rgba(37, 99, 235, 0.1);
  --mars-color-primary-text: #1D4ED8;

  --mars-color-accent: #16A34A;
  --mars-color-accent-hover: #15803D;
  --mars-color-accent-subtle: rgba(22, 163, 74, 0.1);

  --mars-color-surface: #FFFFFF;
  --mars-color-surface-raised: #F9FAFB;
  --mars-color-surface-overlay: #F3F4F6;
  --mars-color-surface-sunken: #E5E7EB;

  --mars-color-bg: #FFFFFF;
  --mars-color-bg-secondary: #F9FAFB;
  --mars-color-bg-tertiary: #F3F4F6;
  --mars-color-bg-hover: rgba(0, 0, 0, 0.04);
  --mars-color-bg-active: rgba(0, 0, 0, 0.06);

  --mars-color-text: #111827;
  --mars-color-text-secondary: #4B5563;
  --mars-color-text-tertiary: #9CA3AF;
  --mars-color-text-disabled: #D1D5DB;
  --mars-color-text-inverse: #F9FAFB;

  --mars-color-border: rgba(0, 0, 0, 0.1);
  --mars-color-border-strong: rgba(0, 0, 0, 0.2);
  --mars-color-border-subtle: rgba(0, 0, 0, 0.05);

  --mars-color-console-bg: #1E1E1E;
  --mars-color-console-text: #E5E5E5;

  --mars-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --mars-shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --mars-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
  --mars-shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

/* --------------------------------------------------------------------------
   4. Base Typographic Styles
   -------------------------------------------------------------------------- */
body {
  font-family: var(--mars-font-sans);
  font-size: var(--mars-text-base);
  line-height: var(--mars-leading-normal);
  color: var(--mars-color-text);
  background-color: var(--mars-color-bg);
}

h1, h2, h3, h4, h5, h6 {
  line-height: var(--mars-leading-tight);
  font-weight: var(--mars-font-semibold);
}

code, pre, kbd, samp {
  font-family: var(--mars-font-mono);
}

/* --------------------------------------------------------------------------
   5. Focus Ring Styles
   -------------------------------------------------------------------------- */
:focus-visible {
  outline: 2px solid var(--mars-color-primary);
  outline-offset: 2px;
}

:focus:not(:focus-visible) {
  outline: none;
}

/* --------------------------------------------------------------------------
   6. Scrollbar Styles
   -------------------------------------------------------------------------- */
.mars-scrollbar::-webkit-scrollbar,
.console-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.mars-scrollbar::-webkit-scrollbar-track,
.console-scrollbar::-webkit-scrollbar-track {
  background: var(--mars-color-surface-sunken);
}

.mars-scrollbar::-webkit-scrollbar-thumb,
.console-scrollbar::-webkit-scrollbar-thumb {
  background: var(--mars-color-text-tertiary);
  border-radius: var(--mars-radius-full);
}

.mars-scrollbar::-webkit-scrollbar-thumb:hover,
.console-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--mars-color-text-secondary);
}

/* --------------------------------------------------------------------------
   7. Utility Classes
   -------------------------------------------------------------------------- */

/* Flex Utilities */
.mars-flex-center {
  display: flex;
  align-items: center;
  justify-content: center;
}

.mars-flex-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mars-flex-col {
  display: flex;
  flex-direction: column;
}

/* Grid Utilities */
.mars-grid {
  display: grid;
  gap: var(--mars-space-4);
}

.mars-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.mars-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.mars-grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }

/* Visibility Helpers */
.mars-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

.mars-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Animation Helpers */
.mars-transition {
  transition-property: color, background-color, border-color, box-shadow, opacity, transform;
  transition-timing-function: var(--mars-ease-standard);
  transition-duration: var(--mars-duration-normal);
}

.mars-transition-fast {
  transition-property: color, background-color, border-color, box-shadow, opacity, transform;
  transition-timing-function: var(--mars-ease-standard);
  transition-duration: var(--mars-duration-fast);
}

/* --------------------------------------------------------------------------
   8. Existing Animations (migrated)
   -------------------------------------------------------------------------- */
@keyframes mars-typing {
  from { width: 0 }
  to { width: 100% }
}

@keyframes mars-blink-caret {
  from, to { border-color: transparent }
  50% { border-color: var(--mars-color-accent); }
}

.typing-animation {
  overflow: hidden;
  border-right: 2px solid var(--mars-color-accent);
  white-space: nowrap;
  animation:
    mars-typing 2s steps(40, end),
    mars-blink-caret .75s step-end infinite;
}

@keyframes mars-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes mars-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes mars-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes mars-slide-up {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes mars-scale-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
```

**Verification:**
- [ ] File exists at `styles/mars.css`
- [ ] All CSS custom properties parse without errors
- [ ] Light and dark theme tokens are complete and symmetric
- [ ] CSS reset does not break existing layout
- [ ] Utility classes are available

### Task 2: Update `globals.css`
**Objective:** Import mars.css and update to use token references

**Files to Modify:**
- `app/globals.css`

**Changes:**

Replace the content of `globals.css` with:

```css
@import '../styles/mars.css';

@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
```

Note: The existing `:root` CSS variables, `body` background styles, console scrollbar styles, and typing animation are now defined in `mars.css`. Remove them from `globals.css` to avoid duplication.

**Verification:**
- [ ] `globals.css` imports `mars.css` before Tailwind directives
- [ ] No duplicate CSS variable definitions
- [ ] Console scrollbar styles still work (now in mars.css)
- [ ] Typing animation still works (now in mars.css)

### Task 3: Update `tailwind.config.js`
**Objective:** Extend Tailwind with references to MARS CSS custom properties

**Files to Modify:**
- `tailwind.config.js`

**Changes:**

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // MARS token-backed colors
        mars: {
          primary: 'var(--mars-color-primary)',
          'primary-hover': 'var(--mars-color-primary-hover)',
          'primary-subtle': 'var(--mars-color-primary-subtle)',
          accent: 'var(--mars-color-accent)',
          'accent-hover': 'var(--mars-color-accent-hover)',
          surface: 'var(--mars-color-surface)',
          'surface-raised': 'var(--mars-color-surface-raised)',
          'surface-overlay': 'var(--mars-color-surface-overlay)',
          bg: 'var(--mars-color-bg)',
          'bg-secondary': 'var(--mars-color-bg-secondary)',
          'bg-hover': 'var(--mars-color-bg-hover)',
          text: 'var(--mars-color-text)',
          'text-secondary': 'var(--mars-color-text-secondary)',
          'text-tertiary': 'var(--mars-color-text-tertiary)',
          border: 'var(--mars-color-border)',
          'border-strong': 'var(--mars-color-border-strong)',
          success: 'var(--mars-color-success)',
          warning: 'var(--mars-color-warning)',
          danger: 'var(--mars-color-danger)',
          info: 'var(--mars-color-info)',
        },
        // Preserve existing colors for backward compat during migration
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        console: {
          bg: '#1a1a1a',
          text: '#e5e5e5',
          success: '#22c55e',
          error: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        }
      },
      fontFamily: {
        sans: ['var(--mars-font-sans)'],
        mono: ['var(--mars-font-mono)'],
      },
      borderRadius: {
        'mars-sm': 'var(--mars-radius-sm)',
        'mars-md': 'var(--mars-radius-md)',
        'mars-lg': 'var(--mars-radius-lg)',
        'mars-xl': 'var(--mars-radius-xl)',
      },
      boxShadow: {
        'mars-sm': 'var(--mars-shadow-sm)',
        'mars-md': 'var(--mars-shadow-md)',
        'mars-lg': 'var(--mars-shadow-lg)',
        'mars-xl': 'var(--mars-shadow-xl)',
      },
      zIndex: {
        'dropdown': 'var(--mars-z-dropdown)',
        'sticky': 'var(--mars-z-sticky)',
        'nav': 'var(--mars-z-nav)',
        'modal-backdrop': 'var(--mars-z-modal-backdrop)',
        'modal': 'var(--mars-z-modal)',
        'toast': 'var(--mars-z-toast)',
        'tooltip': 'var(--mars-z-tooltip)',
      },
      transitionTimingFunction: {
        'mars': 'var(--mars-ease-standard)',
        'mars-bounce': 'var(--mars-ease-bounce)',
      },
      transitionDuration: {
        'mars-fast': 'var(--mars-duration-fast)',
        'mars-normal': 'var(--mars-duration-normal)',
        'mars-slow': 'var(--mars-duration-slow)',
      },
      spacing: {
        'sidenav': 'var(--mars-sidenav-width)',
        'sidenav-collapsed': 'var(--mars-sidenav-collapsed-width)',
        'topbar': 'var(--mars-topbar-height)',
      },
    },
  },
  plugins: [],
}
```

**Verification:**
- [ ] Tailwind classes like `bg-mars-primary`, `text-mars-text`, `border-mars-border` work
- [ ] Existing `bg-primary-500`, `text-gray-400` etc. still work (backward compat)
- [ ] `rounded-mars-md`, `shadow-mars-lg` etc. resolve correctly
- [ ] Build succeeds with no errors

### Task 4: Create `ThemeContext.tsx`
**Objective:** Add theme state management for dark/light switching

**Files to Create:**
- `contexts/ThemeContext.tsx`

**Implementation:**

```tsx
'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface ThemeContextValue {
  theme: 'dark' | 'light'
  toggleTheme: () => void
  setTheme: (theme: 'dark' | 'light') => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<'dark' | 'light'>('dark')

  useEffect(() => {
    // Check localStorage for saved preference
    const saved = localStorage.getItem('mars-theme') as 'dark' | 'light' | null
    if (saved) {
      setThemeState(saved)
    }
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('mars-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }

  const setTheme = (newTheme: 'dark' | 'light') => {
    setThemeState(newTheme)
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
```

**Verification:**
- [ ] ThemeProvider wraps app without errors
- [ ] `useTheme()` returns current theme and toggle function
- [ ] `data-theme` attribute updates on `<html>` element
- [ ] Theme persists across page reloads via localStorage

### Task 5: Update `providers.tsx`
**Objective:** Add ThemeProvider to the provider tree

**Files to Modify:**
- `app/providers.tsx`

**Changes:**

```tsx
'use client'

import { ReactNode } from 'react'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { ThemeProvider } from '@/contexts/ThemeContext'

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        {children}
      </WebSocketProvider>
    </ThemeProvider>
  )
}
```

**Verification:**
- [ ] App starts without errors
- [ ] Both WebSocket and Theme contexts are available throughout the app
- [ ] `data-theme="dark"` is set on `<html>` by default

## Files to Create (Summary)

```
cmbagent-ui/
├── styles/
│   └── mars.css                    # Design tokens & utilities
└── contexts/
    └── ThemeContext.tsx             # Theme state management
```

## Files to Modify

- `app/globals.css` - Import mars.css, remove duplicate variables
- `tailwind.config.js` - Extend with MARS token references
- `app/providers.tsx` - Add ThemeProvider wrapper

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] Dark theme is the default (unchanged visual appearance)
- [ ] All existing Tailwind classes continue to work
- [ ] Console scrollbar and typing animation still function
- [ ] CSS custom properties are accessible via browser DevTools

### Should Pass
- [ ] Light theme renders correctly when `data-theme="light"` is set manually
- [ ] `mars-*` Tailwind utilities (e.g., `bg-mars-primary`) resolve to correct values
- [ ] Focus ring styles appear on keyboard navigation

### Nice to Have
- [ ] Lighthouse performance score unchanged
- [ ] No FOUC (flash of unstyled content) on page load

## Testing Commands

```bash
cd /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui
npm run build
npx tsc --noEmit
npm run dev  # Visual verification
```

## Common Issues and Solutions

### Issue 1: CSS Import Order
**Symptom:** Tailwind utilities override MARS tokens
**Solution:** Ensure `mars.css` is imported BEFORE `@tailwind base` in `globals.css`

### Issue 2: CSS Variables Not Resolving in Tailwind
**Symptom:** `bg-mars-primary` shows as transparent
**Solution:** Ensure CSS custom properties use raw color values (not `rgb()` functions with opacity) since Tailwind's opacity utilities won't work with CSS variable references. Use the values directly.

### Issue 3: Theme Flicker on Load
**Symptom:** Brief flash of wrong theme on page load
**Solution:** Add a `<script>` in `layout.tsx` `<head>` that reads localStorage and sets `data-theme` before React hydrates

## Rollback Procedure

If Stage 1 causes issues:
1. Delete `styles/mars.css`
2. Delete `contexts/ThemeContext.tsx`
3. Revert `app/globals.css` to original content
4. Revert `tailwind.config.js` to original content
5. Revert `app/providers.tsx` to original content
6. Run `npm run build` to confirm clean state

## Success Criteria

Stage 1 is complete when:
1. `styles/mars.css` exists with all design tokens defined
2. Dark and light theme tokens are symmetric and complete
3. `tailwind.config.js` extends with MARS references
4. `ThemeContext` provides theme state management
5. Build passes with no errors
6. UI looks identical to pre-Stage-1 (dark theme default)
7. All verification criteria pass

## Next Stage

Once Stage 1 is verified complete, proceed to:
**Stage 2: AppShell Layout (TopBar + SideNav)**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
