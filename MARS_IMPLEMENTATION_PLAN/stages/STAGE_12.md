# Stage 12: File Viewer Overhaul

**Phase:** 4 - Refinements
**Dependencies:** Stage 4 (Core Components), Stage 8 (Modals)
**Risk Level:** Medium

## Objectives

1. Overhaul the file viewer (used in DAGFilesView, FileBrowser, and SessionManager) to support rich inline preview of multiple file types
2. Support: PDF, PNG/JPG/GIF/SVG (images), Markdown (.md), CSV, JSON, YAML, Python, JavaScript/TypeScript, plain text, and binary fallback
3. Create a unified `FilePreview` component that auto-detects file type and renders the appropriate viewer
4. Add PDF viewer using browser-native rendering (iframe or embed)
5. Render Markdown with proper formatting (headers, lists, code blocks, tables)
6. Render CSV as a formatted data table
7. Code files get syntax highlighting with language detection
8. Apply MARS design tokens to the entire file browsing experience
9. All icons from Lucide -- consistent file type indicators

## Current State Analysis

### What We Have

**`FileBrowser.tsx` (353 lines):**
- Directory listing via `GET /api/files/list?path=`
- File content loading via `GET /api/files/content?path=`
- Image preview: inline `<img>` from `/api/files/serve-image?path=`
- Text preview: raw `<pre>` block with no syntax highlighting
- Binary files: "Preview not available" message
- No PDF, Markdown, or CSV support
- Uses hardcoded dark colors, not MARS tokens

**`DAGFilesView.tsx` (463 lines):**
- Files list from `GET /api/runs/{runId}/files`
- File content loading via `GET /api/files/content?file_path=`
- Image preview: base64 inline `<img>` when `content_type === 'image'`
- Text preview: raw `<pre>` block with no syntax highlighting
- Binary files: `[Binary file - size]` text message
- List view and tree view toggle
- Search and type filter
- No PDF, Markdown, or CSV support
- Uses hardcoded gray-900/gray-800 colors

**`SessionManager/SessionDAGTab.tsx` and related:**
- Also shows files but reuses DAGFilesView

**API Endpoints Available:**
- `GET /api/files/list?path=` → directory listing
- `GET /api/files/content?path=` or `?file_path=` → file content (text/base64)
- `GET /api/files/serve-image?path=` → raw image bytes

### What We Need
- Unified `FilePreview` component handling all file types
- PDF: rendered via `<iframe>` or `<embed>` pointing to serve endpoint
- Markdown: rendered with formatted HTML (headers, lists, tables, inline code)
- CSV: parsed and displayed as a DataTable
- JSON/YAML: syntax-highlighted with collapsible nodes
- Code (.py, .js, .ts, etc.): syntax-highlighted via react-syntax-highlighter (already a dependency)
- Images: current implementation is adequate, needs MARS token styling
- Binary fallback: file info card with download button
- Consistent Lucide icons for all file types

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 complete: Core components (DataTable, Skeleton, Button, Badge) available
2. `react-syntax-highlighter` available (already in package.json)
3. API endpoints for file listing and content are working

## Implementation Tasks

### Task 1: Create FilePreview Component
**Objective:** Unified file preview that auto-detects type and renders appropriate viewer

**Files to Create:**
- `components/files/FilePreview.tsx`

**File type detection and rendering map:**

