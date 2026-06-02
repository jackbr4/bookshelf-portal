ADMIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Download History</title>
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
    .chip-torrent { background: #EDE9FE; border-color: #DDD6FE; color: #5B21B6; }
    .chip-usenet  { background: #FEF3C7; border-color: #FDE68A; color: #92400E; }

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
  <h1>Download History</h1>
  <a href="/portal/test">← back to request</a>
</header>

<main>
  <!-- Stats -->
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

  <!-- History list -->
  <div id="history-section"></div>
</main>

<script>
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

  async function load() {
    try {
      const resp = await fetch('/portal/history', { credentials: 'include' });
      if (resp.status === 401) { handle401(); return; }
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      render(data.items || []);
    } catch (e) {
      document.getElementById('history-section').innerHTML =
        '<div class="empty-state"><p style="color:var(--danger)">' + esc(e.message) + '</p></div>';
    }
  }

  function render(items) {
    // Stats
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

      html += '<div class="history-card ' + statusClass + '">';

      // Left column
      html += '<div class="card-left">';
      html += '<div class="card-title-row">'
            + '<span class="card-title">' + esc(item.title || '—') + '</span>'
            + (item.author ? '<span class="card-author">by ' + esc(item.author) + '</span>' : '')
            + '</div>';

      if (item.release_title && item.release_title !== item.title) {
        html += '<div class="card-release" title="' + esc(item.release_title) + '">'
              + esc(item.release_title) + '</div>';
      }

      html += '<div class="card-chips">' + protoChip + indexerChip + '</div>';
      html += '</div>';

      // Right column
      html += '<div class="card-right">'
            + '<span class="status-badge ' + badgeClass + '">' + esc(statusLabel) + '</span>'
            + '<span class="card-date">' + fmtDate(item.created_at) + '</span>'
            + '</div>';

      // Error row (full width)
      if (item.error) {
        html += '<div class="card-error">&#9888; ' + esc(item.error) + '</div>';
      }

      html += '</div>';
    });

    html += '</div>';
    section.innerHTML = html;
  }

  load();
</script>
</body>
</html>"""
