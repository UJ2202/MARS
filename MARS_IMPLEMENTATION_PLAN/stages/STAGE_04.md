# Stage 4: Core Component Library

**Phase:** 1 - Core Components
**Dependencies:** Stage 1 (Design Tokens), Stage 2 (AppShell)
**Risk Level:** Medium

## Objectives

1. Build all reusable UI primitives in `components/core/`
2. Components must be pure UI - props and callbacks only, no business logic
3. All components use MARS design tokens (CSS custom properties)
4. Components are accessible (ARIA roles, keyboard nav, focus management)
5. Export all components from a barrel `index.ts`

## Current State Analysis

### What We Have
- `components/common/ConnectionStatus.tsx` - connection indicator
- `components/common/ProgressBar.tsx` - basic progress bar
- `components/common/StatusBadge.tsx` - status badge
- `components/tables/DataTable.tsx` - generic data table
- Various inline Tailwind styling patterns across all components

### What We Need
- Standardized Button, IconButton, Dropdown, Tabs, Modal, Toast, InlineAlert, Tooltip, EmptyState, Badge, Tag, Stepper, ProgressIndicator, Skeleton, DataTable components
- All using MARS design tokens
- Exported from `components/core/index.ts`
- TypeScript interfaces for all props

## Implementation Tasks

### Task 1: Button & IconButton
**Objective:** Primary interactive elements

**Files to Create:**
- `components/core/Button.tsx`
- `components/core/IconButton.tsx`

**Button Props:**
```typescript
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode  // Leading icon
  iconRight?: React.ReactNode  // Trailing icon
  fullWidth?: boolean
}
```

**IconButton Props:**
```typescript
interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  label: string  // Required for accessibility (aria-label)
  icon: React.ReactNode
  active?: boolean
  badge?: number | string
}
```

Sizes: sm=32px, md=36px, lg=40px height. Use MARS tokens for colors, radii, transitions.

### Task 2: Badge & Tag
**Objective:** Status indicators and categorization labels

**Files to Create:**
- `components/core/Badge.tsx`
- `components/core/Tag.tsx`

**Badge Props:**
```typescript
interface BadgeProps {
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'
  size?: 'sm' | 'md'
  dot?: boolean  // Show as status dot only
  children: React.ReactNode
}
```

**Tag Props:**
```typescript
interface TagProps {
  label: string
  color?: string  // Optional custom color
  onRemove?: () => void  // Shows remove button if provided
  icon?: React.ReactNode
}
```

### Task 3: Modal
**Objective:** Base modal component with draggable header and resizable edges

**Files to Create:**
- `components/core/Modal.tsx`

**Modal Props:**
```typescript
interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  size?: 'sm' | 'md' | 'lg' | 'xl'  // Width presets
  draggable?: boolean
  resizable?: boolean
  children: React.ReactNode
  footer?: React.ReactNode
  closeOnEscape?: boolean  // Default true
  closeOnBackdrop?: boolean  // Default true
}
```

**Size presets:**
- sm: 480px
- md: 640px (default)
- lg: 960px
- xl: 1200px

**Must include:**
- Backdrop overlay with `--mars-z-modal-backdrop`
- Modal content with `--mars-z-modal`
- Focus trap (Tab cycling within modal)
- Esc to close
- Return focus to trigger on close
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby`
- Draggable header (mouse/touch)
- Resizable edge handles (optional)
- Non-blocking of background app state

### Task 4: Tabs
**Objective:** Tab component for in-modal and in-page use

**Files to Create:**
- `components/core/Tabs.tsx`

**Tabs Props:**
```typescript
interface TabItem {
  id: string
  label: string
  icon?: React.ReactNode
  badge?: number | string
  disabled?: boolean
}

interface TabsProps {
  items: TabItem[]
  activeId: string
  onChange: (id: string) => void
  variant?: 'underline' | 'pills'  // Default underline
  size?: 'sm' | 'md'
}
```

Uses `role="tablist"`, `role="tab"`, `aria-selected`, keyboard arrow navigation.

### Task 5: Toast & InlineAlert
**Objective:** Notification components

**Files to Create:**
- `components/core/Toast.tsx`
- `components/core/InlineAlert.tsx`

**Toast Props:**
```typescript
interface ToastProps {
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message?: string
  duration?: number  // ms, 0 for persistent
  onClose: () => void
  action?: { label: string; onClick: () => void }
}
```

Toast appears at top-right with `--mars-z-toast`. Auto-dismiss after `duration`. Slide-in animation.

**InlineAlert Props:**
```typescript
interface InlineAlertProps {
  type: 'info' | 'success' | 'warning' | 'error'
  title?: string
  children: React.ReactNode
  closable?: boolean
  onClose?: () => void
  action?: { label: string; onClick: () => void }
}
```

Inline within content flow. No z-index needed.

### Task 6: Tooltip
**Objective:** Contextual information popup

**Files to Create:**
- `components/core/Tooltip.tsx`

**Tooltip Props:**
```typescript
interface TooltipProps {
  content: string | React.ReactNode
  children: React.ReactNode
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number  // ms, default 300
}
```

Uses `role="tooltip"`, `aria-describedby`. Shows on hover/focus with delay. Uses `--mars-z-tooltip`.

### Task 7: EmptyState
**Objective:** Placeholder for empty views

**Files to Create:**
- `components/core/EmptyState.tsx`

**EmptyState Props:**
```typescript
interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: {
    label: string
    onClick: () => void
  }
}
```

Centered layout with icon, title, description, and optional CTA button.

### Task 8: ProgressIndicator & Stepper
**Objective:** Progress visualization components

**Files to Create:**
- `components/core/ProgressIndicator.tsx`
- `components/core/Stepper.tsx`

**ProgressIndicator Props:**
```typescript
interface ProgressIndicatorProps {
  value: number  // 0-100
  variant?: 'bar' | 'ring'
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  color?: 'primary' | 'success' | 'warning' | 'danger'
}
```

**Stepper Props:**
```typescript
interface StepperStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed' | 'failed' | 'skipped'
  description?: string
}

