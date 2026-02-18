# Stage 2: AppShell Layout (TopBar + SideNav)

**Phase:** 0 - Foundation
**Dependencies:** Stage 1 (Global CSS & Design Tokens)
**Risk Level:** High

## Objectives

1. Create the `AppShell` component that wraps all pages with a persistent TopBar and SideNav
2. Create `TopBar` component replacing the current `Header.tsx` - includes logo, quick action icons, connection status
3. Create `SideNav` component replacing `TopNavigation.tsx` - collapsible side navigation with Modes, Tasks, Sessions nav items
4. Integrate AppShell into `layout.tsx` so it wraps all page content
5. Move from horizontal tab-based mode switching to vertical side navigation with routing
6. Create `app/sessions/page.tsx` route placeholder for the Sessions screen (actual content in Stage 7)

## Current State Analysis

### What We Have
- `Header.tsx` (42 lines): Logo "CMBAGENT", connection status indicator, GitHub link
- `TopNavigation.tsx` (53 lines): Horizontal mode switcher with Research (/) and Tasks (/tasks) buttons
- `layout.tsx` (32 lines): Metadata, Inter font, Providers wrapper, gradient background div
- Two routes: `/` (Research mode) and `/tasks` (Tasks mode)
- Tabs within the main page: Console, Workflow, Results, Sessions (right panel)

### What We Need
- Persistent `AppShell` with sidebar + top bar on every page
- SideNav with Modes (default), Tasks, Sessions as primary navigation items
- Routes: `/` (Modes), `/tasks` (Tasks), `/sessions` (Sessions)
- TopBar with MARS logo, console/workflow modal triggers, connection status
- Collapsible SideNav (64px collapsed, 240px expanded)

## Pre-Stage Verification

### Check Prerequisites
1. Stage 1 complete: `styles/mars.css` exists with design tokens
2. `ThemeContext.tsx` is available
3. Build passes: `npm run build`

## Implementation Tasks

### Task 1: Create MARS UI Types
**Objective:** Define TypeScript types for new MARS UI components

**Files to Create:**
- `types/mars-ui.ts`

**Implementation:**

```typescript
// types/mars-ui.ts

export type NavItem = {
  id: string
  label: string
  icon: string  // Lucide icon name
  href: string
  badge?: number | string
}

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

export type ModalState = {
  consoleOpen: boolean
  workflowOpen: boolean
}

export type SessionPillData = {
  sessionId: string
  name: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress?: number  // 0-100
  mode?: string
}

export type ToastType = 'info' | 'success' | 'warning' | 'error'

export type ToastData = {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number  // ms, default 5000
  action?: {
    label: string
    onClick: () => void
  }
}
```

**Verification:**
- [ ] Types compile without errors
- [ ] `npx tsc --noEmit` passes

### Task 2: Create `SideNav` Component
**Objective:** Build collapsible side navigation with Modes, Tasks, Sessions items

**Files to Create:**
- `components/layout/SideNav.tsx`

**Implementation:**

