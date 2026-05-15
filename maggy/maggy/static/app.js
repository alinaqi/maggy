// Maggy dashboard — vanilla JS, no build step.
// Talks to /api/* routes. Single-user local install; no auth by default.

const API = '/api';
let CURRENT_TAB = 'chat';

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
function renderMd(raw) {
  if (!raw) return '';
  if (typeof marked !== 'undefined') {
    return '<div class="chat-md text-xs text-gray-300">' + marked.parse(raw) + '</div>';
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

// ── Tabs ────────────────────────────────────────────────────────────────
function switchTab(tab) {
  CURRENT_TAB = tab;
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
  else if (tab === 'followed') loadFollowed();
  else if (tab === 'progress') loadProgress();
  else if (tab === 'competitors') loadCompetitors();
  else if (tab === 'process') loadProcess();
  else if (tab === 'icpg') loadICPG();
  else if (tab === 'memory') loadMemory();
  else if (tab === 'routing') loadRouting();
  else if (tab === 'budget') loadBudget();
  else if (tab === 'forge') loadForge();
  else if (tab === 'settings') loadSettings();
}

// Project switching
function switchProject(name) {
  if (!name) return;
  updateCurrentProject(name);
  // Preload chat sessions for this project
  fetch('/api/chat/preload', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_key: name })
  }).then(function() { loadChat(); }).catch(function() {});
  // Refresh heartbeat for project context
  fetch('/api/heartbeat/trigger/collect_signals', { method: 'POST' }).catch(function(){});
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
  const [activity, inbox] = await Promise.all([
    api('/activity').catch(() => ({ sessions: [], recent: [] })),
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
  if (!sessions.length && !recent.length && !items.length) {
    html = `<div class="card p-4 text-sm text-gray-400">No activity detected. Start a Claude, Codex, or Kimi session to see it here.</div>`;
  }
  pane.innerHTML = html;
}

// ── Followed ────────────────────────────────────────────────────────────
async function loadFollowed() {
  const pane = document.getElementById('pane-followed');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading followed tasks…</div>`;
  try {
    const data = await api('/followed');
    const items = data.items || [];
    if (!items.length) {
      pane.innerHTML = `<div class="card p-4 text-sm text-gray-400">Nothing you're following right now.</div>`;
      return;
    }
    let html = `<h2 class="text-sm font-bold text-white mb-3">Following (${items.length})</h2><div class="space-y-2">`;
    for (const i of items) {
      html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${jsStr(i.id)}')">
        <div class="text-sm text-white">${esc(i.title)}</div>
        <div class="text-[11px] text-gray-500 mt-0.5">
          <span class="text-blue-400">${esc(i.board || '')}</span>
          ${i.assignee ? `· ${esc(i.assignee)}` : ''}
          · ${esc(relDate(i.updated_at))}
        </div>
      </div>`;
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
      <textarea id="reply-box" rows="3" class="w-full bg-gray-900 text-xs text-white rounded px-2 py-1.5 border border-gray-700"></textarea>
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
  const pane = document.getElementById('pane-competitors');
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
  try { return JSON.parse(localStorage.getItem('maggy-collapsed') || '[]'); } catch { return []; }
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
  const collapsed = _collapsedProjects();
  const idx = collapsed.indexOf(key);
  if (idx >= 0) collapsed.splice(idx, 1); else collapsed.push(key);
  localStorage.setItem('maggy-collapsed', JSON.stringify(collapsed));
  const pane = document.getElementById('pane-chat');
  if (pane) renderChatUI(pane);
}

async function loadChat() {
  const pane = document.getElementById('pane-chat');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading projects…</div>`;
  try {
    const result = await api('/chat/preload', { method: 'POST' });
    CHAT_SESSIONS_CACHE = result.sessions || [];
    if (!CHAT_SESSION_ID && CHAT_SESSIONS_CACHE.length) {
      CHAT_SESSION_ID = CHAT_SESSIONS_CACHE[0].id;
    }
    renderChatUI(pane);
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderChatUI(pane) {
  // Don't rebuild DOM while streaming — tab switch just shows/hides pane
  if (_streamingActive && pane.querySelector('#chat-messages')) return;
  const sessions = CHAT_SESSIONS_CACHE;
  let html = `<div class="flex h-full">`;
  html += renderChatSidebar(sessions);
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
  const collapsed = _collapsedProjects();
  // Sort: starred first, then alphabetical
  const keys = Object.keys(groups).sort((a, b) => {
    const aS = starred.includes(a) ? 0 : 1;
    const bS = starred.includes(b) ? 0 : 1;
    return aS - bS || a.localeCompare(b);
  });
  let html = `<div class="w-60 shrink-0 border-r border-gray-800 pr-3 overflow-y-auto">`;
  html += `<div class="flex items-center justify-between mb-2">
    <span class="text-[10px] text-gray-500 uppercase font-bold"><i class="fas fa-circle text-green-400 text-[8px] mr-1"></i>Projects</span>
    <button onclick="newChatSession()" class="text-[10px] px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-plus mr-1"></i>New</button>
  </div>`;
  if (!sessions.length) {
    html += `<div class="text-[10px] text-gray-500 p-2">No active CLI sessions detected</div>`;
  }
  for (const project of keys) {
    const slist = groups[project];
    const isStarred = starred.includes(project);
    const isCollapsed = collapsed.includes(project);
    const starCls = isStarred ? 'text-yellow-400' : 'text-gray-700 hover:text-yellow-400';
    const starIcon = isStarred ? 'fa-star' : 'fa-star';
    const chevron = isCollapsed ? 'fa-chevron-right' : 'fa-chevron-down';
    html += `<div class="mb-2">`;
    html += `<div class="flex items-center gap-1 mb-1 group">
      <button onclick="event.stopPropagation(); toggleCollapse('${jsStr(project)}')" class="text-[9px] text-gray-600 hover:text-white w-3"><i class="fas ${chevron}"></i></button>
      <button onclick="event.stopPropagation(); toggleStar('${jsStr(project)}')" class="text-[9px] ${starCls}" title="${isStarred ? 'Unstar' : 'Star'}"><i class="fas ${starIcon}"></i></button>
      <span class="text-[10px] text-gray-400 font-bold uppercase truncate flex-1 cursor-pointer" onclick="toggleCollapse('${jsStr(project)}')">${esc(project)}</span>
      <button onclick="newSessionForProject('${jsStr(project)}')" class="text-[9px] text-gray-600 hover:text-orange-400 opacity-0 group-hover:opacity-100" title="New session"><i class="fas fa-plus"></i></button>
    </div>`;
    if (!isCollapsed) {
      for (let i = 0; i < slist.length; i++) {
        const s = slist[i];
        const active = s.id === CHAT_SESSION_ID ? 'bg-gray-800 border-orange-500' : 'border-transparent hover:bg-gray-900';
        const displayName = s.label || `Session ${i + 1}`;
        const isBranch = s.label && s.label !== `Session ${i + 1}`;
        const icon = isBranch ? 'fa-code-branch' : 'fa-circle';
        const resumeBadge = s.has_resume_id ? '<i class="fas fa-history text-green-400 text-[7px]" title="Claude session linked"></i>' : '';
        html += `<div class="card px-2 py-1 cursor-pointer border ml-4 ${active}" onclick="openChatSession('${jsStr(s.id)}')">
          <div class="flex items-center gap-1">
            <i class="fas ${icon} ${isBranch ? 'text-orange-400' : 'text-green-400'} text-[7px]"></i>
            <span id="slabel-${esc(s.id)}" class="text-[10px] text-gray-300 flex-1 truncate">${esc(displayName)}</span>
            ${resumeBadge}
            <button onclick="event.stopPropagation(); renameSession('${jsStr(s.id)}')" class="text-[9px] text-gray-600 hover:text-orange-400" title="Rename"><i class="fas fa-pen"></i></button>
            <button onclick="event.stopPropagation(); deleteSession('${jsStr(s.id)}')" class="text-[9px] text-gray-600 hover:text-red-400" title="Delete"><i class="fas fa-trash"></i></button>
          </div>
        </div>`;
      }
    } else {
      // Show count badge when collapsed
      html += `<div class="ml-4 text-[9px] text-gray-600">${slist.length} session${slist.length !== 1 ? 's' : ''}</div>`;
    }
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

function renderChatMain() {
  let html = `<div class="flex-1 flex flex-col min-h-0">`;
  if (CHAT_SESSION_ID) {
    // Top progress shimmer bar (hidden by default)
    html += `<div id="progress-bar" class="hidden h-0.5 w-full overflow-hidden bg-gray-800/50"><div class="progress-shimmer h-full w-1/3"></div></div>`;
    // Model badge (shows current model during/after response)
    html += `<div id="chat-model-badge" class="hidden shrink-0 px-5 py-1.5 text-[10px] text-gray-500 border-b border-gray-800/50">
      <i class="fas fa-robot mr-1 text-orange-400/60"></i><span id="chat-model-name"></span>
    </div>`;
    // Messages scroll area
    html += `<div id="chat-messages" class="flex-1 overflow-y-auto min-h-0 px-5 py-3"><div id="chat-messages-inner" class="flex flex-col justify-end min-h-full space-y-3"></div></div>`;
    // Working zone (hidden by default)
    html += `<div id="working-zone" class="hidden shrink-0 px-5 py-2 border-t border-gray-700/30">
      <div class="flex items-center gap-2 mb-1">
        <span class="inline-block w-2 h-2 rounded-full bg-orange-500 animate-pulse"></span>
        <span id="model-label" class="text-[11px] text-gray-500"></span>
      </div>
      <pre id="joke-text" class="text-[11px] leading-relaxed ml-4 max-h-16 overflow-y-auto"></pre>
    </div>`;
    // Divider + input bar + divider
    html += `<div class="border-t border-gray-700/50"></div>`;
    html += `<div class="shrink-0 px-5 pt-3 pb-2 bg-[#0b0e14]">
      <div id="chat-attachments" class="hidden mb-1.5 flex flex-wrap gap-1"></div>
      <div class="flex gap-2">
        <input id="chat-file" type="file" class="hidden" onchange="handleFileSelect(event)" multiple />
        <button onclick="document.getElementById('chat-file').click()" class="px-3 py-2.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white text-sm" title="Attach file"><i class="fas fa-paperclip"></i></button>
        <div class="flex-1 relative">
          <div id="chat-ghost" class="absolute inset-x-0 top-0 px-3 py-2 text-sm text-gray-600 pointer-events-none whitespace-nowrap overflow-hidden"></div>
          <textarea id="chat-input" rows="1" placeholder="Type a message..."
            class="w-full text-sm text-white rounded-lg px-3 py-2 border border-gray-700 focus:border-orange-500 outline-none resize-none overflow-hidden"
            style="background: #151922; max-height: 120px;"
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
  let projects;
  try {
    const [cfg, activity] = await Promise.all([
      api('/config').catch(() => ({ codebases: [] })),
      api('/activity').catch(() => ({ sessions: [] })),
    ]);
    const configProjects = (cfg.codebases || []).map(c => ({ key: c.key, path: c.path }));
    const activeProjects = (activity.sessions || []).map(s => ({ key: s.project, path: s.project_path }));
    const seen = new Set();
    projects = [];
    for (const p of [...activeProjects, ...configProjects]) {
      if (p.key && !seen.has(p.key)) { seen.add(p.key); projects.push(p); }
    }
  } catch { projects = []; }
  if (!projects.length) { alert('No codebases found.'); return; }
  let chosen = projects[0];
  if (projects.length > 1) {
    const name = prompt('Select project:\n' + projects.map((p, i) => `${i+1}. ${p.key}`).join('\n') + '\n\nEnter name:', projects[0].key);
    if (!name) return;
    chosen = projects.find(p => p.key === name) || { key: name, path: '' };
  }
  try {
    const data = await api('/chat/sessions', { method: 'POST', body: JSON.stringify({ project_key: chosen.key, project_path: chosen.path }) });
    CHAT_SESSION_ID = data.id;
    loadChat();
  } catch (e) { alert('Failed: ' + e.message); }
}

async function newSessionForProject(projectKey) {
  const existing = CHAT_SESSIONS_CACHE.find(s => s.project_key === projectKey);
  const path = existing ? (existing.repo_dir || existing.working_dir) : '';
  try {
    const data = await api('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ project_key: projectKey, project_path: path }),
    });
    CHAT_SESSION_ID = data.id;
    loadChat();
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
  input.className = 'text-[10px] text-white bg-gray-900 border border-orange-500 rounded px-1 w-full outline-none';
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
  if (!confirm('Delete this session?')) return;
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
  return `<div class="flex justify-end"><div class="max-w-[75%] bg-orange-600/20 border border-orange-600/30 rounded-lg px-3 py-2">
    <div class="text-xs text-white whitespace-pre-wrap">${esc(m.content)}</div>${ts}
  </div></div>`;
}

function renderAssistantMsg(m) {
  const ts = m.timestamp ? `<div class="text-[10px] text-gray-500 mt-1">${esc(relDate(m.timestamp))}</div>` : '';
  return `<div class="flex justify-start"><div class="max-w-[75%] card px-3 py-2">
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
  let step = 0;
  const joke = JOKES[idx];
  el.innerHTML = `<span class="text-orange-400">${esc(joke[0])}</span>`;
  _jokeTimer = setInterval(() => {
    step++;
    if (step >= joke.length) {
      idx = (idx + 1) % JOKES.length;
      step = 0;
      const next = JOKES[idx];
      el.innerHTML = `<span class="text-orange-400">${esc(next[0])}</span>`;
    } else {
      const j = JOKES[idx];
      const cls = step % 2 === 1 ? 'text-gray-500' : 'text-orange-400';
      el.innerHTML += `<br><span class="${cls}">${esc(j[step])}</span>`;
    }
  }, 1800);
}

function stopJokeRotation() {
  if (_jokeTimer) { clearInterval(_jokeTimer); _jokeTimer = null; }
}

function showWorking() {
  const bar = document.getElementById('progress-bar');
  const zone = document.getElementById('working-zone');
  const label = document.getElementById('model-label');
  if (bar) bar.classList.remove('hidden');
  if (zone) zone.classList.remove('hidden');
  if (label) label.textContent = 'Thinking…';
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
  if (zone) zone.classList.add('hidden');
  if (joke) joke.innerHTML = '';
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
  const input = document.getElementById('chat-input');
  const ghost = document.getElementById('chat-ghost');
  if (!input || !ghost) return;
  const val = input.value;
  if (val.length > 0 && _currentSuggestion.toLowerCase().startsWith(val.toLowerCase())) {
    ghost.textContent = _currentSuggestion;
    ghost.style.color = '';
  } else if (val.length === 0 && _currentSuggestion) {
    ghost.textContent = _currentSuggestion;
    ghost.style.color = '';
  } else {
    ghost.textContent = '';
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

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  let message = input.value.trim();
  if (!message && !_pendingFiles.length) return;
  if (!CHAT_SESSION_ID) return;
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
  const outer = document.getElementById('chat-messages');
  const el = document.getElementById('chat-messages-inner') || outer;
  el.innerHTML += renderUserMsg({ content: message, timestamp: '' });
  el.innerHTML += `<div id="stream-response" class="flex justify-start"><div class="max-w-[75%] card px-3 py-2">
    <div id="stream-text" class="text-xs text-gray-300"></div>
    <div id="stream-tools" class="mt-1"></div>
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
          const tool = data.tool || data.content || 'tool';
          toolsEl.innerHTML += `<div class="text-[10px] text-gray-500"><i class="fas fa-wrench text-orange-400/50 mr-1"></i>${esc(tool)}</div>`;
          el.scrollTop = el.scrollHeight;
          continue;
        }
        if (data.type === 'agent_status' && toolsEl) {
          toolsEl.innerHTML += `<div class="text-[10px] text-blue-400/70"><i class="fas fa-info-circle mr-1"></i>${esc(data.status || data.content || '')}</div>`;
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
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading settings…</div>`;
  try {
    const cfg = await api('/config');
    pane.innerHTML = `
      <h2 class="text-sm font-bold text-white mb-3">Settings</h2>
      <div class="card p-4 space-y-3 text-sm text-gray-300">
        <div><span class="text-gray-500 text-[10px] uppercase">Org</span> — <b>${esc(cfg.org.name)}</b> ${cfg.org.domain ? `(domain: <span class="text-orange-400">${esc(cfg.org.domain)}</span>)` : ''}</div>
        <div><span class="text-gray-500 text-[10px] uppercase">Issue Tracker</span> — ${esc(cfg.issue_tracker.provider)}</div>
        <div><span class="text-gray-500 text-[10px] uppercase">Codebases</span>
          <ul class="ml-4 text-xs">${cfg.codebases.map(c => `<li>${esc(c.key)} → <code class="text-gray-400">${esc(c.path)}</code></li>`).join('')}</ul>
        </div>
        <div><span class="text-gray-500 text-[10px] uppercase">Competitors</span> — categories: ${cfg.competitors.categories.map(esc).join(', ') || '—'}</div>
        <div><span class="text-gray-500 text-[10px] uppercase">OKRs</span> — source: ${esc(cfg.okrs.source)} (${cfg.okrs.count} items)</div>
        <div><span class="text-gray-500 text-[10px] uppercase">AI</span> — ${esc(cfg.ai.provider)} / ${esc(cfg.ai.model)} · API key ${cfg.ai.has_key ? '<span class="text-green-400">set</span>' : '<span class="text-red-400">MISSING</span>'}</div>
      </div>
      <p class="text-[11px] text-gray-500 mt-4">Edit <code>~/.maggy/config.yaml</code> and restart Maggy to apply changes.</p>
    `;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
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
async function loadProcess() {
  const pane = document.getElementById('pane-process');
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

async function loadICPG() {
  const pane = document.getElementById('pane-icpg');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading iCPG…</div>`;
  try {
    const data = await api('/icpg/overview');
    if (ICPG_PROJECT) { await loadICPGProject(ICPG_PROJECT); return; }
    pane.innerHTML = renderICPGOverview(data);
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

function renderICPGOverview(data) {
  const t = data.total || {};
  let html = `<div class="overflow-y-auto h-full">`;
  html += `<h2 class="text-sm font-bold text-white mb-3"><i class="fas fa-project-diagram text-orange-400 mr-2"></i>iCPG — Intent Graph</h2>`;
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
  const pane = document.getElementById('pane-icpg');
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
    <button onclick="ICPG_PROJECT=null;loadICPG()" class="text-xs text-gray-400 hover:text-white"><i class="fas fa-arrow-left mr-1"></i></button>
    <h2 class="text-sm font-bold text-white"><i class="fas fa-project-diagram text-orange-400 mr-2"></i>${esc(key)}</h2>
    <span class="text-[10px] text-gray-500">${(reasons.reasons||[]).length} intents</span>
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
  html += `<div class="card p-3 mb-3"><div class="text-[10px] text-gray-500 uppercase mb-2"><i class="fas fa-bullseye mr-1"></i>Intents</div>`;
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

async function loadICPGGraph(key) {
  const pane = document.getElementById('pane-icpg');
  try {
    const data = await api(`/icpg/${encodeURIComponent(key)}/graph?limit=150`);
    const nodes = data.nodes || [];
    const edges = data.edges || [];
    if (!nodes.length) { alert('No graph data'); return; }
    renderICPGGraphSVG(pane, key, nodes, edges);
  } catch (e) { alert('Graph failed: ' + e.message); }
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
    const [engramDiag, engramQuery] = await Promise.all([
      api('/engram/diagnostics').catch(function() { return {}; }),
      api('/engram/query?limit=5').catch(function() { return { records: [] }; })
    ]);
    var html = '<div class="p-4 space-y-4 h-full overflow-y-auto scroll-thin">';
    html += '<div class="card p-4">';
    html += '<h3 class="text-sm font-bold text-white mb-3"><i class="fas fa-brain text-orange-500 mr-2"></i>Memory Health</h3>';
    html += '<div class="grid grid-cols-3 gap-3 text-xs">';
    var fatigue = engramDiag.fatigue_score || 0;
    var state = fatigue < 0.4 ? 'FLOW' : fatigue < 0.6 ? 'COMPRESS' : fatigue < 0.75 ? 'PRE_SLEEP' : fatigue < 0.9 ? 'REM' : 'EMERGENCY';
    var stateColor = fatigue < 0.4 ? '#22c55e' : fatigue < 0.6 ? '#eab308' : fatigue < 0.75 ? '#f97316' : '#ef4444';
    html += '<div class="col-span-3"><div class="flex justify-between mb-1"><span>Fatigue</span><span style="color:' + stateColor + '">' + (fatigue * 100).toFixed(0) + '% · ' + state + '</span></div>';
    html += '<div class="w-full h-2 rounded-full" style="background:#1e2636"><div class="h-2 rounded-full" style="width:' + (fatigue * 100) + '%;background:' + stateColor + '"></div></div></div>';
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
        html += '<span class="badge" style="font-size:9px;background:#1e2636">' + esc(r.memory_type || 'fact') + '</span>';
        html += '<span class="flex-1 truncate text-gray-300">' + esc((r.content || '').substring(0, 80)) + '</span>';
        html += '<span class="text-gray-600">' + relDate(r.created_at) + '</span></div>';
      }
      html += '</div>';
    }
    html += '</div>';
    pane.innerHTML = html;
    var fb = document.getElementById('fatigue-badge');
    if (fb) { fb.textContent = (fatigue * 100).toFixed(0) + '% · ' + state; fb.style.color = stateColor; fb.className = ''; }
  } catch (e) {
    pane.innerHTML = '<div class="flex items-center justify-center h-full text-gray-600 text-xs">Memory offline — start a task to populate</div>';
  }
}

// ── Progress Dashboard ──────────────────────────────────────────────────
async function loadProgress() {
  var pane = document.getElementById('pane-progress');
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

// ── Init ────────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    var h = await api('/health');
    var orgEl = document.getElementById('org-badge');
    if (orgEl) orgEl.textContent = h.org + ' · ' + (h.provider || '') + ' · ' + (h.codebases || 0) + ' codebases';
  } catch (e) {}
  try {
    var projData = await api('/projects');
    var projects = (projData.projects || []).map(function(p) { return p.name; });
    updateProjectList(projects);
  } catch (e) {}
  var ready = typeof checkSetup === 'function' ? await checkSetup() : true;
  if (ready) switchTab(CURRENT_TAB);
}

loadAll();
