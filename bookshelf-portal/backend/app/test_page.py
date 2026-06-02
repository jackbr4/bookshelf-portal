TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Direct Book Request</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --page-bg:   #F8F9FA;
      --surface:   #FFFFFF;
      --border:    #DEE2E6;
      --text:      #212529;
      --muted:     #6C757D;
      --primary:   #0D6EFD;
      --success:   #198754;
      --danger:    #DC3545;
      --radius-sm: 6px;
      --radius-md: 8px;
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
      padding: 0.75rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { font-size: 1.05rem; font-weight: 600; }
    header a  { font-size: 0.8rem; color: var(--muted); text-decoration: none; }
    header a:hover { color: var(--text); }

    main { padding: 2rem 1.5rem; max-width: 820px; margin: 0 auto; }

    /* ── Search row ── */
    .search-row {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: flex-end;
      margin-bottom: 1.25rem;
    }
    .field { display: flex; flex-direction: column; gap: 0.3rem; flex: 1; min-width: 160px; }
    label {
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }
    input[type="text"] {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.5rem 0.75rem;
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
      width: 100%;
    }
    input[type="text"]:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(13,110,253,0.15);
    }

    /* ── Buttons ── */
    .btn-search {
      padding: 0.5rem 1.2rem;
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      white-space: nowrap;
    }
    .btn-search:hover:not(:disabled) { background: #0b5ed7; }
    .btn-search:disabled { opacity: 0.5; cursor: not-allowed; }

    .btn-dl {
      padding: 0.3rem 0.75rem;
      background: var(--success);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.77rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, opacity 0.15s;
      white-space: nowrap;
    }
    .btn-dl:hover:not(:disabled) { background: #157347; }
    .btn-dl:disabled { opacity: 0.4; cursor: not-allowed; }

    /* ── Toolbar (status + view toggle) ── */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
      min-height: 1.6rem;
    }
    #status { font-size: 0.82rem; color: var(--muted); }
    #status .err { color: var(--danger); }
    #status .ok  { color: var(--success); }

    .view-toggle {
      display: flex;
      gap: 2px;
      background: #E9ECEF;
      border-radius: var(--radius-sm);
      padding: 3px;
    }
    .view-toggle button {
      padding: 0.28rem 0.75rem;
      border: none;
      background: none;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: inherit;
      color: var(--muted);
      cursor: pointer;
      transition: all 0.15s;
    }
    .view-toggle button.active {
      background: var(--surface);
      color: var(--text);
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* ── Badges ── */
    .badge {
      display: inline-block;
      padding: 0.15rem 0.42rem;
      border-radius: 4px;
      font-size: 0.67rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .badge-epub { background: #D1E7DD; color: #0F5132; }
    .badge-pdf  { background: #FFF3CD; color: #664D03; }
    .badge-unk  { background: #E9ECEF; color: #6C757D; }
    .badge-rej  { background: #F8D7DA; color: #842029; }

    /* ── Basic view: cards ── */
    .card-list { display: flex; flex-direction: column; gap: 0.5rem; }
    .release-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 0.75rem 1rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      transition: box-shadow 0.15s;
    }
    .release-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.07); }
    .card-title {
      flex: 1;
      font-size: 0.875rem;
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .card-score { font-size: 0.75rem; color: var(--muted); font-weight: 500; white-space: nowrap; }

    /* ── Advanced view: table ── */
    .table-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      overflow-x: auto;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th {
      padding: 0.55rem 0.75rem;
      border-bottom: 1px solid var(--border);
      text-align: left;
      font-size: 0.68rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
      color: var(--muted);
      background: var(--page-bg);
    }
    td { padding: 0.55rem 0.75rem; border-bottom: 1px solid #F1F3F5; vertical-align: middle; }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #FAFAFA; }

    .t-title { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .t-num   { color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
    .t-score { color: var(--primary); font-weight: 600; text-align: right; }

    /* ── Rejected toggle ── */
    .rej-toggle {
      margin-top: 1rem;
      background: none;
      border: none;
      color: var(--muted);
      cursor: pointer;
      font-size: 0.78rem;
      font-family: inherit;
      padding: 0;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .rej-toggle:hover { color: var(--text); }
    .rej-body { margin-top: 0.5rem; display: none; }

    /* ── Result box ── */
    .result-box {
      margin-top: 1.25rem;
      padding: 0.875rem 1rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 0.875rem;
      line-height: 1.5;
    }
    .result-box .meta { color: var(--muted); margin-top: 0.2rem; font-size: 0.75rem; }
    .result-box .ok  { color: var(--success); font-weight: 600; }
    .result-box .err { color: var(--danger);  font-weight: 600; }

    .no-results { text-align: center; padding: 3rem 1rem; color: var(--muted); font-size: 0.875rem; }
  </style>
</head>
<body>

<header>
  <h1>Direct Book Request</h1>
  <a href="/">← back to portal</a>
</header>

<main>
  <div class="search-row">
    <div class="field">
      <label>Title <span style="color:#adb5bd;font-weight:400">(optional)</span></label>
      <input type="text" id="inp-title" placeholder="e.g. Dune" autocomplete="off" />
    </div>
    <div class="field">
      <label>Author <span style="color:#adb5bd;font-weight:400">(optional)</span></label>
      <input type="text" id="inp-author" placeholder="e.g. Frank Herbert" autocomplete="off" />
    </div>
    <button class="btn-search" id="btn-search" onclick="fetchReleases()">Search</button>
  </div>

  <div class="toolbar">
    <div id="status"></div>
    <div class="view-toggle" id="view-toggle" style="display:none">
      <button id="btn-basic" class="active" onclick="setView('basic')">Basic</button>
      <button id="btn-advanced" onclick="setView('advanced')">Advanced</button>
    </div>
  </div>

  <div id="results"></div>
  <div id="result-box"></div>
</main>

<script>
  let _accepted = [];
  let _rejected = [];
  let _view = 'basic';

  /* ── Auth ── */
  function handle401() {
    document.getElementById('results').innerHTML = '';
    document.getElementById('result-box').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    setStatus('<a href="/" style="color:var(--primary)">← Log in first</a>, then come back to this page.', 'err');
  }

  /* ── View toggle ── */
  function setView(v) {
    _view = v;
    document.getElementById('btn-basic').classList.toggle('active', v === 'basic');
    document.getElementById('btn-advanced').classList.toggle('active', v === 'advanced');
    renderResults(_accepted, _rejected);
  }

  /* ── Fetch releases ── */
  async function fetchReleases() {
    const title  = document.getElementById('inp-title').value.trim();
    const author = document.getElementById('inp-author').value.trim();

    if (!title && !author) {
      setStatus('Enter a title or author to search.', 'err');
      return;
    }

    const btn = document.getElementById('btn-search');
    btn.disabled = true;
    btn.textContent = 'Searching…';
    setStatus('');
    document.getElementById('results').innerHTML = '';
    document.getElementById('result-box').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    _accepted = [];
    _rejected = [];

    const qs = new URLSearchParams();
    if (title)  qs.set('title', title);
    if (author) qs.set('author', author);

    try {
      const resp = await fetch('/portal/releases?' + qs, { credentials: 'include' });
      if (resp.status === 401) { handle401(); return; }
      if (!resp.ok) throw new Error('HTTP ' + resp.status + ' — ' + (await resp.text()));
      const data = await resp.json();
      _accepted = data.accepted || [];
      _rejected = data.rejected || [];
      renderResults(_accepted, _rejected);
    } catch (e) {
      setStatus(e.message, 'err');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Search';
    }
  }

  /* ── Render ── */
  function renderResults(accepted, rejected) {
    const el = document.getElementById('results');

    if (!accepted.length && !rejected.length) {
      document.getElementById('view-toggle').style.display = 'none';
      el.innerHTML = '<div class="no-results">No results from Prowlarr.</div>';
      setStatus('');
      return;
    }

    const label = accepted.length
      ? accepted.length + ' accepted release' + (accepted.length !== 1 ? 's' : '')
      : 'No accepted releases';
    setStatus(label + (rejected.length ? ' &nbsp;\xb7&nbsp; ' + rejected.length + ' rejected' : ''));

    document.getElementById('view-toggle').style.display = accepted.length ? 'flex' : 'none';

    let html = '';

    if (!accepted.length) {
      html += '<p style="color:var(--muted);font-size:0.85rem;margin-bottom:0.5rem">No accepted releases (epub / pdf).</p>';
    } else if (_view === 'basic') {
      html += '<div class="card-list">';
      accepted.forEach((r, i) => {
        const fmt = (r.detected_format || '').toLowerCase();
        const badgeCls = fmt === 'epub' ? 'badge-epub' : fmt === 'pdf' ? 'badge-pdf' : 'badge-unk';
        html += '<div class="release-card">' +
          '<span class="badge ' + badgeCls + '">' + esc(fmt || '?') + '</span>' +
          '<span class="card-title" title="' + esc(r.title) + '">' + esc(r.title) + '</span>' +
          '<span class="card-score">score ' + r.score + '</span>' +
          '<button class="btn-dl" onclick="dispatch(' + i + ')">Download</button>' +
          '</div>';
      });
      html += '</div>';
    } else {
      html += '<div class="table-wrap"><table><thead><tr>' +
        '<th>Format</th><th>Title</th><th>Indexer</th>' +
        '<th style="text-align:right">Size</th>' +
        '<th style="text-align:right">Seeds</th>' +
        '<th style="text-align:right">Age</th>' +
        '<th style="text-align:right">Score</th>' +
        '<th></th></tr></thead><tbody>';

      accepted.forEach((r, i) => {
        const fmt = (r.detected_format || '').toLowerCase();
        const badgeCls = fmt === 'epub' ? 'badge-epub' : fmt === 'pdf' ? 'badge-pdf' : 'badge-unk';
        html += '<tr>' +
          '<td><span class="badge ' + badgeCls + '">' + esc(fmt || '?') + '</span></td>' +
          '<td class="t-title" title="' + esc(r.title) + '">' + esc(r.title) + '</td>' +
          '<td style="color:var(--muted)">' + esc(r.indexer) + '</td>' +
          '<td class="t-num">' + (r.size_mb != null ? r.size_mb.toFixed(1) + ' MB' : '—') + '</td>' +
          '<td class="t-num">' + (r.seeders != null ? r.seeders : '—') + '</td>' +
          '<td class="t-num">' + (r.age_days != null ? r.age_days + 'd' : '—') + '</td>' +
          '<td class="t-score">' + r.score + '</td>' +
          '<td><button class="btn-dl" onclick="dispatch(' + i + ')">Download</button></td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';
    }

    /* rejected */
    if (rejected.length) {
      html += '<button class="rej-toggle" id="rej-btn" onclick="toggleRejected()">' +
        '<span id="rej-arrow">▶</span> ' + rejected.length + ' rejected</button>' +
        '<div class="rej-body" id="rej-body">' +
        '<div class="table-wrap"><table><thead><tr>' +
        '<th>Format</th><th>Title</th><th>Reason</th>' +
        '</tr></thead><tbody>';

      rejected.forEach(r => {
        const fmt = (r.detected_format || '').toLowerCase();
        html += '<tr>' +
          '<td><span class="badge badge-rej">' + esc(fmt || '?') + '</span></td>' +
          '<td class="t-title" title="' + esc(r.title) + '">' + esc(r.title) + '</td>' +
          '<td style="color:var(--muted)">' + esc(r.reject_reason || '') + '</td>' +
          '</tr>';
      });

      html += '</tbody></table></div></div>';
    }

    el.innerHTML = html;
  }

  function toggleRejected() {
    const body  = document.getElementById('rej-body');
    const arrow = document.getElementById('rej-arrow');
    const open  = body.style.display !== 'none' && body.style.display !== '';
    body.style.display = open ? 'none' : 'block';
    arrow.textContent  = open ? '▶' : '▼';
  }

  /* ── Dispatch ── */
  async function dispatch(index) {
    const release = _accepted[index];
    const title   = document.getElementById('inp-title').value.trim();
    const author  = document.getElementById('inp-author').value.trim();

    document.querySelectorAll('.btn-dl').forEach(b => b.disabled = true);

    const box = document.getElementById('result-box');
    box.innerHTML = '<div class="result-box">Dispatching <strong>' + esc(release.title) + '</strong>…</div>';

    try {
      const resp = await fetch('/portal/download', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title:         title || release.title,
          author:        author || '',
          release_title: release.title,
          indexer:       release.indexer,
          protocol:      release.protocol,
          download_url:  release.download_url,
        }),
      });
      if (resp.status === 401) { handle401(); return; }
      const data = await resp.json();
      if (data.ok) {
        box.innerHTML =
          '<div class="result-box">' +
          '<span class="ok">✓ ' + esc(data.message) + '</span>' +
          '<div class="meta">Download ID: ' + esc(data.download_id) + '</div>' +
          '<div class="meta">Record: ' + esc(data.record_id) + '</div>' +
          '</div>';
      } else {
        throw new Error(data.detail || JSON.stringify(data));
      }
    } catch (e) {
      box.innerHTML = '<div class="result-box"><span class="err">✗ ' + esc(e.message) + '</span></div>';
      document.querySelectorAll('.btn-dl').forEach(b => b.disabled = false);
    }
  }

  /* ── Helpers ── */
  function setStatus(msg, cls) {
    const el = document.getElementById('status');
    el.innerHTML = msg ? '<span class="' + (cls || '') + '">' + msg + '</span>' : '';
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' &&
        (document.activeElement === document.getElementById('inp-title') ||
         document.activeElement === document.getElementById('inp-author'))) {
      fetchReleases();
    }
  });
</script>
</body>
</html>"""