```tsx
'use client'

import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import {
  LayoutGrid,
  ListTodo,
  History,
  ChevronLeft,
  ChevronRight,
  Settings,
  HelpCircle,
} from 'lucide-react'

interface SideNavProps {
  collapsed: boolean
  onToggle: () => void
}

const navItems = [
  { id: 'modes', label: 'Modes', icon: LayoutGrid, href: '/' },
  { id: 'tasks', label: 'Tasks', icon: ListTodo, href: '/tasks' },
  { id: 'sessions', label: 'Sessions', icon: History, href: '/sessions' },
]

export default function SideNav({ collapsed, onToggle }: SideNavProps) {
  const pathname = usePathname()
  const router = useRouter()

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/'
    return pathname.startsWith(href)
  }

  return (
    <nav
      className="h-full flex flex-col border-r transition-all duration-mars-slow"
      style={{
        width: collapsed ? 'var(--mars-sidenav-collapsed-width)' : 'var(--mars-sidenav-width)',
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      aria-label="Main navigation"
    >
      {/* Nav Items */}
      <div className="flex-1 py-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = isActive(item.href)
          return (
            <button
              key={item.id}
              onClick={() => router.push(item.href)}
              className={`
                w-full flex items-center gap-3 px-4 py-3 text-sm font-medium
                transition-colors duration-mars-fast
                ${active
                  ? 'text-[var(--mars-color-primary)] bg-[var(--mars-color-primary-subtle)]'
                  : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)] hover:bg-[var(--mars-color-bg-hover)]'
                }
              `}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? item.label : undefined}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          )
        })}
      </div>

      {/* Collapse Toggle */}
      <div className="border-t py-2" style={{ borderColor: 'var(--mars-color-border)' }}>
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-3 px-4 py-2 text-sm
            text-[var(--mars-color-text-tertiary)] hover:text-[var(--mars-color-text)]
            transition-colors duration-mars-fast"
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </nav>
  )
}
```

**Verification:**
- [ ] SideNav renders with three navigation items
- [ ] Active item is highlighted based on current route
- [ ] Collapse/expand toggle works with smooth animation
- [ ] Collapsed state shows only icons with titles
- [ ] Keyboard navigation works (Tab through items)

### Task 3: Create `TopBar` Component
**Objective:** Build top bar with logo, action icons, and connection status

**Files to Create:**
- `components/layout/TopBar.tsx`

**Implementation:**

```tsx
'use client'

import { Terminal, GitBranch, Sun, Moon } from 'lucide-react'
import { ConnectionStatus } from '@/components/common/ConnectionStatus'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { useTheme } from '@/contexts/ThemeContext'

interface TopBarProps {
  onOpenConsole: () => void
  onOpenWorkflow: () => void
}

export default function TopBar({ onOpenConsole, onOpenWorkflow }: TopBarProps) {
  const { connected, reconnectAttempt, lastError, reconnect, isRunning } = useWebSocketContext()
  const { theme, toggleTheme } = useTheme()

  return (
    <header
      className="flex items-center justify-between px-4 border-b"
      style={{
        height: 'var(--mars-topbar-height)',
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      role="banner"
    >
      {/* Logo */}
      <div className="flex items-center gap-3">
        <h1
          className="text-xl font-bold"
          style={{ color: 'var(--mars-color-text)', fontFamily: 'var(--mars-font-sans)' }}
        >
          MARS
        </h1>
      </div>

      {/* Center: Session pills placeholder (Stage 9) */}
      <div className="flex-1 flex items-center justify-center px-4">
        {/* SessionPillBar will be added in Stage 9 */}
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-2">
        {/* Console Toggle */}
        <button
          onClick={onOpenConsole}
          className="p-2 rounded-mars-md transition-colors duration-mars-fast
            hover:bg-[var(--mars-color-bg-hover)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          aria-label="Open console"
          title="Console"
        >
          <Terminal className="w-5 h-5" />
          {isRunning && (
            <span
              className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full"
              style={{ backgroundColor: 'var(--mars-color-success)' }}
            />
          )}
        </button>

        {/* Workflow Toggle */}
        <button
          onClick={onOpenWorkflow}
          className="p-2 rounded-mars-md transition-colors duration-mars-fast
            hover:bg-[var(--mars-color-bg-hover)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          aria-label="Open workflow"
          title="Workflow"
        >
          <GitBranch className="w-5 h-5" />
        </button>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-mars-md transition-colors duration-mars-fast
            hover:bg-[var(--mars-color-bg-hover)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          title={`${theme === 'dark' ? 'Light' : 'Dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        {/* Connection Status */}
        <ConnectionStatus
          connected={connected}
          reconnectAttempt={reconnectAttempt}
          lastError={lastError}
          onReconnect={reconnect}
        />
      </div>
    </header>
  )
}
```

**Verification:**
- [ ] TopBar renders with MARS logo on the left
- [ ] Console and Workflow icon buttons are present
- [ ] Theme toggle switches between dark and light
- [ ] Connection status indicator works as before
- [ ] Fixed height matches `--mars-topbar-height`

### Task 4: Create `AppShell` Component
**Objective:** Compose TopBar + SideNav + content area into a unified shell

**Files to Create:**
- `components/layout/AppShell.tsx`

**Implementation:**

```tsx
'use client'

