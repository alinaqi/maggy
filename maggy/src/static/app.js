// Maggy dashboard — vanilla JS, no build step.
// Talks to /api/* routes. Single-user local install; no auth by default.

const API = '/api';
let CURRENT_TAB = 'inbox';

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
  for (const b of document.querySelectorAll('.tab-btn')) {
    b.classList.toggle('active', b.dataset.tab === tab);
  }
  for (const p of document.querySelectorAll('.pane')) {
    p.classList.toggle('hidden', p.id !== `pane-${tab}`);
  }
  if (tab === 'inbox') loadInbox();
  else if (tab === 'followed') loadFollowed();
  else if (tab === 'competitors') loadCompetitors();
  else if (tab === 'sessions') loadSessions();
  else if (tab === 'settings') loadSettings();
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
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading inbox…</div>`;
  try {
    const data = await api(`/inbox${refresh ? '?refresh=true' : ''}`);
    const items = data.items || [];
    if (!items.length) {
      pane.innerHTML = `<div class="card p-4 text-sm text-gray-400">No open tasks found. Check your config or try <button class="text-orange-400 underline" onclick="loadInbox(true)">refresh</button>.</div>`;
      return;
    }
    let html = `<div class="flex items-center gap-3 mb-3">
      <h2 class="text-sm font-bold text-white">Inbox (${items.length})</h2>
      <button onclick="loadInbox(true)" class="text-[10px] text-gray-400 hover:text-white"><i class="fas fa-rotate mr-1"></i>Re-rank</button>
    </div>`;
    html += `<div class="space-y-2">`;
    for (const i of items) {
      const labels = (i.labels || []).slice(0, 4).map(l => `<span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">${esc(l)}</span>`).join(' ');
      html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${esc(i.id)}')">
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
            ${i.ai_reason ? `<div class="text-[11px] text-gray-400 mt-1 italic">“${esc(i.ai_reason)}”</div>` : ''}
          </div>
          <div class="flex gap-1 shrink-0" onclick="event.stopPropagation()">
            <button onclick="executeTask('${esc(i.id)}', 'plan')" class="text-[10px] px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300">Plan</button>
            <button onclick="executeTask('${esc(i.id)}', 'tdd')" class="text-[10px] px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white">Execute</button>
          </div>
        </div>
      </div>`;
    }
    html += `</div>`;
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
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
      html += `<div class="card p-3 hover:bg-gray-900 cursor-pointer" onclick="openTaskDetail('${esc(i.id)}')">
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
      <button onclick="executeTask('${esc(t.id)}', 'plan')" class="flex-1 text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-white"><i class="fas fa-list-check mr-1"></i>Plan</button>
      <button onclick="executeTask('${esc(t.id)}', 'tdd')" class="flex-1 text-xs px-3 py-1.5 rounded bg-orange-600 hover:bg-orange-700 text-white"><i class="fas fa-play mr-1"></i>Execute (TDD)</button>
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
      <button onclick="postReply('${esc(t.id)}')" class="mt-2 text-xs px-3 py-1 rounded bg-blue-600 text-white">Post</button>
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
  document.getElementById('briefing').innerHTML = '<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Regenerating…</div>';
  await api('/competitors/news/summary?refresh=true');
  loadBriefing();
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

// ── Sessions ────────────────────────────────────────────────────────────
async function loadSessions() {
  const pane = document.getElementById('pane-sessions');
  pane.innerHTML = `<div class="text-xs text-gray-500"><i class="fas fa-spinner fa-spin mr-1"></i>Loading sessions…</div>`;
  try {
    const sessions = await api('/execute/sessions');
    if (!sessions.length) {
      pane.innerHTML = `<div class="card p-4 text-sm text-gray-400">No execution sessions yet. Click <b>Execute</b> on a task in the Inbox.</div>`;
      return;
    }
    let html = `<h2 class="text-sm font-bold text-white mb-3">Sessions (${sessions.length})</h2><div class="space-y-2">`;
    for (const s of sessions) {
      const statusCls = s.status === 'running' ? 'text-yellow-400' : s.status === 'completed' ? 'text-green-400' : 'text-red-400';
      html += `<div class="card p-3 cursor-pointer" onclick="openSession('${esc(s.id)}')">
        <div class="flex items-center justify-between">
          <div class="text-sm text-white">${esc(s.task_title || s.task_id)}</div>
          <span class="text-[10px] ${statusCls}">${esc(s.status)}</span>
        </div>
        <div class="text-[10px] text-gray-500 mt-0.5">${esc(s.mode)} · ${esc(relDate(s.started_at))} · ${esc(s.id)}</div>
      </div>`;
    }
    html += `</div>`;
    pane.innerHTML = html;
  } catch (e) {
    pane.innerHTML = `<div class="card p-4 text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
}

async function openSession(id) {
  openDrawer('Session ' + id, '<div class="text-xs text-gray-500">Loading…</div>');
  try {
    const s = await api(`/execute/sessions/${id}`);
    document.getElementById('drawer-title').textContent = s.task_title || s.task_id;
    document.getElementById('drawer-body').innerHTML = `
      <div class="text-[10px] text-gray-500 mb-2">
        ${esc(s.status)} · ${esc(s.mode)} · ${esc(s.working_dir || '')}
      </div>
      <pre class="text-xs text-gray-300 bg-black/40 p-3 rounded max-h-[70vh] overflow-y-auto">${esc(s.output || '(no output yet)')}</pre>
    `;
  } catch (e) {
    document.getElementById('drawer-body').innerHTML = `<div class="text-sm text-red-400">Failed: ${esc(e.message)}</div>`;
  }
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

// ── Init ────────────────────────────────────────────────────────────────
async function loadAll() {
  try {
    const h = await api('/health');
    document.getElementById('org-badge').textContent = `${h.org} · ${h.provider} · ${h.codebases} codebases`;
  } catch {}
  if (CURRENT_TAB === 'inbox') loadInbox();
  else if (CURRENT_TAB === 'followed') loadFollowed();
  else if (CURRENT_TAB === 'competitors') loadCompetitors();
  else if (CURRENT_TAB === 'sessions') loadSessions();
  else if (CURRENT_TAB === 'settings') loadSettings();
}

loadAll();
