# Frontend Scaffold Design

## Purpose
Demo/showcase frontend for the Social Simulation Engine. Dark scientific/terminal aesthetic. Embedded in FastAPI as a single HTML file with vanilla JS — no build step, no dependencies.

## Architecture
- Single `static/index.html` served via FastAPI `StaticFiles`
- Hash-based client-side routing (`#/`, `#/run/{type}`, `#/sim/{id}`, `#/history`)
- FastAPI mount: `app.mount("/", StaticFiles(directory="static", html=True))`
- API calls to `/api/v1/*` (no conflict with static mount order)

## Views

### 1. Experiment Picker (`#/`)
- Fetches `GET /api/v1/experiments`
- Renders cards: icon + title + description + status badge
- Working experiments are clickable → `#/run/{type}`
- Stub experiments show "Coming Soon" badge, disabled

### 2. Config Form (`#/run/{type}`)
- Dynamic form based on experiment's `config_schema`
- Policy: textarea (policy_text) + number (sample_size)
- Game theory: numeric inputs for type-specific params
- Submit → `POST /api/v1/simulations` → redirect to `#/sim/{id}`

### 3. Simulation Progress & Results (`#/sim/{id}`)
- Polls `GET /api/v1/simulations/{id}` every 3s while pending/running
- Stage pipeline visualization from `GET /api/v1/simulations/{id}/stages`
- On completed: stop polling, fetch agents, render:
  - Synthesis report (markdown from `summary` field)
  - Agent response cards (expandable, persona details + response + stance badge)
- On failed: error display from `summary`

### 4. History (`#/history`)
- Fetches `GET /api/v1/simulations`
- Table/list of past runs with type, status, timestamp
- Click row → `#/sim/{id}`

## Visual Design
- **Background**: `#0a0e17` with subtle grid pattern
- **Cards**: `rgba(15, 20, 35, 0.8)` with `1px solid #1a2340`
- **Primary accent**: Electric cyan `#00d4ff`
- **Warning accent**: Amber `#f59e0b`
- **Error**: Red `#ef4444`
- **Success**: Green `#22c55e`
- **Text**: `#e2e8f0` primary, `#64748b` secondary
- **Fonts**: System monospace for data, system sans-serif for headings
- **Effects**: Subtle glow on active elements, smooth transitions

## Status Badges
- Pending: amber
- Running: cyan with pulse animation
- Completed: green
- Failed: red

## Error Handling
- Toast notifications for API errors
- Retry button on network failures
- Graceful fallback if API is unreachable

## Tech Decisions
- Vanilla JS — no framework, no build step
- CSS custom properties for theming
- `fetch()` for API calls
- `setInterval` for polling (cleared on navigation/completion)
- Simple hash router (~30 lines)