| Extension(s) | MIME Type Pattern | Viewer | Implementation |
|---|---|---|---|
| `.pdf` | `application/pdf` | PDF Viewer | `<iframe>` or `<embed>` pointing to serve endpoint |
| `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`, `.bmp`, `.tiff` | `image/*` | Image Viewer | `<img>` with zoom on click, MARS-styled container |
| `.md` | `text/markdown` | Markdown Renderer | Parse markdown and render as formatted HTML |
| `.csv` | `text/csv` | Data Table | Parse CSV rows/columns, render using DataTable component |
| `.json` | `application/json` | JSON Viewer | Syntax-highlighted, collapsible tree |
| `.yaml`, `.yml` | `text/yaml` | YAML Viewer | Syntax-highlighted |
| `.py` | `text/x-python` | Code Viewer | `react-syntax-highlighter` with Python language |
| `.js`, `.jsx`, `.ts`, `.tsx` | `text/javascript` | Code Viewer | `react-syntax-highlighter` with JS/TS language |
| `.html`, `.css` | `text/html`, `text/css` | Code Viewer | Syntax-highlighted |
| `.txt`, `.log` | `text/plain` | Text Viewer | Monospace `<pre>` with line numbers |
| `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx` | `application/*` | Office Fallback | File info card + download button (no inline preview) |
| Other binary | `application/octet-stream` | Binary Fallback | File info card + size + download button |

**Props:**
```typescript
interface FilePreviewProps {
  fileName: string
  filePath: string
  content?: string          // Text content (already loaded)
  contentType?: string      // 'text' | 'image' | 'binary'
  mimeType?: string
  encoding?: string         // 'utf-8' | 'base64'
  sizeBytes?: number
  serveUrl?: string         // URL to serve raw file (for images/PDF)
  onDownload?: () => void
  maxHeight?: string        // Default '600px'
}
```

### Task 2: Create Markdown Renderer
**Objective:** Render .md files with proper formatting

**Files to Create:**
- `components/files/MarkdownRenderer.tsx`

**Implementation approach:**
Simple Markdown parser (no external dependency) that handles:
- `#`, `##`, `###` → `<h1>`, `<h2>`, `<h3>` with MARS typography tokens
- `**bold**` → `<strong>`
- `*italic*` → `<em>`
- `` `code` `` → `<code>` with MARS code background
- ``` ```code blocks``` ``` → Syntax-highlighted block via react-syntax-highlighter
- `- item` → `<ul><li>`
- `1. item` → `<ol><li>`
- `> blockquote` → Styled blockquote with left border
- `[text](url)` → `<a>` link
- `![alt](url)` → `<img>`
- `| col | col |` → `<table>` with MARS-styled rows

If a full parser is needed, use a lightweight regex-based approach. Do NOT add `marked` or `remark` as dependencies -- keep it minimal. If the built-in is insufficient, this can be upgraded later.

**Styling:**
All rendered HTML uses MARS typography tokens. Headers, paragraphs, lists, tables, code blocks all styled via a `.mars-markdown` CSS class in `mars.css`.

### Task 3: Create CSV Table Viewer
**Objective:** Render .csv files as a formatted data table

**Files to Create:**
- `components/files/CSVTableViewer.tsx`

**Implementation:**
```typescript
interface CSVTableViewerProps {
  content: string   // Raw CSV text
  fileName: string
  maxRows?: number  // Default 100 (paginate or virtualize beyond this)
}
```

Features:
- Parse CSV content (split by newline, split by comma, handle quoted fields)
- First row treated as headers
- Render using DataTable component from `components/core`
- Sortable columns
- Show row count badge
- Truncate cells with tooltip for full content
- If > 100 rows, show "Showing first 100 of N rows" with option to load more

### Task 4: Create PDF Viewer
**Objective:** Render PDF files inline

**Files to Create:**
- `components/files/PDFViewer.tsx`

**Implementation:**
```typescript
interface PDFViewerProps {
  serveUrl: string    // URL to serve the raw PDF
  fileName: string
  sizeBytes?: number
}
```

Use browser-native PDF rendering:
```tsx
<iframe
  src={serveUrl}
  title={fileName}
  className="w-full rounded-mars-md border"
  style={{
    height: maxHeight || '600px',
    borderColor: 'var(--mars-color-border)',
  }}
/>
```

Fallback for browsers that don't support inline PDF:
```tsx
<div className="text-center py-12">
  <FileText className="w-12 h-12 mx-auto mb-4" style={{ color: 'var(--mars-color-text-tertiary)' }} />
  <p>PDF preview not available in this browser</p>
  <Button onClick={onDownload} variant="primary" className="mt-4">Download PDF</Button>
</div>
```

