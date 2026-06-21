// Maggy dashboard — vanilla JS, no build step.
// Talks to /api/* routes. Single-user local install; no auth by default.

const API = '/api';
let CURRENT_TAB = 'chat';

// ── Theme ──────────────────────────────────────────────────────────────
function getTheme() {
  return localStorage.getItem('maggy-theme') || 'light';
}
function applyTheme(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.classList.toggle('light', theme === 'light');
  const icon = document.querySelector('#btn-theme i');
  if (icon) icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
}
function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  localStorage.setItem('maggy-theme', next);
  applyTheme(next);
}
applyTheme(getTheme());

// ── URL-driven tab state ───────────────────────────────────────────────
function tabFromHash() {
  const h = location.hash.replace('#', '');
  return h || null;
}
window.addEventListener('hashchange', function() {
  const tab = tabFromHash();
  if (tab && tab !== CURRENT_TAB) switchTab(tab, true);
});

// ── Fetch helper ────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const apiKey = localStorage.getItem('maggy-api-key') || '';
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (apiKey) headers['X-API-Key'] = apiKey;
  const resp = await fetch(`${API}${path}`, { ...opts, headers });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`${resp.status}: ${text || resp.statusText}`);
  }
  return resp.json();
}

// ── HTML escape ─────────────────────────────────────────────────────────
function esc(s) {
  if (s === null || s === undefined) return '';
  if (typeof s !== 'string') s = String(s);
  return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Only allow http(s) / mailto URLs when rendering external `href`.
// Blocks javascript:, data:, vbscript: and other script-capable schemes that
// would slip past `esc()` (since it only encodes angle brackets and quotes).
function safeHref(url) {
  if (!url || typeof url !== 'string') return '';
  const trimmed = url.trim();
  if (!/^(https?:|mailto:)/i.test(trimmed)) return '';
  return esc(trimmed);
}

// ── Markdown renderer (uses marked.js CDN, falls back to pre) ─────────
function _mergeBashDetails(blocks) {
  let inner = '';
  for (const block of blocks) {
    const m = block.match(/<summary\b[^>]*>[\s\S]*?<\/summary>([\s\S]*?)<\/details>/i);
    if (m) inner += m[1];
  }
  return '<details class="bash-group"><summary class="bash-group-summary">Bash (' + blocks.length + ')</summary>' + inner + '</details>';
}

function groupBashBlocks(html) {
  const re = /<details\b[^>]*>([\s\S]*?)<\/details>/gi;
  const matches = Array.from(html.matchAll(re));
  if (!matches.length) return html;
  const bashRe = /<summary\b[^>]*>\s*Bash\s*<\/summary>/i;
  const bashMatches = matches.filter(m => bashRe.test(m[1]));
  if (bashMatches.length <= 1) return html;
  // Collapse every Bash <details> in the message into a single grouped card
  // placed at the position of the first Bash block. Non-Bash content keeps
  // its original location.
  const merged = _mergeBashDetails(bashMatches.map(m => m[0]));
  let out = '';
  let idx = 0;
  let placed = false;
  for (const m of bashMatches) {
    out += html.slice(idx, m.index);
    if (!placed) { out += merged; placed = true; }
    idx = m.index + m[0].length;
  }
  out += html.slice(idx);
  return out;
}

function renderMd(raw) {
  if (!raw) return '';
  if (typeof marked !== 'undefined') {
    return '<div class="chat-md text-xs text-gray-300">' + groupBashBlocks(marked.parse(raw)) + '</div>';
  }
  return '<pre class="text-xs text-gray-300 whitespace-pre-wrap">' + esc(raw) + '</pre>';
}

// Escape a value for use inside a JS string literal that is itself embedded in
// an HTML attribute. esc() is NOT enough here — it leaves single quotes and
// backslashes intact, so a task id containing `'); alert(1);//` would break
// out of onclick="executeTask('${id}', ...)". We need to:
//   1. escape the backslash first (so later escapes don't double-encode)
//   2. escape the single quote that wraps the JS string
//   3. escape angle brackets in case the attribute is interpreted as HTML
//   4. escape newlines and carriage returns that would break the statement
function jsStr(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/</g, '\\u003C')
    .replace(/>/g, '\\u003E')
    .replace(/\r?\n/g, '\\n');
}

function relDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 2592000) return `${Math.floor(diff/86400)}d ago`;
  return d.toLocaleDateString();
}

// ── Project helper ─────────────────────────────────────────────────────
function getProjectKey() {
  const el = document.getElementById('current-project-label');
  const v = el ? el.textContent.trim() : '';
  return (v && v !== 'Select project...') ? v : '';
}

// ── Tabs ────────────────────────────────────────────────────────────────
function switchTab(tab, fromHash) {
  // Backward-compat hash redirects
  var redirects = { 'followed': 'team', 'icpg': 'cortex', 'progress': 'insights', 'process': 'insights', 'competitors': 'cortex', 'build-in-public': 'plugins' };
  if (redirects[tab]) tab = redirects[tab];
  CURRENT_TAB = tab;
  if (!fromHash) location.hash = tab;
  // Highlight active sidebar link
  for (const b of document.querySelectorAll('.sidebar-link')) {
    b.classList.toggle('active', b.dataset.tab === tab);
  }
  // Show/hide panes (all elements with id starting pane-)
  var panes = document.querySelectorAll('[id^="pane-"]');
  for (var i = 0; i < panes.length; i++) {
    panes[i].classList.toggle('hidden', panes[i].id !== 'pane-' + tab);
  }
  if (tab === 'chat') loadChat();
  else if (tab === 'inbox') loadInbox();
  else if (tab === 'issues') loadIssues();
  else if (tab === 'team') loadTeam();
  else if (tab === 'cortex') loadCortex();
  else if (tab === 'plugins') loadPlugins();
  else if (tab === 'insights') loadInsights();
  else if (tab === 'memory') loadMemory();
  else if (tab === 'routing') loadRouting();
  else if (tab === 'budget') loadBudget();
  else if (tab === 'forge') loadForge();
  else if (tab === 'pr-review') loadPrReview();
  else if (tab === 'logs') loadLogs();
  else if (tab === 'skills') loadSkills();
  else if (tab === 'settings') loadSettings();
  else if (tab === 'project-settings') loadProjectSettings();
}

// Project switching
function switchProject(name) {
  if (!name) return;
  updateCurrentProject(name);
  history.replaceState(null, '', '/' + encodeURIComponent(name));
  // Reset chat and cortex to pick up new project's session
  CHAT_SESSION_ID = null;
  ICPG_PROJECT = null;
  // Preload chat sessions for this project
  fetch('/api/chat/preload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_key: name })
  }).then(function() { loadChat(name); _showRefreshBubble(); }).catch(function() {});
  // Load project bootstrap status (CLIs, git, cortex)
  loadProjectStatus(name);
  // Refresh heartbeat for project context
  fetch('/api/heartbeat/trigger/collect_signals', { method: 'POST' }).catch(function(){});
}

function _showRefreshBubble() {
  _loadQuickActions();
}

function dismissRefreshBubble() {
  var el = document.getElementById('refresh-suggest');
  if (el) el.classList.add('hidden');
}

function runQuickAction(cmd) {
  var input = document.getElementById('chat-input');
  if (input) { input.value = cmd; sendChatMessage(); }
}

