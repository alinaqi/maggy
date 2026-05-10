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
  // Close system dropdown
  const menu = document.getElementById('system-menu');
  if (menu) menu.classList.add('hidden');
  // Highlight active tab button (nav bar)
  for (const b of document.querySelectorAll('.tab-btn')) {
    b.classList.toggle('active', b.dataset.tab === tab);
  }
  // Highlight active system dropdown item
  const gear = document.getElementById('system-gear');
  const sysTabs = ['budget', 'routing', 'forge', 'settings'];
  if (gear) {
    gear.classList.toggle('active', sysTabs.includes(tab));
  }
  for (const s of document.querySelectorAll('.sys-item')) {
    s.classList.toggle(
      'text-orange-400', s.dataset.tab === tab,
    );
  }
  // Show/hide panes
  for (const p of document.querySelectorAll('.pane')) {
    p.classList.toggle('hidden', p.id !== `pane-${tab}`);
  }
  if (tab === 'chat') loadChat();
  else if (tab === 'inbox') loadInbox();
  else if (tab === 'followed') loadFollowed();
  else if (tab === 'competitors') loadCompetitors();
  else if (tab === 'process') loadProcess();
  else if (tab === 'budget') loadBudget();
  else if (tab === 'routing') loadRouting();
  else if (tab === 'forge') loadForge();
  else if (tab === 'settings') loadSettings();
}

function toggleSystemMenu() {
  const menu = document.getElementById('system-menu');
  if (menu) menu.classList.toggle('hidden');
}

// Close system menu when clicking outside
document.addEventListener('click', (e) => {
  const menu = document.getElementById('system-menu');
  const gear = document.getElementById('system-gear');
  if (!menu || !gear) return;
  if (!gear.contains(e.target) && !menu.contains(e.target)) {
    menu.classList.add('hidden');
  }
});

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