### Task 5: Create Code Viewer
**Objective:** Syntax-highlighted code display for source files

**Files to Create:**
- `components/files/CodeViewer.tsx`

**Implementation:**
```typescript
interface CodeViewerProps {
  content: string
  language: string   // 'python' | 'javascript' | 'typescript' | 'json' | 'yaml' | 'html' | 'css'
  fileName: string
  showLineNumbers?: boolean  // Default true
  maxHeight?: string
}
```

Use existing `react-syntax-highlighter` dependency:
```tsx
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// Custom theme overrides to match MARS tokens
const marsCodeTheme = {
  ...oneDark,
  'pre[class*="language-"]': {
    ...oneDark['pre[class*="language-"]'],
    background: 'var(--mars-color-console-bg)',
    fontFamily: 'var(--mars-font-mono)',
    fontSize: 'var(--mars-font-size-sm)',
  },
}
```

Features:
- Language auto-detection from file extension
- Line numbers with MARS token styling
- Copy button in header
- File name and language badge in header

### Task 6: Create File Type Icon Map
**Objective:** Consistent Lucide icon assignments for all file types

**Files to Create:**
- `components/files/fileIcons.ts`

**Implementation:**
```typescript
import {
  FileText, Code, Image, Database, File, FileJson, FileSpreadsheet,
  FileType, Presentation, Table, BookOpen, FileCode, FileImage,
} from 'lucide-react'

export function getFileIcon(fileName: string, mimeType?: string): {
  icon: React.ElementType
  color: string  // MARS token reference
} {
  const ext = fileName.split('.').pop()?.toLowerCase()

  // By extension
  switch (ext) {
    case 'pdf': return { icon: FileText, color: 'var(--mars-color-danger)' }
    case 'md': return { icon: BookOpen, color: 'var(--mars-color-info)' }
    case 'csv': return { icon: Table, color: 'var(--mars-color-success)' }
    case 'json': return { icon: FileJson, color: 'var(--mars-color-warning)' }
    case 'yaml': case 'yml': return { icon: FileCode, color: 'var(--mars-color-warning)' }
    case 'py': return { icon: Code, color: 'var(--mars-color-info)' }
    case 'js': case 'jsx': case 'ts': case 'tsx': return { icon: Code, color: 'var(--mars-color-primary)' }
    case 'html': case 'css': return { icon: Code, color: 'var(--mars-color-accent)' }
    case 'png': case 'jpg': case 'jpeg': case 'gif': case 'svg': case 'webp': case 'bmp': case 'tiff':
      return { icon: Image, color: 'var(--mars-color-accent)' }
    case 'db': case 'sql': case 'sqlite': return { icon: Database, color: 'var(--mars-color-warning)' }
    case 'doc': case 'docx': return { icon: FileType, color: 'var(--mars-color-primary)' }
    case 'xls': case 'xlsx': return { icon: FileSpreadsheet, color: 'var(--mars-color-success)' }
    case 'ppt': case 'pptx': return { icon: Presentation, color: 'var(--mars-color-danger)' }
    case 'txt': case 'log': return { icon: FileText, color: 'var(--mars-color-text-secondary)' }
    default: return { icon: File, color: 'var(--mars-color-text-tertiary)' }
  }
}
```

### Task 7: Update DAGFilesView to Use FilePreview
**Objective:** Replace raw `<pre>` and inline image rendering with FilePreview component

**Files to Modify:**
- `components/dag/DAGFilesView.tsx`

**Changes:**
- Replace `getFileIcon()` with the shared `getFileIcon()` from `components/files/fileIcons.ts`
- Replace the file content preview section (lines 423-458) with `<FilePreview />`
- Pass appropriate props from `FileNode` to `FilePreview`:
  ```tsx
  <FilePreview
    fileName={selectedFile.file_name}
    filePath={selectedFile.file_path}
    content={selectedFile.file_content}
    contentType={selectedFile.content_type}
    mimeType={selectedFile.mime_type}
    encoding={selectedFile.encoding}
    sizeBytes={selectedFile.size_bytes}
    onDownload={() => handleDownload(selectedFile)}
  />
  ```