import { useState, ReactNode } from 'react'
import TopBar from './TopBar'
import SideNav from './SideNav'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const [sideNavCollapsed, setSideNavCollapsed] = useState(false)
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [workflowOpen, setWorkflowOpen] = useState(false)

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--mars-color-bg)' }}>
      {/* Top Bar */}
      <TopBar
        onOpenConsole={() => setConsoleOpen(prev => !prev)}
        onOpenWorkflow={() => setWorkflowOpen(prev => !prev)}
      />

      {/* Body: SideNav + Content */}
      <div className="flex-1 flex min-h-0">
        <SideNav
          collapsed={sideNavCollapsed}
          onToggle={() => setSideNavCollapsed(prev => !prev)}
        />

        {/* Content Area */}
        <main
          className="flex-1 min-h-0 overflow-auto"
          style={{ backgroundColor: 'var(--mars-color-bg)' }}
        >
          {children}
        </main>
      </div>

      {/* Modals will be rendered here in Stage 8 */}
      {/* <ConsoleModal open={consoleOpen} onClose={() => setConsoleOpen(false)} /> */}
      {/* <WorkflowModal open={workflowOpen} onClose={() => setWorkflowOpen(false)} /> */}
    </div>
  )
}
```

**Verification:**
- [ ] AppShell renders TopBar at the top and SideNav on the left
- [ ] Content area fills remaining space
- [ ] SideNav collapse/expand works smoothly
- [ ] No overflow issues on any screen size
- [ ] `h-screen` properly fills viewport

### Task 5: Integrate AppShell into `layout.tsx`
**Objective:** Replace the existing gradient div wrapper with AppShell

**Files to Modify:**
- `app/layout.tsx`

**Changes:**

```tsx
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import AppShell from '@/components/layout/AppShell'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'MARS',
  description: 'MARS - Autonomous Research Platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" data-theme="dark">
      <body className={inter.className}>
        <Providers>
          <AppShell>
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  )
}
```

Note: The old `<div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">` is removed. Background color is now controlled by `--mars-color-bg` through the AppShell and mars.css tokens.

**Important:** The Google Fonts link for Jersey 10 is removed since we're dropping that font for the MARS brand (uses Inter/system-ui instead).

**Verification:**
- [ ] Layout renders AppShell wrapping page content
- [ ] `data-theme="dark"` is set on `<html>`
- [ ] No duplicate background gradient definitions
- [ ] Both `/` and `/tasks` routes render within the AppShell

### Task 6: Create Sessions Route Placeholder
**Objective:** Add `/sessions` route so SideNav link works

**Files to Create:**
- `app/sessions/page.tsx`

**Implementation:**

```tsx
'use client'

export default function SessionsPage() {
  return (
    <div className="p-6">
      <h2
        className="text-2xl font-semibold mb-4"
        style={{ color: 'var(--mars-color-text)' }}
      >
        Sessions
      </h2>
      <p style={{ color: 'var(--mars-color-text-secondary)' }}>
        Sessions management will be implemented in Stage 7.
      </p>
    </div>
  )
}
```

**Verification:**
- [ ] `/sessions` route renders without errors
- [ ] SideNav highlights "Sessions" when on this route
- [ ] Navigation between all three routes works

### Task 7: Update Page Components
**Objective:** Remove Header and TopNavigation from page components since AppShell now provides them

