# ProductFlow AI Internal UI Implementation Plan

> **Execution:** Follow this plan task-by-task within the user-authorized scope.

**Goal:** Apply the approved light green prototype to the existing internal application without replacing real business data or service calls.

**Architecture:** Keep the React/FastAPI contracts and product detail workflows. Consolidate navigation into Dashboard, Product Library, a collapsible AI Content Factory, Content Assets, and Quality/Delivery. Reuse product workflows for focused planning, image, video and data-cleaning views.

**Tech Stack:** React 18, TypeScript, Vite, existing CSS and REST endpoints.

---

### Task 1: Shell and design system
Modify `frontend/main.tsx`, `frontend/style.css`, `frontend/ui.tsx`. Use aligned icons, collapsible navigation, mobile navigation and visible keyboard focus. Remove technical sidebar copy and optional promotional subtitles; keep actionable errors and business evidence.

### Task 2: Dashboard and production records
Create `frontend/workspace.ts` and `frontend/pages/Tasks.tsx`; replace `frontend/pages/Dashboard.tsx`. Read existing product/run/output endpoints, poll safely and show real step counts. Per-product run endpoints currently return the latest 20 records: label lists as recent records, not total historical counts. Do not trigger paid generation during verification.

### Task 3: Consolidated libraries and focused factory pages
Create `frontend/pages/Catalog.tsx`; update Products, BatchImport, ProductDetail, Studio, product-tabs, Library and Reviews. Product Library owns data import/cleaning/quality. Existing confirmed facts and assets stay intact; source and output assets remain distinct. Move new-product form into an accessible dialog. Preserve legacy deep links.

### Task 4: Verify
Run `npm run build` and the existing backend tests. Start the actual app, inspect desktop/mobile rendering, keyboard navigation, collapsed factory navigation, catalog tabs, BP01 facts, asset filters and error states. Use read-only browser checks; do not modify real records or call AI services just to validate styling.

## Completed verification

- `npm run build`: passed (TypeScript and Vite).
- Existing backend suite: 33 passed, one existing AnyIO deprecation warning; isolated temporary test data.
- Browser: expandable factory navigation, BP01 global search, new-product dialog and Escape dismissal, catalog quality (real 4/4 required fields for BP01), focused image/video forms, actual video preview, recent task records.
- At 390px: mobile menu opens/closes, catalog page width remains 390px, and production form remains usable. Desktop layout also visually inspected.
- Reproduced an asset-tab crash caused by rendering source records as outputs during a tab transition. Fixed by associating results with their query and discarding obsolete requests. Rechecked rapid source/output switching and video preview.
- Real data preserved; no generation, review decision, product creation or paid model call was performed during browser QA. Provider integration and production error conditions were not re-exercised in this UI refresh.
