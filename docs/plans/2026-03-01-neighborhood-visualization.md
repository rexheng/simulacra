# Neighborhood Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an interactive p5.js neighborhood view where pixel art agents wander on grass and show speech bubbles with their simulation responses on hover.

**Architecture:** p5.js in instance mode mounted inside the existing SPA's `#app` div via a new `#/neighborhood/{simId}` route. Agents fetch their data from the existing API. The p5 instance is created on route enter and destroyed on route leave.

**Tech Stack:** p5.js (CDN), existing vanilla JS SPA router, existing REST API (`/api/v1/simulations/{simId}/agents`)

---

### Task 1: Add p5.js CDN script and neighborhood route skeleton

**Files:**
- Modify: `static/index.html:5` (add p5.js script tag after line 5)
- Modify: `static/index.html:777-785` (add `neighborhood/` route to router)

**Step 1: Add the p5.js CDN script tag**

In `<head>`, after the `<title>` tag (line 6), add:

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
```

**Step 2: Add route handler in the router function**

In the `router()` function, add a new `else if` branch before the `routes[hash]` check (around line 779):

```javascript
} else if (hash.startsWith('neighborhood/')) {
  renderNeighborhood(hash.slice('neighborhood/'.length));
```

**Step 3: Add a global variable to track the p5 instance for cleanup**

Before the `// === ROUTER ===` comment, add:

```javascript
// === P5 CLEANUP ===
let p5Instance = null;
function cleanupP5() {
  if (p5Instance) { p5Instance.remove(); p5Instance = null; }
}
```

**Step 4: Call `cleanupP5()` at the top of the `router()` function**

Add `cleanupP5();` right after `clearPolling();` inside `router()`.

**Step 5: Add empty `renderNeighborhood` function stub**

At the end of the `<script>`, before `</script>`, add:

```javascript
async function renderNeighborhood(simId) {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div>Loading neighborhood...</div>';
  // Will be implemented in next tasks
}
```

**Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat: add p5.js CDN and neighborhood route skeleton"
```

---

### Task 2: Implement the core p5.js sketch with background rendering

**Files:**
- Modify: `static/index.html` (replace the `renderNeighborhood` stub)

**Step 1: Replace `renderNeighborhood` with full implementation**

Replace the stub with this complete function. This loads the background image and creates the p5 canvas:

```javascript
async function renderNeighborhood(simId) {
  const app = document.getElementById('app');
  app.innerHTML = '<div class="loading"><div class="spinner"></div>Loading neighborhood...</div>';

  // Fetch agent data from API
  let agentData = [];
  try {
    const agents = await api('/simulations/' + simId + '/agents');
    agentData = agents.filter(a =>
      a.agent_name !== 'distribution_generator' && a.agent_name !== 'synthesizer'
    ).slice(0, 8);
  } catch (e) {
    app.innerHTML = `
      <div class="view-header">
        <a href="#/sim/${esc(simId)}" class="back-link">&larr; Back to Simulation</a>
        <h2>Neighborhood View</h2>
      </div>
      <div class="empty-state"><h3>Could not load agents</h3><p>Make sure the simulation has completed.</p></div>`;
    return;
  }

  if (agentData.length === 0) {
    app.innerHTML = `
      <div class="view-header">
        <a href="#/sim/${esc(simId)}" class="back-link">&larr; Back to Simulation</a>
        <h2>Neighborhood View</h2>
      </div>
      <div class="empty-state"><h3>No agents found</h3><p>This simulation has no respondent agents.</p></div>`;
    return;
  }

  // Set up container
  app.innerHTML = `
    <div class="view-header" style="margin-bottom:16px;">
      <a href="#/sim/${esc(simId)}" class="back-link">&larr; Back to Simulation</a>
      <h2>Neighborhood View</h2>
      <p>${agentData.length} agents wandering the neighborhood</p>
    </div>
    <div id="p5-container" style="border-radius:var(--radius);overflow:hidden;border:1px solid var(--border);"></div>`;

  // Launch p5 sketch
  const sketch = function(p) {
    let bgImg, spriteSheet;
    let sprites = [];
    let agents = [];
    let canvasW, canvasH;
    const SPRITE_COLS = 4;
    const SPRITE_ROWS = 2;
    const AGENT_DISPLAY_SIZE = 48;
    const HIT_RADIUS = 28;
    const MOVE_SPEED = 0.8;
    const WANDER_RADIUS = 80;

    // Grass zones — manually defined rectangles based on the neighborhood image layout.
    // The image has 4 house lots arranged in a 2x2 grid with roads between them.
    // Grass is the green areas around houses. These are expressed as fractions of image size.
    // We define walkable zones as the yard areas (excluding house footprints, roads, sidewalks).
    let grassZones = [];

    p.preload = function() {
      bgImg = p.loadImage('/static/WhatsApp%20Image%202026-03-01%20at%201.05.27%20PM.jpeg');
      spriteSheet = p.loadImage('/static/WhatsApp%20Image%202026-03-01%20at%201.13.01%20PM.jpeg');
    };

    p.setup = function() {
      const container = document.getElementById('p5-container');
      canvasW = Math.min(container.offsetWidth, 950);
      canvasH = Math.round(canvasW * (bgImg.height / bgImg.width));
      const canvas = p.createCanvas(canvasW, canvasH);
      canvas.parent('p5-container');
      p.imageMode(p.CORNER);
      p.textFont('monospace');

      // Slice sprite sheet into individual character sprites
      const sw = spriteSheet.width / SPRITE_COLS;
      const sh = spriteSheet.height / SPRITE_ROWS;
      for (let row = 0; row < SPRITE_ROWS; row++) {
        for (let col = 0; col < SPRITE_COLS; col++) {
          sprites.push(spriteSheet.get(col * sw, row * sh, sw, sh));
        }
      }

      // Define grass zones based on the neighborhood layout image.
      // The image layout (approximate fractions):
      //   Top-left yard:    x: 0.02-0.46, y: 0.02-0.38  (house occupies center-right area)
      //   Top-right yard:   x: 0.54-0.98, y: 0.02-0.38
      //   Middle-left yard: x: 0.02-0.46, y: 0.42-0.72
      //   Middle-right yard:x: 0.54-0.98, y: 0.42-0.72
      //   Bottom-left yard: x: 0.02-0.46, y: 0.78-0.96
      //   Bottom-right yard:x: 0.54-0.98, y: 0.78-0.96
      // We use pixel-sampling as primary method and these as fallback bounds.

      // Load background pixels for grass detection
      bgImg.loadPixels();

      // Initialize agents
      for (let i = 0; i < agentData.length; i++) {
        const ad = agentData[i];
        const sprite = sprites[i % sprites.length];
        let ax, ay;
        let attempts = 0;
        do {
          ax = p.random(AGENT_DISPLAY_SIZE, canvasW - AGENT_DISPLAY_SIZE);
          ay = p.random(AGENT_DISPLAY_SIZE, canvasH - AGENT_DISPLAY_SIZE);
          attempts++;
        } while (!isGrass(ax, ay) && attempts < 500);

        agents.push({
          x: ax,
          y: ay,
          targetX: ax,
          targetY: ay,
          speed: MOVE_SPEED + p.random(-0.2, 0.2),
          sprite: sprite,
          state: 'CHOOSING',
          pauseTimer: 0,
          hovering: false,
          response: ad.output_text || 'No response recorded.',
          name: (ad.persona && ad.persona.name) || ad.agent_name || ('Agent ' + (i + 1)),
        });
      }
    };

    function isGrass(px, py) {
      // Map canvas coords to image coords
      const imgX = Math.floor((px / canvasW) * bgImg.width);
      const imgY = Math.floor((py / canvasH) * bgImg.height);
      if (imgX < 0 || imgX >= bgImg.width || imgY < 0 || imgY >= bgImg.height) return false;
      const idx = (imgY * bgImg.width + imgX) * 4;
      const r = bgImg.pixels[idx];
      const g = bgImg.pixels[idx + 1];
      const b = bgImg.pixels[idx + 2];
      // Green grass: G channel dominant
      return g > r && g > b && g > 80;
    }

    function pickWanderTarget(agent) {
      let tx, ty;
      let attempts = 0;
      do {
        const angle = p.random(p.TWO_PI);
        const dist = p.random(40, WANDER_RADIUS);
        tx = agent.x + Math.cos(angle) * dist;
        ty = agent.y + Math.sin(angle) * dist;
        // Clamp to canvas
        tx = p.constrain(tx, AGENT_DISPLAY_SIZE, canvasW - AGENT_DISPLAY_SIZE);
        ty = p.constrain(ty, AGENT_DISPLAY_SIZE, canvasH - AGENT_DISPLAY_SIZE);
        attempts++;
      } while (!isGrass(tx, ty) && attempts < 100);
      // If no valid target found after 100 tries, stay put
      if (!isGrass(tx, ty)) {
        tx = agent.x;
        ty = agent.y;
      }
      return { x: tx, y: ty };
    }

    p.draw = function() {
      // Draw background
      p.image(bgImg, 0, 0, canvasW, canvasH);

      // Update and draw agents
      for (const agent of agents) {
        if (!agent.hovering) {
          updateAgent(agent);
        }
        drawAgent(agent);
      }

      // Draw hover tooltips on top (separate pass so they're above all agents)
      for (const agent of agents) {
        if (agent.hovering) {
          drawTooltip(agent);
        }
      }
    };

    function updateAgent(agent) {
      switch (agent.state) {
        case 'CHOOSING': {
          const target = pickWanderTarget(agent);
          agent.targetX = target.x;
          agent.targetY = target.y;
          agent.state = 'MOVING';
          break;
        }
        case 'MOVING': {
          const dx = agent.targetX - agent.x;
          const dy = agent.targetY - agent.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 2) {
            agent.x = agent.targetX;
            agent.y = agent.targetY;
            agent.pauseTimer = p.floor(p.random(120, 240)); // 2-4 seconds at 60fps
            agent.state = 'PAUSING';
          } else {
            agent.x += (dx / dist) * agent.speed;
            agent.y += (dy / dist) * agent.speed;
          }
          break;
        }
        case 'PAUSING': {
          agent.pauseTimer--;
          if (agent.pauseTimer <= 0) {
            agent.state = 'CHOOSING';
          }
          break;
        }
      }
    }

    function drawAgent(agent) {
      // Check hover
      const d = p.dist(p.mouseX, p.mouseY, agent.x, agent.y);
      const wasHovering = agent.hovering;
      agent.hovering = d < HIT_RADIUS;

      // If just stopped hovering, pick a new target
      if (wasHovering && !agent.hovering) {
        agent.state = 'CHOOSING';
      }

      // Draw sprite centered on position
      const s = AGENT_DISPLAY_SIZE;
      p.push();
      if (agent.hovering) {
        // Slight highlight effect
        p.tint(255, 255, 200);
      }
      p.image(agent.sprite, agent.x - s / 2, agent.y - s / 2, s, s);
      p.pop();

      // Draw name below agent
      p.push();
      p.fill(255);
      p.stroke(0);
      p.strokeWeight(2);
      p.textAlign(p.CENTER, p.TOP);
      p.textSize(10);
      p.text(agent.name.split(' ')[0], agent.x, agent.y + s / 2 + 2);
      p.pop();
    }

    function drawTooltip(agent) {
      const text = agent.response;
      const maxW = 220;
      const padding = 10;
      const lineH = 14;
      const bubbleX = agent.x;
      const s = AGENT_DISPLAY_SIZE;

      // Word wrap
      p.textSize(11);
      p.textFont('monospace');
      const words = text.split(' ');
      let lines = [];
      let currentLine = '';
      for (const word of words) {
        const testLine = currentLine ? currentLine + ' ' + word : word;
        if (p.textWidth(testLine) > maxW - padding * 2) {
          if (currentLine) lines.push(currentLine);
          currentLine = word;
        } else {
          currentLine = testLine;
        }
        // Cap at 6 lines
        if (lines.length >= 5) {
          currentLine = currentLine + '...';
          break;
        }
      }
      if (currentLine) lines.push(currentLine);

      const bubbleW = maxW;
      const bubbleH = lines.length * lineH + padding * 2;
      const bubbleY = agent.y - s / 2 - bubbleH - 12;

      // Clamp bubble position to canvas
      const bx = p.constrain(bubbleX - bubbleW / 2, 4, canvasW - bubbleW - 4);
      const by = Math.max(4, bubbleY);

      p.push();
      // Shadow
      p.noStroke();
      p.fill(0, 0, 0, 40);
      p.rect(bx + 3, by + 3, bubbleW, bubbleH, 6);

      // Bubble background
      p.fill(255, 255, 245);
      p.stroke(60);
      p.strokeWeight(2);
      p.rect(bx, by, bubbleW, bubbleH, 6);

      // Tail triangle
      const tailX = p.constrain(bubbleX, bx + 10, bx + bubbleW - 10);
      p.fill(255, 255, 245);
      p.stroke(60);
      p.strokeWeight(2);
      p.triangle(
        tailX - 6, by + bubbleH,
        tailX + 6, by + bubbleH,
        tailX, by + bubbleH + 8
      );
      // Cover the stroke inside the bubble for the tail
      p.noStroke();
      p.fill(255, 255, 245);
      p.rect(tailX - 5, by + bubbleH - 2, 10, 3);

      // Text
      p.fill(30);
      p.noStroke();
      p.textAlign(p.LEFT, p.TOP);
      p.textSize(11);
      for (let i = 0; i < lines.length; i++) {
        p.text(lines[i], bx + padding, by + padding + i * lineH);
      }
      p.pop();
    }
  };

  p5Instance = new p5(sketch, document.getElementById('p5-container'));
}
```

**Step 2: Verify it renders by running the dev server and navigating to `#/neighborhood/{simId}`**