**Files to Modify:**
- `app/page.tsx` - Remove `<TopNavigation />` and `<Header />` from the JSX
- `app/tasks/page.tsx` - Remove `<TopNavigation />` and the inline header

**Changes for `app/page.tsx`:**
Remove these two lines from the return JSX (around lines 682-684):
```diff
  return (
    <div className="h-screen flex flex-col overflow-hidden">
-     <TopNavigation />
-     <Header />
+     {/* TopBar and SideNav are now provided by AppShell in layout.tsx */}
```

Also remove the `min-h-screen bg-gradient-to-br` className from the tasks page wrapper.

**Note:** The `h-screen flex flex-col overflow-hidden` wrapper in `page.tsx` needs adjustment since AppShell already provides the full-height layout. Change it to `flex-1 flex flex-col overflow-hidden min-h-0` or just use `h-full`.

**Verification:**
- [ ] Home page renders without duplicate headers or navigation
- [ ] Tasks page renders without duplicate navigation
- [ ] All existing functionality (task submission, console, workflow tabs) still works
- [ ] No layout overflow or scrolling issues

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── mars-ui.ts
├── components/
│   └── layout/
│       ├── AppShell.tsx
│       ├── TopBar.tsx
│       └── SideNav.tsx
└── app/
    └── sessions/
        └── page.tsx
```

## Files to Modify

- `app/layout.tsx` - Replace gradient wrapper with AppShell, update metadata
- `app/page.tsx` - Remove TopNavigation and Header; adjust container sizing
- `app/tasks/page.tsx` - Remove TopNavigation and inline header

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] AppShell renders on all routes (/, /tasks, /sessions)
- [ ] SideNav shows correct active state on each route
- [ ] Navigation between routes works without full page reload
- [ ] All existing page content still renders (TaskInput, ConsoleOutput, tabs, etc.)
- [ ] WebSocket connection status still visible in TopBar

### Should Pass
- [ ] SideNav collapse/expand animation is smooth (300ms)
- [ ] TopBar height is consistent at 56px
- [ ] Keyboard navigation through SideNav items works (Tab + Enter)
- [ ] No content is cut off or overlapping

### Nice to Have
- [ ] SideNav collapsed state persists across page reloads
- [ ] Responsive: SideNav auto-collapses on small screens

## Common Issues and Solutions

### Issue 1: Page Content Height
**Symptom:** Page content overflows or doesn't fill available space
**Solution:** Ensure the main content area uses `flex-1 min-h-0 overflow-auto` instead of explicit heights. The AppShell manages the viewport height.

### Issue 2: Double Scroll Bars
**Symptom:** Both the page content and AppShell body show scrollbars
**Solution:** Ensure `overflow-hidden` is on the AppShell root and `overflow-auto` is on the content area only

### Issue 3: Existing Page Layout Breaks
**Symptom:** TaskInput/Console grid layout doesn't render properly
**Solution:** The page components previously measured from viewport height; they need to use `100%` or `flex-1` height within the AppShell content area

## Rollback Procedure

If Stage 2 causes issues:
1. Revert `app/layout.tsx` to original (remove AppShell import, restore gradient div)
2. Restore `<TopNavigation />` and `<Header />` in `app/page.tsx` and `app/tasks/page.tsx`
3. Delete `components/layout/` directory
4. Delete `app/sessions/page.tsx`
5. Delete `types/mars-ui.ts`
6. Run `npm run build` to confirm clean state

## Success Criteria

Stage 2 is complete when:
1. AppShell wraps all pages with TopBar and SideNav
2. SideNav navigates between Modes, Tasks, Sessions routes
3. TopBar shows MARS logo and action icons
4. Old Header and TopNavigation are no longer rendered
5. All existing page functionality works within the new shell
6. Build passes with no errors

## Next Stage

Once Stage 2 is verified complete, proceed to:
**Stage 3: Branding & Renaming**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
