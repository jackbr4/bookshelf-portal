TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Direct Book Request</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, sans-serif;
      background: #0d0d0d;
      color: #d4d4d4;
      padding: 2rem;
      min-height: 100vh;
    }

    header {
      display: flex;
      align-items: baseline;
      gap: 1.5rem;
      margin-bottom: 2rem;
      border-bottom: 1px solid #1e1e1e;
      padding-bottom: 1rem;
    }
    header h1 { font-size: 1.2rem; font-weight: 600; color: #fff; }
    header a  { font-size: 0.8rem; color: #555; text-decoration: none; }
    header a:hover { color: #888; }

    .form {
      display: flex;
      gap: 1rem;
      align-items: flex-end;
      flex-wrap: wrap;
      margin-bottom: 1.5rem;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      flex: 1;
      min-width: 180px;
    }
    label {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #555;
      font-weight: 600;
    }
    input[type="text"] {
      background: #181818;
      border: 1px solid #2a2a2a;
      color: #d4d4d4;
      padding: 0.55rem 0.75rem;
      border-radius: 6px;
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.15s;
      width: 100%;
    }
    input[type="text"]:focus { border-color: #444; }

    button {
      padding: 0.55rem 1.2rem;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      transition: background 0.15s, opacity 0.15s;
      white-space: nowrap;
    }
    .btn-primary { background: #2563eb; color: #fff; }
    .btn-primary:hover:not(:disabled) { background: #1d4ed8; }
    .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-dl { background: #166534; color: #bbf7d0; padding: 0.35rem 0.7rem; font-size: 0.78rem; }
    .btn-dl:hover:not(:disabled) { background: #15803d; }
    .btn-dl:disabled { opacity: 0.35; cursor: not-allowed; }

    #status {
      font-size: 0.85rem;
      color: #666;
      min-height: 1.2em;
      margin-bottom: 1rem;
    }
    .err { color: #f87171; }
    .ok  { color: #4ade80; }

    /* ── Release table ── */
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th {
      text-align: left;
      padding: 0.45rem 0.75rem;
      border-bottom: 1px solid #1e1e1e;
      color: #444;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    td {
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid #161616;
      vertical-align: middle;
    }
    tr:hover td { background: #111; }

    .badge {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .badge-epub { background: #14532d; color: #86efac; }
    .badge-pdf  { background: #3b2800; color: #fcd34d; }
    .badge-unk  { background: #1e1e1e; color: #666; }
    .badge-rej  { background: #3b0c0c; color: #fca5a5; }

    .t-title {
      max-width: 300px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #bbb;
    }
    .t-num { color: #777; text-align: right; font-variant-numeric: tabular-nums; }
    .t-score { color: #3b82f6; font-weight: 600; text-align: right; }

    /* ── Rejected section ── */
    .rej-toggle {
      margin-top: 1.25rem;
      background: none;
      border: none;
      color: #3a3a3a;
      cursor: pointer;
      font-size: 0.78rem;
      padding: 0;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .rej-toggle:hover { color: #666; }
    .rej-body { margin-top: 0.5rem; display: none; }

    /* ── Result box ── */
    .result-box {
      margin-top: 1.5rem;
      padding: 1rem 1.25rem;
      background: #111;
      border: 1px solid #222;
      border-radius: 8px;
      font-size: 0.85rem;
      line-height: 1.6;
    }
    .result-box .meta { color: #444; margin-top: 0.25rem; font-size: 0.75rem; }
  </style>
</head>
<body>

<header>
  <h1>Direct Book Request</h1>
  <a href="/">← back to portal</a>
</header>

<div class="form">
  <div class="field">
    <label>Title <span style="color:#333;font-weight:400">(optional)</span></label>
    <input type="text" id="inp-title" placeholder="e.g. Dune" autocomplete="off" />
  </div>
  <div class="field">
    <label>Author <span style="color:#333;font-weight:400">(optional)</span></label>
    <input type="text" id="inp-author" placeholder="e.g. Frank Herbert" autocomplete="off" />
  </div>
  <button class="btn-primary" id="btn-search" onclick="fetchReleases()">Search releases</button>
</div>

<div id="status"></div>
<div id="results"></div>
<div id="result-box"></div>

<script>
  let _accepted = [];

  /* ── Auth ── */
  function handle401() { window.location.href = '/'; }

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
    _accepted = [];

    const qs = new URLSearchParams();
    if (title)  qs.set('title', title);
    if (author) qs.set('author', author);

    try {
      const resp = await fetch('/portal/releases?' + qs, { credentials: 'include' });
      if (resp.status === 401) { handle401(); return; }
      if (!resp.ok) throw new Error('HTTP ' + resp.status + ' — ' + (await resp.text()));
      const data = await resp.json();
      _accepted = data.accepted || [];
      renderResults(data.accepted || [], data.rejected || []);
    } catch (e) {
      setStatus(e.message, 'err');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Search releases';
    }
  }

  /* ── Render ── */
  function renderResults(accepted, rejected) {
    const el = document.getElementById('results');

    if (!accepted.length && !rejected.length) {
      setStatus('No results from Prowlarr.', 'err');
      return;
    }

    const label = accepted.length
      ? accepted.length + ' accepted release' + (accepted.length !== 1 ? 's' : '')
      : 'No accepted releases';
    setStatus(label + (rejected.length ? ' &nbsp;·&nbsp; ' + rejected.length + ' rejected' : ''));

    let html = '';

    if (accepted.length) {
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
          '<td style="color:#888">' + esc(r.indexer) + '</td>' +
          '<td class="t-num">' + (r.size_mb != null ? r.size_mb.toFixed(1) + ' MB' : '—') + '</td>' +
          '<td class="t-num">' + (r.seeders != null ? r.seeders : '—') + '</td>' +
          '<td class="t-num">' + (r.age_days != null ? r.age_days + 'd' : '—') + '</td>' +
          '<td class="t-score">' + r.score + '</td>' +
          '<td><button class="btn-dl" onclick="dispatch(' + i + ')">Download</button></td>' +
          '</tr>';
      });

      html += '</tbody></table></div>';
    } else {
      html += '<p style="color:#555;font-size:0.85rem;margin-bottom:0.5rem">No accepted releases (epub / pdf).</p>';
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
          '<td style="color:#666">' + esc(r.reject_reason || '') + '</td>' +
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
    body.style.display  = open ? 'none' : 'block';
    arrow.textContent   = open ? '▶' : '▼';
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