async function loadChat() {
  const pane = document.getElementById('pane-chat');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Auto-connecting to active projects…</div>`;
  try {
    const result = await api('/chat/auto-connect', { method: 'POST' });
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
  const sessions = CHAT_SESSIONS_CACHE;
  let html = `<div class="flex h-[calc(100vh-10rem)]">`;
  html += renderChatSidebar(sessions);
  html += renderChatMain();
  html += `</div>`;
  pane.innerHTML = html;
  if (CHAT_SESSION_ID) loadChatMessages(CHAT_SESSION_ID);
}

function renderChatSidebar(sessions) {
  let html = `<div class="w-60 shrink-0 border-r border-gray-800 pr-3 overflow-y-auto">`;
  html += `<div class="flex items-center justify-between mb-2">
    <span class="text-[10px] text-gray-500 uppercase font-bold"><i class="fas fa-circle text-green-400 text-[8px] mr-1"></i>Connected Projects</span>
    <button onclick="newChatSession()" class="text-[10px] px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-plus mr-1"></i>New</button>
  </div><div class="space-y-1">`;
  if (!sessions.length) {
    html += `<div class="text-[10px] text-gray-500 p-2">No active CLI sessions detected</div>`;
  }
  for (const s of sessions) {
    const active = s.id === CHAT_SESSION_ID ? 'bg-gray-800 border-orange-500' : 'border-transparent hover:bg-gray-900';
    const ctx = s.history_context ? ' title="' + esc(s.history_context) + '"' : '';
    html += `<div class="card px-2 py-1.5 cursor-pointer border ${active}" onclick="openChatSession('${jsStr(s.id)}')"${ctx}>
      <div class="flex items-center gap-1"><i class="fas fa-circle text-green-400 text-[6px]"></i><span class="text-xs text-white truncate">${esc(s.project_key)}</span></div>
      <div class="text-[10px] text-gray-500 truncate">${esc(s.working_dir)}</div>
      ${s.history_context ? '<div class="text-[9px] text-gray-600 mt-0.5 truncate"><i class="fas fa-history mr-0.5"></i>has history</div>' : ''}
    </div>`;
  }
  html += `</div></div>`;
  return html;
}

function renderChatMain() {
  let html = `<div class="flex-1 flex flex-col pl-4">`;
  if (CHAT_SESSION_ID) {
    html += `<div id="chat-messages" class="flex-1 overflow-y-auto space-y-3 mb-3"></div>`;
    html += `<div class="shrink-0 flex gap-2">
      <input id="chat-input" type="text" placeholder="Type a message to Claude…"
        class="flex-1 bg-gray-900 text-sm text-white rounded px-3 py-2 border border-gray-700 focus:border-orange-500 outline-none"
        onkeydown="if(event.key==='Enter')sendChatMessage()" />
      <button onclick="sendChatMessage()" class="px-4 py-2 rounded bg-orange-600 hover:bg-orange-700 text-white text-sm"><i class="fas fa-paper-plane"></i></button>
    </div>`;
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

function openChatSession(id) {
  CHAT_SESSION_ID = id;
  const pane = document.getElementById('pane-chat');
  if (pane) renderChatUI(pane);
}

async function loadChatMessages(id) {
  const el = document.getElementById('chat-messages');
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
    el.scrollTop = el.scrollHeight;
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
  return `<div class="flex justify-end"><div class="max-w-[80%] bg-orange-600/20 border border-orange-600/30 rounded-lg px-3 py-2">
    <div class="text-xs text-white">${esc(m.content)}</div>
    <div class="text-[10px] text-gray-500 mt-1">${esc(relDate(m.timestamp))}</div>
  </div></div>`;
}

function renderAssistantMsg(m) {
  return `<div class="flex justify-start"><div class="max-w-[80%] card px-3 py-2">
    <pre class="text-xs text-gray-300 whitespace-pre-wrap">${esc(m.content)}</pre>
    <div class="text-[10px] text-gray-500 mt-1">${esc(relDate(m.timestamp))}</div>
  </div></div>`;
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const message = input.value.trim();
  if (!message || !CHAT_SESSION_ID) return;
  input.value = '';
  input.disabled = true;
  const el = document.getElementById('chat-messages');
  el.innerHTML += renderUserMsg({ content: message, timestamp: '' });
  el.innerHTML += `<div id="stream-response" class="flex justify-start"><div class="max-w-[80%] card px-3 py-2">
    <pre id="stream-text" class="text-xs text-gray-300"><i class="fas fa-spinner fa-spin text-orange-400"></i> Claude is thinking…</pre>
  </div></div>`;
  el.scrollTop = el.scrollHeight;
  try {
    await streamChatResponse(message, el);
  } catch (e) {
    const streamEl = document.getElementById('stream-text');
    if (streamEl) streamEl.innerHTML = `<span class="text-red-400">Error: ${esc(e.message)}</span>`;
  }
  input.disabled = false;
  input.focus();
}

async function streamChatResponse(message, el) {
  const apiKey = localStorage.getItem('maggy-api-key') || '';
  const resp = await fetch(`${API}/chat/sessions/${CHAT_SESSION_ID}/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(apiKey ? { 'X-API-Key': apiKey } : {}) },
    body: JSON.stringify({ message }),
  });
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let responseText = '';
  const streamEl = document.getElementById('stream-text');
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const line of chunk.split('\n')) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.type === 'done') continue;
        if (data.type === 'error') { streamEl.innerHTML = `<span class="text-red-400">${esc(data.content)}</span>`; continue; }
        if (data.content) { responseText += data.content; streamEl.textContent = responseText; el.scrollTop = el.scrollHeight; }
      } catch {}
    }
  }
  if (!responseText) streamEl.textContent = '(no response)';
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

// ── Init ────────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    const h = await api('/health');
    document.getElementById('org-badge').textContent = `${h.org} · ${h.provider} · ${h.codebases} codebases`;
  } catch {}
  const ready = await checkSetup();
  if (ready) switchTab(CURRENT_TAB);
}

loadAll();