interface StepperProps {
  steps: StepperStep[]
  orientation?: 'horizontal' | 'vertical'
  size?: 'sm' | 'md'
}
```

### Task 9: Skeleton & Dropdown
**Objective:** Loading states and selection menus

**Files to Create:**
- `components/core/Skeleton.tsx`
- `components/core/Dropdown.tsx`

**Skeleton Props:**
```typescript
interface SkeletonProps {
  variant?: 'text' | 'rectangular' | 'circular'
  width?: string | number
  height?: string | number
  lines?: number  // For text variant, number of lines
}
```

Pulsing animation. Uses `--mars-color-surface-overlay`.

**Dropdown Props:**
```typescript
interface DropdownItem {
  id: string
  label: string
  icon?: React.ReactNode
  disabled?: boolean
  danger?: boolean
  divider?: boolean
}

interface DropdownProps {
  trigger: React.ReactNode
  items: DropdownItem[]
  onSelect: (id: string) => void
  align?: 'left' | 'right'
}
```

Uses `--mars-z-dropdown`. Keyboard accessible (arrow keys, Enter, Esc).

### Task 10: DataTable (Enhanced)
**Objective:** Enhance existing DataTable with MARS tokens

**Files to Create:**
- `components/core/DataTable.tsx`

**DataTable Props:**
```typescript
interface Column<T> {
  id: string
  header: string
  accessor: (row: T) => React.ReactNode
  sortable?: boolean
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  loading?: boolean
  emptyMessage?: string
  onRowClick?: (row: T) => void
  selectedId?: string
  stickyHeader?: boolean
}
```

Uses MARS tokens for borders, text colors, hover states. Shows Skeleton rows when loading.

### Task 11: Barrel Export
**Objective:** Export all core components from a single entry point

**Files to Create:**
- `components/core/index.ts`

```typescript
export { default as Button } from './Button'
export type { ButtonProps } from './Button'
export { default as IconButton } from './IconButton'
export { default as Badge } from './Badge'
export { default as Tag } from './Tag'
export { default as Modal } from './Modal'
export { default as Tabs } from './Tabs'
export { default as Toast } from './Toast'
export { default as InlineAlert } from './InlineAlert'
export { default as Tooltip } from './Tooltip'
export { default as EmptyState } from './EmptyState'
export { default as ProgressIndicator } from './ProgressIndicator'
export { default as Stepper } from './Stepper'
export { default as Skeleton } from './Skeleton'
export { default as Dropdown } from './Dropdown'
export { default as DataTable } from './DataTable'
```

## Files to Create (Summary)

```
components/core/
├── Button.tsx
├── IconButton.tsx
├── Badge.tsx
├── Tag.tsx
├── Modal.tsx
├── Tabs.tsx
├── Toast.tsx
├── InlineAlert.tsx
├── Tooltip.tsx
├── EmptyState.tsx
├── ProgressIndicator.tsx
├── Stepper.tsx
├── Skeleton.tsx
├── Dropdown.tsx
├── DataTable.tsx
└── index.ts
```

**Total: 16 files**

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds with all components
- [ ] `npx tsc --noEmit` passes
- [ ] All components render without errors (import from `@/components/core`)
- [ ] Modal traps focus and handles Esc
- [ ] All interactive components have `aria-*` attributes
- [ ] Components use MARS CSS custom properties (not hardcoded colors)

### Should Pass
- [ ] Button variants (primary, secondary, ghost, danger) render correctly
- [ ] Badge variants (success, warning, danger, info) use correct token colors
- [ ] Modal size presets render at correct widths
- [ ] Tabs support keyboard arrow navigation
- [ ] Toast auto-dismisses after duration
- [ ] Skeleton shows pulsing animation
- [ ] Dropdown positions correctly (left/right align)

### Nice to Have
- [ ] Components work correctly in both dark and light themes
- [ ] ProgressIndicator ring variant renders as SVG circle
- [ ] DataTable supports sort indicators

## Common Issues and Solutions

### Issue 1: Focus Trap in Modal
**Symptom:** Tab key exits modal
**Solution:** Use a focus trap that wraps Tab key navigation between first and last focusable elements in the modal. Query `:focus-visible` elements inside the modal container.

### Issue 2: Tooltip Positioning
**Symptom:** Tooltip clips off screen edge
**Solution:** Simple implementation can use CSS transform + position. If advanced positioning is needed, consider `@floating-ui/react` as an optional dependency.

### Issue 3: CSS Variable References in Tailwind
**Symptom:** `bg-mars-primary` doesn't work with opacity utilities
**Solution:** Tailwind's opacity utilities (`bg-opacity-50`) won't work with CSS variable color values. Use explicit opacity alternatives: `bg-[var(--mars-color-primary-subtle)]` or inline styles.

## Rollback Procedure

If Stage 4 causes issues:
1. Delete `components/core/` directory
2. Run `npm run build` to confirm existing components are unaffected

## Success Criteria

Stage 4 is complete when:
1. All 15 components exist in `components/core/`
2. Each component is typed with TypeScript interfaces
3. Components use MARS design tokens exclusively
4. Barrel export works: `import { Button, Modal, Toast } from '@/components/core'`
5. Build passes with no errors
6. Components are accessible (keyboard, screen reader)

## Next Stage

Once Stage 4 is verified complete, proceed to:
**Stage 5: Modes Gallery Redesign** (or Stage 6/7 in parallel)

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