- Apply MARS tokens to the file list panel (replace hardcoded `bg-gray-900`, `border-gray-700`, etc.)

### Task 8: Update FileBrowser to Use FilePreview
**Objective:** Replace raw preview in FileBrowser with FilePreview component

**Files to Modify:**
- `components/FileBrowser.tsx`

**Changes:**
- Replace `getFileIcon()` with shared `getFileIcon()` from `components/files/fileIcons.ts`
- Replace the file content preview section (lines 258-349) with `<FilePreview />`
- For images, pass `serveUrl={/api/files/serve-image?path=...}`
- For PDF, pass `serveUrl={/api/files/serve-image?path=...}` (assuming the backend can serve PDFs via this endpoint)
- Apply MARS tokens to the entire component (replace hardcoded colors)

### Task 9: Add Markdown CSS to mars.css
**Objective:** Style rendered Markdown content

**Files to Modify:**
- `styles/mars.css`

**Add:**
```css
/* Markdown rendering styles */
.mars-markdown h1 { font-size: var(--mars-font-size-2xl); font-weight: 700; margin-top: var(--mars-space-6); margin-bottom: var(--mars-space-3); color: var(--mars-color-text); }
.mars-markdown h2 { font-size: var(--mars-font-size-xl); font-weight: 600; margin-top: var(--mars-space-5); margin-bottom: var(--mars-space-2); color: var(--mars-color-text); }
.mars-markdown h3 { font-size: var(--mars-font-size-lg); font-weight: 600; margin-top: var(--mars-space-4); margin-bottom: var(--mars-space-2); color: var(--mars-color-text); }
.mars-markdown p { margin-bottom: var(--mars-space-3); color: var(--mars-color-text-secondary); line-height: 1.7; }
.mars-markdown ul, .mars-markdown ol { padding-left: var(--mars-space-5); margin-bottom: var(--mars-space-3); }
.mars-markdown li { margin-bottom: var(--mars-space-1); color: var(--mars-color-text-secondary); }
.mars-markdown code { padding: 2px 6px; border-radius: var(--mars-radius-sm); background: var(--mars-color-surface-overlay); font-family: var(--mars-font-mono); font-size: 0.875em; }
.mars-markdown pre { padding: var(--mars-space-4); border-radius: var(--mars-radius-md); background: var(--mars-color-console-bg); overflow-x: auto; margin-bottom: var(--mars-space-3); }
.mars-markdown pre code { padding: 0; background: none; }
.mars-markdown blockquote { border-left: 3px solid var(--mars-color-primary); padding-left: var(--mars-space-4); margin: var(--mars-space-3) 0; color: var(--mars-color-text-tertiary); font-style: italic; }
.mars-markdown table { width: 100%; border-collapse: collapse; margin-bottom: var(--mars-space-3); }
.mars-markdown th { text-align: left; padding: var(--mars-space-2) var(--mars-space-3); border-bottom: 2px solid var(--mars-color-border); font-weight: 600; color: var(--mars-color-text); }
.mars-markdown td { padding: var(--mars-space-2) var(--mars-space-3); border-bottom: 1px solid var(--mars-color-border); color: var(--mars-color-text-secondary); }
.mars-markdown a { color: var(--mars-color-primary); text-decoration: underline; }
.mars-markdown img { max-width: 100%; border-radius: var(--mars-radius-md); margin: var(--mars-space-3) 0; }
.mars-markdown hr { border: none; border-top: 1px solid var(--mars-color-border); margin: var(--mars-space-5) 0; }
```

### Task 10: Barrel Export
**Files to Create:**
- `components/files/index.ts`

```typescript
export { default as FilePreview } from './FilePreview'
export { default as MarkdownRenderer } from './MarkdownRenderer'
export { default as CSVTableViewer } from './CSVTableViewer'
export { default as PDFViewer } from './PDFViewer'
export { default as CodeViewer } from './CodeViewer'
export { getFileIcon } from './fileIcons'
```