You need a completed simulation ID. Start the server, run a simulation, then navigate to `#/neighborhood/{id}`.

**Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: implement p5.js neighborhood visualization with wandering agents"
```

---

### Task 3: Add "View Neighborhood" button to simulation results page

**Files:**
- Modify: `static/index.html` — the `renderResults` function (around line 1059)

**Step 1: Add a "View Neighborhood" link in the results view**

In the `renderResults` function, add a button before the report HTML. Change the function to:

```javascript
async function renderResults(sim) {
  // Neighborhood link
  let neighborhoodLink = `
    <div style="margin-bottom:20px;">
      <a href="#/neighborhood/${esc(sim.id)}" class="btn btn-primary">View Neighborhood</a>
    </div>`;

  let reportHtml = '';
  if (sim.summary) {
    reportHtml = `
      <div class="section-title">Synthesis Report</div>
      <div class="report-panel">
        <div class="report-content">${simpleMarkdown(sim.summary)}</div>
      </div>`;
  }

  let agentsHtml = '';
  try {
    const agents = await api('/simulations/' + sim.id + '/agents');
    const respondents = agents.filter(a =>
      a.agent_name !== 'distribution_generator' && a.agent_name !== 'synthesizer'
    );

    if (respondents.length > 0) {
      agentsHtml = `
        <div class="section-title">Respondents (${respondents.length})</div>
        <div class="agent-cards">
          ${respondents.map(agent => renderAgentCard(agent)).join('')}
        </div>`;
    }
  } catch {}

  return neighborhoodLink + reportHtml + agentsHtml;
}
```

**Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat: add View Neighborhood button to simulation results"
```

---

### Task 4: Manual integration test

**Step 1: Start the dev server**

```bash
python -m uvicorn app.main:app --reload
```

**Step 2: Run a simulation (e.g., policy_opinion) through the UI**

Navigate to `http://localhost:8000/static/index.html`, pick an experiment, configure, and run.

**Step 3: After completion, click "View Neighborhood"**

Verify:
- Background image loads and fills the canvas
- Agent sprites appear on green grass areas
- Agents slowly wander to random points and pause
- Hovering over an agent freezes it and shows a speech bubble with their `output_text`
- Moving mouse away resumes wandering
- Navigating back (`← Back to Simulation`) destroys the canvas cleanly

**Step 4: Commit any fixes discovered during testing**

```bash
git add static/index.html
git commit -m "fix: address issues found during neighborhood integration test"
```
