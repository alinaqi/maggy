# Maggy Sidebar Navigation Design

## Philosophy

**Zero ambiguity about scope.** Every item in the sidebar must immediately communicate whether it belongs to the currently selected project or is a global system feature. We achieve this through:

1. **Section grouping** — project items live under a "Project" section
2. **Visual hierarchy** — the project switcher acts as a "context header"
3. **Disabled states** — project items are visibly disabled when no project is selected
4. **Conditional visibility** — optional features appear/disappear based on project settings

---

## Final Navigation Tree

| Section | Item | Icon | Scope | Condition |
|---------|------|------|-------|-----------|
| **Quick Actions** | Search (⌘K) | `fa-search` | Global | always |
| | New Session | `fa-plus` | Global | always — creates chat for *current* project |
| **Project** | Project Switcher | `fa-folder` | — | always — the context setter |
| | Chat | `fa-terminal` | Project | disabled if no project |
| | Inbox | `fa-list-check` | Project | disabled if no project |
| | Issues | `fa-ticket` | Project | disabled if no project — label shows tracker type |
| | Watching | `fa-eye` | Project | disabled if no project |
| | Progress | `fa-bars-progress` | Project | disabled if no project |
| | iCPG | `fa-project-diagram` | Project | disabled if no project |
| | — | — | — | — |
| | Project Settings | `fa-sliders` | Project | disabled if no project |
| **Plugins** | Competitors | `fa-chess` | Project | hidden if feature disabled in project settings |
| | Build in Public | `fa-bullhorn` | Project | hidden if plugin not enabled |
| **Command Center** | Insights | `fa-chart-line` | Global | always |
| | Memory | `fa-brain` | Global | always |
| | Models | `fa-route` | Global | always |
| | Budget | `fa-wallet` | Global | always |
| **System** | Forge | `fa-hammer` | Global | always |
| | Settings | `fa-gear` | Global | always |

**Sidebar width:** 200px (labeled, not icon-only).  
**Theme:** Dark glassmorphism — `rgba(6,9,18,0.95)` background with `backdrop-filter: blur(20px)`.

---

## Section Rationale

### Quick Actions
Always-available verbs. Search and New Session are actions, not destinations. Separating them at the top prevents them from getting lost in longer lists.

### Project
Everything that requires a project context. The Project Switcher is the FIRST item in this section, establishing a visual "container" — everything below it is implicitly scoped to the selected project. When no project is selected, all items get `.disabled` (opacity 0.3, pointer-events none).

### Plugins
Optional project-scoped features that can be toggled on/off. These are visually separated from core project features because:
- They may not exist for every project
- They communicate "this project has extras enabled"
- Hiding them entirely (rather than disabling) when off keeps the sidebar clean

### Command Center
Global intelligence features that work across all projects. Named "Command Center" instead of "Intel" to emphasize these are operational tools, not passive reports.

### System
Infrastructure and configuration. Forge (MCP tools) sits here because it is a system-level capability registry, not a project workspace.

---

## Settings Architecture

### Two Settings Pages

| | Project Settings | System Settings |
|---|---|---|
| **Location** | Bottom of Project section | System section |
| **Icon** | `fa-sliders` | `fa-gear` |
| **Scope** | Per-project | Global |
| **Key configs** | Issue tracker type, auto-index toggle, competitor toggle, plugin enablement | API keys, org name/domain, mesh nodes, heartbeat interval, default feature toggles |

### Project Settings Page
```
┌─────────────────────────────┐
│ Project Settings · my-app   │
├─────────────────────────────┤
│ Issue Tracker               │
│ [Native ▼]                  │
│                             │
│ Auto-index on change   [●]  │
│                             │
│ Features                    │
│ ☑ Competitor tracking       │
│ ☐ Build in Public           │
└─────────────────────────────┘
```

- **Issue Tracker** dropdown: Native (built-in) / GitHub Issues / Asana / Linear
- **Auto-index**: Toggle iCPG re-indexing on file changes
- **Features**: Checkboxes for optional plugins. Changing these immediately shows/hides the corresponding sidebar items.