## Files to Create (Summary)

```
components/files/
├── FilePreview.tsx
├── MarkdownRenderer.tsx
├── CSVTableViewer.tsx
├── PDFViewer.tsx
├── CodeViewer.tsx
├── fileIcons.ts
└── index.ts
```

**Total: 7 files**

## Files to Modify

- `components/dag/DAGFilesView.tsx` - Use FilePreview, shared icons, MARS tokens
- `components/FileBrowser.tsx` - Use FilePreview, shared icons, MARS tokens
- `styles/mars.css` - Add `.mars-markdown` styles

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] PDF files render inline via iframe
- [ ] PNG/JPG images render inline
- [ ] Markdown (.md) files render with formatted headers, lists, code blocks
- [ ] CSV files render as a formatted data table with sortable columns
- [ ] JSON files render with syntax highlighting
- [ ] Python/JS/TS files render with syntax highlighting and line numbers
- [ ] Unknown/binary files show info card with download button
- [ ] DAGFilesView uses the new FilePreview component
- [ ] FileBrowser uses the new FilePreview component
- [ ] All file icons are Lucide components (no emojis)

### Should Pass
- [ ] CSV table supports sorting
- [ ] Code viewer has copy button
- [ ] Markdown tables render correctly
- [ ] Markdown code blocks are syntax-highlighted
- [ ] File type filter in DAGFilesView works with all supported types
- [ ] MARS design tokens applied consistently (no hardcoded gray-900/gray-800)
- [ ] File type icons have distinct colors per type

### Nice to Have
- [ ] JSON files support collapsible tree nodes
- [ ] Image viewer supports zoom on click
- [ ] CSV viewer supports pagination for large files (>100 rows)
- [ ] YAML files render with syntax highlighting
- [ ] SVG files render inline (not as image)

## Common Issues and Solutions

### Issue 1: PDF Serve Endpoint
**Symptom:** PDF doesn't render -- `/api/files/serve-image` only serves images
**Solution:** Check if the backend `/api/files/serve-image` endpoint can serve any binary file or only images. If only images, a new endpoint may be needed. Alternative: use the content endpoint with base64 encoding and convert to a data URL for the iframe `src`. If backend changes are not allowed, use the download fallback for PDF.

### Issue 2: CSV Parsing Edge Cases
**Symptom:** CSV with commas inside quoted fields breaks
**Solution:** Use a proper CSV parser that handles quoted fields. Simple implementation:
```typescript
function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  // Handle quoted fields, newlines within quotes, escaped quotes
  // ... regex-based or state-machine parser
}
```

### Issue 3: Large File Content
**Symptom:** Syntax highlighter freezes on 10,000+ line files
**Solution:** Truncate content to first 500 lines with a "Show more" button. Display a warning: "Showing first 500 of N lines."

### Issue 4: Markdown XSS
**Symptom:** Rendered markdown contains executable HTML/scripts
**Solution:** The markdown renderer must sanitize output. Do not use `dangerouslySetInnerHTML` with raw HTML. Use React element creation instead, or sanitize HTML through a whitelist of allowed tags.

## Rollback Procedure

If Stage 12 causes issues:
1. Revert `components/dag/DAGFilesView.tsx` to pre-Stage-12 state
2. Revert `components/FileBrowser.tsx` to pre-Stage-12 state
3. Delete `components/files/` directory
4. Remove `.mars-markdown` styles from `mars.css`
5. Run `npm run build`

## Success Criteria

Stage 12 is complete when:
1. FilePreview component handles PDF, images, Markdown, CSV, JSON, code, and binary files
2. DAGFilesView and FileBrowser use the new FilePreview component
3. All file type icons are Lucide components
4. MARS design tokens applied consistently
5. Markdown renders with proper formatting
6. CSV renders as an interactive data table
7. Code files have syntax highlighting
8. Build passes with no errors

## Next Stage

Stage 12 is the final stage. Proceed to full verification using `tests/test_scenarios.md`.

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
