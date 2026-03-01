# Neighborhood Visualization Design

## Overview

A p5.js-powered interactive neighborhood visualization integrated into the existing SPA. Displays a pixel art neighborhood background with wandering agent sprites that show speech bubbles with their simulation responses on hover.

## Architecture

- New `#/neighborhood/{simId}` route added to the SPA router in `index.html`
- p5.js loaded from CDN in `<head>`
- `renderNeighborhood(simId)` creates a container div, initializes p5 in instance mode
- p5 instance destroyed (`.remove()`) on route change to clean up

## Sprite Handling

- **Background**: `WhatsApp Image 2026-03-01 at 1.05.27 PM.jpeg` — scaled to fit canvas
- **Characters**: `WhatsApp Image 2026-03-01 at 1.13.01 PM.jpeg` — 8 sprites in 4x2 grid, sliced at load time
- **Grass detection**: Sample background pixels; green channel dominant (G > R, G > B, G > 80) = walkable

## Agent Data Model

```
{
  x, y,             // current position
  targetX, targetY, // movement target
  speed,            // ~0.5-1 px/frame
  sprite,           // p5.Image slice
  state,            // MOVING | PAUSING | CHOOSING
  pauseTimer,       // frames remaining in pause
  hovering,         // boolean
  response,         // AgentResponse.output_text from API
  name,             // persona name for label
}
```

## Wander AI State Machine

1. **MOVING** — Lerp toward target at slow speed
2. **PAUSING** — On arrival, pause for 2-4 seconds (random)
3. **CHOOSING** — Pick new random target within ~60-100px radius on grass, transition to MOVING

Targets that land on non-grass pixels are rejected and re-sampled.

## Hover Interaction

- Per-frame distance check: `dist(mouseX, mouseY, agent.x, agent.y) < hitRadius`
- Hover: freeze movement, display speech bubble with `output_text`
- Speech bubble: rounded rect above agent, pixel-art styling
- Leave: resume wandering from current position

## API Integration

- Fetch `GET /api/v1/simulations/{simId}/agents` on mount
- Map first 8 agents (excluding distribution_generator/synthesizer) to the 8 character sprites
- Each agent's `output_text` and `persona.name` populate the tooltip

## Route Integration

- Add `neighborhood/{simId}` case to the router's hash handler
- Add "Neighborhood" nav link or button on simulation results page
- Canvas resizes responsively within `#app` container
