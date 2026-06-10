ADMIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --page-bg:      #F4F6F8;
      --surface:      #FFFFFF;
      --border:       #E2E8F0;
      --text:         #1A202C;
      --text-sec:     #4A5568;
      --muted:        #718096;
      --primary:      #0D6EFD;
      --success:      #198754;
      --success-bg:   #D1E7DD;
      --success-text: #0A3622;
      --warning:      #B45309;
      --warning-bg:   #FEF3C7;
      --warning-text: #78350F;
      --danger:       #DC3545;
      --danger-bg:    #FEE2E2;
      --danger-text:  #7F1D1D;
      --info-bg:      #DBEAFE;
      --info-text:    #1E3A8A;
      --radius-sm:    6px;
      --radius-md:    10px;
      --radius-lg:    14px;
      --shadow-sm:    0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
      --shadow-md:    0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--page-bg);
      color: var(--text);
      min-height: 100vh;
    }

    /* ── Header ── */
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0.875rem 1.75rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { font-size: 1rem; font-weight: 600; letter-spacing: -0.01em; }
    header a  { font-size: 0.8rem; color: var(--muted); text-decoration: none; transition: color 0.12s; }
    header a:hover { color: var(--text); }

    main { padding: 2rem 1.75rem; max-width: 860px; margin: 0 auto; }

    /* ── Tabs ── */
    .tabs {
      display: flex;
      gap: 0;
      border-bottom: 1px solid var(--border);
      margin-bottom: 2rem;
    }
    .tab-btn {
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      padding: 0.6rem 1.1rem;
      font-size: 0.875rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      color: var(--muted);
      margin-bottom: -1px;
      transition: color 0.12s, border-color 0.12s;
    }
    .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
    .tab-btn:hover:not(.active) { color: var(--text-sec); }

    /* ── Stat cards ── */
    .stats-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }
    @media (max-width: 640px) {
      .stats-row { grid-template-columns: repeat(2, 1fr); }
    }

    .stat-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1.25rem 1.25rem 1rem;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
    }
    .stat-value {
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1;
      color: var(--text);
    }
    .stat-label {
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }
    .stat-card.green .stat-value { color: var(--success); }
    .stat-card.blue  .stat-value { color: var(--primary); }
    .stat-card.red   .stat-value { color: var(--danger); }

    /* ── Section heading ── */
    .section-heading {
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--muted);
      margin-bottom: 0.75rem;
    }

    /* ── History cards ── */
    .history-list { display: flex; flex-direction: column; gap: 0.625rem; }

    .history-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      box-shadow: var(--shadow-sm);
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.5rem 1rem;
      align-items: start;
      position: relative;
      overflow: hidden;
      transition: box-shadow 0.15s, border-color 0.15s;
    }
    .history-card:hover {
      box-shadow: var(--shadow-md);
      border-color: #CBD5E1;
    }
    .history-card::before {
      content: '';
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      border-radius: 3px 0 0 3px;
    }
    .history-card.status-imported::before   { background: var(--success); }
    .history-card.status-downloading::before,
    .history-card.status-importing::before  { background: var(--primary); }
    .history-card.status-error::before      { background: var(--danger); }

    .card-left { min-width: 0; }

    .card-title-row {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 0.3rem;
    }
    .card-title {
      font-size: 0.925rem;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.01em;
    }
    .card-author {
      font-size: 0.8rem;
      color: var(--text-sec);
    }

    .card-release {
      font-size: 0.75rem;
      color: var(--muted);
      margin-bottom: 0.5rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .card-chips {
      display: flex;
      align-items: center;
      gap: 0.375rem;
      flex-wrap: wrap;
    }
    .chip {
      font-size: 0.68rem;
      font-weight: 500;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      border: 1px solid var(--border);
      background: var(--page-bg);
      color: var(--text-sec);
      white-space: nowrap;
    }
    .chip-torrent    { background: #EDE9FE; border-color: #DDD6FE; color: #5B21B6; }
    .chip-usenet     { background: #FEF3C7; border-color: #FDE68A; color: #92400E; }
    .chip-goodreads  { background: #FCE7F3; border-color: #F9A8D4; color: #9D174D; }

    .card-right {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.4rem;
      flex-shrink: 0;
    }

    /* Status badge */
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.2rem 0.55rem;
      border-radius: 20px;
    }
    .status-badge::before {
      content: '';
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
    }
    .badge-imported    { background: var(--success-bg); color: var(--success-text); }
    .badge-downloading { background: var(--info-bg);    color: var(--info-text); }
    .badge-importing   { background: var(--info-bg);    color: var(--info-text); }
    .badge-error       { background: var(--danger-bg);  color: var(--danger-text); }
    .badge-unknown     { background: #F1F5F9;            color: var(--muted); }

    .card-date {
      font-size: 0.72rem;
      color: var(--muted);
      text-align: right;
    }

    .card-error {
      grid-column: 1 / -1;
      font-size: 0.75rem;
      color: var(--danger);
      background: var(--danger-bg);
      border-radius: var(--radius-sm);
      padding: 0.4rem 0.65rem;
      margin-top: 0.25rem;
    }

    /* ── Profiles tab ── */
    .profiles-list {
      display: flex;
      flex-direction: column;
      gap: 0.625rem;
      margin-bottom: 1.5rem;
    }

    .profile-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      box-shadow: var(--shadow-sm);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .profile-info { min-width: 0; }
    .profile-name {
      font-size: 0.925rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.2rem;
    }
    .profile-meta {
      font-size: 0.78rem;
      color: var(--muted);
    }

    .btn-remove {
      background: none;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 0.3rem 0.65rem;
      font-size: 0.75rem;
      font-weight: 500;
      font-family: inherit;
      color: var(--muted);
      cursor: pointer;
      transition: border-color 0.12s, color 0.12s, background 0.12s;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .btn-remove:hover {
      border-color: var(--danger);
      color: var(--danger);
      background: var(--danger-bg);
    }

    /* ── Add profile form card ── */
    .add-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1.5rem;
      box-shadow: var(--shadow-sm);
    }
    .add-card h2 {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.375rem;
    }
    .add-card .hint {
      font-size: 0.78rem;
      color: var(--muted);
      line-height: 1.5;
      margin-bottom: 1.25rem;
    }
    .add-card .hint code {
      font-size: 0.75rem;
      background: var(--page-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.1rem 0.35rem;
      font-family: 'SFMono-Regular', Consolas, monospace;
      color: var(--text-sec);
    }

    .form-row {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: flex-end;
      margin-bottom: 0.75rem;
    }
    .form-field {
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
    }
    .form-field.field-name  { flex: 0 0 140px; }
    .form-field.field-uid   { flex: 1; min-width: 180px; }
    .form-field.field-shelf { flex: 0 0 130px; }

    .form-field label {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--text-sec);
      letter-spacing: 0.02em;
    }
    .form-field input {
      background: var(--page-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.5rem 0.75rem;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
    }
    .form-field input:focus {
      border-color: var(--primary);
      background: var(--surface);
      box-shadow: 0 0 0 3px rgba(13,110,253,0.12);
    }

    .btn-add {
      padding: 0.5rem 1.25rem;
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.12s, opacity 0.12s;
      white-space: nowrap;
      align-self: flex-end;
    }
    .btn-add:hover:not(:disabled) { background: #0b5ed7; }
    .btn-add:disabled { opacity: 0.5; cursor: not-allowed; }

    .backlog-row {
      display: flex;
      align-items: flex-start;
      gap: 0.6rem;
      margin-top: 0.25rem;
    }
    .backlog-row input[type="checkbox"] {
      margin-top: 0.15rem;
      flex-shrink: 0;
      accent-color: var(--primary);
      width: 15px;
      height: 15px;
      cursor: pointer;
    }
    .backlog-row label {
      font-size: 0.82rem;
      color: var(--text-sec);
      cursor: pointer;
      font-weight: 500;
      letter-spacing: 0;
    }

    .backlog-notice {
      font-size: 0.78rem;
      color: var(--warning-text);
      background: var(--warning-bg);
      border-radius: var(--radius-sm);
      padding: 0.5rem 0.75rem;
      margin-top: 0.75rem;
      display: none;
      line-height: 1.5;
    }
    .backlog-notice.visible { display: block; }

    .form-msg {
      font-size: 0.78rem;
      padding: 0.4rem 0.65rem;
      border-radius: var(--radius-sm);
      display: none;
      margin-top: 0.75rem;
    }
    .form-msg.success { display: block; background: var(--success-bg); color: var(--success-text); }
    .form-msg.error   { display: block; background: var(--danger-bg);  color: var(--danger-text); }

    /* ── Empty / loading ── */
    .empty-state {
      text-align: center;
      padding: 4rem 1rem;
      color: var(--muted);
    }
    .empty-state .empty-icon { font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.4; }
    .empty-state p { font-size: 0.875rem; }
  </style>
</head>
<body>

<header>
  <h1>Admin</h1>
  <a href="/portal">← back to requests</a>
</header>

<main>
  <!-- Tabs -->
  <div class="tabs">
    <button class="tab-btn active" data-tab="history"  onclick="showTab('history')">History</button>
    <button class="tab-btn"        data-tab="profiles" onclick="showTab('profiles')">Goodreads Profiles</button>
  </div>

  <!-- History tab -->
  <div id="panel-history" class="tab-panel">
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value" id="stat-total">—</div>
        <div class="stat-label">Total requested</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value" id="stat-imported">—</div>
        <div class="stat-label">In Library</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-value" id="stat-active">—</div>
        <div class="stat-label">In progress</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value" id="stat-errors">—</div>
        <div class="stat-label">Errors</div>
      </div>
    </div>
    <div id="history-section"></div>
  </div>

  <!-- Profiles tab -->
  <div id="panel-profiles" class="tab-panel" style="display:none">
    <div class="section-heading" id="profiles-heading">Profiles</div>
    <div class="profiles-list" id="profiles-list"></div>

    <div class="add-card">
      <h2>Add a profile</h2>
      <p class="hint">
        Enter a first name and a Goodreads user ID. To find your user ID, go to your
        Goodreads profile page — the URL will look like<br>
        <code>goodreads.com/user/show/12345678-firstname</code><br>
        Copy the entire <code>12345678-firstname</code> portion.
      </p>
      <div class="form-row">
        <div class="form-field field-name">
          <label for="inp-name">First name</label>
          <input id="inp-name" type="text" placeholder="e.g. Sarah" autocomplete="off">
        </div>
        <div class="form-field field-uid">
          <label for="inp-uid">Goodreads user ID</label>
          <input id="inp-uid" type="text" placeholder="e.g. 98765432-sarah" autocomplete="off">
        </div>
        <div class="form-field field-shelf">
          <label for="inp-shelf">Shelf</label>
          <input id="inp-shelf" type="text" placeholder="to-read" value="to-read" autocomplete="off">
        </div>
        <button class="btn-add" onclick="addProfile()">Add profile</button>
      </div>
      <div class="backlog-row">
        <input type="checkbox" id="chk-backlog" onchange="toggleBacklog()">
        <label for="chk-backlog">Download all books from my Want to Read shelf</label>
      </div>
      <div class="backlog-notice" id="backlog-notice">
        Depending on the number of books in your shelf, it could take a few days to add them all to the Calibre library.
      </div>
      <div class="form-msg" id="form-msg"></div>
    </div>
  </div>
</main>

<script>
  // ── Tab switching ──────────────────────────────────────────────────────────

  let _profilesLoaded = false;

  function showTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tab === name)
    );
    document.getElementById('panel-history').style.display  = name === 'history'  ? '' : 'none';
    document.getElementById('panel-profiles').style.display = name === 'profiles' ? '' : 'none';
    if (name === 'profiles') loadProfiles();
    history.replaceState(null, '', '#' + name);
  }

  // Restore tab from URL hash on load
  (function () {
    const hash = location.hash.replace('#', '');
    if (hash === 'profiles') showTab('profiles');
  })();


  // ── Shared helpers ─────────────────────────────────────────────────────────

  function handle401() {
    document.getElementById('history-section').innerHTML =
      '<div class="empty-state"><div class="empty-icon">🔒</div>'
      + '<p><a href="/" style="color:var(--primary)">← Log in first</a>, then return to this page.</p></div>';
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }


  // ── History tab ────────────────────────────────────────────────────────────

  async function load() {
    try {
      const resp = await fetch('/portal/history', { credentials: 'include' });
      if (resp.status === 401) { handle401(); return; }
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      renderHistory(data.items || []);
    } catch (e) {
      document.getElementById('history-section').innerHTML =
        '<div class="empty-state"><p style="color:var(--danger)">' + esc(e.message) + '</p></div>';
    }
  }

  function renderHistory(items) {
    const total    = items.length;
    const imported = items.filter(i => i.status === 'imported').length;
    const active   = items.filter(i => i.status === 'downloading' || i.status === 'importing').length;
    const errors   = items.filter(i => i.status === 'error').length;

    document.getElementById('stat-total').textContent    = total;
    document.getElementById('stat-imported').textContent = imported;
    document.getElementById('stat-active').textContent   = active;
    document.getElementById('stat-errors').textContent   = errors;

    const section = document.getElementById('history-section');

    if (!items.length) {
      section.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div>'
        + '<p>No downloads recorded yet.</p></div>';
      return;
    }

    let html = '<div class="section-heading">' + total + ' download' + (total !== 1 ? 's' : '') + '</div>';
    html += '<div class="history-list">';

    items.forEach(item => {
      const statusClass = 'status-' + (item.status || 'unknown');
      const badgeClass  = 'badge-' + (item.status || 'unknown');
      const statusLabel = (item.status || 'unknown').replace(/_/g, ' ');

      const proto = (item.protocol || '').toLowerCase();
      const protoChip = proto === 'torrent'
        ? '<span class="chip chip-torrent">torrent</span>'
        : proto === 'nzb' || proto === 'usenet'
          ? '<span class="chip chip-usenet">usenet</span>'
          : '';

      const indexerChip = item.indexer
        ? '<span class="chip">' + esc(item.indexer) + '</span>'
        : '';

      const grChip = (item.source || '').startsWith('goodreads:')
        ? '<span class="chip chip-goodreads">Goodreads: ' + esc(item.source.slice('goodreads:'.length)) + '</span>'
        : '';

      html += '<div class="history-card ' + statusClass + '">';

      html += '<div class="card-left">';
      html += '<div class="card-title-row">'
            + '<span class="card-title">' + esc(item.title || '—') + '</span>'
            + (item.author ? '<span class="card-author">by ' + esc(item.author) + '</span>' : '')
            + '</div>';

      if (item.release_title && item.release_title !== item.title) {
        html += '<div class="card-release" title="' + esc(item.release_title) + '">'
              + esc(item.release_title) + '</div>';
      }

      html += '<div class="card-chips">' + protoChip + indexerChip + grChip + '</div>';
      html += '</div>';

      html += '<div class="card-right">'
            + '<span class="status-badge ' + badgeClass + '">' + esc(statusLabel) + '</span>'
            + '<span class="card-date">' + fmtDate(item.created_at) + '</span>'
            + '</div>';

      if (item.error) {
        html += '<div class="card-error">&#9888; ' + esc(item.error) + '</div>';
      }

      html += '</div>';
    });

    html += '</div>';
    section.innerHTML = html;
  }


  // ── Goodreads Profiles tab ────────────────────────────────────────────────

  async function loadProfiles() {
    if (_profilesLoaded) return;
    try {
      const resp = await fetch('/portal/goodreads-profiles', { credentials: 'include' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      renderProfiles(data.profiles || []);
      _profilesLoaded = true;
    } catch (e) {
      document.getElementById('profiles-list').innerHTML =
        '<div class="empty-state"><p style="color:var(--danger)">' + esc(e.message) + '</p></div>';
    }
  }

  function renderProfiles(profiles) {
    const heading = document.getElementById('profiles-heading');
    const list    = document.getElementById('profiles-list');

    heading.textContent = profiles.length + ' profile' + (profiles.length !== 1 ? 's' : '');

    if (!profiles.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-icon">👤</div>'
        + '<p>No profiles yet — add the first one below.</p></div>';
      return;
    }

    list.innerHTML = profiles.map(p => {
      const syncLabel = p.sync_from
        ? 'New additions from ' + p.sync_from
        : 'Full shelf';
      return `
        <div class="profile-card" id="profile-${esc(p.id)}">
          <div class="profile-info">
            <div class="profile-name">${esc(p.name)}</div>
            <div class="profile-meta">ID: ${esc(p.user_id)} &nbsp;·&nbsp; Shelf: ${esc(p.shelf)} &nbsp;·&nbsp; ${esc(syncLabel)}</div>
          </div>
          <button class="btn-remove" onclick="removeProfile('${esc(p.id)}', '${esc(p.name)}')">Remove</button>
        </div>
      `;
    }).join('');
  }

  function toggleBacklog() {
    const checked = document.getElementById('chk-backlog').checked;
    document.getElementById('backlog-notice').classList.toggle('visible', checked);
  }

  async function addProfile() {
    const name     = document.getElementById('inp-name').value.trim();
    const uid      = document.getElementById('inp-uid').value.trim();
    const shelf    = document.getElementById('inp-shelf').value.trim() || 'to-read';
    const fullSync = document.getElementById('chk-backlog').checked;
    const msg      = document.getElementById('form-msg');
    const btn      = document.querySelector('.btn-add');

    msg.className = 'form-msg';
    msg.textContent = '';

    if (!name) { showMsg('error', 'Please enter a first name.'); return; }
    if (!uid)  { showMsg('error', 'Please enter a Goodreads user ID.'); return; }

    // null = full backlog; today's date = new additions only from this point forward
    const sync_from = fullSync ? null : new Date().toISOString().slice(0, 10);

    btn.disabled = true;
    try {
      const resp = await fetch('/portal/goodreads-profiles', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, user_id: uid, shelf, sync_from }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'HTTP ' + resp.status);
      }
      document.getElementById('inp-name').value  = '';
      document.getElementById('inp-uid').value   = '';
      document.getElementById('inp-shelf').value = 'to-read';
      document.getElementById('chk-backlog').checked = false;
      document.getElementById('backlog-notice').classList.remove('visible');
      showMsg('success', `Profile for ${name} added. It will be picked up on the next sync.`);
      _profilesLoaded = false;
      loadProfiles();
    } catch (e) {
      showMsg('error', e.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function removeProfile(id, name) {
    if (!confirm(`Remove ${name}'s profile? Their shelf will no longer be synced.`)) return;
    try {
      const resp = await fetch('/portal/goodreads-profiles/' + encodeURIComponent(id), {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      document.getElementById('profile-' + id)?.remove();
      _profilesLoaded = false;
      loadProfiles();
    } catch (e) {
      alert('Failed to remove profile: ' + e.message);
    }
  }

  function showMsg(type, text) {
    const el = document.getElementById('form-msg');
    el.className = 'form-msg ' + type;
    el.textContent = text;
  }


  // ── Init ──────────────────────────────────────────────────────────────────

  load();
</script>
</body>
</html>"""