async function _loadQuickActions() {
  var s = (CHAT_SESSIONS_CACHE || []).find(function(x) { return x.id === CHAT_SESSION_ID; });
  var projPath = (s && (s.repo_dir || s.working_dir)) || '';
  var url = '/quick-actions';
  if (projPath) url += '?project_path=' + encodeURIComponent(projPath);
  var data = await api(url).catch(function() { return { actions: [] }; });
  var actions = data.actions || [];
  var el = document.getElementById('refresh-suggest');
  if (!el || !actions.length) return;
  var btns = '';
  for (var i = 0; i < actions.length; i++) {
    var a = actions[i];
    btns += '<button onclick="runQuickAction(\'' + a.cmd.replace(/'/g, "\\'") + '\')" class="px-2 py-0.5 rounded text-[10px] shrink-0" style="background:var(--surface);color:var(--text);border:1px solid var(--border)" title="' + esc(a.hint || '') + '"><i class="fas ' + esc(a.icon) + ' mr-1"></i>' + esc(a.label) + '</button>';
  }
  var inner = el.querySelector('.quick-actions-inner');
  if (inner) {
    inner.innerHTML = '<i class="fas fa-bolt text-orange-400 text-[10px]"></i>'
      + '<span style="color:var(--text-muted)" class="mr-1 shrink-0">Quick actions</span>'
      + btns
      + '<button onclick="dismissRefreshBubble()" class="ml-auto text-gray-600 hover:text-gray-400 text-[10px] shrink-0" title="Dismiss"><i class="fas fa-xmark"></i></button>';
  }
  el.classList.remove('hidden');
}

function updateProjectList(projects) {
  window._projectList = (projects || []).map(function(p) { return p.name || p; });
  if (window._projectList.length) updateCurrentProject(window._projectList[0]);
}

// ── Drawer ──────────────────────────────────────────────────────────────
function openDrawer(title, html) {
  document.getElementById('drawer-title').textContent = title;
  document.getElementById('drawer-body').innerHTML = html;
  document.getElementById('drawer').classList.remove('translate-x-full');
}
function closeDrawer() {
  document.getElementById('drawer').classList.add('translate-x-full');
}

// ── Inbox ───────────────────────────────────────────────────────────────
async function loadInbox(refresh = false) {
  const pane = document.getElementById('pane-inbox');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading…</div>`;
  const proj = getProjectKey();
  const activityUrl = proj ? '/activity?project=' + encodeURIComponent(proj) : '/activity';
  const [activity, inbox] = await Promise.all([
    api(activityUrl).catch(() => ({ sessions: [], recent: [] })),
    api(`/inbox${refresh ? '?refresh=true' : ''}`).catch(() => ({ items: [] })),
  ]);
  const sessions = activity.sessions || [];
  const recent = activity.recent || [];
  const items = inbox.items || [];
  let html = '';
  if (sessions.length) {
    html += `<div class="mb-4"><h2 class="text-sm font-bold text-white mb-2"><i class="fas fa-terminal mr-1 text-green-400"></i>Active Sessions (${sessions.length})</h2><div class="space-y-2">`;
    for (const s of sessions) {
      const badge = s.status === 'agent'
        ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-purple-900 text-purple-300">agent</span>'
        : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-green-900 text-green-300">running</span>';
      const label = s.status === 'agent' ? `${esc(s.agent_name)} @ ${esc(s.team_name)}` : esc(s.project || 'unknown');
      html += `<div class="card p-3"><div class="flex items-center gap-2">
        <span class="text-[10px] font-mono text-blue-400 uppercase">${esc(s.cli)}</span>
        ${badge}
        <span class="text-sm text-white">${label}</span>
        <span class="text-[10px] text-gray-500 ml-auto">PID ${s.pid}</span>
      </div>
      ${s.last_prompt ? `<div class="text-[11px] text-gray-400 mt-1 truncate">"${esc(s.last_prompt)}"</div>` : ''}
      </div>`;
    }
    html += `</div></div>`;
  }
  if (recent.length) {
    html += `<div class="mb-4"><h2 class="text-sm font-bold text-white mb-2"><i class="fas fa-clock-rotate-left mr-1 text-yellow-400"></i>Recent Activity</h2><div class="space-y-1">`;
    for (const r of recent.slice(0, 10)) {
      html += `<div class="card p-2 flex items-center gap-2">
        <span class="text-[10px] font-mono text-blue-400 uppercase w-10">${esc(r.cli)}</span>
        <span class="text-[11px] text-gray-300 flex-1 truncate">${esc(r.text)}</span>
        <span class="text-[10px] text-gray-500 shrink-0">${r.project ? esc(r.project) + ' · ' : ''}${esc(relDate(r.timestamp))}</span>
      </div>`;
    }
    html += `</div></div>`;
  }
  if (items.length) {
    html += `<div class="mb-4"><div class="flex items-center gap-3 mb-2">
      <h2 class="text-sm font-bold text-white"><i class="fas fa-inbox mr-1 text-orange-400"></i>Issues (${items.length})</h2>
      <button onclick="loadInbox(true)" class="text-[10px] text-gray-400 hover:text-white"><i class="fas fa-rotate mr-1"></i>Re-rank</button>
    </div><div class="space-y-2">`;
    for (const i of items) {
      const labels = (i.labels || []).slice(0, 4).map(l => `<span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">${esc(l)}</span>`).join(' ');
      html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${jsStr(i.id)}')">
        <div class="flex items-start gap-3">
          <div class="text-xs font-mono text-orange-400 mt-0.5">#${i.rank}</div>
          <div class="flex-1 min-w-0">
            <div class="text-sm text-white">${esc(i.title)}</div>
            <div class="text-[11px] text-gray-500 mt-0.5">
              <span class="text-blue-400">${esc(i.board || '')}</span>
              ${i.assignee ? `· ${esc(i.assignee)}` : ''}
              · ${esc(relDate(i.updated_at))}
              ${labels ? '· ' + labels : ''}
            </div>
            ${i.ai_reason ? `<div class="text-[11px] text-gray-400 mt-1 italic">"${esc(i.ai_reason)}"</div>` : ''}
          </div>
          <div class="flex gap-1 shrink-0" onclick="event.stopPropagation()">
            <button onclick="executeTask('${jsStr(i.id)}', 'plan')" class="text-[10px] px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300">Plan</button>
            <button onclick="executeTask('${jsStr(i.id)}', 'tdd')" class="text-[10px] px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white">Execute</button>
          </div>
        </div>
      </div>`;
    }
    html += `</div></div>`;
  }
  const [pendingApprovals, approvalHistory] = await Promise.all([
    api('/approval/pending').catch(() => ({ items: [] })),
    api('/approval/history?limit=20').catch(() => ({ items: [] })),
  ]);
  const pending = pendingApprovals.items || [];
  const resolved = approvalHistory.items || [];
  if (pending.length) {
    html += `<div class="mb-4"><div class="flex items-center gap-3 mb-2">
      <h2 class="text-sm font-bold text-white"><i class="fas fa-shield-halved mr-1 text-yellow-400"></i>Pending Approvals (${pending.length})</h2>
    </div><div class="space-y-2">`;
    for (const a of pending) {
      html += `<div class="card p-3 border border-yellow-900/50">
        <div class="flex items-start gap-3">
          <div class="text-xs font-mono text-yellow-400 mt-0.5">${esc(a.action)}</div>
          <div class="flex-1 min-w-0">
            <div class="text-sm text-white">${esc(a.context || '').substring(0, 120)}</div>
            <div class="text-[10px] text-gray-500 mt-1">${esc(relDate(a.created_at))}</div>
          </div>
          <div class="flex gap-1 shrink-0">
            <button onclick="approvalAction('${jsStr(a.id)}','approve')" class="text-[10px] px-2 py-1 rounded bg-green-700 hover:bg-green-600 text-white">Approve</button>
            <button onclick="approvalAction('${jsStr(a.id)}','reject')" class="text-[10px] px-2 py-1 rounded bg-red-700 hover:bg-red-600 text-white">Reject</button>
          </div>
        </div>
      </div>`;
    }
    html += `</div></div>`;
  }
  if (resolved.length) {
    html += `<div class="mb-4"><div class="flex items-center gap-3 mb-2">
      <h2 class="text-sm font-bold text-white"><i class="fas fa-clock-rotate-left mr-1 text-gray-400"></i>Approval History</h2>
    </div><div class="space-y-1">`;
    for (const a of resolved) {
      const badge = a.status === 'approved'
        ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-green-900 text-green-300">approved</span>'
        : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-red-900 text-red-300">rejected</span>';
      html += `<div class="card p-2 flex items-center gap-2">
        <span class="text-[10px] font-mono text-gray-400 w-16">${esc(a.action)}</span>
        ${badge}
        <span class="text-[11px] text-gray-300 flex-1 truncate">${esc(a.context || '').substring(0, 80)}</span>
        <span class="text-[10px] text-gray-500 shrink-0">${a.resolved_by ? esc(a.resolved_by) + ' · ' : ''}${esc(relDate(a.resolved_at || a.created_at))}</span>
      </div>`;
    }
    html += `</div></div>`;
  }
  if (!sessions.length && !recent.length && !items.length && !pending.length && !resolved.length) {
    html = `<div class="card p-4 text-sm text-gray-400">
      <div class="mb-2"><i class="fas fa-inbox mr-1 text-orange-400"></i>Inbox is empty</div>
      <div class="text-[11px] text-gray-500 space-y-1">
        <div>• Connect an issue tracker (Asana, GitHub, Linear) in Settings to see assigned tasks</div>
        <div>• AI tool executions and approval requests will appear here</div>
        <div>• Active CLI sessions show when Claude, Codex, or Kimi are running</div>
      </div>
    </div>`;
  }
  pane.innerHTML = html;
}

async function approvalAction(id, action) {
  try {
    await api(`/approval/${id}/${action}`, { method: 'POST' });
    loadInbox();
  } catch (e) {
    console.error('Approval action failed:', e);
  }
}

// ── Issues (raw tracker view) ───────────────────────────────────────────
async function loadIssues() {
  const pane = document.getElementById('pane-issues');
  const project = document.getElementById('current-project-label')?.textContent;
  if (!project || project === 'Select project...') {
    pane.innerHTML = `<div class="flex items-center justify-center h-full text-gray-600 text-xs">Select a project to view issues.</div>`;
    return;
  }
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading issues…</div>`;
  try {
    const data = await api('/projects/' + encodeURIComponent(project) + '/tasks');
    const tasks = data.tasks || [];
    const tracker = data.tracker || 'native';
    let html = `<div class="flex items-center gap-2 mb-3">
      <h2 class="text-sm font-bold text-white"><i class="fas fa-ticket text-orange-400 mr-2"></i>Issues</h2>
      <span class="badge model-badge">${esc(tracker)}</span>
      <span class="text-[10px] text-gray-500 ml-auto">${tasks.length} open</span>
    </div>`;
    if (!tasks.length) {
      html += `<div class="card p-4 text-sm text-gray-400">No open issues in ${esc(project)}.</div>`;
    } else {
      html += `<div class="space-y-2">`;
      for (const t of tasks) {
        const labels = (t.labels || []).slice(0, 4).map(l => `<span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">${esc(l)}</span>`).join(' ');
        html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${jsStr(t.id)}')">
          <div class="flex items-start gap-3">
            <div class="flex-1 min-w-0">
              <div class="text-sm text-white">${esc(t.title)}</div>
              <div class="text-[11px] text-gray-500 mt-0.5">
                <span class="text-blue-400">${esc(t.board || '')}</span>
                ${t.assignee ? `· ${esc(t.assignee)}` : ''}
                · ${esc(relDate(t.updated_at))}
                ${labels ? '· ' + labels : ''}
              </div>
            </div>
            <div class="flex gap-1 shrink-0" onclick="event.stopPropagation()">
              <button onclick="executeTask('${jsStr(t.id)}', 'plan')" class="text-[10px] px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300">Plan</button>
              <button onclick="executeTask('${jsStr(t.id)}', 'tdd')" class="text-[10px] px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white">Execute</button>
            </div>
          </div>
        </div>`;
      }
      html += `</div>`;
    }
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Build in Public (plugin) ────────────────────────────────────────────
async function loadPlugins() {
  const pane = document.getElementById('pane-plugins');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading plugins…</div>`;
  try {
    const data = await api('/plugins').catch(() => ({ plugins: [] }));
    const plugins = data.plugins || [];
    let html = `<div class="p-4 space-y-4 h-full overflow-y-auto scroll-thin">`;
    html += `<div class="flex items-center gap-2 mb-2">
      <i class="fas fa-puzzle-piece text-orange-500"></i>
      <h2 class="text-sm font-bold" style="color:var(--text)">Plugins</h2>
      <span class="badge model-badge ml-1">${plugins.length}</span>
      <span class="flex-1"></span>
      <button onclick="api('/plugins/reload',{method:'POST'}).then(()=>loadPlugins())" class="btn btn-ghost text-[10px]"><i class="fas fa-sync-alt mr-1"></i>Reload</button>
    </div>`;
    if (!plugins.length) {
      html += `<div class="card p-6 text-center">
        <i class="fas fa-puzzle-piece text-3xl text-gray-700 mb-3"></i>
        <div class="text-sm" style="color:var(--text)">No Plugins Loaded</div>
        <div class="text-xs text-gray-500 mt-1">Drop a folder with <code class="text-orange-400">plugin.yaml</code> + <code class="text-orange-400">plugin.py</code> into <code>plugins/</code>.</div>
      </div>`;
    } else {
      html += `<div class="space-y-2">`;
      for (const p of plugins) {
        const active = p.status === 'active' || p.enabled !== false;
        html += `<div class="card p-3 flex items-center gap-3">
          <div class="w-2 h-2 rounded-full flex-shrink-0" style="background:${active ? 'var(--green)' : 'var(--text-muted)'}"></div>
          <div class="flex-1 min-w-0">
            <div class="text-xs font-medium" style="color:var(--text)">${esc(p.name || p.id)}</div>
            <div class="text-[10px] text-gray-500">${esc(p.description || '')} ${p.version ? '· v' + esc(p.version) : ''}</div>
          </div>
          <span class="text-[9px] px-2 py-0.5 rounded-full" style="background:var(--pill-bg);color:var(--text-muted)">${esc(p.id)}</span>
        </div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Followed ────────────────────────────────────────────────────────────
async function loadTeam() {
  const pane = document.getElementById('pane-team');
  const proj = getProjectKey();
  if (!proj) {
    pane.innerHTML = `<div class="flex items-center justify-center h-full text-gray-600 text-xs">Select a project to view team activity.</div>`;
    return;
  }
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading team…</div>`;
  try {
    const data = await api('/projects/' + encodeURIComponent(proj) + '/tasks').catch(() => ({ tasks: [] }));
    const items = data.tasks || [];
    let html = `<div class="p-4 space-y-4 h-full overflow-y-auto scroll-thin">`;
    html += `<div class="flex items-center gap-2 mb-2">
      <i class="fas fa-users text-orange-500"></i>
      <h2 class="text-sm font-bold" style="color:var(--text)">Team</h2>
      <span class="badge model-badge ml-1">${items.length}</span>
    </div>`;
    if (!items.length) {
      html += `<div class="card p-6 text-center">
        <i class="fas fa-users text-3xl text-gray-700 mb-3"></i>
        <div class="text-sm" style="color:var(--text)">No Team Activity</div>
        <div class="text-xs text-gray-500 mt-1">Configure a project tracker in Project Settings to see team items.</div>
      </div>`;
    } else {
      html += `<div class="space-y-2">`;
      for (const i of items) {
        html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${jsStr(i.id)}')">
          <div class="text-sm" style="color:var(--text)">${esc(i.title)}</div>
          <div class="text-[11px] text-gray-500 mt-0.5">
            <span class="text-blue-400">${esc(i.board || '')}</span>
            ${i.assignee ? `· ${esc(i.assignee)}` : ''}
            · ${esc(relDate(i.updated_at))}
          </div>
        </div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Task detail drawer ──────────────────────────────────────────────────
async function openTaskDetail(taskId) {
  openDrawer('Loading…', '<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading task…</div>');
  try {
    const data = await api(`/task/${encodeURIComponent(taskId)}`);
    const t = data.task;
    const comments = data.comments || [];
    document.getElementById('drawer-title').textContent = t.title;
    let html = `<div class="space-y-3">
      <div class="card p-3">
        <div class="text-[10px] text-gray-500 uppercase mb-1">Details</div>
        <div class="flex flex-wrap gap-2 text-[11px] text-gray-400">
          <span class="text-blue-400">${esc(t.board)}</span>
          <span>${esc(t.status)}</span>
          ${t.assignee ? `<span>@${esc(t.assignee)}</span>` : ''}
          <span>${esc(relDate(t.updated_at))}</span>
          ${safeHref(t.url) ? `<a href="${safeHref(t.url)}" target="_blank" rel="noopener noreferrer" class="text-orange-400">Open ↗</a>` : ''}
        </div>
      </div>`;
    if (t.description) {
      html += `<div class="card p-3"><div class="text-[10px] text-gray-500 uppercase mb-1">Description</div><pre class="text-xs text-gray-300 max-h-48 overflow-y-auto">${esc(t.description)}</pre></div>`;
    }
    html += `<div class="flex gap-2">
      <button onclick="executeTask('${jsStr(t.id)}', 'plan')" class="flex-1 text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white"><i class="fas fa-list-check mr-1"></i>Plan</button>
      <button onclick="executeTask('${jsStr(t.id)}', 'tdd')" class="flex-1 text-xs px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-play mr-1"></i>Execute (TDD)</button>
    </div>`;
    if (comments.length) {
      html += `<div class="card p-3"><div class="text-[10px] text-gray-500 uppercase mb-2">Comments (${comments.length})</div><div class="space-y-2 max-h-64 overflow-y-auto">`;
      for (const c of comments) {
        html += `<div class="bg-gray-900 rounded p-2">
          <div class="flex justify-between text-[10px] text-gray-500 mb-1"><span>${esc(c.author)}</span><span>${esc(relDate(c.created_at))}</span></div>
          <div class="text-xs text-gray-300 whitespace-pre-wrap">${esc(c.text)}</div>
        </div>`;
      }
      html += `</div></div>`;
    }
    html += `<div class="card p-3">
      <div class="text-[10px] text-gray-500 uppercase mb-1">Reply</div>
      <textarea id="reply-box" rows="3" class="w-full text-xs rounded px-2 py-1.5" style="background:var(--surface);color:var(--text);border:1px solid var(--border)"></textarea>
      <button onclick="postReply('${jsStr(t.id)}')" class="mt-2 text-xs px-3 py-1 rounded bg-blue-600 text-white">Post</button>
    </div>`;
    html += `</div>`;
    document.getElementById('drawer-body').innerHTML = html;
  } catch (e) {
    document.getElementById('drawer-body').innerHTML = `<div class="text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

async function postReply(taskId) {
  const text = document.getElementById('reply-box').value.trim();
  if (!text) return;
  try {
    await api(`/task/${encodeURIComponent(taskId)}/comment`, { method: 'POST', body: JSON.stringify({ text }) });
    openTaskDetail(taskId);  // refresh
  } catch (e) {
    alert('Failed to post: ' + e.message);
  }
}

async function executeTask(taskId, mode) {
  try {
    const data = await api('/execute', { method: 'POST', body: JSON.stringify({ task_id: taskId, mode }) });
    alert(`Started session ${data.session_id} (${mode}). Open the Sessions tab to follow progress.`);
    switchTab('sessions');
  } catch (e) {
    alert('Execute failed: ' + e.message);
  }
}

// ── Competitors ─────────────────────────────────────────────────────────
let COMP_VIEW = 'news';  // 'news' | 'list'

async function loadCompetitors() {
  const pane = document.getElementById('pane-cortex');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading competitors…</div>`;
  try {
    const [comps, news] = await Promise.all([
      api('/competitors'),
      api('/competitors/news?limit=100').catch(() => []),
    ]);
    let html = `<div class="flex items-center gap-2 mb-3">
      <button onclick="COMP_VIEW='news'; loadCompetitors()" class="text-[10px] px-3 py-1.5 rounded-full ${COMP_VIEW==='news' ? 'bg-orange-600 text-white' : 'bg-gray-800 text-gray-300'}"><i class="fas fa-newspaper mr-1"></i>News (${news.length})</button>
      <button onclick="COMP_VIEW='list'; loadCompetitors()" class="text-[10px] px-3 py-1.5 rounded-full ${COMP_VIEW==='list' ? 'bg-orange-600 text-white' : 'bg-gray-800 text-gray-300'}"><i class="fas fa-list mr-1"></i>Competitors (${comps.length})</button>
      <div class="flex-1"></div>
      ${COMP_VIEW==='news' ? '<button onclick="scanCompetitors()" class="text-[10px] px-3 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600"><i class="fas fa-rotate mr-1"></i>Scan</button>' : '<button onclick="discoverCompetitors()" class="text-[10px] px-3 py-1 rounded bg-purple-600 text-white hover:bg-purple-700"><i class="fas fa-magnifying-glass-plus mr-1"></i>Discover More</button>'}
    </div>`;

    if (COMP_VIEW === 'news') {
      html += `<div id="briefing" class="card p-4 mb-3 border-purple-700/50"><div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading daily briefing…</div></div>`;
      pane.innerHTML = html + renderNewsFeed(news);
      loadBriefing();
    } else {
      if (!comps.length) {
        html += `<div class="card p-4 text-sm text-gray-400">No competitors yet. Click <b>Discover More</b> to have Maggy find competitors in your domain.</div>`;
      } else {
        html += `<div class="grid grid-cols-1 md:grid-cols-2 gap-3">`;
        for (const c of comps) {
          html += `<div class="card p-3">
            <div class="text-sm font-bold text-white">${esc(c.name)}</div>
            <div class="text-[10px] text-gray-500">${esc(c.category || '')} · ${esc(c.website || '')}</div>
            <div class="text-xs text-gray-400 mt-2">${esc(c.description || '')}</div>
          </div>`;
        }
        html += `</div>`;
      }
      pane.innerHTML = html;
    }
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderNewsFeed(news) {
  if (!news.length) return '<div class="card p-4 text-sm text-gray-400">No competitor news yet. Click <b>Scan</b> to fetch.</div>';
  const typeIcon = {
    feature_launch: 'fa-rocket text-cyan-400',
    acquisition: 'fa-handshake text-yellow-400',
    partnership: 'fa-link text-green-400',
    pricing_change: 'fa-tag text-orange-400',
    funding: 'fa-dollar-sign text-green-400',
    blog_post: 'fa-rss text-blue-400',
    news: 'fa-newspaper text-gray-400',
  };
  let html = `<div class="space-y-1.5 max-h-[70vh] overflow-y-auto">`;
  for (const n of news.slice(0, 80)) {
    const icon = typeIcon[n.event_type] || 'fa-circle text-gray-500';
    html += `<div class="card px-3 py-2 flex items-start gap-2">
      <i class="fas ${icon} text-[10px] mt-1.5"></i>
      <div class="flex-1 min-w-0">
        <div class="text-xs text-white">${esc(n.title)}</div>
        <div class="text-[10px] text-gray-500 mt-0.5">
          <span class="text-orange-400">${esc(n.competitor_name)}</span>
          · ${esc(n.source === 'rss' ? 'blog' : 'news')}
          · ${esc(relDate(n.created_at))}
        </div>
      </div>
      ${safeHref(n.url) ? `<a href="${safeHref(n.url)}" target="_blank" rel="noopener noreferrer" class="text-blue-400 text-[10px]"><i class="fas fa-external-link-alt"></i></a>` : ''}
    </div>`;
  }
  html += `</div>`;
  return html;
}

async function loadBriefing() {
  try {
    const data = await api('/competitors/news/summary');
    document.getElementById('briefing').innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <div class="text-[10px] text-purple-400 uppercase font-bold"><i class="fas fa-robot mr-1"></i>Daily Briefing — ${esc(data.date || '')}</div>
        <button onclick="regenerateBriefing()" class="text-[10px] text-gray-500 hover:text-purple-400"><i class="fas fa-sync-alt mr-1"></i>Regenerate</button>
      </div>
      <pre class="text-xs text-gray-300">${esc(data.summary || '')}</pre>
      <div class="text-[10px] text-gray-600 mt-2">${data.total_signals || 0} signals analyzed</div>`;
  } catch (e) {
    document.getElementById('briefing').innerHTML = `<div class="text-xs text-red-400">Briefing failed: ${esc(e.message)}</div>`;
  }
}

async function regenerateBriefing() {
  const el = document.getElementById('briefing');
  if (el) el.innerHTML = '<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Regenerating…</div>';
  try {
    await api('/competitors/news/summary?refresh=true');
    loadBriefing();
  } catch (e) {
    if (el) el.innerHTML = `<div class="text-xs text-red-400">Regenerate failed: ${esc(e.message)}</div>`;
  }
}

async function discoverCompetitors() {
  if (!confirm('Ask Maggy to discover competitors for your domain? This calls the AI.')) return;
  try {
    const data = await api('/competitors/discover', { method: 'POST' });
    alert(`Added ${data.added} new competitors (total: ${data.total})`);
    loadCompetitors();
  } catch (e) {
    alert('Discovery failed: ' + e.message);
  }
}

async function scanCompetitors() {
  try {
    const data = await api('/competitors/monitor', { method: 'POST' });
    alert(`Found ${data.rss || 0} blog posts + ${data.news || 0} news items across ${data.total_competitors} competitors`);
    loadCompetitors();
  } catch (e) {
    alert('Scan failed: ' + e.message);
  }
}

// ── Chat ────────────────────────────────────────────────────────────────
let CHAT_SESSION_ID = null;
let CHAT_SESSIONS_CACHE = [];
let CURRENT_MODEL = '';
let _streamingActive = false;
let _lastStreamRender = 0;

// Sidebar star + collapse state (persisted in localStorage)
function _starredProjects() {
  try { return JSON.parse(localStorage.getItem('maggy-starred') || '[]'); } catch { return []; }
}
function _collapsedProjects() {
  // Default: all collapsed. localStorage stores the *expanded* list.
  return null; // Sentinel — renderChatSidebar checks explicitly
}
function _expandedProjects() {
  try { return JSON.parse(localStorage.getItem('maggy-expanded') || '[]'); } catch { return []; }
}
function toggleStar(key) {
  const starred = _starredProjects();
  const idx = starred.indexOf(key);
  if (idx >= 0) starred.splice(idx, 1); else starred.push(key);
  localStorage.setItem('maggy-starred', JSON.stringify(starred));
  const pane = document.getElementById('pane-chat');
  if (pane) renderChatUI(pane);
}
function toggleCollapse(key) {
  const expanded = _expandedProjects();
  const idx = expanded.indexOf(key);
  if (idx >= 0) expanded.splice(idx, 1); else expanded.push(key);
  localStorage.setItem('maggy-expanded', JSON.stringify(expanded));
  const pane = document.getElementById('pane-chat');
  if (pane) renderChatUI(pane);
}

async function loadChat(forProject) {
  const pane = document.getElementById('pane-chat');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading projects…</div>`;
  try {
    const result = await api('/chat/preload', { method: 'POST' });
    CHAT_SESSIONS_CACHE = result.sessions || [];
    if (!CHAT_SESSION_ID && CHAT_SESSIONS_CACHE.length) {
      if (forProject) {
        const match = CHAT_SESSIONS_CACHE.find(s => s.project_key === forProject);
        CHAT_SESSION_ID = match ? match.id : CHAT_SESSIONS_CACHE[0].id;
      } else {
        CHAT_SESSION_ID = CHAT_SESSIONS_CACHE[0].id;
      }
    }
    renderChatUI(pane);
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderChatUI(pane) {
  // Don't rebuild DOM while streaming — tab switch just shows/hides pane
  if (_streamingActive && pane.querySelector('#chat-messages')) return;
  let html = `<div class="flex h-full">`;
  html += renderChatMain();
  html += `</div>`;
  pane.innerHTML = html;
  if (CHAT_SESSION_ID) loadChatMessages(CHAT_SESSION_ID);
  setTimeout(refreshSuggestion, 100);
}

function renderChatSidebar(sessions) {
  const groups = {};
  for (const s of sessions) {
    const key = s.project_key || 'unknown';
    (groups[key] = groups[key] || []).push(s);
  }
  const starred = _starredProjects();
  const expanded = _expandedProjects();
  // Sort: starred first, then alphabetical
  const keys = Object.keys(groups).sort((a, b) => {
    const aS = starred.includes(a) ? 0 : 1;
    const bS = starred.includes(b) ? 0 : 1;
    return aS - bS || a.localeCompare(b);
  });
  let html = `<div class="w-56 shrink-0 border-r border-gray-800/60 overflow-y-auto scroll-thin" style="padding:12px 14px 12px 10px">`;
  html += `<div class="flex items-center gap-1.5 mb-3 pb-2 border-b border-gray-800/40">
    <i class="fas fa-folder-tree text-orange-500/60 text-[10px]"></i>
    <span class="text-[10px] text-gray-500 uppercase font-semibold tracking-wide">Projects</span>
    <span class="text-[9px] text-gray-600 ml-auto">${keys.length}</span>
  </div>`;
  if (!sessions.length) {
    html += `<div class="text-[10px] text-gray-600 py-3 text-center">No active sessions</div>`;
  }
  for (const project of keys) {
    const slist = groups[project];
    const isStarred = starred.includes(project);
    const isExpanded = expanded.includes(project);
    const starCls = isStarred ? 'text-yellow-400' : 'text-gray-700 hover:text-yellow-400';
    const chevron = isExpanded ? 'fa-chevron-down' : 'fa-chevron-right';
    html += `<div class="mb-1">`;
    html += `<div class="flex items-center gap-1.5 py-1.5 px-1 rounded hover:bg-white/[0.02] group cursor-pointer" onclick="toggleCollapse('${jsStr(project)}')">
      <i class="fas ${chevron} text-[8px] text-gray-600 w-3 text-center"></i>
      <button onclick="event.stopPropagation(); toggleStar('${jsStr(project)}')" class="text-[9px] ${starCls}" title="${isStarred ? 'Unstar' : 'Star'}"><i class="fas fa-star"></i></button>
      <span class="text-[10px] text-gray-400 font-medium truncate flex-1">${esc(project)}</span>
      <span class="text-[9px] text-gray-700">${slist.length}</span>
      <button onclick="event.stopPropagation(); newSessionForProject('${jsStr(project)}')" class="text-[9px] text-gray-700 hover:text-orange-400 opacity-0 group-hover:opacity-100 ml-0.5" title="New session"><i class="fas fa-plus"></i></button>
    </div>`;
    if (isExpanded) {
      html += `<div class="ml-5 mt-0.5 mb-1 space-y-0.5">`;
      for (let i = 0; i < slist.length; i++) {
        const s = slist[i];
        const active = s.id === CHAT_SESSION_ID ? 'bg-orange-500/10 border-orange-500/40' : 'border-transparent hover:bg-white/[0.03]';
        const displayName = s.label || `Session ${i + 1}`;
        const isBranch = s.label && s.label !== `Session ${i + 1}`;
        const icon = isBranch ? 'fa-code-branch' : 'fa-circle';
        const resumeBadge = s.has_resume_id ? '<i class="fas fa-history text-green-400/60 text-[7px]" title="Claude session linked"></i>' : '';
        html += `<div class="flex items-center gap-1.5 px-2 py-1 rounded border cursor-pointer group ${active}" onclick="openChatSession('${jsStr(s.id)}')">
            <i class="fas ${icon} ${isBranch ? 'text-orange-400/70' : 'text-green-400/50'} text-[6px]"></i>
            <span id="slabel-${esc(s.id)}" class="text-[10px] text-gray-400 flex-1 truncate">${esc(displayName)}</span>
            ${resumeBadge}
            <button onclick="event.stopPropagation(); renameSession('${jsStr(s.id)}')" class="text-[8px] text-gray-700 hover:text-orange-400 opacity-0 group-hover:opacity-100" title="Rename"><i class="fas fa-pen"></i></button>
            <button onclick="event.stopPropagation(); deleteSession('${jsStr(s.id)}')" class="text-[8px] text-gray-700 hover:text-red-400 opacity-0 group-hover:opacity-100" title="Delete"><i class="fas fa-trash"></i></button>
        </div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

function renderSessionTabs() {
  // Sub-tab bar: every chat for the CURRENT project. Each additional chat runs
  // in its own git worktree + branch. + opens a new parallel (isolated) chat.
  const cur = (CHAT_SESSIONS_CACHE || []).find(s => s.id === CHAT_SESSION_ID);
  if (!cur) return '';
  const proj = cur.project_key;
  const tabs = (CHAT_SESSIONS_CACHE || []).filter(s => s.project_key === proj);
  let h = `<div class="shrink-0 flex items-center gap-1 px-3 py-1 border-b overflow-x-auto scroll-thin" style="border-color:var(--border);background:rgba(10,13,20,0.5);min-height:34px">`;
  h += `<span class="text-[9px] text-gray-600 uppercase tracking-wide mr-1 shrink-0"><i class="fas fa-folder text-orange-500/50 mr-1"></i>${esc(proj)}</span>`;
  tabs.forEach((s, i) => {
    const active = s.id === CHAT_SESSION_ID;
    const isWt = s.isolation === 'worktree' || (s.label || '').startsWith('maggy/');
    const name = isWt ? (s.label || '').replace('maggy/', 'wt·') : (s.label || `chat ${i + 1}`);
    const icon = isWt ? 'fa-code-branch' : 'fa-comment-dots';
    const cls = active ? 'bg-orange-500/15 text-orange-300 border-orange-500/40'
                       : 'text-gray-400 hover:bg-white/5 border-transparent';
    h += `<div onclick="openChatSession('${jsStr(s.id)}')" class="group flex items-center gap-1 px-2 py-1 rounded cursor-pointer text-[10px] border shrink-0 ${cls}">
      <i class="fas ${icon} text-[8px] ${isWt ? 'text-orange-400/70' : 'text-green-400/50'}"></i>
      <span class="truncate max-w-[140px]">${esc(name)}</span>
      <i onclick="event.stopPropagation();deleteSession('${jsStr(s.id)}')" class="fas fa-xmark text-[8px] text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100" title="Close chat"></i>
    </div>`;
  });
  h += `<button onclick="newSessionForProject('${jsStr(proj)}')" class="px-2 py-1 rounded text-[10px] text-gray-500 hover:text-orange-400 shrink-0" title="New parallel chat — its own git worktree + branch"><i class="fas fa-plus"></i></button>`;
  h += `</div>`;
  return h;
}

function renderChatMain() {
  let html = `<div class="flex-1 flex flex-col min-h-0">`;
  if (CHAT_SESSION_ID) {
    html += renderSessionTabs();
    // Top progress shimmer bar (hidden by default)
    html += `<div id="progress-bar" class="hidden h-0.5 w-full overflow-hidden bg-gray-800/50"><div class="progress-shimmer h-full w-1/3"></div></div>`;
    // Model badge (shows current model during/after response)
    html += `<div id="chat-model-badge" class="hidden shrink-0 px-5 py-1.5 text-[10px] text-gray-500 border-b border-gray-800/50">
      <i class="fas fa-robot mr-1 text-orange-400/60"></i><span id="chat-model-name"></span>
    </div>`;
    // Editor tab bar (hidden until an editor tab opens)
    html += `<div id="editor-tab-bar" class="hidden shrink-0 flex items-center gap-0 border-b overflow-x-auto scroll-thin" style="border-color:var(--border);background:rgba(10,13,20,0.6);min-height:28px;"></div>`;
    // Messages scroll area (wrapped for show/hide)
    html += `<div id="chat-content-area" class="flex-1 overflow-hidden min-h-0 flex flex-col">`;
    html += `<div id="chat-messages" class="flex-1 overflow-y-auto overflow-x-hidden min-h-0 px-5 py-3"><div id="chat-messages-inner" class="flex flex-col justify-end min-h-full space-y-3 pb-4 min-w-0"></div></div>`;
    html += `</div>`;
    // Editor panes container (hidden by default)
    html += `<div id="editor-panes-container" class="hidden flex-1 overflow-hidden min-h-0"></div>`;
    // Working status bar (single line, compact)
    html += `<div id="working-zone" class="hidden shrink-0 px-5 py-1.5 border-t border-gray-700/30 flex items-center gap-2">
      <span class="inline-block w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse"></span>
      <span id="model-label" class="text-[10px] text-gray-500">Working...</span>
      <span class="text-[10px] text-gray-700">·</span>
      <span id="joke-text" class="text-[10px] text-gray-600 truncate flex-1"></span>
    </div>`;
    // Quick-action suggestion bubble (contextual, always loaded)
    html += `<div id="refresh-suggest" class="hidden shrink-0 px-5 py-1.5">
      <div class="quick-actions-inner flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] overflow-x-auto" style="background:var(--input-bg);border:1px solid var(--border)">
      </div>
    </div>`;
    // Divider + input bar + divider
    html += `<div class="border-t border-gray-700/50"></div>`;
    html += `<div class="shrink-0 px-5 pt-3 pb-2" style="background:var(--bg)">
      <div id="chat-attachments" class="hidden mb-1.5 flex flex-wrap gap-1"></div>
      <div class="flex gap-2">
        <input id="chat-file" type="file" class="hidden" onchange="handleFileSelect(event)" multiple />
        <button onclick="document.getElementById('chat-file').click()" class="px-3 py-2.5 rounded-lg text-sm" style="background:var(--input-bg);color:var(--text-muted);border:1px solid var(--border)" title="Attach file"><i class="fas fa-paperclip"></i></button>
        <div class="flex-1 relative">
          <div id="chat-ghost" class="absolute inset-x-0 top-0 px-3 py-2 text-sm text-gray-600 pointer-events-none whitespace-nowrap overflow-hidden"></div>
          <textarea id="chat-input" rows="1" placeholder="Ask anything... (! for shell, / for commands)"
            class="w-full text-sm rounded-lg px-3 py-2 focus:border-orange-500 outline-none resize-none overflow-hidden"
            style="background: var(--surface); color: var(--text); border: 1px solid var(--border); max-height: 120px;"
            onkeydown="handleChatKeydown(event)" oninput="autoResizeInput(); updateGhostText()"></textarea>
        </div>
        <button onclick="sendChatMessage()" class="self-end px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-sm"><i class="fas fa-paper-plane"></i></button>
      </div>
      <div class="text-[9px] text-gray-600 mt-1 text-center">Tab to accept · Enter to send · Shift+Enter for newline</div>
    </div>`;
    html += `<div class="border-t border-gray-700/50"></div>`;
  } else {
    html += `<div class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <i class="fas fa-robot text-4xl text-gray-700 mb-3"></i>
        <div class="text-sm text-gray-400 mb-2">No active CLI sessions detected</div>
        <div class="text-xs text-gray-500">Start a Claude Code session in any project and Maggy will auto-connect</div>
      </div>
    </div>`;
  }
  html += `</div>`;
  return html;
}

async function newChatSession() {
  const currentProject = document.getElementById('current-project-label')?.textContent;
  if (!currentProject || currentProject === 'Select project...') {
    alert('Select a project first.');
    return;
  }
  let path = '';
  try {
    const cfg = await api('/config').catch(() => ({ codebases: [] }));
    const found = (cfg.codebases || []).find(c => c.key === currentProject);
    if (found) path = found.path || '';
  } catch {}
  try {
    const data = await api('/chat/sessions', { method: 'POST', body: JSON.stringify({ project_key: currentProject, project_path: path }) });
    CHAT_SESSION_ID = data.id;
    loadChat();
    switchTab('chat');
  } catch (e) { alert('Failed: ' + e.message); }
}

async function newSessionForProject(projectKey) {
  const existing = CHAT_SESSIONS_CACHE.find(s => s.project_key === projectKey);
  const path = existing ? (existing.repo_dir || existing.working_dir) : '';
  // An additional chat for a project runs in its OWN git worktree + branch, so
  // parallel chats don't collide. The first chat (no existing one) stays on the
  // main tree — the backend also auto-isolates if a main chat already exists.
  const isolated = !!existing;
  try {
    const data = await api('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ project_key: projectKey, project_path: path, isolated: isolated }),
    });
    CHAT_SESSION_ID = data.id;
    loadChat();
    if (data.isolation === 'worktree') {
      showToast(`New parallel chat on branch ${data.label} (isolated worktree)`);
    }
  } catch (e) { alert('Failed: ' + e.message); }
}

function openChatSession(id) {
  if (CHAT_SESSION_ID === id) return;
  CHAT_SESSION_ID = id;
  const pane = document.getElementById('pane-chat');
  if (pane) renderChatUI(pane);
}

function renameSession(sessionId) {
  const el = document.getElementById('slabel-' + sessionId);
  if (!el) return;
  const current = el.textContent;
  const input = document.createElement('input');
  input.type = 'text';
  input.value = current;
  input.className = 'text-[10px] rounded px-1 w-full outline-none';
  input.style.cssText = 'background:var(--surface);color:var(--text);border:1px solid var(--accent)';
  input.onblur = () => commitRename(sessionId, input, el, current);
  input.onkeydown = (e) => {
    if (e.key === 'Enter') input.blur();
    if (e.key === 'Escape') { el.textContent = current; }
  };
  el.textContent = '';
  el.appendChild(input);
  input.focus();
  input.select();
}

async function commitRename(sessionId, input, el, fallback) {
  const label = input.value.trim();
  el.textContent = label || fallback || 'Session';
  if (!label) return;
  try {
    await api(`/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ label }),
    });
    const cached = CHAT_SESSIONS_CACHE.find(s => s.id === sessionId);
    if (cached) cached.label = label;
  } catch (e) {
    console.error('Rename failed:', e);
  }
}

async function deleteSession(sessionId) {
  const s = (CHAT_SESSIONS_CACHE || []).find(x => x.id === sessionId);
  const isWt = s && (s.isolation === 'worktree' || (s.label || '').startsWith('maggy/'));
  const msg = isWt
    ? `Delete this chat? Its worktree is removed (uncommitted changes there are lost). The branch ${s.label} and any commits are kept.`
    : 'Delete this session?';
  if (!confirm(msg)) return;
  try {
    await api(`/chat/sessions/${sessionId}`, { method: 'DELETE' });
    if (CHAT_SESSION_ID === sessionId) {
      CHAT_SESSION_ID = null;
    }
    loadChat();
  } catch (e) {
    alert('Delete failed: ' + e.message);
  }
}

async function loadChatMessages(id) {
  const outer = document.getElementById('chat-messages');
  const el = document.getElementById('chat-messages-inner') || outer;
  if (!el) return;
  try {
    const data = await api(`/chat/sessions/${id}`);
    let html = renderSessionHeader(data);
    if (data.history_context && !(data.messages || []).length) {
      html += renderHistoryContext(data.history_context);
    }
    for (const m of data.messages || []) {
      if (!m.content || !m.content.trim()) continue;
      html += m.role === 'user' ? renderUserMsg(m) : renderAssistantMsg(m);
    }
    el.innerHTML = html;
    if (outer) outer.scrollTop = outer.scrollHeight;
  } catch (e) {
    el.innerHTML = `<div class="text-xs text-red-400">${esc(e.message)}</div>`;
  }
}

function renderSessionHeader(data) {
  return `<div class="text-[10px] text-gray-500 mb-2"><i class="fas fa-folder-open mr-1"></i>${esc(data.project_key)} · <span class="font-mono">${esc(data.working_dir)}</span></div>`;
}

function renderHistoryContext(ctx) {
  return `<div class="card px-3 py-2 mb-2 border border-gray-700 bg-gray-900/50">
    <div class="text-[10px] text-gray-400 font-bold mb-1"><i class="fas fa-history mr-1"></i>Session History (Maggy knows this)</div>
    <pre class="text-[10px] text-gray-500 whitespace-pre-wrap">${esc(ctx)}</pre>
  </div>`;
}

function renderUserMsg(m) {
  const ts = m.timestamp ? `<div class="text-[10px] text-gray-500 mt-1">${esc(relDate(m.timestamp))}</div>` : '';
  return `<div class="flex justify-end px-2 min-w-0"><div class="max-w-[65%] min-w-0 bg-orange-600/20 border border-orange-600/30 rounded-lg px-3 py-2">
    <div class="text-xs text-white whitespace-pre-wrap break-words overflow-hidden">${esc(m.content)}</div>${ts}
  </div></div>`;
}

function renderAssistantMsg(m) {
  const ts = m.timestamp ? `<div class="text-[10px] text-gray-500 mt-1">${esc(relDate(m.timestamp))}</div>` : '';
  return `<div class="flex justify-start min-w-0"><div class="max-w-[75%] min-w-0 card px-3 py-2 overflow-hidden">
    ${renderMd(m.content)}${ts}
  </div></div>`;
}

// ── Knock-knock jokes for waiting state ──────────────────────────────
const JOKES = [
  ["Knock knock.", "Who's there?", "Git.", "Git who?", "Git commit or git out!"],
  ["Knock knock.", "Who's there?", "Bug.", "Bug who?", "Bug off, I'm compiling!"],
  ["Knock knock.", "Who's there?", "Cache.", "Cache who?", "Cache me outside, how bout dat?"],
  ["Knock knock.", "Who's there?", "Docker.", "Docker who?", "Docker-ated environment, no excuses!"],
  ["Knock knock.", "Who's there?", "Async.", "Async who?", "Async-ronously waiting for your response!"],
  ["Knock knock.", "Who's there?", "Claude.", "Claude who?", "Claude-strophobic from all this context!"],
  ["Knock knock.", "Who's there?", "Null.", "Null who?", "Exactly."],
  ["Knock knock.", "Who's there?", "Recursion.", "Recursion who?", "Knock knock."],
  ["Knock knock.", "Who's there?", "API.", "API who?", "A-PI-ece of cake, this task!"],
  ["Knock knock.", "Who's there?", "Sudo.", "Sudo who?", "Sudo make me a sandwich!"],
  ["Knock knock.", "Who's there?", "404.", "404 who?", "Page not found. Try again."],
  ["Knock knock.", "Who's there?", "Python.", "Python who?", "Python my way through this code!"],
  ["Knock knock.", "Who's there?", "SSH.", "SSH who?", "SSH! I'm debugging!"],
  ["Knock knock.", "Who's there?", "Token.", "Token who?", "Token my time thinking about this!"],
  ["Knock knock.", "Who's there?", "React.", "React who?", "React-ing to your code changes!"],
  ["Knock knock.", "Who's there?", "Lint.", "Lint who?", "Lint-eresting, no errors this time!"],
  ["Knock knock.", "Who's there?", "SQL.", "SQL who?", "SQL-ling my secrets to the database!"],
  ["Knock knock.", "Who's there?", "Merge.", "Merge who?", "Merge conflict! Good luck."],
  ["Knock knock.", "Who's there?", "AI.", "AI who?", "AI'll handle this, don't worry!"],
  ["Knock knock.", "Who's there?", "Regex.", "Regex who?", "Regex-ter your patterns carefully!"],
  ["Knock knock.", "Who's there?", "Java.", "Java who?", "Java nice day for some coding!"],
  ["Knock knock.", "Who's there?", "Npm.", "Npm who?", "Npm install patience --save!"],
  ["Knock knock.", "Who's there?", "REST.", "REST who?", "REST assured, I'm working on it!"],
  ["Knock knock.", "Who's there?", "Stack.", "Stack who?", "Stack Overflow to the rescue!"],
  ["Knock knock.", "Who's there?", "Bit.", "Bit who?", "Bit by bit, we'll get there!"],
  ["Knock knock.", "Who's there?", "CSS.", "CSS who?", "CSS-iously, fix the layout!"],
  ["Knock knock.", "Who's there?", "Debug.", "Debug who?", "De-bug stops here!"],
  ["Knock knock.", "Who's there?", "Hash.", "Hash who?", "Hash browns! Wait, wrong hash."],
  ["Knock knock.", "Who's there?", "Array.", "Array who?", "Array of sunshine on a cloudy day!"],
  ["Knock knock.", "Who's there?", "Rust.", "Rust who?", "Rust-le up some safe code!"],
  ["Knock knock.", "Who's there?", "Branch.", "Branch who?", "Branch out and try something new!"],
  ["Knock knock.", "Who's there?", "Deploy.", "Deploy who?", "Deploy the code before Friday!"],
  ["Knock knock.", "Who's there?", "YAML.", "YAML who?", "YAML never believe this config!"],
  ["Knock knock.", "Who's there?", "Pod.", "Pod who?", "Pod-cast about Kubernetes!"],
  ["Knock knock.", "Who's there?", "Test.", "Test who?", "Test-ify that the code works!"],
  ["Knock knock.", "Who's there?", "JSON.", "JSON who?", "JSON the right track!"],
  ["Knock knock.", "Who's there?", "Shell.", "Shell who?", "Shell we dance... in the terminal?"],
  ["Knock knock.", "Who's there?", "Ping.", "Ping who?", "Ping me when you're done!"],
  ["Knock knock.", "Who's there?", "Vim.", "Vim who?", "Vim trying to exit for hours!"],
  ["Knock knock.", "Who's there?", "Query.", "Query who?", "Query-ous about the results!"],
  ["Knock knock.", "Who's there?", "CI.", "CI who?", "CI you later, pipeline's running!"],
  ["Knock knock.", "Who's there?", "Pipe.", "Pipe who?", "Pipe down, I'm thinking!"],
  ["Knock knock.", "Who's there?", "Thread.", "Thread who?", "Thread carefully, it's concurrent!"],
  ["Knock knock.", "Who's there?", "Cron.", "Cron who?", "Cron-gratulations, it's scheduled!"],
  ["Knock knock.", "Who's there?", "Port.", "Port who?", "Port 8080 is already in use!"],
  ["Knock knock.", "Who's there?", "Float.", "Float who?", "Float your boat with IEEE 754!"],
  ["Knock knock.", "Who's there?", "Agile.", "Agile who?", "Agile-ity is my middle name!"],
  ["Knock knock.", "Who's there?", "Loop.", "Loop who?", "Loop de loop, infinite style!"],
  ["Knock knock.", "Who's there?", "Schema.", "Schema who?", "Schema-ybe we need a migration!"],
  ["Knock knock.", "Who's there?", "Webpack.", "Webpack who?", "Webpack your bags, we're shipping!"],
];
let _jokeTimer = null;

function startJokeRotation(el) {
  let idx = Math.floor(Math.random() * JOKES.length);
  // Show punchline (last element) as a single line
  const punchline = (joke) => joke[joke.length - 1];
  el.textContent = punchline(JOKES[idx]);
  _jokeTimer = setInterval(() => {
    idx = (idx + 1) % JOKES.length;
    el.textContent = punchline(JOKES[idx]);
  }, 4000);
}

function stopJokeRotation() {
  if (_jokeTimer) { clearInterval(_jokeTimer); _jokeTimer = null; }
}

function showWorking() {
  const bar = document.getElementById('progress-bar');
  const zone = document.getElementById('working-zone');
  const label = document.getElementById('model-label');
  if (bar) bar.classList.remove('hidden');
  if (zone) { zone.classList.remove('hidden'); zone.style.display = 'flex'; }
  if (label) label.textContent = 'Working...';
  const jokeEl = document.getElementById('joke-text');
  if (jokeEl) startJokeRotation(jokeEl);
}

function hideWorking() {
  stopJokeRotation();
  const bar = document.getElementById('progress-bar');
  const zone = document.getElementById('working-zone');
  const joke = document.getElementById('joke-text');
  const label = document.getElementById('model-label');
  if (bar) bar.classList.add('hidden');
  if (zone) { zone.classList.add('hidden'); zone.style.display = ''; }
  if (joke) joke.textContent = '';
  if (label) label.textContent = '';
}

function updateModelLabel(model, blast, taskType) {
  const label = document.getElementById('model-label');
  if (label) {
    if (!model) { label.textContent = 'Thinking…'; }
    else {
      const parts = [`Working with ${esc(model)}`];
      if (blast) parts.push(`blast ${blast}`);
      if (taskType && taskType !== 'general') parts.push(esc(taskType));
      label.textContent = parts.join(' · ');
    }
  }
  // Persistent model badge in chat header
  const badge = document.getElementById('chat-model-name');
  if (badge && model) {
    var text = model;
    if (blast) text += ' · blast ' + blast;
    if (taskType && taskType !== 'general') text += ' · ' + taskType;
    badge.textContent = text;
    badge.parentElement.classList.remove('hidden');
  }
  // Update header badge
  var hb = document.getElementById('header-model');
  if (hb && model) {
    hb.textContent = model;
    if (blast) hb.textContent += ' · blast ' + blast;
    hb.classList.remove('hidden');
    hb.className = 'badge model-badge ' + (model.indexOf('deepseek') >= 0 ? '' : '');
  }
  var hblast = document.getElementById('header-blast');
  if (hblast && taskType && taskType !== 'general') {
    hblast.textContent = taskType;
    hblast.classList.remove('hidden');
  }
}

// ── Ghost-text suggestions ───────────────────────────────────────────
let _chatHistory = [];
let _lastResponse = '';
let _currentSuggestion = '';

const SUGGESTION_RULES = [
  { after: /\b(fix|bug|error|broke)\b/i, suggest: 'now run the tests to verify the fix' },
  { after: /\b(test|tests|spec)\b/i, suggest: 'check coverage and fix any failures' },
  { after: /\b(review|PR|validate)\b/i, suggest: 'use claude and review the implementation' },
  { after: /\b(implement|feature|add)\b/i, suggest: 'write tests for the new feature' },
  { after: /\b(deploy|release|ship)\b/i, suggest: 'run the full test suite first' },
  { after: /\b(refactor|cleanup|clean)\b/i, suggest: 'verify nothing broke after the refactor' },
  { after: /\b(security|auth|csrf)\b/i, suggest: 'use claude and audit the security flow' },
  { after: /\b(docs|readme|documentation)\b/i, suggest: 'review the docs for accuracy' },
  { after: /\b(style|css|layout|ui)\b/i, suggest: 'check the layout on mobile' },
  { after: /\b(database|schema|migration)\b/i, suggest: 'verify the migration runs cleanly' },
  { after: /\b(api|endpoint|route)\b/i, suggest: 'test the endpoint with sample requests' },
  { after: /\b(config|env|setup)\b/i, suggest: 'verify the config changes work' },
  { after: /\b(performance|slow|optimize)\b/i, suggest: 'profile and measure the improvement' },
  { after: /\b(lint|format|ruff)\b/i, suggest: 'commit the formatting changes' },
];

function getSuggestion() {
  const context = (_chatHistory.slice(-3).join(' ') + ' ' + _lastResponse).toLowerCase();
  for (const rule of SUGGESTION_RULES) {
    if (rule.after.test(context)) return rule.suggest;
  }
  if (_chatHistory.length === 0) return 'describe what you want to build or fix';
  return '';
}

function updateGhostText() {
  var input = document.getElementById('chat-input');
  var ghost = document.getElementById('chat-ghost');
  if (!input || !ghost) return;
  var val = input.value;
  if (val.length > 0 && _currentSuggestion && _currentSuggestion.toLowerCase().startsWith(val.toLowerCase())) {
    ghost.textContent = val + _currentSuggestion.slice(val.length);
    ghost.style.display = '';
  } else {
    ghost.textContent = '';
    ghost.style.display = 'none';
  }
}

function handleChatKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendChatMessage(); return; }
  if (event.key === 'Tab' && _currentSuggestion) {
    const input = document.getElementById('chat-input');
    if (input && (!input.value || _currentSuggestion.toLowerCase().startsWith(input.value.toLowerCase()))) {
      event.preventDefault();
      input.value = _currentSuggestion;
      updateGhostText();
    }
  }
}

function autoResizeInput() {
  const el = document.getElementById('chat-input');
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  el.style.overflowY = el.scrollHeight > 120 ? 'auto' : 'hidden';
}

function refreshSuggestion() {
  _currentSuggestion = getSuggestion();
  updateGhostText();
}

// ── File attachments ──────────────────────────────────────────────────
let _pendingFiles = [];

async function handleFileSelect(event) {
  for (const f of event.target.files) {
    _pendingFiles.push(f);
  }
  event.target.value = '';
  _renderAttachments();
}

function removeAttachment(idx) {
  _pendingFiles.splice(idx, 1);
  _renderAttachments();
}

function _renderAttachments() {
  const el = document.getElementById('chat-attachments');
  if (!el) return;
  if (!_pendingFiles.length) { el.classList.add('hidden'); el.innerHTML = ''; return; }
  el.classList.remove('hidden');
  el.innerHTML = _pendingFiles.map((f, i) =>
    `<span class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-800 text-[10px] text-gray-300">
      <i class="fas fa-file text-orange-400"></i>${esc(f.name)}
      <button onclick="removeAttachment(${i})" class="text-gray-500 hover:text-red-400 ml-1"><i class="fas fa-xmark"></i></button>
    </span>`
  ).join('');
}

async function _uploadFiles() {
  const paths = [];
  const apiKey = localStorage.getItem('maggy-api-key') || '';
  for (const f of _pendingFiles) {
    const form = new FormData();
    form.append('file', f);
    const headers = apiKey ? { 'X-API-Key': apiKey } : {};
    const resp = await fetch(`${API}/chat/upload`, { method: 'POST', headers, body: form });
    if (!resp.ok) throw new Error(`Upload failed: ${f.name}`);
    const data = await resp.json();
    paths.push(data.path);
  }
  _pendingFiles = [];
  _renderAttachments();
  return paths;
}

// ── CLI command handling ────────────────────────────────────────────────
// Track virtual cwd per session (falls back to session working_dir)
var _shellCwd = {};

function _getShellCwd() {
  if (_shellCwd[CHAT_SESSION_ID]) return _shellCwd[CHAT_SESSION_ID];
  // Find session working_dir from cache
  var s = (CHAT_SESSIONS_CACHE || []).find(function(x) { return x.id === CHAT_SESSION_ID; });
  var cwd = (s && (s.repo_dir || s.working_dir)) || '';
  if (cwd) { _shellCwd[CHAT_SESSION_ID] = cwd; return cwd; }
  // Last resort: try to get from project config
  var proj = (s && s.project_key) || '';
  if (proj && window._projectList) {
    // Use home dir as fallback
    return '';
  }
  return '';
}

function _setShellCwd(path) {
  if (CHAT_SESSION_ID && path) _shellCwd[CHAT_SESSION_ID] = path;
}

// Sync client commands (return string or null)
var _CLIENT_COMMANDS = {
  'clear': function() { var el = document.getElementById('chat-messages-inner'); if (el) el.innerHTML = ''; return null; },
  'help': function() {
    return 'Input routing:\n'
      + '  anything          AI chat (LLM-routed via blast-score)\n'
      + '  ! <command>       shell exec (e.g. !ls, !git status)\n'
      + '  / <command>       slash command (see below)\n'
      + '  clear             clear chat\n\n'
      + 'Shell (prefix with !):\n'
      + '  !ls, !git status, !grep -r foo .\n'
      + '  !python script.py, !npm test\n\n'
      + 'Editor:\n'
      + '  vim/edit <file>   open file in editor tab\n'
      + '  Ctrl+S            save current file\n'
      + '  Ctrl+W            close editor tab\n\n'
      + 'Slash commands:\n'
      + '  /help             this help\n'
      + '  /mnemos           memory status & recent nodes\n'
      + '  /icpg             intent graph overview\n'
      + '  /competitors      competitor intel summary\n'
      + '  /budget           token spend summary\n'
      + '  /routing          model routing heatmap\n'
      + '  /progress         execution progress\n'
      + '  /forge            tool registry status\n'
      + '  /plan <topic>     draft a build-in-public plan\n'
      + '  /status           system health overview\n\n'
      + 'Everything without ! or / goes to AI.';
  },
};

// Async slash commands (return promise of HTML string)
var _SLASH_COMMANDS = {
  '/help': function() { return Promise.resolve(_CLIENT_COMMANDS['help']()); },

  '/mnemos': async function() {
    var diag = await api('/engram/diagnostics').catch(function() { return {}; });
    var q = await api('/engram/query?limit=8').catch(function() { return { records: [] }; });
    var total = diag.total_memories || diag.total_engrams || 0;
    var active = diag.active_count || total;
    var superseded = diag.superseded_count || 0;
    var out = 'Mnemos Memory:\n';
    out += '  Total: ' + total + '  |  Active: ' + active + '  |  Superseded: ' + superseded + '\n';
    if (diag.facts || diag.decisions || diag.code_refs || diag.handoffs) {
      out += '  Facts: ' + (diag.facts || 0) + '  Decisions: ' + (diag.decisions || 0)
        + '  Code refs: ' + (diag.code_refs || 0) + '  Handoffs: ' + (diag.handoffs || 0) + '\n';
    }
    var recs = q.records || q.memories || [];
    if (recs.length) {
      out += '\nRecent memories:\n';
      for (var i = 0; i < recs.length; i++) {
        var r = recs[i];
        var tag = (r.memory_type || r.type || 'fact').toUpperCase();
        var content = (r.content || r.text || '').substring(0, 100);
        out += '  [' + tag + '] ' + content + '\n';
      }
    }
    return out;
  },

  '/icpg': async function() {
    var data = await api('/icpg/overview').catch(function() { return {}; });
    var keys = data.projects || Object.keys(data).filter(function(k) { return k !== 'projects'; });
    if (!keys.length && typeof data === 'object') keys = Object.keys(data);
    var out = 'iCPG Overview:\n';
    if (Array.isArray(keys) && keys.length) {
      for (var i = 0; i < keys.length; i++) {
        var k = typeof keys[i] === 'string' ? keys[i] : (keys[i].key || keys[i].name || '');
        var info = data[k] || keys[i] || {};
        var intents = info.intent_count || info.intents || '?';
        var drift = info.drift_count || info.drifts || 0;
        out += '  ' + k + '  —  intents: ' + intents + (drift ? '  drift: ' + drift : '') + '\n';
      }
    } else {
      out += '  No projects indexed. Run /icpg-bootstrap in Claude Code.\n';
    }
    return out;
  },

  '/competitors': async function() {
    var comps = await api('/competitors').catch(function() { return []; });
    var news = await api('/competitors/news?limit=5').catch(function() { return []; });
    var out = 'Competitors: ' + (Array.isArray(comps) ? comps.length : 0) + ' tracked\n';
    if (Array.isArray(comps) && comps.length) {
      for (var i = 0; i < Math.min(comps.length, 8); i++) {
        var c = comps[i];
        out += '  ' + (c.name || '?') + (c.category ? '  (' + c.category + ')' : '') + '\n';
      }
    }
    if (Array.isArray(news) && news.length) {
      out += '\nLatest news:\n';
      for (var j = 0; j < news.length; j++) {
        var n = news[j];
        out += '  ' + (n.title || n.headline || '').substring(0, 80) + '\n';
      }
    }
    return out;
  },

  '/budget': async function() {
    var b = await api('/budget').catch(function() { return {}; });
    var byProv = await api('/budget/by-provider').catch(function() { return {}; });
    var out = 'Token Budget:\n';
    out += '  Today: $' + ((b.today_cost || 0)).toFixed(4);
    out += '  |  Limit: $' + ((b.daily_limit || 0)).toFixed(2);
    out += '  |  Month: $' + ((b.month_cost || 0)).toFixed(2) + '\n';
    var providers = Object.keys(byProv);
    if (providers.length) {
      out += '\nBy provider:\n';
      for (var i = 0; i < providers.length; i++) {
        var p = providers[i];
        var v = byProv[p];
        var cost = typeof v === 'number' ? v : (v && v.cost) || 0;
        out += '  ' + p + ': $' + cost.toFixed(4) + '\n';
      }
    }
    return out;
  },

  '/routing': async function() {
    var data = await api('/routing/heatmap').catch(function() { return []; });
    if (!Array.isArray(data)) data = [];
    var out = 'Model Routing Heatmap:\n';
    if (!data.length) { out += '  No routing data yet.\n'; return out; }
    var byModel = {};
    for (var i = 0; i < data.length; i++) {
      var row = data[i];
      var m = row.model || '?';
      if (!byModel[m]) byModel[m] = [];
      byModel[m].push(row);
    }
    var models = Object.keys(byModel);
    for (var j = 0; j < models.length; j++) {
      var model = models[j];
      var entries = byModel[model];
      out += '  ' + model + ':\n';
      for (var k = 0; k < entries.length; k++) {
        var e = entries[k];
        out += '    ' + (e.task_type || '?') + '  tier=' + (e.blast_tier || '?')
          + '  reward=' + (e.avg_reward || 0).toFixed(2) + '  n=' + (e.samples || 0) + '\n';
      }
    }
    return out;
  },

  '/progress': async function() {
    var data = await api('/execute/sessions').catch(function() { return { sessions: [] }; });
    var sessions = data.sessions || data || [];
    if (!Array.isArray(sessions)) sessions = [];
    var out = 'Execution Progress:  ' + sessions.length + ' session(s)\n';
    for (var i = 0; i < Math.min(sessions.length, 10); i++) {
      var s = sessions[i];
      var status = s.status || '?';
      var icon = status === 'running' ? '[*]' : status === 'done' ? '[v]' : '[ ]';
      out += '  ' + icon + ' ' + (s.task_id || s.id || '?') + '  ' + status + '\n';
    }
    if (!sessions.length) out += '  No active sessions.\n';
    return out;
  },

  '/forge': async function() {
    var status = await api('/forge/status').catch(function() { return {}; });
    var gaps = await api('/forge/gaps').catch(function() { return []; });
    var out = 'Forge — Tool Registry:\n';
    var tools = status.tools || [];
    out += '  Tools: ' + (Array.isArray(tools) ? tools.length : (status.total || '?')) + '\n';
    if (Array.isArray(gaps) && gaps.length) {
      out += '\nCapability gaps:\n';
      for (var i = 0; i < Math.min(gaps.length, 5); i++) {
        out += '  - ' + (gaps[i].description || gaps[i].name || gaps[i]) + '\n';
      }
    }
    return out;
  },

  '/status': async function() {
    var health = await api('/health').catch(function() { return {}; });
    var diag = await api('/engram/diagnostics').catch(function() { return {}; });
    var b = await api('/budget').catch(function() { return {}; });
    var total = diag.total_memories || diag.total_engrams || 0;
    var out = 'System Status:\n';
    out += '  Server:  ' + (health.status || 'ok') + '\n';
    out += '  Memory:  ' + total + ' engrams  (active: ' + (diag.active_count || total) + ')\n';
    out += '  Budget:  $' + ((b.today_cost || 0)).toFixed(4) + ' today  /  $' + ((b.daily_limit || 0)).toFixed(2) + ' limit\n';
    out += '  Mode:    ' + (health.mode || '?') + '\n';
    return out;
  },

  '/plan': async function(args) {
    var topic = args || 'build-in-public';
    return 'Planning: ' + topic + '\n\n'
      + 'To generate a build-in-public plan, send this to AI:\n'
      + '  "Create a build-in-public content plan for: ' + topic + '"\n\n'
      + 'Or use the plugin directly:\n'
      + '  ~/.maggy/plugins/build-in-public/\n';
  },

  '/refresh': async function() {
    var s = (CHAT_SESSIONS_CACHE || []).find(function(x) { return x.id === CHAT_SESSION_ID; });
    var projPath = (s && (s.repo_dir || s.working_dir)) || '';
    var url = '/refresh?limit=5';
    if (projPath) url += '&project=' + encodeURIComponent(projPath);
    var data = await api(url).catch(function() { return { sessions: [] }; });
    var sessions = data.sessions || [];
    if (!sessions.length) return 'No recent CLI sessions found for this project.';
    var latest = sessions[0];
    var imported = await api('/refresh/import', {
      method: 'POST',
      body: JSON.stringify({
        session_id: latest.session_id,
        target_session_id: CHAT_SESSION_ID
      })
    }).catch(function() { return { imported: 0 }; });
    if (imported.imported > 0) {
      await loadChatMessages(CHAT_SESSION_ID);
      return 'Imported ' + imported.imported + ' turns from ' + (latest.cli || 'CLI').toUpperCase() + ' session (' + latest.session_id.substring(0, 8) + ') into project history.';
    }
    var out = 'CLI Sessions (' + sessions.length + ')\n';
    out += '─'.repeat(30) + '\n\n';
    for (var i = 0; i < sessions.length; i++) {
      var sess = sessions[i];
      out += (sess.cli || 'claude').toUpperCase() + ' — ' + (sess.project || '?') + '\n';
      out += 'Session: ' + (sess.session_id || '').substring(0, 8) + '\n';
      var turns = sess.turns || [];
      var shown = turns.slice(-6);
      for (var j = 0; j < shown.length; j++) {
        var t = shown[j];
        var role = t.role === 'user' ? 'You' : 'AI';
        var text = (t.text || '').substring(0, 100).replace(/\n/g, ' ');
        out += '  ' + role + ': ' + text + '\n';
      }
      out += '\n';
    }
    return out;
  },
};

// ── Editor tab system ────────────────────────────────────────────────
var _editorTabs = {};
var _editorTabOrder = [];
var _activeEditorTab = '__chat__';

var _EDITOR_PROGRAMS = ['vim', 'vi', 'nvim', 'nano', 'emacs', 'edit', 'code'];

function _genTabId(filePath) {
  return 'ed-' + filePath.replace(/[^a-zA-Z0-9]/g, '_');
}

function renderEditorTabBar() {
  var bar = document.getElementById('editor-tab-bar');
  if (!bar) return;
  if (!_editorTabOrder.length) { bar.classList.add('hidden'); return; }
  bar.classList.remove('hidden');
  var html = '';
  // Chat tab (always first)
  var chatActive = _activeEditorTab === '__chat__';
  html += '<div class="editor-tab ' + (chatActive ? 'active' : '') + ' flex items-center gap-1.5 px-3 py-1.5 text-[10px] border-r" '
    + 'style="border-right-color:var(--border);" onclick="switchEditorTab(\'__chat__\')">'
    + '<i class="fas fa-terminal text-[9px] text-orange-400/70"></i>'
    + '<span>Chat</span></div>';
  // Editor tabs
  for (var i = 0; i < _editorTabOrder.length; i++) {
    var tid = _editorTabOrder[i];
    var tab = _editorTabs[tid];
    if (!tab) continue;
    var isActive = _activeEditorTab === tid;
    html += '<div class="editor-tab ' + (isActive ? 'active' : '') + ' flex items-center gap-1.5 px-3 py-1.5 text-[10px] border-r" '
      + 'style="border-right-color:var(--border);" onclick="switchEditorTab(\'' + tid + '\')">'
      + '<i class="fas fa-file-code text-[9px] text-blue-400/60"></i>'
      + '<span class="max-w-[120px] truncate">' + esc(tab.fileName) + '</span>';
    if (tab.dirty) {
      html += '<span class="dirty-dot w-1.5 h-1.5 rounded-full bg-orange-400 ml-0.5 inline-block"></span>';
    }
    html += '<button onclick="event.stopPropagation();closeEditorTab(\'' + tid + '\')" '
      + 'class="text-gray-600 hover:text-red-400 ml-1 text-[8px]"><i class="fas fa-xmark"></i></button>'
      + '</div>';
  }
  bar.innerHTML = html;
}

function switchEditorTab(tabId) {
  // Save state of current editor tab
  if (_activeEditorTab !== '__chat__' && _editorTabs[_activeEditorTab]) {
    var ta = document.getElementById('editor-textarea-' + _activeEditorTab);
    if (ta) {
      _editorTabs[_activeEditorTab].cursorStart = ta.selectionStart;
      _editorTabs[_activeEditorTab].cursorEnd = ta.selectionEnd;
      _editorTabs[_activeEditorTab].scrollTop = ta.scrollTop;
    }
  }
  _activeEditorTab = tabId;
  var chatArea = document.getElementById('chat-content-area');
  var editorArea = document.getElementById('editor-panes-container');
  var workingZone = document.getElementById('working-zone');
  if (tabId === '__chat__') {
    if (chatArea) chatArea.classList.remove('hidden');
    if (editorArea) editorArea.classList.add('hidden');
  } else {
    if (chatArea) chatArea.classList.add('hidden');
    if (editorArea) { editorArea.classList.remove('hidden'); _showEditorPane(tabId); }
  }
  renderEditorTabBar();
  // Restore cursor in new tab
  if (tabId !== '__chat__' && _editorTabs[tabId]) {
    var ta = document.getElementById('editor-textarea-' + tabId);
    if (ta) {
      ta.focus();
      ta.selectionStart = _editorTabs[tabId].cursorStart || 0;
      ta.selectionEnd = _editorTabs[tabId].cursorEnd || 0;
      ta.scrollTop = _editorTabs[tabId].scrollTop || 0;
    }
  }
}

function _showEditorPane(tabId) {
  var container = document.getElementById('editor-panes-container');
  if (!container) return;
  var panes = container.children;
  for (var i = 0; i < panes.length; i++) {
    panes[i].classList.add('hidden');
  }
  var pane = document.getElementById('editor-pane-' + tabId);
  if (pane) pane.classList.remove('hidden');
}

function _createEditorPane(tabId) {
  var container = document.getElementById('editor-panes-container');
  if (!container) return;
  var tab = _editorTabs[tabId];
  if (!tab) return;
  var pane = document.createElement('div');
  pane.id = 'editor-pane-' + tabId;
  pane.className = 'h-full flex flex-col';
  var shortPath = tab.filePath.replace(/^\/Users\/[^/]+/, '~');
  pane.innerHTML = '<div class="shrink-0 flex items-center gap-2 px-4 py-1.5 border-b" style="border-color:var(--border);background:rgba(10,13,20,0.4);">'
    + '<i class="fas fa-file-code text-blue-400/60 text-xs"></i>'
    + '<span class="text-[11px] text-gray-300 font-mono truncate">' + esc(shortPath) + '</span>'
    + '<span class="text-[9px] text-gray-600 ml-1">(' + esc(tab.language) + ')</span>'
    + '<span id="editor-line-info-' + tabId + '" class="ml-auto text-[9px] text-gray-600">Ln 1, Col 1</span>'
    + '<span id="editor-save-status-' + tabId + '" class="text-[9px] text-green-400/70"></span>'
    + '<button onclick="saveEditorTab(\'' + tabId + '\')" class="text-[10px] px-2.5 py-0.5 rounded bg-orange-600 hover:bg-orange-700 text-white">'
    + '<i class="fas fa-save mr-1"></i>Save</button>'
    + '<span class="text-[9px] text-gray-600">\u2318S</span>'
    + '</div>'
    + '<textarea id="editor-textarea-' + tabId + '" '
    + 'class="editor-textarea flex-1 w-full resize-none outline-none font-mono text-[12px] leading-5 p-4" '
    + 'style="background:rgba(6,9,18,0.9);color:var(--text);tab-size:4;border:none;" '
    + 'spellcheck="false" '
    + 'oninput="markEditorDirty(\'' + tabId + '\')" '
    + 'onkeydown="handleEditorKeydown(event,\'' + tabId + '\')" '
    + 'onkeyup="_updateEditorLineInfo(\'' + tabId + '\')" '
    + 'onclick="_updateEditorLineInfo(\'' + tabId + '\')">'
    + '</textarea>';
  container.appendChild(pane);
  var textarea = document.getElementById('editor-textarea-' + tabId);
  if (textarea) textarea.value = tab.content;
}

function markEditorDirty(tabId) {
  var tab = _editorTabs[tabId];
  if (!tab) return;
  var ta = document.getElementById('editor-textarea-' + tabId);
  if (!ta) return;
  var wasDirty = tab.dirty;
  tab.dirty = ta.value !== tab.originalContent;
  tab.content = ta.value;
  if (tab.dirty !== wasDirty) renderEditorTabBar();
}

function _updateEditorLineInfo(tabId) {
  var ta = document.getElementById('editor-textarea-' + tabId);
  var info = document.getElementById('editor-line-info-' + tabId);
  if (!ta || !info) return;
  var pos = ta.selectionStart;
  var text = ta.value.substring(0, pos);
  var line = (text.match(/\n/g) || []).length + 1;
  var lastNl = text.lastIndexOf('\n');
  var col = pos - (lastNl >= 0 ? lastNl : 0);
  info.textContent = 'Ln ' + line + ', Col ' + col;
}

function handleEditorKeydown(event, tabId) {
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault();
    saveEditorTab(tabId);
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'w') {
    event.preventDefault();
    closeEditorTab(tabId);
    return;
  }
  if (event.key === 'Tab' && !event.shiftKey) {
    event.preventDefault();
    var ta = document.getElementById('editor-textarea-' + tabId);
    if (!ta) return;
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    ta.value = ta.value.substring(0, start) + '  ' + ta.value.substring(end);
    ta.selectionStart = ta.selectionEnd = start + 2;
    markEditorDirty(tabId);
  }
}

async function saveEditorTab(tabId) {
  var tab = _editorTabs[tabId];
  if (!tab) return;
  var ta = document.getElementById('editor-textarea-' + tabId);
  if (ta) tab.content = ta.value;
  var statusEl = document.getElementById('editor-save-status-' + tabId);
  if (statusEl) statusEl.textContent = 'Saving...';
  try {
    var apiKey = localStorage.getItem('maggy-api-key') || '';
    var headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;
    var resp = await fetch(API + '/editor/write', {
      method: 'POST', headers: headers,
      body: JSON.stringify({ path: tab.filePath, content: tab.content }),
    });
    if (!resp.ok) {
      var errText = await resp.text();
      if (statusEl) { statusEl.textContent = 'Save failed'; statusEl.className = 'text-[9px] text-red-400'; }
      return;
    }
    tab.originalContent = tab.content;
    tab.dirty = false;
    renderEditorTabBar();
    if (statusEl) {
      statusEl.textContent = 'Saved';
      statusEl.className = 'text-[9px] text-green-400/70';
      setTimeout(function() { statusEl.textContent = ''; }, 2000);
    }
  } catch (e) {
    if (statusEl) { statusEl.textContent = 'Error: ' + e.message; statusEl.className = 'text-[9px] text-red-400'; }
  }
}

function closeEditorTab(tabId) {
  var tab = _editorTabs[tabId];
  if (!tab) return;
  if (tab.dirty && !confirm('Unsaved changes in ' + tab.fileName + '. Close anyway?')) return;
  // Remove pane DOM
  var pane = document.getElementById('editor-pane-' + tabId);
  if (pane) pane.remove();
  // Remove state
  delete _editorTabs[tabId];
  var idx = _editorTabOrder.indexOf(tabId);
  if (idx >= 0) _editorTabOrder.splice(idx, 1);
  // Switch to previous tab or Chat
  if (_activeEditorTab === tabId) {
    var nextTab = _editorTabOrder.length ? _editorTabOrder[_editorTabOrder.length - 1] : '__chat__';
    switchEditorTab(nextTab);
  } else {
    renderEditorTabBar();
  }
}

async function openFileInEditor(filePathArg) {
  var cwd = _getShellCwd();
  var filePath = filePathArg;
  if (filePath && filePath.charAt(0) !== '/' && filePath.charAt(0) !== '~') {
    filePath = (cwd || '') + '/' + filePath;
  }
  // Check if already open
  var tabId = _genTabId(filePath);
  if (_editorTabs[tabId]) { switchEditorTab(tabId); return; }
  // Fetch file
  try {
    var data = await api('/editor/read?path=' + encodeURIComponent(filePath) + (cwd ? '&cwd=' + encodeURIComponent(cwd) : ''));
    if (data.binary) {
      var outer = document.getElementById('chat-messages');
      var el = document.getElementById('chat-messages-inner') || outer;
      el.innerHTML += _renderTerminalOutput('open ' + filePathArg,
        filePath + ' is a binary file (' + (data.mime || 'unknown') + ', ' + data.size + ' bytes).\n'
        + 'Binary files cannot be opened in the editor.\n'
        + 'Use your local terminal instead.', 1, cwd);
      if (outer) outer.scrollTop = outer.scrollHeight;
      return;
    }
    if (data.too_large) {
      var outer = document.getElementById('chat-messages');
      var el = document.getElementById('chat-messages-inner') || outer;
      el.innerHTML += _renderTerminalOutput('open ' + filePathArg,
        filePath + ' is too large (' + (data.size / 1024).toFixed(0) + ' KB).\n'
        + 'Max editor size is 1 MB. Use head or tail to view parts.', 1, cwd);
      if (outer) outer.scrollTop = outer.scrollHeight;
      return;
    }
    var fileName = filePath.split('/').pop();
    _editorTabs[tabId] = {
      filePath: filePath, fileName: fileName,
      content: data.content || '', originalContent: data.content || '',
      dirty: false, cursorStart: 0, cursorEnd: 0, scrollTop: 0,
      language: data.language || 'plaintext', readOnly: false,
    };
    _editorTabOrder.push(tabId);
    renderEditorTabBar();
    _createEditorPane(tabId);
    switchEditorTab(tabId);
  } catch (e) {
    var outer = document.getElementById('chat-messages');
    var el = document.getElementById('chat-messages-inner') || outer;
    el.innerHTML += _renderTerminalOutput('open ' + filePathArg,
      'Failed to open: ' + e.message, 1, cwd);
    if (outer) outer.scrollTop = outer.scrollHeight;
  }
}

// Shell commands that go to backend /api/shell/exec
var _SHELL_PREFIXES = [
  'ls', 'll', 'la', 'pwd', 'cd', 'cat', 'head', 'tail', 'wc',
  'find', 'grep', 'rg', 'tree', 'file', 'stat', 'du', 'df',
  'whoami', 'date', 'echo', 'which', 'git', 'env', 'printenv',
  'uname', 'hostname',
];

// Known programs — recognized but blocked in web terminal (editors handled separately)
var _KNOWN_PROGRAMS = [
  'less', 'more', 'open',
  'python', 'python3', 'node', 'npm', 'npx', 'pip',
  'pip3', 'cargo', 'go', 'ruby', 'java', 'javac', 'gcc', 'g++',
  'docker', 'docker-compose', 'kubectl', 'terraform',
  'make', 'cmake', 'man', 'top', 'htop', 'ps',
  'curl', 'wget', 'ssh', 'scp', 'rsync',
  'tar', 'zip', 'unzip', 'gzip', 'gunzip',
  'kill', 'killall', 'pkill', 'mv', 'cp', 'rm', 'mkdir', 'rmdir',
  'chmod', 'chown', 'chgrp', 'sudo', 'su',
  'brew', 'apt', 'apt-get', 'yum', 'dnf', 'pacman',
  'tmux', 'screen', 'nohup', 'watch', 'xargs', 'tee',
  'sed', 'awk', 'sort', 'uniq', 'cut', 'tr', 'diff', 'patch',
  'touch', 'ln', 'readlink', 'basename', 'dirname',
  'nc', 'nmap', 'ping', 'traceroute', 'dig', 'nslookup', 'ifconfig',
];

function _isShellCommand(msg) {
  if (!msg) return false;
  if (msg.charAt(0) === '/') return true;
  if (msg.charAt(0) === '!') return true;
  var first = msg.split(/\s/)[0];
  if (_CLIENT_COMMANDS[first]) return true;
  return false;
}

// ── Self-healing: fuzzy match + unknown command handling ──────────────
function _levenshtein(a, b) {
  var m = a.length, n = b.length;
  var dp = [];
  for (var i = 0; i <= m; i++) {
    dp[i] = [i];
    for (var j = 1; j <= n; j++) dp[i][j] = i === 0 ? j : 0;
  }
  for (var i = 1; i <= m; i++) {
    for (var j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[m][n];
}

function _looksLikeCommand(msg) {
  return false;
}

async function _handleUnknownCommand(cmd) {
  var outer = document.getElementById('chat-messages');
  var el = document.getElementById('chat-messages-inner') || outer;
  var first = cmd.split(/\s/)[0];
  var cwd = _getShellCwd();

  el.innerHTML += _renderTerminalPrompt(cmd, cwd);

  var msg = "'" + first + "' is not a recognized command.\n\n";

  // Fuzzy-match against all known commands
  var allCmds = _SHELL_PREFIXES
    .concat(Object.keys(_SLASH_COMMANDS).map(function(s) { return s.slice(1); }))
    .concat(Object.keys(_CLIENT_COMMANDS));
  var suggestions = allCmds.filter(function(c) {
    return c.indexOf(first) >= 0 || first.indexOf(c) >= 0
      || _levenshtein(c, first) <= 2;
  });
  // Deduplicate
  var seen = {};
  suggestions = suggestions.filter(function(s) {
    if (seen[s]) return false;
    seen[s] = true;
    return true;
  });

  if (suggestions.length) {
    msg += 'Did you mean: ' + suggestions.slice(0, 5).join(', ') + '?\n\n';
  }
  msg += 'Type "help" for available commands.\n';
  msg += 'Or type naturally to chat with AI.';

  el.innerHTML += _renderTerminalOutput(cmd, msg, 127, cwd);
  if (outer) outer.scrollTop = outer.scrollHeight;
}

function _renderTerminalOutput(cmd, output, exitCode, cwd) {
  var exitClass = exitCode === 0 ? 'text-green-500' : 'text-red-400';
  var cwdShort = cwd ? cwd.replace(/^\/Users\/[^/]+/, '~') : '';
  return '<div class="flex justify-start"><div class="w-full max-w-[90%]">'
    + '<div class="flex items-center gap-2 mb-1">'
    + '<span class="text-[9px] text-gray-600">' + esc(cwdShort) + '</span>'
    + '<span class="text-[9px] ' + exitClass + '">' + (exitCode === 0 ? '✓' : '✗ ' + exitCode) + '</span>'
    + '</div>'
    + '<pre class="text-[11px] text-gray-300 bg-black/30 rounded-md px-3 py-2 overflow-x-auto border border-gray-800/50" style="white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto">'
    + esc(output || '(no output)')
    + '</pre></div></div>';
}

function _renderTerminalPrompt(cmd, cwd) {
  var cwdShort = cwd ? cwd.replace(/^\/Users\/[^/]+/, '~') : '$';
  return '<div class="flex justify-end"><div class="max-w-[75%]">'
    + '<div class="flex items-center gap-1.5 bg-gray-800/60 rounded-md px-3 py-1.5 border border-gray-700/40">'
    + '<span class="text-[10px] text-orange-400/70 font-mono">' + esc(cwdShort) + '</span>'
    + '<span class="text-[10px] text-gray-500">$</span>'
    + '<span class="text-[11px] text-gray-200 font-mono">' + esc(cmd) + '</span>'
    + '</div></div></div>';
}

function _renderSlashPrompt(cmd) {
  return '<div class="flex justify-end"><div class="max-w-[75%]">'
    + '<div class="flex items-center gap-1.5 bg-purple-900/30 rounded-md px-3 py-1.5 border border-purple-700/30">'
    + '<i class="fas fa-terminal text-[9px] text-purple-400/70"></i>'
    + '<span class="text-[11px] text-purple-300 font-mono">' + esc(cmd) + '</span>'
    + '</div></div></div>';
}

function _renderSlashOutput(text, isError) {
  var borderCls = isError ? 'border-red-800/40' : 'border-purple-800/30';
  var bgCls = isError ? 'bg-red-950/20' : 'bg-purple-950/15';
  return '<div class="flex justify-start"><div class="w-full max-w-[90%]">'
    + '<pre class="text-[11px] text-gray-300 ' + bgCls + ' rounded-md px-3 py-2 overflow-x-auto border ' + borderCls + '" style="white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto">'
    + esc(text || '(no output)')
    + '</pre></div></div>';
}

async function _execShellCommand(cmd) {
  var directShell = cmd.charAt(0) === '!' && cmd.charAt(1) !== '!';
  if (directShell) {
    cmd = cmd.slice(1).trim();
    if (!cmd) return;
  }

  // Expand aliases
  var expanded = cmd;
  if (expanded === 'll') expanded = 'ls -la';
  else if (expanded === 'la') expanded = 'ls -A';

  var cwd = _getShellCwd();
  var outer = document.getElementById('chat-messages');
  var el = document.getElementById('chat-messages-inner') || outer;

  // Slash commands — async, fetch data from API
  if (cmd.charAt(0) === '/') {
    var parts = cmd.split(/\s+/);
    var slashCmd = parts[0].toLowerCase();
    var slashArgs = parts.slice(1).join(' ');
    var handler = _SLASH_COMMANDS[slashCmd];
    if (!handler) {
      el.innerHTML += _renderSlashPrompt(cmd);
      var slashKeys = Object.keys(_SLASH_COMMANDS);
      var slashSuggestions = slashKeys.filter(function(k) {
        return k.indexOf(slashCmd) >= 0 || slashCmd.indexOf(k) >= 0
          || _levenshtein(k, slashCmd) <= 3;
      });
      var errMsg = 'Unknown command: ' + slashCmd;
      if (slashSuggestions.length) {
        errMsg += '\nDid you mean: ' + slashSuggestions.join(', ') + '?';
      }
      errMsg += '\nType /help for available commands.';
      el.innerHTML += _renderSlashOutput(errMsg, true);
      if (outer) outer.scrollTop = outer.scrollHeight;
      return;
    }
    el.innerHTML += _renderSlashPrompt(cmd);
    if (outer) outer.scrollTop = outer.scrollHeight;
    try {
      var result = await handler(slashArgs);
      el.innerHTML += _renderSlashOutput(result, false);
    } catch (e) {
      el.innerHTML += _renderSlashOutput('Error: ' + e.message, true);
    }
    if (outer) outer.scrollTop = outer.scrollHeight;
    return;
  }

  // Check sync client-side commands
  var first = cmd.split(/\s/)[0];
  if (_CLIENT_COMMANDS[first]) {
    var result = _CLIENT_COMMANDS[first]();
    if (result === null) return;
    el.innerHTML += _renderTerminalPrompt(cmd, cwd);
    el.innerHTML += _renderTerminalOutput(cmd, result, 0, cwd);
    if (outer) outer.scrollTop = outer.scrollHeight;
    return;
  }

  // Editor programs — open in-browser editor tab (skip for !-prefixed)
  if (!directShell && _EDITOR_PROGRAMS.indexOf(first) >= 0) {
    var filePath = cmd.split(/\s+/).slice(1).join(' ').trim();
    if (!filePath) {
      el.innerHTML += _renderTerminalPrompt(cmd, cwd);
      el.innerHTML += _renderTerminalOutput(cmd,
        'Usage: ' + first + ' <filename>\nOpens the file in the browser editor tab.', 1, cwd);
      if (outer) outer.scrollTop = outer.scrollHeight;
      return;
    }
    el.innerHTML += _renderTerminalPrompt(cmd, cwd);
    el.innerHTML += _renderTerminalOutput(cmd, 'Opening ' + filePath + ' in editor...', 0, cwd);
    if (outer) outer.scrollTop = outer.scrollHeight;
    await openFileInEditor(filePath);
    return;
  }

  // Show prompt
  el.innerHTML += _renderTerminalPrompt(cmd, cwd);
  if (outer) outer.scrollTop = outer.scrollHeight;

  try {
    var apiKey = localStorage.getItem('maggy-api-key') || '';
    var headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers['X-API-Key'] = apiKey;
    var payload = { command: expanded };
    if (cwd) payload.cwd = cwd;
    var resp = await fetch(API + '/shell/exec', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      var errText = await resp.text();
      el.innerHTML += _renderTerminalOutput(expanded, 'API error ' + resp.status + ': ' + errText, 1, cwd);
    } else {
      var data = await resp.json();
      var exitCode = typeof data.exit_code === 'number' ? data.exit_code : 0;
      if (data.cwd) _setShellCwd(data.cwd);
      el.innerHTML += _renderTerminalOutput(expanded, data.output || '', exitCode, data.cwd || cwd);
    }
  } catch (e) {
    el.innerHTML += _renderTerminalOutput(expanded, 'Error: ' + e.message, 1, cwd);
  }
  if (outer) outer.scrollTop = outer.scrollHeight;
}

// ── Chat message send ──────────────────────────────────────────────────
async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  let message = input.value.trim();
  if (!message && !_pendingFiles.length) return;
  if (!CHAT_SESSION_ID) return;

  // Check if it's a CLI command (no file attachments)
  if (!_pendingFiles.length && _isShellCommand(message)) {
    input.value = '';
    input.style.height = 'auto';
    await _execShellCommand(message);
    input.focus();
    refreshSuggestion();
    return;
  }

  // Self-healing: intercept command-like input before AI chat
  if (!_pendingFiles.length && _looksLikeCommand(message)) {
    input.value = '';
    input.style.height = 'auto';
    await _handleUnknownCommand(message);
    input.focus();
    return;
  }

  if (_pendingFiles.length) {
    try {
      const paths = await _uploadFiles();
      const refs = paths.map(p => `[Attached file: ${p}]`).join('\n');
      message = refs + (message ? '\n\n' + message : '\nAnalyze the attached file(s).');
    } catch (e) {
      alert('Upload failed: ' + e.message);
      return;
    }
  }
  if (!message) return;
  _chatHistory.push(message);
  if (_chatHistory.length > 10) _chatHistory.shift();
  input.value = '';
  input.disabled = true;
  const ghost = document.getElementById('chat-ghost');
  if (ghost) ghost.textContent = '';
  // Finalize any previous streaming response before starting new one
  const prevStream = document.getElementById('stream-response');
  if (prevStream) prevStream.removeAttribute('id');
  const prevText = document.getElementById('stream-text');
  if (prevText) prevText.removeAttribute('id');
  const prevTools = document.getElementById('stream-tools');
  if (prevTools) prevTools.removeAttribute('id');
  const outer = document.getElementById('chat-messages');
  const el = document.getElementById('chat-messages-inner') || outer;
  el.innerHTML += renderUserMsg({ content: message, timestamp: '' });
  el.innerHTML += `<div id="stream-response" class="flex justify-start min-w-0"><div class="max-w-[75%] min-w-0 card px-3 py-2 overflow-hidden">
    <div id="stream-text" class="text-xs text-gray-300 chat-md overflow-hidden"></div>
    <div id="stream-tools" class="mt-1 overflow-hidden"></div>
  </div></div>`;
  if (outer) outer.scrollTop = outer.scrollHeight;
  showWorking();
  _streamingActive = true;
  try {
    await streamChatResponse(message, outer);
  } catch (e) {
    const streamEl = document.getElementById('stream-text');
    if (streamEl) streamEl.innerHTML = `<span class="text-red-400">Error: ${esc(e.message)}</span>`;
  }
  _streamingActive = false;
  hideWorking();
  input.disabled = false;
  input.style.height = 'auto';
  input.focus();
  refreshSuggestion();
}

async function streamChatResponse(message, el) {
  const apiKey = localStorage.getItem('maggy-api-key') || '';
  const headers = { 'Content-Type': 'application/json', ...(apiKey ? { 'X-API-Key': apiKey } : {}) };
  let resp = await fetch(`${API}/chat/sessions/${CHAT_SESSION_ID}/send-routed`, {
    method: 'POST', headers, body: JSON.stringify({ message }),
  });
  if (!resp.ok) {
    resp = await fetch(`${API}/chat/sessions/${CHAT_SESSION_ID}/send`, {
      method: 'POST', headers, body: JSON.stringify({ message }),
    });
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let responseText = '';
  const streamEl = document.getElementById('stream-text');
  const toolsEl = document.getElementById('stream-tools');
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const line of chunk.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'done') continue;
        if (data.type === 'routing') {
          CURRENT_MODEL = data.model || '';
          updateModelLabel(data.model, data.blast, data.task_type);
          continue;
        }
        if (data.type === 'error') { streamEl.innerHTML = `<span class="text-red-400">${esc(data.content)}</span>`; continue; }
        if (data.type === 'tool_use' && toolsEl) {
          var tool = data.tool || data.content || 'tool';
          var toolInput = data.input ? JSON.stringify(data.input).substring(0, 200) : '';
          // Group all same-type tools within this turn into one collapsible
          // card, even when other event types (agent_status, protocol_step)
          // arrive between them.
          var groupSel = '[data-tool-group="' + tool.replace(/"/g, '\\"') + '"]';
          var existingGroup = toolsEl.querySelector(groupSel);
          if (existingGroup) {
            var body = existingGroup.querySelector('.tool-group-body');
            var countEl = existingGroup.querySelector('.tool-group-count');
            if (body) {
              var entry = document.createElement('div');
              entry.className = 'py-1 border-t border-gray-800/40';
              entry.innerHTML = '<div class="tool-detail mt-1 p-1 text-[9px] font-mono text-gray-600 truncate">' + esc(toolInput) + '</div>';
              body.appendChild(entry);
            }
            if (countEl) {
              var n = parseInt(countEl.textContent.replace(/[()]/g, ''), 10) || 1;
              countEl.textContent = '(' + (n + 1) + ')';
            }
          } else {
            var groupId = 'tool-group-' + tool.replace(/[^a-zA-Z0-9]/g, '_') + '-' + Date.now();
            var groupHtml = '<div id="' + groupId + '" data-tool-group="' + esc(tool) + '" class="card p-1.5 my-1 cursor-pointer" onclick="var b=this.querySelector(\'.tool-group-body\'),c=this.querySelector(\'.tool-chevron\');if(b){b.classList.toggle(\'hidden\');c.classList.toggle(\'fa-chevron-down\');c.classList.toggle(\'fa-chevron-up\');}"><div class="flex items-center gap-1.5 text-[10px] text-gray-500"><i class="fas fa-wrench text-orange-400/50"></i><span class="text-orange-400/60">' + esc(tool) + '</span><span class="tool-group-count text-[9px] text-gray-600">(1)</span><i class="tool-chevron fas fa-chevron-down text-[7px] ml-auto text-gray-600"></i></div><div class="tool-group-body hidden mt-1"><div class="py-1"><div class="tool-detail p-1 text-[9px] font-mono text-gray-600 truncate">' + esc(toolInput) + '</div></div></div></div>';
            toolsEl.insertAdjacentHTML('beforeend', groupHtml);
          }
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.type === 'agent_status' && toolsEl) {
          toolsEl.innerHTML += `<div class="text-[10px] text-blue-400/70"><i class="fas fa-info-circle mr-1"></i>${esc(data.status || data.content || '')}</div>`;
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.type === 'protocol_step' && toolsEl) {
          var stepId = 'proto-step-' + (data.step || '');
          var existing = toolsEl.querySelector('#' + stepId);
          var icon = '⏳', color = 'text-gray-400';
          if (data.status === 'done') { icon = '✅'; color = 'text-green-400'; }
          else if (data.status === 'failed') { icon = '❌'; color = 'text-red-400'; }
          else if (data.status === 'skipped') { icon = '⏭️'; color = 'text-gray-500'; }
          else if (data.status === 'warning') { icon = '⚠️'; color = 'text-yellow-400'; }
          var stepHtml = '<div id="' + stepId + '" class="p-1.5 my-1 cursor-pointer" onclick="var d=this.querySelector(\'.step-output\');if(d)d.classList.toggle(\'hidden\')">'
            + '<div class="flex items-center gap-1.5 text-[11px] ' + color + '">'
            + '<span>' + icon + '</span>'
            + '<span class="font-medium">' + esc(data.label || data.step) + '</span>'
            + '<span class="text-[9px] text-gray-600 ml-auto">' + esc(data.status) + '</span>'
            + '</div>';
          if (data.output) {
            stepHtml += '<pre class="step-output hidden mt-1 p-1.5 text-[9px] font-mono text-gray-500 rounded overflow-x-auto" style="background:rgba(0,0,0,0.3);max-height:150px;overflow-y:auto">' + esc(data.output) + '</pre>';
          }
          stepHtml += '</div>';
          if (existing) { existing.outerHTML = stepHtml; } else { toolsEl.innerHTML += stepHtml; }
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.type === 'protocol_complete' && toolsEl) {
          toolsEl.innerHTML += '<div class="text-[11px] text-green-400 mt-2 p-1.5 border-t border-gray-700/50"><i class="fas fa-check-circle mr-1"></i>Protocol <strong>' + esc(data.protocol) + '</strong> completed</div>';
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.type === 'protocol_abort' && toolsEl) {
          toolsEl.innerHTML += '<div class="text-[11px] text-red-400 mt-2 p-1.5 border-t border-gray-700/50"><i class="fas fa-times-circle mr-1"></i>' + esc(data.reason) + '</div>';
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.content) {
          responseText += data.content;
          // Debounced markdown render during streaming
          const now = Date.now();
          if (now - _lastStreamRender > 300) {
            streamEl.innerHTML = renderMd(responseText);
            _lastStreamRender = now;
          } else {
            streamEl.textContent = responseText;
          }
          if (el) el.scrollTop = el.scrollHeight;
        }
      } catch {}
    }
  }
  if (responseText && streamEl) { streamEl.innerHTML = renderMd(responseText); }
  if (!responseText && streamEl) streamEl.textContent = '(no response)';
  if (el) el.scrollTop = el.scrollHeight;
  _lastResponse = responseText.slice(0, 500);
}

// ── Settings ────────────────────────────────────────────────────────────
async function loadSettings() {
  const pane = document.getElementById('pane-settings');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Detecting system…</div>`;
  try {
    const [sys, cfg] = await Promise.all([
      api('/system/status'),
      api('/config').catch(() => null),
    ]);
    let html = `<h2 class="text-sm font-bold text-white mb-3">System Setup</h2>`;

    // Routing via srooter — one-click enable
    html += `<div class="card p-4 mb-3" id="srooter-card">
      <div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-route mr-1"></i>Model Routing (srooter)</div>
      <div id="srooter-body" class="text-[10px] text-gray-600"><i class="fas fa-spinner fa-spin mr-1"></i>Checking…</div>
    </div>`;

    // Reviewer bot — GitHub token the council PR reviewer posts with
    html += `<div class="card p-4 mb-3" id="reviewbot-card">
      <div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-robot mr-1"></i>Reviewer Bot (PR review)</div>
      <div id="reviewbot-body" class="text-[10px] text-gray-600"><i class="fas fa-spinner fa-spin mr-1"></i>Checking…</div>
    </div>`;

    // AI Models section
    const clis = sys.clis || [];
    const installed = clis.filter(c => c.installed);
    const missing = clis.filter(c => !c.installed);
    html += `<div class="card p-4 mb-3">
      <div class="flex items-center gap-2 mb-2">
        <div class="text-[10px] text-gray-500 uppercase">AI Models (${installed.length}/${clis.length})</div>
        <span class="flex-1"></span>
        <button onclick="toggleAddModelForm()" class="btn btn-ghost text-[10px]" id="btn-add-model"><i class="fas fa-plus mr-1"></i>Add Model</button>
      </div>`;
    html += `<div class="flex flex-wrap gap-1.5 mb-3">`;
    for (const c of clis) {
      const color = c.installed ? 'text-green-400 border-green-900' : 'text-gray-600 border-gray-800';
      const icon = c.installed ? 'fa-check-circle' : 'fa-times-circle';
      html += `<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border ${color}" title="${esc(c.path || 'not found')}"><i class="fas ${icon}" style="font-size:8px"></i>${esc(c.name)}</span>`;
    }
    html += `</div>`;
    html += `<div id="add-model-form" class="hidden mb-3 p-3 rounded border" style="border-color:var(--border);background:var(--bg-secondary)">
        <div class="space-y-2">
          <input id="am-id" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="Model ID (e.g. my-llama)">
          <input id="am-label" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="Display name (e.g. Local Llama 3)">
          <select id="am-type" onchange="toggleAccessFields()" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
            <option value="cli">CLI Command</option>
            <option value="api">API Key</option>
          </select>
          <input id="am-cli" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="CLI command (e.g. ollama run llama3)">
          <input id="am-apikey" class="w-full px-2 py-1 rounded text-xs hidden" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="API key" type="password">
          <input id="am-apibase" class="w-full px-2 py-1 rounded text-xs hidden" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="API base URL (optional)">
          <div class="flex gap-2">
            <button onclick="submitAddModel()" class="btn btn-primary text-[10px] flex-1">Validate & Add</button>
            <button onclick="toggleAddModelForm()" class="btn btn-ghost text-[10px]">Cancel</button>
          </div>
          <div id="am-status" class="text-[10px] hidden"></div>
        </div>
      </div>`;
    html += `<div id="custom-models-list" class="space-y-1"></div>`;
    html += `</div>`;

    // Dev Tools section
    const tools = sys.tools || [];
    const cats = {};
    for (const t of tools) {
      const cat = t.category || 'other';
      if (!cats[cat]) cats[cat] = [];
      cats[cat].push(t);
    }
    const catLabels = {vcs: 'Version Control', pkg: 'Package Managers', lint: 'Linting', type: 'Type Checking', test: 'Testing', infra: 'Infrastructure', deploy: 'Deployment'};
    html += `<div class="card p-4 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2">Development Tools</div>`;
    for (const [cat, items] of Object.entries(cats)) {
      html += `<div class="mb-2"><div class="text-[9px] text-gray-600 uppercase mb-1">${esc(catLabels[cat] || cat)}</div><div class="flex flex-wrap gap-1.5">`;
      for (const t of items) {
        const color = t.installed ? 'text-green-400 border-green-900' : 'text-gray-600 border-gray-800';
        const icon = t.installed ? 'fa-check-circle' : 'fa-times-circle';
        html += `<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border ${color}" title="${esc(t.path || 'not found')}"><i class="fas ${icon}" style="font-size:8px"></i>${esc(t.name)}</span>`;
      }
      html += `</div></div>`;
    }
    html += `</div>`;

    // Model Health section
    html += `<div class="card p-4 mb-3">
      <div class="flex items-center gap-2 mb-2">
        <div class="text-[10px] text-gray-500 uppercase">Model Health</div>
        <span class="flex-1"></span>
        <button onclick="runModelHealthCheck()" class="btn btn-ghost text-[10px]" id="btn-health-check"><i class="fas fa-heartbeat mr-1"></i>Test All</button>
      </div>
      <div id="model-health-grid" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
        <div class="text-[10px] text-gray-600">Click "Test All" to check model availability</div>
      </div>
    </div>`;

    // Suggested Local Models section
    html += `<div class="card p-4 mb-3" id="local-models-card">
      <div class="flex items-center gap-2 mb-2">
        <div class="text-[10px] text-gray-500 uppercase">Suggested Local Models</div>
        <span class="flex-1"></span>
        <button onclick="loadLocalSuggestions()" class="btn btn-ghost text-[10px]" id="btn-scan-hw"><i class="fas fa-microchip mr-1"></i>Scan Hardware</button>
      </div>
      <div id="local-hw-summary" class="text-[10px] text-gray-600 mb-2"></div>
      <div id="local-models-list" class="space-y-1">
        <div class="text-[10px] text-gray-600">Click "Scan Hardware" to detect your system and get model recommendations</div>
      </div>
    </div>`;

    // Council Config section
    html += `<div class="card p-4 mb-3" id="council-config-card">
      <div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-users-gear mr-1"></i>Council of Experts</div>
      <div id="council-config-body" class="text-[10px] text-gray-600">Loading…</div>
    </div>`;

    // Editable Configuration
    if (cfg) {
      html += `<div class="card p-4 mb-3" id="config-card">
        <div class="flex items-center gap-2 mb-3">
          <div class="text-[10px] text-gray-500 uppercase"><i class="fas fa-cog mr-1"></i>Configuration</div>
          <span class="flex-1"></span>
          <span id="cfg-status" class="text-[10px] text-gray-600 hidden"></span>
        </div>
        <div class="grid grid-cols-2 gap-3 text-[11px]">
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">AI Provider</label>
            <input id="cfg-ai-provider" value="${esc(cfg.ai?.provider || '')}" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
          </div>
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">AI Model</label>
            <input id="cfg-ai-model" value="${esc(cfg.ai?.model || '')}" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
          </div>
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">Issue Tracker</label>
            <select id="cfg-tracker" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
              ${['github','asana','linear','monday','none'].map(t => `<option value="${t}" ${cfg.issue_tracker?.provider === t ? 'selected' : ''}>${t}</option>`).join('')}
            </select>
          </div>
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">Routing Mode</label>
            <select id="cfg-routing" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
              ${['dynamic','static','manual'].map(m => `<option value="${m}" ${cfg.routing?.mode === m ? 'selected' : ''}>${m}</option>`).join('')}
            </select>
          </div>
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">Daily Budget (USD)</label>
            <input id="cfg-budget" type="number" step="0.5" value="${cfg.budget?.daily_limit_usd ?? 10}" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
          </div>
          <div>
            <label class="text-[9px] text-gray-500 uppercase block mb-0.5">Dashboard Port</label>
            <input id="cfg-port" type="number" value="${cfg.dashboard?.port ?? 8080}" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)">
          </div>
        </div>
        <div class="flex gap-2 mt-3">
          <button onclick="saveConfig()" class="btn btn-primary text-[10px]"><i class="fas fa-save mr-1"></i>Save</button>
          <div class="flex-1"></div>
          <span class="text-[9px] text-gray-600 self-center">API Key: ${cfg.ai?.has_key ? '<span class="text-green-400">set (env)</span>' : '<span class="text-red-400">missing</span>'}</span>
        </div>
      </div>`;
    }

    pane.innerHTML = html;
    loadCustomModels();
    loadCouncilConfig();
    loadSrooterStatus();
    loadReviewBot();
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Detection failed: ${esc(e.message)}</div>`;
  }
}

// ---- srooter routing: one-click enable from Settings -----------------------

async function loadSrooterStatus() {
  const body = document.getElementById('srooter-body');
  if (!body) return;
  try {
    const s = await api('/srooter/status');
    body.innerHTML = renderSrooter(s);
  } catch (e) {
    body.innerHTML = `<span class="text-red-400">Status check failed: ${esc(e.message)}</span>`;
  }
}

function renderSrooter(s) {
  if (!s.installed) {
    return `<div class="text-gray-500">srooter routing isn't installed on this machine.</div>
      <a href="https://www.srooter.ai" target="_blank" class="text-orange-400 hover:underline">Get started at srooter.ai →</a>`;
  }
  if (s.enabled) {
    return `<div class="flex items-center gap-2 mb-2">
        <span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border text-green-400 border-green-900"><i class="fas fa-check-circle" style="font-size:8px"></i>Routed via srooter</span>
        <span class="text-gray-600">${esc(s.gateway || '')}</span>
      </div>
      <button onclick="disableSrooter()" class="btn btn-ghost text-[10px]" id="srooter-btn"><i class="fas fa-power-off mr-1"></i>Switch back to direct</button>`;
  }
  if (s.key_set) {
    return `<div class="text-gray-500 mb-2">Your srooter key is saved${s.gateway ? ' (' + esc(s.gateway) + ')' : ''}. Routing is currently off — turn it on with one click.</div>
      <div class="flex gap-2 items-center">
        <button onclick="enableSrooter(true)" class="btn btn-primary text-[10px]" id="srooter-btn"><i class="fas fa-bolt mr-1"></i>Turn on routing</button>
        <a href="#" onclick="event.preventDefault();showSrooterForm()" class="text-[9px] text-gray-500 hover:underline">Use a different key</a>
      </div>
      <div id="srooter-form" class="hidden mt-2"></div>
      <div id="srooter-msg" class="text-[10px] hidden mt-1"></div>`;
  }
  return srooterForm();
}

function srooterForm() {
  return `<div class="text-gray-500 mb-2">Route Claude, Codex &amp; more through the cheapest capable model. Paste your srooter key to enable.</div>
    <div class="space-y-2">
      <input id="srooter-key" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="srooter API key (srt_…)" type="password">
      <input id="srooter-url" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="Gateway URL (optional — defaults to api.srooter.ai)">
      <div class="flex gap-2 items-center">
        <button onclick="enableSrooter()" class="btn btn-primary text-[10px]" id="srooter-btn"><i class="fas fa-bolt mr-1"></i>Enable srooter</button>
        <a href="https://www.srooter.ai" target="_blank" class="text-[9px] text-gray-500 hover:underline">Need a key?</a>
      </div>
      <div id="srooter-msg" class="text-[10px] hidden"></div>
    </div>`;
}

function showSrooterForm() {
  const holder = document.getElementById('srooter-form');
  if (!holder) return;
  holder.innerHTML = srooterForm();
  holder.classList.remove('hidden');
}

async function enableSrooter(useStored) {
  const key = useStored ? '' : ((document.getElementById('srooter-key') || {}).value || '');
  const url = (document.getElementById('srooter-url') || {}).value || '';
  const btn = document.getElementById('srooter-btn');
  const msg = document.getElementById('srooter-msg');
  if (!useStored && !key.trim()) { srooterMsg(msg, 'Enter your srooter API key first.', true); return; }
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Enabling…'; }
  try {
    const s = await api('/srooter/enable', { method: 'POST', body: JSON.stringify({ api_key: key.trim(), gateway_url: url.trim() }) });
    document.getElementById('srooter-body').innerHTML = renderSrooter(s);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-bolt mr-1"></i>Enable srooter'; }
    srooterMsg(msg, e.message, true);
  }
}

async function disableSrooter() {
  const btn = document.getElementById('srooter-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Switching…'; }
  try {
    const s = await api('/srooter/disable', { method: 'POST' });
    document.getElementById('srooter-body').innerHTML = renderSrooter(s);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-power-off mr-1"></i>Switch back to direct'; }
  }
}

function srooterMsg(el, text, isErr) {
  if (!el) return;
  el.textContent = text;
  el.className = `text-[10px] ${isErr ? 'text-red-400' : 'text-green-400'}`;
}

// ---- PR Review: agentic council reviewer (maggy.review) --------------------

async function loadPrReview() {
  const pane = document.getElementById('pane-pr-review');
  if (!pane) return;
  pane.innerHTML = `<h2 class="text-sm font-bold text-white mb-3"><i class="fas fa-scale-balanced mr-1"></i>PR Review — agentic council</h2>
    <div id="prr-status" class="text-[10px] text-gray-500 mb-3"><i class="fas fa-spinner fa-spin mr-1"></i>Checking reviewer…</div>
    <div class="card p-4 mb-3">
      <div class="grid grid-cols-2 gap-3 text-[11px]">
        <div><label class="text-[9px] text-gray-500 uppercase block mb-0.5">Repo (owner/repo)</label>
          <input id="prr-repo" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="zenloopGmbH/surveys-backend"></div>
        <div><label class="text-[9px] text-gray-500 uppercase block mb-0.5">PR number</label>
          <input id="prr-num" type="number" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="525"></div>
        <div><label class="text-[9px] text-gray-500 uppercase block mb-0.5">GitHub token (optional — overrides default)</label>
          <input id="prr-token" type="password" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="ghp_… (blank = use configured/env)"></div>
        <div><label class="text-[9px] text-gray-500 uppercase block mb-0.5">Local checkout path (optional — enables static gate)</label>
          <input id="prr-path" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="~/Documents/…"></div>
      </div>
      <div class="flex gap-2 items-center mt-3">
        <label class="text-[10px] text-gray-400 flex items-center gap-1"><input type="checkbox" id="prr-dry" checked> Dry-run (don't post to GitHub)</label>
        <span class="flex-1"></span>
        <button onclick="runPrReview()" class="btn btn-primary text-[10px]" id="prr-btn"><i class="fas fa-play mr-1"></i>Run council</button>
      </div>
      <div id="prr-msg" class="text-[10px] hidden mt-2"></div>
    </div>
    <div id="prr-result"></div>`;
  loadPrReviewStatus();
}

async function loadPrReviewStatus() {
  const el = document.getElementById('prr-status');
  if (!el) return;
  try {
    const s = await api('/pr-review/status');
    if (!s.installed) {
      el.innerHTML = `<span class="text-yellow-500">Reviewer not installed.</span> ${esc(s.hint || '')}`;
      return;
    }
    const models = (s.models || []).join(', ') || 'none (set provider keys)';
    const tok = s.token_configured ? '<span class="text-green-400">token ✓</span>' : '<span class="text-red-400">no token</span>';
    el.innerHTML = `Models: <span class="text-gray-300">${esc(models)}</span> · ${tok} · ${(s.languages || []).length} languages`;
  } catch (e) {
    el.innerHTML = `<span class="text-red-400">Status failed: ${esc(e.message)}</span>`;
  }
}

async function runPrReview() {
  const repo = (document.getElementById('prr-repo').value || '').trim();
  const num = parseInt(document.getElementById('prr-num').value, 10);
  const msg = document.getElementById('prr-msg');
  if (!repo.includes('/') || !num) { prrMsg(msg, 'Enter owner/repo and a PR number.', true); return; }
  const [owner, name] = repo.split('/', 2);
  const body = {
    owner: owner, repo: name, pr_number: num,
    dry_run: document.getElementById('prr-dry').checked,
    github_token: (document.getElementById('prr-token').value || '').trim() || null,
    repo_path: (document.getElementById('prr-path').value || '').trim() || null
  };
  const btn = document.getElementById('prr-btn');
  btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Reviewing… (may take a minute)';
  if (msg) msg.classList.add('hidden');
  try {
    const r = await api('/pr-review/run', { method: 'POST', body: JSON.stringify(body) });
    document.getElementById('prr-result').innerHTML = renderPrReview(r);
  } catch (e) {
    prrMsg(msg, e.message, true);
  } finally {
    btn.disabled = false; btn.innerHTML = '<i class="fas fa-play mr-1"></i>Run council';
  }
}

function renderPrReview(r) {
  const ok = r.decision === 'approve';
  const badge = ok ? '<span class="text-green-400">✅ Approve</span>' : '<span class="text-red-400">🛑 Changes requested</span>';
  const cost = r.cost ? `~$${(r.cost.total_usd || 0).toFixed(3)}` : '';
  let h = `<div class="card p-4">
    <div class="flex items-center gap-2 mb-2 text-[11px]">${badge}
      <span class="text-gray-600">blast ${esc(String(r.blast_radius || '?'))} · ${(r.findings || []).length} findings · ${esc(cost)}${r.dry_run ? ' · dry-run' : ''}</span></div>
    <div class="text-[11px] text-gray-300 mb-3">${esc(r.summary || '')}</div>`;
  for (const f of (r.findings || [])) {
    const tag = f.severity === 'blocking' ? '🔴' : '🟡';
    h += `<div class="mb-2 p-2 rounded" style="background:var(--bg-secondary)">
      <div class="text-[11px] text-white">${tag} <span class="text-gray-400">${esc(f.file || '')}${f.line ? ':' + f.line : ''}</span> — <b>${esc(f.title || '')}</b></div>
      <div class="text-[10px] text-gray-400 mt-0.5">${esc(f.detail || '')}</div></div>`;
  }
  if (r.logs && r.logs.length) {
    h += `<details class="mt-2"><summary class="text-[10px] text-gray-500 cursor-pointer">Run log (${r.logs.length})</summary>
      <pre class="text-[9px] text-gray-500 mt-1 whitespace-pre-wrap">${esc(r.logs.join('\n'))}</pre></details>`;
  }
  return h + '</div>';
}

function prrMsg(el, text, isErr) {
  if (!el) return;
  el.textContent = text;
  el.className = `text-[10px] ${isErr ? 'text-red-400' : 'text-green-400'}`;
  el.classList.remove('hidden');
}

// ---- Reviewer bot token (Settings) -----------------------------------------

async function loadReviewBot() {
  const body = document.getElementById('reviewbot-body');
  if (!body) return;
  try {
    const c = await api('/pr-review/config');
    body.innerHTML = renderReviewBot(c);
  } catch (e) {
    body.innerHTML = `<span class="text-red-400">Failed: ${esc(e.message)}</span>`;
  }
}

function renderReviewBot(c) {
  let state;
  if (c.token_set) state = `<span class="text-green-400">Bot token set (${esc(c.token_hint)})</span> — reviews post as the bot.`;
  else if (c.uses_env_fallback) state = `<span class="text-yellow-500">Using your <code>GITHUB_TOKEN</code> env</span> — reviews post as you (self-review → comment only).`;
  else state = `<span class="text-red-400">No token</span> — set one below or export <code>GITHUB_TOKEN</code>.`;
  return `<div class="text-gray-400 mb-2">${state}</div>
    <div class="text-gray-600 mb-2">Use a dedicated bot account's <a href="https://github.com/settings/tokens/new?scopes=repo&description=maggy-reviewer" target="_blank" class="text-orange-400 hover:underline">Personal Access Token (repo scope)</a> so reviews come from the bot, not you.</div>
    <div class="space-y-2">
      <input id="rb-token" type="password" class="w-full px-2 py-1 rounded text-xs" style="background:var(--bg-card);color:var(--text);border:1px solid var(--border)" placeholder="ghp_… bot token (blank = leave unchanged)">
      <label class="text-[10px] text-gray-400 flex items-center gap-1"><input type="checkbox" id="rb-dry" ${c.default_dry_run ? 'checked' : ''}> Default new reviews to dry-run (don't post)</label>
      <div class="flex gap-2 items-center">
        <button onclick="saveReviewBot()" class="btn btn-primary text-[10px]" id="rb-btn"><i class="fas fa-save mr-1"></i>Save</button>
        ${c.token_set ? '<button onclick="clearReviewBot()" class="btn btn-ghost text-[10px]"><i class="fas fa-trash mr-1"></i>Clear (use env)</button>' : ''}
        <span id="rb-msg" class="text-[10px] hidden"></span>
      </div>
    </div>`;
}

async function saveReviewBot() {
  const tok = (document.getElementById('rb-token') || {}).value || '';
  const dry = document.getElementById('rb-dry').checked;
  const btn = document.getElementById('rb-btn');
  const msg = document.getElementById('rb-msg');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Saving…'; }
  try {
    const c = await api('/pr-review/config', { method: 'POST', body: JSON.stringify({ github_token: tok.trim() || null, default_dry_run: dry }) });
    document.getElementById('reviewbot-body').innerHTML = renderReviewBot(c);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-save mr-1"></i>Save'; }
    prrMsg(msg, e.message, true);
  }
}

async function clearReviewBot() {
  try {
    const c = await api('/pr-review/config', { method: 'POST', body: JSON.stringify({ clear_token: true }) });
    document.getElementById('reviewbot-body').innerHTML = renderReviewBot(c);
  } catch (e) { /* leave UI as-is on error */ }
}

async function runModelHealthCheck() {
  const grid = document.getElementById('model-health-grid');
  const btn = document.getElementById('btn-health-check');
  if (!grid) return;
  grid.innerHTML = '<div class="col-span-full text-[10px] text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Testing all models…</div>';
  if (btn) btn.disabled = true;
  try {
    const data = await api('/models/health', { method: 'POST' });
    const results = data.results || [];
    let html = '';
    for (const r of results) {
      const ok = r.success;
      const border = ok ? 'border-green-900' : 'border-red-900/50';
      const icon = ok ? 'fa-check-circle text-green-400' : 'fa-times-circle text-red-400';
      const latency = ok ? `<span class="text-gray-600">${r.latency_ms}ms</span>` : `<span class="text-red-400 truncate">${esc(r.error).slice(0, 30)}</span>`;
      html += `<div class="flex items-center gap-1.5 px-2 py-1.5 rounded border ${border} text-[11px]">
        <i class="fas ${icon}" style="font-size:8px"></i>
        <span style="color:var(--text)" class="flex-1 truncate">${esc(r.model_id)}</span>
        ${latency}
      </div>`;
    }
    grid.innerHTML = html || '<div class="text-[10px] text-gray-600">No models configured</div>';
  } catch (e) {
    grid.innerHTML = `<div class="text-[10px] text-red-400">Failed: ${esc(e.message)}</div>`;
  }
  if (btn) btn.disabled = false;
}

function toggleAddModelForm() {
  const form = document.getElementById('add-model-form');
  if (form) form.classList.toggle('hidden');
}

function toggleAccessFields() {
  const type = document.getElementById('am-type')?.value;
  const cli = document.getElementById('am-cli');
  const key = document.getElementById('am-apikey');
  const base = document.getElementById('am-apibase');
  if (type === 'api') {
    if (cli) cli.classList.add('hidden');
    if (key) key.classList.remove('hidden');
    if (base) base.classList.remove('hidden');
  } else {
    if (cli) cli.classList.remove('hidden');
    if (key) key.classList.add('hidden');
    if (base) base.classList.add('hidden');
  }
}

async function submitAddModel() {
  const status = document.getElementById('am-status');
  const id = document.getElementById('am-id')?.value?.trim();
  const label = document.getElementById('am-label')?.value?.trim();
  const type = document.getElementById('am-type')?.value;
  const cli = document.getElementById('am-cli')?.value?.trim();
  const key = document.getElementById('am-apikey')?.value?.trim();
  const base = document.getElementById('am-apibase')?.value?.trim();
  if (!id || !label) {
    if (status) { status.className = 'text-[10px] text-red-400'; status.textContent = 'Model ID and name required'; status.classList.remove('hidden'); }
    return;
  }
  if (status) { status.className = 'text-[10px] text-yellow-400'; status.textContent = 'Validating…'; status.classList.remove('hidden'); }
  try {
    const vr = await api('/models/check/validate', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ access_type: type, cli_cmd: cli || '', api_key: key || '', api_base: base || '' }) });
    if (!vr.valid) {
      if (status) { status.className = 'text-[10px] text-red-400'; status.textContent = vr.error || 'Validation failed'; }
      return;
    }
    const ar = await api('/models', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ model_id: id, label: label, access_type: type, cli_cmd: cli || '', api_key: key || '', api_base: base || '' }) });
    if (!ar.ok) {
      if (status) { status.className = 'text-[10px] text-red-400'; status.textContent = ar.error || 'Add failed'; }
      return;
    }
    if (status) { status.className = 'text-[10px] text-green-400'; status.textContent = 'Added!'; }
    toggleAddModelForm();
    loadCustomModels();
  } catch (e) {
    if (status) { status.className = 'text-[10px] text-red-400'; status.textContent = e.message; }
  }
}

async function removeCustomModel(id) {
  if (!confirm(`Remove model "${id}"?`)) return;
  try {
    const r = await api(`/models/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (!r.ok) { alert(r.error || 'Remove failed'); return; }
    loadCustomModels();
  } catch (e) { alert(e.message); }
}

async function loadCustomModels() {
  const list = document.getElementById('custom-models-list');
  if (!list) return;
  try {
    const data = await api('/models');
    const custom = (data.models || []).filter(m => m.custom);
    if (!custom.length) {
      list.innerHTML = '<div class="text-[10px] text-gray-600">No custom models added yet</div>';
      return;
    }
    let html = '';
    for (const m of custom) {
      html += `<div class="flex items-center gap-2 px-2 py-1.5 rounded border text-[11px]" style="border-color:var(--border)">
        <i class="fas fa-robot text-purple-400" style="font-size:9px"></i>
        <span style="color:var(--text)" class="flex-1 truncate">${esc(m.label || m.id)}</span>
        <span class="text-gray-600">tier ${m.tier}</span>
        <button onclick="removeCustomModel('${esc(m.id)}')" class="text-red-400 hover:text-red-300" title="Remove"><i class="fas fa-trash" style="font-size:9px"></i></button>
      </div>`;
    }
    list.innerHTML = html;
  } catch (e) {
    list.innerHTML = `<div class="text-[10px] text-red-400">${esc(e.message)}</div>`;
  }
}

async function saveConfig() {
  const status = document.getElementById('cfg-status');
  if (status) { status.textContent = 'Saving…'; status.classList.remove('hidden'); }
  try {
    const body = {
      ai: {
        provider: document.getElementById('cfg-ai-provider')?.value || '',
        model: document.getElementById('cfg-ai-model')?.value || ''
      },
      issue_tracker: { provider: document.getElementById('cfg-tracker')?.value || 'github' },
      routing: { mode: document.getElementById('cfg-routing')?.value || 'dynamic' },
      budget: { daily_limit_usd: parseFloat(document.getElementById('cfg-budget')?.value) || 10 },
      dashboard: { port: parseInt(document.getElementById('cfg-port')?.value) || 8080 }
    };
    await api('/config', { method: 'PATCH', body: JSON.stringify(body) });
    if (status) { status.textContent = 'Saved ✓'; status.style.color = 'var(--green)'; }
    setTimeout(() => { if (status) status.classList.add('hidden'); }, 2000);
  } catch (e) {
    if (status) { status.textContent = 'Error: ' + e.message; status.style.color = 'var(--red)'; }
  }
}

async function loadLocalSuggestions() {
  const hw = document.getElementById('local-hw-summary');
  const list = document.getElementById('local-models-list');
  const btn = document.getElementById('btn-scan-hw');
  if (btn) btn.disabled = true;
  if (hw) hw.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Scanning…';
  if (list) list.innerHTML = '';
  try {
    const data = await api('/system/suggest-models');
    const h = data.hardware || {};
    const gpu = h.gpu || {};
    let hwHtml = `<span class="text-gray-400">RAM:</span> ${h.ram_gb}GB`;
    hwHtml += ` · <span class="text-gray-400">CPU:</span> ${h.cpu_cores} cores`;
    hwHtml += ` · <span class="text-gray-400">Disk:</span> ${h.disk_free_gb}GB free`;
    if (gpu.type !== 'none') hwHtml += ` · <span class="text-gray-400">GPU:</span> ${esc(gpu.name)} (${gpu.vram_gb}GB)`;
    hwHtml += ` · <span class="text-gray-400">Ollama:</span> ${h.ollama_installed ? '<span class="text-green-400">installed</span>' : '<span class="text-red-400">not found</span>'}`;
    if (hw) hw.innerHTML = hwHtml;
    const suggestions = data.suggestions || [];
    if (!suggestions.length) {
      if (list) list.innerHTML = '<div class="text-[10px] text-yellow-400">No models fit your hardware</div>';
    } else {
      let html = '';
      for (const s of suggestions) {
        const fitColor = s.fit === 'comfortable' ? 'text-green-400' : 'text-yellow-400';
        const fitIcon = s.fit === 'comfortable' ? 'fa-check-circle' : 'fa-exclamation-circle';
        html += `<div class="flex items-center gap-2 px-2 py-1.5 rounded border text-[11px]" style="border-color:var(--border)">
          <i class="fas ${fitIcon} ${fitColor}" style="font-size:9px"></i>
          <span style="color:var(--text)" class="truncate">${esc(s.label)}</span>
          <span class="text-gray-600 flex-shrink-0">${s.min_ram_gb}GB RAM · ${s.disk_gb}GB disk</span>
          <span class="text-gray-600 flex-shrink-0 truncate ml-auto" title="${esc(s.strengths)}">${esc(s.strengths)}</span>
        </div>`;
      }
      if (list) list.innerHTML = html;
    }
  } catch (e) {
    if (hw) hw.innerHTML = '';
    if (list) list.innerHTML = `<div class="text-[10px] text-red-400">${esc(e.message)}</div>`;
  }
  if (btn) btn.disabled = false;
}

async function loadCouncilConfig() {
  const body = document.getElementById('council-config-body');
  if (!body) return;
  try {
    const cfg = await api('/council/config');
    let html = `<div class="space-y-2">`;
    html += `<div class="flex items-center justify-between">
      <span class="text-xs text-gray-400">Enabled</span>
      <span class="text-xs ${cfg.enabled ? 'text-green-400' : 'text-red-400'}">${cfg.enabled ? 'Yes' : 'No'}</span>
    </div>`;
    html += `<div class="flex items-center justify-between">
      <span class="text-xs text-gray-400">Approval threshold</span>
      <span class="text-xs" style="color:var(--text)">${cfg.threshold} of N reviewers</span>
    </div>`;
    const flags = [
      ['Auto-validate plans', cfg.auto_validate_plans],
      ['Auto-review architecture', cfg.auto_review_architecture],
      ['Auto-review PRs', cfg.auto_review_prs],
    ];
    for (const [label, val] of flags) {
      html += `<div class="flex items-center justify-between">
        <span class="text-xs text-gray-400">${label}</span>
        <span class="text-xs ${val ? 'text-green-400' : 'text-gray-600'}">${val ? 'on' : 'off'}</span>
      </div>`;
    }
    const contexts = Object.entries(cfg.reviewers || {});
    if (contexts.length) {
      html += `<div class="mt-2 border-t pt-2" style="border-color:var(--border)">`;
      for (const [ctx, reviewers] of contexts) {
        const enabled = reviewers.filter(r => r.enabled);
        html += `<div class="text-[10px] text-gray-500 mt-1"><b>${esc(ctx)}</b>: ${enabled.map(r => esc(r.id)).join(', ') || 'none'}</div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = `<div class="text-[10px] text-gray-600">Council config not available</div>`;
  }
}

async function loadProjectSettings() {
  const pane = document.getElementById('pane-project-settings');
  if (!pane) return;
  const proj = document.getElementById('current-project-label')?.textContent;
  if (!proj || proj === 'Select project...') {
    pane.querySelector('#ps-status')?.remove();
    return;
  }
  let target = document.getElementById('ps-status');
  if (!target) {
    target = document.createElement('div');
    target.id = 'ps-status';
    pane.querySelector('.space-y-4')?.prepend(target);
  }
  target.innerHTML = '<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Detecting…</div>';
  try {
    const ps = await api('/projects/' + encodeURIComponent(proj) + '/status');
    const g = ps.git || {};
    const s = ps.stack || {};
    const cx = ps.cortex || {};
    let html = `<div class="card p-4"><div class="text-[10px] text-gray-500 uppercase mb-2">Project: ${esc(proj)}</div>`;
    html += '<div class="space-y-1 text-xs text-gray-300">';
    if (g.is_repo) {
      html += `<div><i class="fas fa-code-branch text-gray-500 mr-1" style="font-size:10px"></i>Branch: <b class="text-white">${esc(g.branch)}</b>${g.has_uncommitted ? ' <span class="text-yellow-400">(uncommitted)</span>' : ''}</div>`;
      if (g.recent_branches && g.recent_branches.length > 1) {
        html += `<div class="text-gray-500">Recent: ${g.recent_branches.map(esc).join(', ')}</div>`;
      }
    } else {
      html += '<div class="text-gray-500">No git repo detected</div>';
    }
    if (s.type && s.type !== 'unknown') {
      html += `<div><i class="fas fa-layer-group text-gray-500 mr-1" style="font-size:10px"></i>Stack: <b class="text-white">${esc(s.type)}</b>`;
      if (s.test_runner) html += ` · test: ${esc(s.test_runner)}`;
      if (s.linter) html += ` · lint: ${esc(s.linter)}`;
      html += '</div>';
    }
    html += `<div><i class="fas fa-brain text-gray-500 mr-1" style="font-size:10px"></i>Cortex: ${cx.exists ? '<span class="text-green-400">indexed</span>' : '<span class="text-gray-500">not indexed</span>'}</div>`;
    html += '</div></div>';
    target.innerHTML = html;
  } catch (e) {
    target.innerHTML = '';
  }
}

// ── Budget ──────────────────────────────────────────────────────────────
async function loadBudget() {
  const pane = document.getElementById('pane-budget');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading budget…</div>`;
  try {
    const [status, byProvider] = await Promise.all([
      api('/budget'),
      api('/budget/by-provider'),
    ]);
    const statusColor = status.status === 'ok' ? 'text-green-400' : status.status === 'warning' ? 'text-yellow-400' : 'text-red-400';
    let html = `<h2 class="text-sm font-bold text-white mb-3">Token Budget</h2>`;
    html += `<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold ${statusColor}">$${esc(status.spent_today_usd)}</div>
        <div class="text-[10px] text-gray-500">Spent Today</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold text-gray-300">$${esc(status.daily_limit_usd)}</div>
        <div class="text-[10px] text-gray-500">Daily Limit</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-2xl font-bold ${statusColor}">${esc(Math.round(status.utilization * 100))}%</div>
        <div class="text-[10px] text-gray-500">${esc(status.status)}</div>
      </div>
    </div>`;
    const providers = byProvider.providers || byProvider || [];
    if (providers.length) {
      html += `<h3 class="text-xs font-bold text-gray-400 mb-2">By Provider</h3><div class="space-y-1">`;
      for (const p of providers) {
        html += `<div class="card px-3 py-2 flex justify-between"><span class="text-xs text-white">${esc(p.provider)}</span><span class="text-xs text-orange-400">$${esc(p.spent_usd)}</span></div>`;
      }
      html += `</div>`;
    }
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Model Routing ───────────────────────────────────────────────────────
async function loadRouting() {
  const pane = document.getElementById('pane-routing');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading model performance…</div>`;
  try {
    const data = await api('/routing/heatmap');
    const heatmap = data.heatmap || data || [];
    let html = `<h2 class="text-sm font-bold text-white mb-3">Model Performance Heatmap</h2>`;
    if (!heatmap.length) {
      html += `<div class="card p-4 text-sm text-gray-400">No reward data yet. Execute some tasks to build the heatmap.</div>`;
    } else {
      html += `<div class="overflow-x-auto"><table class="text-xs w-full"><thead><tr class="text-gray-500">
        <th class="text-left p-2">Model</th><th class="text-left p-2">Task Type</th><th class="text-left p-2">Blast Tier</th><th class="text-right p-2">Avg Reward</th><th class="text-right p-2">Samples</th>
      </tr></thead><tbody>`;
      for (const r of heatmap) {
        const color = r.avg_reward >= 0.7 ? 'text-green-400' : r.avg_reward >= 0.4 ? 'text-yellow-400' : 'text-red-400';
        html += `<tr class="border-t border-gray-800"><td class="p-2 text-white">${esc(r.model)}</td><td class="p-2">${esc(r.task_type)}</td><td class="p-2">${esc(r.blast_tier)}</td><td class="p-2 text-right ${color}">${esc(r.avg_reward)}</td><td class="p-2 text-right text-gray-500">${esc(r.samples)}</td></tr>`;
      }
      html += `</tbody></table></div>`;
    }
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Process Intelligence ────────────────────────────────────────────────
async function loadInsights() {
  const pane = document.getElementById('pane-insights');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading process intelligence…</div>`;
  try {
    const [events, history, improve, landscape, activity] = await Promise.all([
      api('/events/count').catch(() => ({ count: 0 })),
      api('/history/report').catch(() => ({ status: 'no_data' })),
      api('/improve/report').catch(() => ({ report: null })),
      api('/cikg/landscape').catch(() => ({ technologies: 0 })),
      api('/activity').catch(() => ({ sessions: [], recent: [] })),
    ]);
    let html = `<h2 class="text-sm font-bold text-white mb-3">Process Intelligence</h2>`;
    html += renderPIStats(events, history, landscape);
    html += renderPIPatterns(history);
    html += renderPIHealth(improve);
    html += renderPIActivity(activity);
    html += renderPIActions();
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderPIStats(events, history, landscape) {
  return `<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
    <div class="card p-3 text-center"><div class="text-xl font-bold text-orange-400">${esc(events.count || 0)}</div><div class="text-[10px] text-gray-500">Events</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold text-blue-400">${esc(history.total_sessions || 0)}</div><div class="text-[10px] text-gray-500">CLI Sessions</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold text-green-400">${esc(history.total_prompts || 0)}</div><div class="text-[10px] text-gray-500">Total Prompts</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold text-purple-400">${esc(landscape.technologies || 0)}</div><div class="text-[10px] text-gray-500">Technologies</div></div>
  </div>`;
}

function renderPIPatterns(history) {
  if (!history.patterns || !history.patterns.length) return '';
  let html = `<div class="card p-4 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-chart-bar mr-1"></i>Session Patterns</div><div class="space-y-1">`;
  for (const p of history.patterns.slice(0, 5)) {
    html += `<div class="text-xs text-gray-300">- ${esc(typeof p === 'string' ? p : JSON.stringify(p))}</div>`;
  }
  return html + `</div></div>`;
}

function renderPIHealth(improve) {
  const report = improve.report;
  if (!report) return '';
  const health = report.health_summary || {};
  const keys = Object.keys(health);
  if (!keys.length) return '';
  let html = `<div class="card p-4 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-heartbeat mr-1"></i>Health Signals</div>`;
  html += `<div class="grid grid-cols-2 md:grid-cols-4 gap-2">`;
  for (const k of keys) {
    const val = health[k];
    const pct = Math.round(val * 100);
    const color = pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-yellow-400' : 'text-red-400';
    html += `<div class="text-center"><div class="text-lg font-bold ${color}">${pct}%</div><div class="text-[10px] text-gray-500 capitalize">${esc(k)}</div></div>`;
  }
  html += `</div>`;
  if (report.top_actions && report.top_actions.length) {
    html += `<div class="mt-3 space-y-1">`;
    for (const a of report.top_actions) {
      html += `<div class="text-xs text-yellow-300"><i class="fas fa-lightbulb mr-1"></i>${esc(a)}</div>`;
    }
    html += `</div>`;
  }
  return html + `</div>`;
}

function renderPIActivity(activity) {
  const sessions = activity.sessions || [];
  const recent = activity.recent || [];
  if (!sessions.length && !recent.length) return '';
  let html = `<div class="card p-4 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-bolt mr-1"></i>Live Activity</div>`;
  if (sessions.length) {
    html += `<div class="mb-2"><span class="text-[10px] text-green-400 font-bold">${sessions.length} active session${sessions.length > 1 ? 's' : ''}</span></div>`;
    html += `<div class="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">`;
    const seen = new Set();
    for (const s of sessions) {
      if (seen.has(s.project)) continue;
      seen.add(s.project);
      html += `<div class="bg-gray-900 rounded px-2 py-1.5"><div class="text-xs text-white truncate"><i class="fas fa-circle text-green-400 text-[6px] mr-1"></i>${esc(s.project)}</div><div class="text-[9px] text-gray-500">${esc(s.status)}</div></div>`;
    }
    html += `</div>`;
  }
  if (recent.length) {
    html += `<div class="text-[10px] text-gray-500 mb-1">Recent prompts:</div><div class="space-y-1">`;
    for (const p of recent.slice(0, 5)) {
      html += `<div class="text-[10px] text-gray-400 truncate"><span class="text-gray-600">${esc(p.project)}</span> ${esc(p.text)}</div>`;
    }
    html += `</div>`;
  }
  return html + `</div>`;
}

function renderPIActions() {
  return `<div class="card p-4"><div class="text-[10px] text-gray-500 uppercase mb-2">Quick Actions</div>
    <div class="flex flex-wrap gap-2">
      <button id="btn-history" onclick="triggerAnalysis('history')" class="text-[10px] px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300"><i class="fas fa-clock-rotate-left mr-1"></i>Analyze History</button>
      <button id="btn-improve" onclick="triggerAnalysis('improve')" class="text-[10px] px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300"><i class="fas fa-brain mr-1"></i>Self-Improve</button>
      <a href="/api/events?limit=20" target="_blank" class="text-[10px] px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-blue-400">Events JSON</a>
      <a href="/api/cikg/landscape" target="_blank" class="text-[10px] px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-blue-400">CIKG Landscape</a>
    </div>
  </div>`;
}

async function triggerAnalysis(type) {
  const btn = document.getElementById('btn-' + type);
  const origText = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-1"></i>Running…`;
  if (btn) btn.disabled = true;
  try {
    let result;
    if (type === 'history') result = await api('/history/analyze', { method: 'POST' });
    else if (type === 'improve') result = await api('/improve/analyze', { method: 'POST' });
    showToast(type === 'history'
      ? `History: ${result.total_sessions || 0} sessions, ${result.total_prompts || 0} prompts`
      : `Improve: ${(result.report || {}).total_signals || 0} signals collected`);
    loadProcess();
  } catch (e) {
    alert('Analysis failed: ' + e.message);
    if (btn) { btn.innerHTML = origText; btn.disabled = false; }
  }
}

function showToast(msg) {
  const el = document.createElement('div');
  el.className = 'fixed bottom-4 right-4 bg-green-600 text-white text-xs px-4 py-2 rounded shadow-lg z-50';
  el.innerHTML = `<i class="fas fa-check mr-1"></i>${esc(msg)}`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ── Skills ──────────────────────────────────────────────────────────────
async function loadSkills() {
  const pane = document.getElementById('pane-skills');
  const list = document.getElementById('skills-list');
  list.innerHTML = '<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading skills...</div>';
  try {
    const pk = document.getElementById('current-project-label')?.textContent || '';
    const isDefault = !pk || pk === 'Select project...';
    const data = await api('/skills' + (!isDefault ? '?project_key=' + encodeURIComponent(pk) : ''));
    document.getElementById('skills-count').textContent = data.total;
    if (!data.skills.length) {
      list.innerHTML = '<div class="text-xs text-gray-500">No skills loaded.</div>';
      return;
    }
    let html = '<table class="w-full text-xs"><thead><tr class="text-gray-500 text-left"><th class="pb-1 pr-3">Name</th><th class="pb-1 pr-3">Description</th><th class="pb-1 pr-3">Source</th><th class="pb-1">Effort</th></tr></thead><tbody>';
    for (const s of data.skills) {
      const m = s.metadata;
      const src = s.is_override ? '<span class="text-yellow-400">override</span>' : (s.source === 'project' ? '<span class="text-blue-400">project</span>' : '<span class="text-gray-400">global</span>');
      html += '<tr class="border-t border-gray-800 hover:bg-gray-800/30"><td class="py-1.5 pr-3 text-white font-mono">' + esc(m.name) + '</td><td class="py-1.5 pr-3 text-gray-400">' + esc(m.description || '-') + '</td><td class="py-1.5 pr-3">' + src + '</td><td class="py-1.5 text-gray-500">' + esc(m.effort || '-') + '</td></tr>';
    }
    html += '</tbody></table>';
    list.innerHTML = html;
  } catch (e) {
    list.innerHTML = '<div class="text-xs text-red-400">Failed to load skills: ' + esc(e.message) + '</div>';
  }
}

async function validateAllSkills() {
  const banner = document.getElementById('skills-validation-banner');
  banner.classList.remove('hidden');
  banner.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Validating...';
  try {
    const data = await api('/skills/validate-all', { method: 'POST' });
    const color = data.invalid === 0 ? 'text-green-400' : 'text-yellow-400';
    banner.innerHTML = '<span class="' + color + '">' + data.valid + '/' + data.total + ' valid</span>' + (data.invalid ? ' &middot; <span class="text-red-400">' + data.invalid + ' with errors</span>' : '');
  } catch (e) {
    banner.innerHTML = '<span class="text-red-400">Validation failed: ' + esc(e.message) + '</span>';
  }
}

async function reloadSkills() {
  try {
    await api('/skills/reload', { method: 'POST' });
    loadSkills();
  } catch (e) {
    showToast('Failed to reload skills');
  }
}

// ── System & Project Status ─────────────────────────────────────────────
async function refreshSystemStatus() {
  const container = document.getElementById('header-clis');
  if (!container) return;
  container.innerHTML = '<span class="cli-pill"><i class="fas fa-spinner fa-spin" style="font-size:8px"></i></span>';
  try {
    const data = await api('/system/status');
    let html = _renderToolPills(data.clis || [], 'ai');
    html += _renderToolPills(data.tools || [], 'dev');
    container.innerHTML = html;
    _lastSetupData = data;
    if (!sessionStorage.getItem('setup-seen')) {
      _showSetupModal(data);
      sessionStorage.setItem('setup-seen', '1');
    }
  } catch (e) {
    container.innerHTML = '';
  }
}

var _lastSetupData = null;

function closeSetupModal() {
  var ov = document.getElementById('setup-modal-overlay');
  if (ov) ov.classList.add('hidden');
}

function _showSetupModal(data) {
  var ov = document.getElementById('setup-modal-overlay');
  var body = document.getElementById('setup-modal-body');
  if (!ov || !body) return;
  ov.classList.remove('hidden');
  var cats = {};
  var all = (data.clis || []).concat(data.tools || []);
  for (var i = 0; i < all.length; i++) {
    var t = all[i];
    var cat = t.category || 'other';
    if (!cats[cat]) cats[cat] = [];
    cats[cat].push(t);
  }
  var catLabels = { ai: 'AI Models', dev: 'Dev Tools', lint: 'Linting', type: 'Type Checking', test: 'Testing', infra: 'Infrastructure', deploy: 'Deployment', scm: 'Source Control', pkg: 'Package Managers', other: 'Other' };
  var catIcons = { ai: 'fa-robot', dev: 'fa-wrench', lint: 'fa-broom', type: 'fa-spell-check', test: 'fa-vial', infra: 'fa-server', deploy: 'fa-rocket', scm: 'fa-code-branch', pkg: 'fa-box', other: 'fa-ellipsis' };
  var html = '';
  var totalOk = 0, totalAll = 0;
  for (var c in cats) {
    var items = cats[c];
    var label = catLabels[c] || c;
    var icon = catIcons[c] || 'fa-circle';
    html += '<div class="mb-3"><div class="flex items-center gap-1.5 mb-1.5 text-[11px] text-gray-300 font-semibold"><i class="fas ' + icon + ' text-orange-400/70" style="font-size:10px"></i>' + esc(label) + '</div>';
    html += '<div class="grid grid-cols-2 gap-1">';
    for (var j = 0; j < items.length; j++) {
      var item = items[j];
      totalAll++;
      var ok = item.installed;
      if (ok) totalOk++;
      var dotCls = ok ? 'text-green-400' : 'text-gray-600';
      var ico = ok ? 'fa-circle-check' : 'fa-circle-xmark';
      var nameCls = ok ? 'text-gray-300' : 'text-gray-600';
      var pathTip = item.path ? ' title="' + esc(item.path) + '"' : '';
      html += '<div class="flex items-center gap-1.5 py-0.5 px-1.5 rounded" style="background:rgba(255,255,255,0.02)"' + pathTip + '>';
      html += '<i class="fas ' + ico + ' ' + dotCls + '" style="font-size:9px"></i>';
      html += '<span class="' + nameCls + '">' + esc(item.name) + '</span>';
      html += '</div>';
    }
    html += '</div></div>';
  }
  var summary = '<div class="flex items-center gap-2 mb-4 py-2 px-3 rounded" style="background:rgba(249,115,22,0.08);border:1px solid rgba(249,115,22,0.15)">';
  summary += '<i class="fas fa-circle-check text-green-400" style="font-size:11px"></i>';
  summary += '<span class="text-gray-300"><span class="text-white font-bold">' + totalOk + '</span> tools available</span>';
  var missing = totalAll - totalOk;
  if (missing > 0) summary += '<span class="ml-auto text-[10px] text-gray-600">' + missing + ' not installed</span>';
  summary += '</div>';
  body.innerHTML = summary + html;
}

function _renderToolPills(tools, group) {
  let html = '';
  for (const cli of tools) {
    if (!cli.installed && group === 'dev') continue;
    const cls = cli.installed ? 'ok' : 'missing';
    const tip = cli.installed ? cli.name + ' ready' : cli.name + ' not found';
    html += '<span class="cli-pill" title="' + esc(tip) + '"><span class="cli-dot ' + cls + '"></span>' + esc(cli.name) + '</span>';
  }
  return html;
}

async function loadProjectStatus(projectName) {
  const container = document.getElementById('header-clis');
  if (!container || !projectName) return;
  try {
    const data = await api('/projects/' + encodeURIComponent(projectName) + '/status');
    let html = _renderToolPills(data.clis || [], 'ai');
    html += _renderToolPills(data.tools || [], 'dev');
    const git = data.git || {};
    if (git.is_repo) {
      html += '<span class="cli-pill" title="branch: ' + esc(git.branch) + '"><i class="fas fa-code-branch" style="font-size:8px"></i>' + esc(git.branch || '?') + (git.has_uncommitted ? ' *' : '') + '</span>';
    }
    const cx = data.cortex || {};
    if (cx.exists) {
      html += '<span class="cli-pill" title="Cortex indexed"><i class="fas fa-brain" style="font-size:8px;color:var(--green)"></i>cortex</span>';
    }
    const stack = data.stack || {};
    if (stack.type && stack.type !== 'unknown') {
      html += '<span class="cli-pill" title="' + esc(stack.type) + ' project"><i class="fas fa-layer-group" style="font-size:8px"></i>' + esc(stack.type) + '</span>';
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '';
  }
}

// ── Pipeline Logs ───────────────────────────────────────────────────────
async function loadLogs() {
  const period = document.getElementById('logs-period')?.value || 'today';
  try {
    const [logsRes, statsRes] = await Promise.all([
      fetch('/api/pipeline/logs?limit=100'),
      fetch('/api/pipeline/stats?period=' + period),
    ]);
    const logs = await logsRes.json();
    const stats = await statsRes.json();
    document.getElementById('logs-total').textContent = stats.total_calls;
    document.getElementById('logs-stat-calls').textContent = stats.total_calls;
    document.getElementById('logs-stat-success').textContent = Math.round(stats.success_rate * 100) + '%';
    document.getElementById('logs-stat-latency').textContent = Math.round(stats.avg_latency_ms) + 'ms';
    document.getElementById('logs-stat-cost').textContent = '$' + (stats.total_cost || 0).toFixed(4);
    const tbody = document.getElementById('logs-table-body');
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="py-4 text-center text-gray-500">No pipeline logs yet</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(l => {
      const ts = l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : '-';
      const lat = Math.round(l.latency_ms || 0);
      const cost = (l.cost_usd || 0).toFixed(4);
      const ok = l.success;
      const fb = l.fallback_used;
      let statusBadge;
      if (ok && !fb) statusBadge = '<span class="text-green-400">OK</span>';
      else if (ok && fb) statusBadge = '<span class="text-yellow-400">FB:' + fb + '</span>';
      else statusBadge = '<span class="text-red-400">ERR</span>';
      return '<tr class="border-b" style="border-color:var(--border)">'
        + '<td class="py-1.5 pr-3">' + ts + '</td>'
        + '<td class="py-1.5 pr-3 font-mono">' + (l.model || '-') + '</td>'
        + '<td class="py-1.5 pr-3">' + (l.backend || '-') + '</td>'
        + '<td class="py-1.5 pr-3">' + (l.blast ?? '-') + '</td>'
        + '<td class="py-1.5 pr-3">' + (l.task_type || '-') + '</td>'
        + '<td class="py-1.5 pr-3">' + lat + 'ms</td>'
        + '<td class="py-1.5 pr-3">$' + cost + '</td>'
        + '<td class="py-1.5">' + statusBadge + '</td></tr>';
    }).join('');
  } catch (e) {
    document.getElementById('logs-table-body').innerHTML =
      '<tr><td colspan="8" class="py-4 text-center text-red-400">Failed to load logs</td></tr>';
  }
}

// ── Forge ───────────────────────────────────────────────────────────────
async function loadForge() {
  const pane = document.getElementById('pane-forge');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading forge…</div>`;
  try {
    const [status, gaps] = await Promise.all([
      api('/forge/status'),
      api('/forge/gaps'),
    ]);
    let html = `<h2 class="text-sm font-bold text-white mb-3">MCP Forge</h2>`;
    html += `<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      <div class="card p-4 text-center">
        <div class="text-xl font-bold ${status.available ? 'text-green-400' : 'text-red-400'}">${status.available ? 'Online' : 'Offline'}</div>
        <div class="text-[10px] text-gray-500">Status</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-xl font-bold text-orange-400">${esc(status.registry_count || 0)}</div>
        <div class="text-[10px] text-gray-500">Tools in Registry</div>
      </div>
      <div class="card p-4 text-center">
        <div class="text-xl font-bold text-yellow-400">${esc(status.pending_gaps || 0)}</div>
        <div class="text-[10px] text-gray-500">Detected Gaps</div>
      </div>
    </div>`;
    const gapList = gaps.gaps || [];
    if (gapList.length) {
      html += `<h3 class="text-xs font-bold text-gray-400 mb-2">Capability Gaps</h3><div class="space-y-1">`;
      for (const g of gapList) {
        html += `<div class="card px-3 py-2 flex justify-between"><span class="text-xs text-white">${esc(g.capability)}</span><span class="text-xs text-gray-400">${esc(g.occurrences)} hits ${g.triggered ? '<span class="text-orange-400">TRIGGERED</span>' : ''}</span></div>`;
      }
      html += `</div>`;
    }
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

// ── Setup Wizard ────────────────────────────────────────────────────────
async function checkSetup() {
  try {
    const status = await api('/setup/status');
    if (status.configured) return true;
    showSetupWizard(status);
    return false;
  } catch { return true; }
}

function showSetupWizard(status) {
  const pane = document.getElementById('pane-inbox');
  const missing = status.steps.filter(s => s.status === 'missing');
  const disc = status.discovery || {};
  const clis = disc.clis || {};
  const cliAuth = disc.cli_auth || {};
  const tokens = disc.tokens || {};
  let html = `<div class="max-w-2xl mx-auto mt-4 space-y-4">`;
  // Header
  html += `<div class="card p-6">
    <div class="flex items-center gap-3 mb-3">
      <i class="fas fa-wand-magic-sparkles text-orange-500 text-xl"></i>
      <h2 class="text-lg font-bold text-white">Welcome to Maggy</h2>
      <span class="text-[10px] text-gray-500">${esc(status.progress)} configured</span>
    </div>
    <div class="space-y-2">`;
  for (const step of status.steps) {
    const icon = step.status === 'done'
      ? '<i class="fas fa-check-circle text-green-400"></i>'
      : '<i class="fas fa-circle-xmark text-red-400/60"></i>';
    html += `<div class="flex items-center gap-3 px-3 py-2 rounded ${step.status === 'done' ? 'bg-green-900/20' : 'bg-red-900/10'}">
      ${icon}
      <span class="text-sm ${step.status === 'done' ? 'text-green-300' : 'text-gray-300'}">${esc(step.label)}</span>
      ${step.status !== 'done' && step.hint ? `<span class="text-[10px] text-gray-500 ml-auto">${esc(step.hint)}</span>` : ''}
    </div>`;
  }
  html += `</div></div>`;
  // Discovered CLIs
  const cliNames = Object.keys(clis);
  if (cliNames.length) {
    html += `<div class="card p-4">
      <div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-terminal mr-1"></i>Detected CLI Tools</div>
      <div class="space-y-1">`;
    for (const name of cliNames) {
      const auth = cliAuth[name];
      html += `<div class="flex items-center gap-2 text-xs">
        <i class="fas fa-check text-green-400"></i>
        <span class="text-white font-mono">${esc(name)}</span>
        <span class="text-gray-500">${esc(clis[name])}</span>
        ${auth ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-green-900/40 text-green-400">authenticated</span>' : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-500">not logged in</span>'}
      </div>`;
    }
    html += `</div></div>`;
  }
  // Token sources
  html += `<div class="card p-4">
    <div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-key mr-1"></i>Credential Sources</div>
    <div class="space-y-1 text-xs">`;
  if (tokens.GITHUB_TOKEN) html += `<div class="text-green-400"><i class="fas fa-check mr-1"></i>GITHUB_TOKEN (env var)</div>`;
  else if (tokens.GIT_CREDENTIAL) html += `<div class="text-green-400"><i class="fas fa-check mr-1"></i>GitHub token (git credential helper)</div>`;
  else html += `<div class="text-red-400/60"><i class="fas fa-xmark mr-1"></i>No GitHub token found</div>`;
  if (tokens.ANTHROPIC_API_KEY) html += `<div class="text-green-400"><i class="fas fa-check mr-1"></i>ANTHROPIC_API_KEY (env var)</div>`;
  else if (cliAuth.claude) html += `<div class="text-green-400"><i class="fas fa-check mr-1"></i>Claude Code subscription (CLI auth)</div>`;
  else html += `<div class="text-gray-500"><i class="fas fa-info-circle mr-1"></i>No Anthropic API key (Claude CLI can be used instead)</div>`;
  html += `</div></div>`;
  // Actions
  html += `<div class="flex gap-2">
    <button onclick="autoConfigureSetup()" class="text-xs px-4 py-2 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-wand-magic mr-1"></i>Auto-Configure</button>
    <button onclick="reloadConfig()" class="text-xs px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-gray-300"><i class="fas fa-rotate mr-1"></i>Reload</button>
    <button onclick="enterLocalMode()" class="text-xs px-4 py-2 rounded bg-gray-800 hover:bg-gray-700 text-gray-400"><i class="fas fa-laptop mr-1"></i>Local Mode</button>
  </div>`;
  html += `</div>`;
  pane.innerHTML = html;
}

function enterLocalMode() {
  const pane = document.getElementById('pane-inbox');
  pane.innerHTML = `<div class="card p-6 max-w-2xl mx-auto mt-4">
    <div class="flex items-center gap-3 mb-3">
      <i class="fas fa-laptop text-blue-400 text-lg"></i>
      <h2 class="text-sm font-bold text-white">Local Mode</h2>
    </div>
    <p class="text-xs text-gray-400 mb-3">These features work without provider credentials:</p>
    <div class="grid grid-cols-2 gap-2">
      <button onclick="switchTab('budget')" class="card p-3 text-left hover:bg-gray-900"><div class="text-xs text-white"><i class="fas fa-wallet text-orange-400 mr-1"></i>Budget</div><div class="text-[10px] text-gray-500">Track token spend</div></button>
      <button onclick="switchTab('routing')" class="card p-3 text-left hover:bg-gray-900"><div class="text-xs text-white"><i class="fas fa-route text-blue-400 mr-1"></i>Model Routing</div><div class="text-[10px] text-gray-500">Performance heatmap</div></button>
      <button onclick="switchTab('process')" class="card p-3 text-left hover:bg-gray-900"><div class="text-xs text-white"><i class="fas fa-chart-line text-green-400 mr-1"></i>Process</div><div class="text-[10px] text-gray-500">Events + knowledge graph</div></button>
      <button onclick="switchTab('forge')" class="card p-3 text-left hover:bg-gray-900"><div class="text-xs text-white"><i class="fas fa-hammer text-yellow-400 mr-1"></i>Forge</div><div class="text-[10px] text-gray-500">MCP tool gaps</div></button>
    </div>
    <button onclick="loadAll()" class="mt-3 text-[10px] text-gray-500 hover:text-white"><i class="fas fa-arrow-left mr-1"></i>Back to setup</button>
  </div>`;
}

async function reloadConfig() {
  try {
    const result = await api('/setup/reload', { method: 'POST' });
    if (result.mode === 'full') {
      loadAll();
    } else {
      const status = await api('/setup/status');
      showSetupWizard(status);
    }
  } catch (e) {
    alert('Reload failed: ' + e.message);
  }
}

async function autoConfigureSetup() {
  const btn = event.target;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Discovering...';
  btn.disabled = true;
  try {
    const result = await api('/setup/auto-configure', { method: 'POST' });
    if (result.mode === 'full') {
      loadAll();
    } else {
      const status = await api('/setup/status');
      showSetupWizard(status);
    }
  } catch (e) {
    alert('Auto-configure failed: ' + e.message);
    btn.innerHTML = '<i class="fas fa-wand-magic mr-1"></i>Auto-Configure';
    btn.disabled = false;
  }
}

// ── iCPG ─────────────────────────────────────────────────────────────────
let ICPG_PROJECT = null;

async function loadCortex() {
  const pane = document.getElementById('pane-cortex');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading Cortex…</div>`;
  try {
    const proj = ICPG_PROJECT || getProjectKey();
    if (proj) {
      ICPG_PROJECT = proj;
      await loadICPGProject(proj);
      return;
    }
    const data = await api('/icpg/overview');
    pane.innerHTML = renderICPGOverview(data);
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}
async function loadICPG() { return loadCortex(); }

function renderICPGOverview(data) {
  const t = data.total || {};
  let html = `<div class="overflow-y-auto h-full">`;
  html += `<h2 class="text-sm font-bold text-white mb-3"><i class="fas fa-project-diagram text-orange-400 mr-2"></i>Cortex — Code Intelligence</h2>`;
  html += `<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
    <div class="card p-3 text-center"><div class="text-xl font-bold text-orange-400">${t.reasons || 0}</div><div class="text-[10px] text-gray-500">ReasonNodes</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold text-blue-400">${t.symbols || 0}</div><div class="text-[10px] text-gray-500">Symbols</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold text-green-400">${t.edges || 0}</div><div class="text-[10px] text-gray-500">Edges</div></div>
    <div class="card p-3 text-center"><div class="text-xl font-bold ${t.drift > 0 ? 'text-red-400' : 'text-gray-500'}">${t.drift || 0}</div><div class="text-[10px] text-gray-500">Drift Events</div></div>
  </div>`;
  const projects = (data.projects || []).filter(p => p.reasons > 0);
  if (!projects.length) {
    html += `<div class="card p-4 text-xs text-gray-500">No iCPG databases found. Run <code class="bg-gray-800 px-1 rounded">icpg init && icpg bootstrap</code> in a project.</div>`;
    return html + `</div>`;
  }
  html += `<div class="card p-4 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2">Projects with iCPG</div>`;
  html += `<div class="space-y-1">`;
  for (const p of projects) {
    const driftBadge = p.drift > 0 ? `<span class="text-[9px] text-red-400 ml-1">${p.drift} drift</span>` : '';
    html += `<div class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-800 cursor-pointer" onclick="openICPGProject('${jsStr(p.key)}')">
      <i class="fas fa-folder text-orange-400 text-[10px]"></i>
      <span class="text-xs text-white flex-1">${esc(p.key)}</span>
      <span class="text-[9px] text-gray-500">${p.reasons}R · ${p.symbols}S · ${p.edges}E</span>${driftBadge}
      <i class="fas fa-chevron-right text-[8px] text-gray-600"></i>
    </div>`;
  }
  html += `</div></div>`;
  // Also show projects with 0 reasons but db exists
  const empty = (data.projects || []).filter(p => p.reasons === 0);
  if (empty.length) {
    html += `<div class="text-[10px] text-gray-600 mt-2">${empty.length} project(s) with empty iCPG: ${empty.map(p => p.key).join(', ')}</div>`;
  }
  return html + `</div>`;
}

async function openICPGProject(key) {
  ICPG_PROJECT = key;
  await loadICPGProject(key);
}

async function loadICPGProject(key) {
  const pane = document.getElementById('pane-cortex');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading ${esc(key)}…</div>`;
  try {
    const [reasons, drift] = await Promise.all([
      api(`/icpg/${encodeURIComponent(key)}/reasons?limit=100`),
      api(`/icpg/${encodeURIComponent(key)}/drift`),
    ]);
    pane.innerHTML = renderICPGProject(key, reasons, drift);
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderICPGProject(key, reasons, drift) {
  let html = `<div class="overflow-y-auto h-full">`;
  html += `<div class="flex items-center gap-2 mb-3">
    <button onclick="ICPG_PROJECT=null;loadCortex()" class="text-xs text-gray-400 hover:text-white"><i class="fas fa-arrow-left mr-1"></i></button>
    <h2 class="text-sm font-bold text-white"><i class="fas fa-project-diagram text-orange-400 mr-2"></i>${esc(key)}</h2>
    <span class="text-[10px] text-gray-500">${(reasons.reasons||[]).length} intents</span>
    <div class="flex-1"></div>
    <div class="relative">
      <input id="icpg-search" type="text" placeholder="Search intents..." 
        class="glass-input text-[11px] py-1 px-2 w-40" style="font-size:11px"
        oninput="filterICPGIntents()" />
      <i class="fas fa-search absolute right-2 top-1.5 text-gray-600 text-[10px]"></i>
    </div>
  </div>`;
  // Drift alerts
  const driftList = drift.drift || [];
  if (driftList.length) {
    html += `<div class="card p-3 mb-3 border-red-900/50"><div class="text-[10px] text-red-400 uppercase mb-1"><i class="fas fa-exclamation-triangle mr-1"></i>${driftList.length} Unresolved Drift</div>`;
    html += `<div class="space-y-1">`;
    for (const d of driftList.slice(0, 10)) {
      const dims = (d.drift_dimensions || []).join(', ');
      const sev = Math.round(d.severity * 100);
      const color = sev >= 70 ? 'text-red-400' : sev >= 40 ? 'text-yellow-400' : 'text-gray-400';
      html += `<div class="text-[10px]"><span class="${color} font-bold">[${sev}%]</span> <span class="text-gray-300">${esc(d.symbol_name || '?')}</span> <span class="text-gray-600">— ${esc(dims)}</span></div>`;
    }
    if (driftList.length > 10) html += `<div class="text-[9px] text-gray-600">+${driftList.length - 10} more</div>`;
    html += `</div></div>`;
  }
  // ReasonNodes
  const rlist = reasons.reasons || [];
  html += `<div class="card p-3 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-bullseye mr-1"></i>Intents</div><div id="icpg-intents-list">`;
  if (!rlist.length) {
    html += `<div class="text-[10px] text-gray-600">No ReasonNodes found.</div>`;
  } else {
    // Group by status
    const groups = {};
    for (const r of rlist) { (groups[r.status] = groups[r.status] || []).push(r); }
    const statusOrder = ['executing', 'proposed', 'fulfilled', 'drifted', 'rejected', 'abandoned'];
    const statusIcon = { proposed: 'fa-question text-yellow-400', executing: 'fa-play text-blue-400', fulfilled: 'fa-check text-green-400', drifted: 'fa-exclamation text-red-400', rejected: 'fa-xmark text-gray-500', abandoned: 'fa-ban text-gray-600' };
    const statusColor = { proposed: 'text-yellow-400', executing: 'text-blue-400', fulfilled: 'text-green-400', drifted: 'text-red-400', rejected: 'text-gray-500', abandoned: 'text-gray-600' };
    for (const st of statusOrder) {
      const items = groups[st];
      if (!items) continue;
      html += `<div class="mb-2"><div class="text-[9px] ${statusColor[st] || 'text-gray-500'} uppercase font-bold mb-1">${esc(st)} (${items.length})</div>`;
      for (const r of items.slice(0, 20)) {
        const typeLabel = r.decision_type !== 'task' ? `<span class="text-[8px] text-gray-600 ml-1">${esc(r.decision_type)}</span>` : '';
        html += `<div class="flex items-start gap-1.5 py-0.5">
          <i class="fas ${statusIcon[st] || 'fa-circle text-gray-600'} text-[8px] mt-0.5"></i>
          <div class="flex-1 min-w-0"><div class="text-[10px] text-gray-300 truncate">${esc(r.goal)}${typeLabel}</div>
          <div class="text-[8px] text-gray-600">${esc(r.owner)} · ${esc((r.created_at||'').slice(0,10))}</div></div>
        </div>`;
      }
      if (items.length > 20) html += `<div class="text-[9px] text-gray-600 ml-3">+${items.length - 20} more</div>`;
      html += `</div>`;
    }
  }
  html += `</div>`;
  // Graph viz button
  html += `<div class="card p-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-diagram-project mr-1"></i>Graph</div>
    <button onclick="loadICPGGraph('${jsStr(key)}')" class="text-[10px] px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-project-diagram mr-1"></i>Visualize Graph</button>
    <a href="/api/icpg/${encodeURIComponent(key)}/graph?limit=200" target="_blank" class="text-[10px] px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-blue-400 ml-2">Raw JSON</a>
  </div>`;
  return html + `</div>`;
}

// Search/filter iCPG intents
function filterICPGIntents() {
  var q = (document.getElementById('icpg-search') || {}).value || '';
  q = q.toLowerCase();
  var items = document.querySelectorAll('#icpg-intents-list > div');
  for (var i = 0; i < items.length; i++) {
    var text = items[i].textContent.toLowerCase();
    items[i].style.display = q && !text.includes(q) ? 'none' : '';
  }
}

async function loadICPGGraph(key, autoBuilt = false) {
  const pane = document.getElementById('pane-cortex');
  try {
    const data = await api(`/icpg/${encodeURIComponent(key)}/graph?limit=150`);
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    if (!nodes.length) {
      if (autoBuilt) { alert('No graph data — build produced no intents'); return; }
      return buildICPGGraph(key);
    }
    renderICPGGraphSVG(pane, key, nodes, edges);
  } catch (e) { alert('Graph failed: ' + e.message); }
}

async function buildICPGGraph(key) {
  const pane = document.getElementById('pane-cortex');
  if (!confirm(`No iCPG graph for "${key}" yet. Build it now from git history?`)) return;
  pane.innerHTML = `<div class="p-8 text-center text-gray-400 text-sm">`
    + `<i class="fas fa-spinner fa-spin mr-2"></i>Building iCPG for ${esc(key)}… this can take a minute.</div>`;
  try {
    const res = await api(`/icpg/${encodeURIComponent(key)}/build`, { method: 'POST' });
    if (res.error) { pane.innerHTML = `<div class="p-8 text-center text-red-400 text-sm">Build failed: ${esc(res.error)}</div>`; return; }
    await loadICPGGraph(key, true);
  } catch (e) {
    pane.innerHTML = `<div class="p-8 text-center text-red-400 text-sm">Build failed: ${esc(e.message)}</div>`;
  }
}

function renderICPGGraphSVG(pane, key, nodes, edges) {
  const W = pane.clientWidth - 40, H = Math.max(500, pane.clientHeight - 80);
  // Position nodes using simple force-layout approximation
  const nmap = {};
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const angle = (i / nodes.length) * Math.PI * 2;
    const r = n.type === 'reason' ? W * 0.2 : W * 0.35;
    n.x = W / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 30;
    n.y = H / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 30;
    nmap[n.id] = n;
  }
  let svg = `<svg width="${W}" height="${H}" class="mx-auto">`;
  // Edges
  for (const e of edges) {
    const from = nmap[e.from], to = nmap[e.to];
    if (!from || !to) continue;
    const color = e.type === 'CREATES' ? '#22c55e' : e.type === 'MODIFIES' ? '#f59e0b' : e.type === 'DRIFTS_FROM' ? '#ef4444' : '#6b7280';
    svg += `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="${color}" stroke-width="0.5" opacity="0.4"/>`;
  }
  // Nodes
  for (const n of nodes) {
    const fill = n.type === 'reason' ? '#ea580c' : '#3b82f6';
    const r = n.type === 'reason' ? 6 : 3;
    svg += `<circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${fill}" opacity="0.8"/>`;
    if (n.type === 'reason') {
      svg += `<text x="${n.x + 8}" y="${n.y + 3}" fill="#9ca3af" font-size="8" class="select-none">${esc(n.label.slice(0, 30))}</text>`;
    }
  }
  // Legend
  svg += `<g transform="translate(10, ${H - 50})">
    <circle cx="5" cy="5" r="5" fill="#ea580c"/><text x="14" y="8" fill="#9ca3af" font-size="9">ReasonNode</text>
    <circle cx="5" cy="20" r="3" fill="#3b82f6"/><text x="14" y="23" fill="#9ca3af" font-size="9">Symbol</text>
    <line x1="90" y1="5" x2="110" y2="5" stroke="#22c55e" stroke-width="1.5"/><text x="114" y="8" fill="#9ca3af" font-size="9">CREATES</text>
    <line x1="90" y1="20" x2="110" y2="20" stroke="#f59e0b" stroke-width="1.5"/><text x="114" y="23" fill="#9ca3af" font-size="9">MODIFIES</text>
  </g>`;
  svg += `</svg>`;
  let html = `<div class="overflow-y-auto h-full">`;
  html += `<div class="flex items-center gap-2 mb-3">
    <button onclick="ICPG_PROJECT='${jsStr(key)}';loadICPGProject('${jsStr(key)}')" class="text-xs text-gray-400 hover:text-white"><i class="fas fa-arrow-left mr-1"></i></button>
    <h2 class="text-sm font-bold text-white"><i class="fas fa-project-diagram text-orange-400 mr-2"></i>${esc(key)} — Graph</h2>
    <span class="text-[10px] text-gray-500">${nodes.length} nodes · ${edges.length} edges</span>
  </div>`;
  html += `<div class="card p-2">${svg}</div>`;
  html += `</div>`;
  pane.innerHTML = html;
}

// ── Memory (Mnemos + Engrams) ───────────────────────────────────────────
async function loadMemory() {
  const pane = document.getElementById('pane-memory');
  pane.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i>Loading memory...</div>';
  try {
    const proj = getProjectKey();
    const ns = proj ? '?namespace=' + encodeURIComponent(proj) : '';
    const [engramDiag, engramQuery] = await Promise.all([
      api('/engram/diagnostics' + ns).catch(function() { return {}; }),
      api('/engram/query?limit=5' + (proj ? '&namespace=' + encodeURIComponent(proj) : '')).catch(function() { return { records: [] }; })
    ]);
    var html = '<div class="p-4 space-y-4 h-full overflow-y-auto scroll-thin">';
    html += '<div class="card p-4">';
    html += '<h3 class="text-sm font-bold text-white mb-3"><i class="fas fa-brain text-orange-500 mr-2"></i>Memory Health</h3>';
    html += '<div class="grid grid-cols-3 gap-3 text-xs">';
    var fatigue = engramDiag.fatigue_score || 0;
    var state = fatigue < 0.4 ? 'FLOW' : fatigue < 0.6 ? 'COMPRESS' : fatigue < 0.75 ? 'PRE_SLEEP' : fatigue < 0.9 ? 'REM' : 'EMERGENCY';
    var stateColor = fatigue < 0.4 ? '#22c55e' : fatigue < 0.6 ? '#eab308' : fatigue < 0.75 ? '#f97316' : '#ef4444';
    html += '<div class="col-span-3"><div class="flex justify-between mb-1"><span>Fatigue</span><span style="color:' + stateColor + '">' + (fatigue * 100).toFixed(0) + '% · ' + state + '</span></div>';
    html += '<div class="w-full h-2 rounded-full" style="background:var(--input-bg);border:1px solid var(--border)"><div class="h-2 rounded-full" style="width:' + (fatigue * 100) + '%;background:' + stateColor + '"></div></div></div>';
    html += '<div><div class="text-gray-500">Engrams</div><div class="text-white text-lg font-bold">' + (engramDiag.total_engrams || 0) + '</div></div>';
    html += '<div><div class="text-gray-500">Checkpoints</div><div class="text-white text-lg font-bold">' + (engramDiag.checkpoints || 0) + '</div></div>';
    html += '<div><div class="text-gray-500">Expired</div><div class="text-white text-lg font-bold">' + (engramDiag.expired || 0) + '</div></div>';
    html += '</div></div>';
    var records = engramQuery.records || [];
    if (records.length) {
      html += '<div class="card p-4"><h3 class="text-sm font-bold text-white mb-2">Recent Memories</h3>';
      for (var i = 0; i < records.length; i++) {
        var r = records[i];
        html += '<div class="flex items-center gap-2 py-1.5 border-b text-xs" style="border-color:#1e2636">';
        html += '<span class="badge" style="font-size:9px;background:var(--input-bg);border:1px solid var(--border)">' + esc(r.memory_type || 'fact') + '</span>';
        html += '<span class="flex-1 truncate text-gray-300">' + esc((r.content || '').substring(0, 80)) + '</span>';
        html += '<span class="text-gray-600">' + relDate(r.created_at) + '</span></div>';
      }
      html += '</div>';
    }
    html += '</div>';
    pane.innerHTML = html;
    var fb = document.getElementById('fatigue-badge');
    if (fb) { fb.style.backgroundColor = stateColor; fb.title = (fatigue * 100).toFixed(0) + '% · ' + state; fb.className = 'w-2 h-2 rounded-full inline-block'; }
  } catch (e) {
    pane.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs">Memory offline — start a task to populate</div>';
  }
}

// ── Progress Dashboard ──────────────────────────────────────────────────
async function loadProgress() {
  var pane = document.getElementById('pane-insights');
  pane.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs"><i class="fas fa-spinner fa-spin mr-2"></i>Loading progress...</div>';
  try {
    var [execSessions, signals] = await Promise.all([
      api('/execute/sessions').catch(function(){ return { sessions: [] }; }),
      api('/observability/signals?limit=20').catch(function(){ return { signals: [] }; })
    ]);
    var sessions = execSessions.sessions || [];
    var html = '<div class="p-4 space-y-4 h-full overflow-y-auto scroll-thin">';
    html += '<h3 class="text-sm font-bold text-white"><i class="fas fa-bars-progress text-orange-500 mr-2"></i>Execution Progress</h3>';
    if (!sessions.length) {
      html += '<div class="text-gray-600 text-xs py-8 text-center">No active executions. Execute a task from the Inbox.</div>';
    } else {
      for (var i = 0; i < sessions.length; i++) {
        var s = sessions[i];
        var statusColor = s.status === 'completed' ? '#22c55e' : s.status === 'failed' ? '#ef4444' : '#eab308';
        html += '<div class="card p-3 flex items-center gap-3">';
        html += '<div class="w-2 h-2 rounded-full flex-shrink-0" style="background:' + statusColor + '"></div>';
        html += '<div class="flex-1 min-w-0"><div class="text-xs font-medium text-white truncate">' + esc(s.task_title || s.task_id) + '</div>';
        html += '<div class="text-[10px] text-gray-500">' + esc(s.mode || 'tdd') + ' · ' + esc(s.status) + ' · ' + relDate(s.started_at) + '</div></div>';
        if (s.status === 'running') html += '<div class="shimmer-bar h-1 w-12 rounded"></div>';
        html += '</div>';
      }
    }
    var sigs = signals.signals || [];
    if (sigs.length) {
      html += '<h3 class="text-sm font-bold text-white mt-4">Recent Activity</h3>';
      for (var j = 0; j < sigs.length; j++) {
        var sig = sigs[j];
        html += '<div class="flex items-center gap-2 py-1 text-[10px] text-gray-400"><span class="text-gray-600 w-12">' + relDate(sig.ts || sig.timestamp) + '</span>' + esc(sig.signal_type || sig.type || '') + '</div>';
      }
    }
    html += '</div>';
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs">Progress offline</div>';
  }
}

// ── Heartbeat updater ──────────────────────────────────────────────────
function updateHeartbeat() {
  fetch('/api/heartbeat/status').then(function(r) { return r.json(); }).then(function(data) {
    var jobs = data.jobs || [];
    var indicator = document.getElementById('heartbeat-indicator');
    if (indicator && jobs.length) {
      var failed = jobs.filter(function(j) { return j.last_error; });
      var dot = indicator.querySelector('span:first-child');
      if (dot) {
        dot.className = 'w-1.5 h-1.5 rounded-full ' + (failed.length ? 'bg-red-500' : 'bg-green-500 pulse-glow');
      }
    }
  }).catch(function(){});
}
setInterval(updateHeartbeat, 30000);
updateHeartbeat();


// ── Multi-tab chat ─────────────────────────────────────────────────────
var _chatTabs = [];
var _activeChatTab = null;

function openChatTab(sessionId, label) {
  // Set as active
  CHAT_SESSION_ID = sessionId;
  loadChatMessages(sessionId);
  // Update tab bar
  updateChatTabs(label);
}

function updateChatTabs(label) {
  var container = document.getElementById('chat-tabs');
  if (!container) return;
  if (!_activeChatTab || _activeChatTab !== CHAT_SESSION_ID) {
    _activeChatTab = CHAT_SESSION_ID;
    var tab = document.createElement('span');
    tab.className = 'text-[10px] px-2 py-1 rounded bg-gray-800 text-gray-300 cursor-pointer hover:bg-gray-700 flex items-center gap-1';
    tab.innerHTML = '<i class=\'fas fa-circle text-[6px] text-green-400\'></i>' + (label || 'Chat');
    tab.onclick = function() { CHAT_SESSION_ID = _activeChatTab; loadChatMessages(_activeChatTab); };
    container.appendChild(tab);
  }
}

// ── Init ────────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    var h = await api('/health');
    var orgEl = document.getElementById('org-badge');
    if (orgEl) orgEl.textContent = h.org + ' · ' + (h.provider || '') + ' · ' + (h.codebases || 0) + ' codebases';
  } catch (e) {}
  refreshSystemStatus();
  try {
    var projData = await api('/projects');
    var projects = (projData.projects || []).map(function(p) { return p.name; });
    updateProjectList(projects);
  } catch (e) {}
  var ready = typeof checkSetup === 'function' ? await checkSetup() : true;
  if (ready) {
    var hashTab = tabFromHash();
    if (hashTab) CURRENT_TAB = hashTab;
    switchTab(CURRENT_TAB);
  }
}

applyTheme(getTheme());
loadAll();