### System Settings Page
```
┌─────────────────────────────┐
│ System Settings             │
├─────────────────────────────┤
│ Organization                │
│ Name: [________]            │
│ Domain: [________]          │
│                             │
│ API Keys                    │
│ Anthropic: [••••••]    ✓   │
│ GitHub: [••••••]       ✓   │
│                             │
│ Mesh                        │
│ Nodes: [________]           │
│                             │
│ Heartbeat                   │
│ Interval: [30s ▼]           │
│                             │
│ Defaults                    │
│ ☑ Enable competitors on     │
│   new projects              │
└─────────────────────────────┘
```

---

## Handling Optional/Toggleable Features

### Rule 1: Hide, don't disable
If a feature is turned off in project settings, its sidebar item is **removed from the DOM** (or `display: none`), not just disabled. This keeps the sidebar minimal. Users shouldn't see what they can't use.

### Rule 2: Instant feedback
Toggling a feature in Project Settings immediately updates the sidebar — no page reload required.

### Rule 3: State persistence
Feature toggle state is stored in the project's config (via `PATCH /api/projects/{name}/config`). On project switch, the sidebar re-evaluates which plugin items to show.

### Implementation

Each optional sidebar item gets a data attribute:
```html
<a data-tab="competitors" data-feature="competitors" class="sidebar-link plugin-item">...</a>
```

On project selection:
```javascript
function updateFeatureVisibility(projectName, projectConfig) {
  const enabled = projectConfig.enabled_plugins || [];
  document.querySelectorAll('.sidebar-link[data-feature]').forEach(el => {
    const feature = el.dataset.feature;
    const show = enabled.includes(feature);
    el.style.display = show ? '' : 'none';
    if (show) el.classList.add('project-scoped');
  });
}
```

### Default Toggles
- **Competitors**: OFF by default for new projects (discoverable via global Settings default toggle)
- **Build in Public**: OFF by default (requires plugin installation)

---

## Project Scoping Rules

### CSS
```css
.sidebar-link.project-scoped.disabled {
  opacity: 0.3;
  pointer-events: none;
}
```

### JavaScript
```javascript
function updateProjectScope(name) {
  const hasProject = name && name !== 'Select project...';
  // Disable/enable all project-scoped links
  document.querySelectorAll('.sidebar-link.project-scoped').forEach(el => {
    el.classList.toggle('disabled', !hasProject);
  });
  // Update header
  document.getElementById('header-project-name').textContent = hasProject ? name : 'No project';
}
```

### New Session Behavior
```javascript
function newChatSession() {
  const currentProject = getCurrentProject();
  if (!currentProject) {
    // No project selected — prompt user to pick one first
    openProjectSearch();
    return;
  }
  // Create session for current project directly
  createSessionForProject(currentProject);
}
```

If the user has a project selected, **New Session is instant** — no prompts, no modals. It creates a chat session for the current project and switches to the Chat tab.

---

## Visual Design Notes

### Color Coding
- **Accent (orange)**: Active tab, project switcher hover, badges
- **Green dot**: Live heartbeat indicator
- **Gray/muted**: Disabled project-scoped items
- **Section labels**: `9px uppercase` with `letter-spacing: 0.08em`, color `#5e6570`

### Icons (FontAwesome 6)
All icons use the `fas` prefix. The icon in each link is `13px` with `opacity: 0.6` (1.0 on hover/active). Active links get the orange accent color and a left border indicator.

### Project Switcher
```
┌─────────────────────────┐
│ 📁 my-awesome-app    ▼  │
└─────────────────────────┘
```
- Background: `rgba(255,255,255,0.03)`
- Border: `1px solid rgba(255,255,255,0.06)`
- Hover: orange-tinted background
- Truncates long names with ellipsis

### Empty State
When no project is selected:
```
┌─────────────────────────┐
│ 📁 Select project...   ▼ │
└─────────────────────────┘
```
All project-scoped items below are at 30% opacity.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + K` | Open Search / Project Switcher |
| `Cmd/Ctrl + Shift + N` | New Session (for current project) |
| `Esc` | Close modals / drawer |

---

## Responsive Behavior

At 200px fixed width, the sidebar is always visible on desktop. On mobile (< 768px), the sidebar collapses to a bottom nav or hamburger menu — out of scope for this design but the section order provides a natural tab-bar grouping:
- Tab 1: Quick Actions (search)
- Tab 2: Project (chat, inbox)
- Tab 3: Command Center (insights, memory)
- Tab 4: System (settings)
