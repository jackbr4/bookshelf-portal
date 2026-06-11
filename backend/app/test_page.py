TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Book Request Portal</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='85'>📚</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;500italic;600&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --page-bg:      #F0F4F8;
      --surface:      #FFFFFF;
      --border:       #E2E8F0;
      --border-hover: #CBD5E1;
      --text:         #1A202C;
      --text-sec:     #4A5568;
      --muted:        #718096;
      --primary:      #0D6EFD;
      --primary-bg:   #EBF4FF;
      --success:      #198754;
      --success-bg:   #D1E7DD;
      --success-text: #0A3622;
      --warning-bg:   #FFF3CD;
      --warning-text: #664D03;
      --danger:       #DC3545;
      --danger-bg:    #F8D7DA;
      --danger-text:  #58151C;
      --radius-sm:    6px;
      --radius-md:    10px;
      --radius-lg:    14px;
      --shadow-sm:    0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
      --shadow-md:    0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: linear-gradient(160deg, #E8EEF5 0%, #F7F9FC 100%);
      background-attachment: fixed;
      color: var(--text);
      min-height: 100vh;
    }

    /* ── Header (sticky) ── */
    header {
      position: sticky;
      top: 0;
      z-index: 50;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--border);
      padding: 0.875rem 1.75rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { font-size: 1rem; font-weight: 600; letter-spacing: -0.01em; }
    .header-nav { display: flex; align-items: center; gap: 0.75rem; }
    .btn-admin {
      padding: 0.35rem 0.85rem;
      background: var(--page-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 0.78rem;
      font-weight: 600;
      font-family: inherit;
      color: var(--text-sec);
      text-decoration: none;
      transition: background 0.12s, border-color 0.12s, color 0.12s;
      white-space: nowrap;
    }
    .btn-admin:hover { background: var(--border); color: var(--text); border-color: #CBD5E1; }

    main { padding: 2rem 1.75rem; max-width: 780px; margin: 0 auto; }

    /* ── Search card ── */
    .search-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      box-shadow: var(--shadow-sm);
      margin-bottom: 1.75rem;
    }
    .search-card h2 {
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--muted);
      margin-bottom: 0.3rem;
    }
    .search-card .search-hint {
      font-size: 0.8rem;
      color: var(--muted);
      margin-bottom: 1rem;
      line-height: 1.5;
    }
    .search-row {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      align-items: flex-end;
    }
    .field { display: flex; flex-direction: column; gap: 0.35rem; flex: 1; min-width: 150px; }
    label {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--text-sec);
      letter-spacing: 0.02em;
    }

    /* ── Input with inline clear (option B) ── */
    .input-wrap { position: relative; }
    .input-wrap input[type="text"] { padding-right: 2rem; }
    .input-clear {
      position: absolute;
      right: 0.5rem;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: var(--muted);
      cursor: pointer;
      font-size: 1rem;
      line-height: 1;
      padding: 0.15rem 0.2rem;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.15s;
    }
    .input-clear.visible { opacity: 0.5; pointer-events: auto; }
    .input-clear:hover { opacity: 1 !important; }

    input[type="text"] {
      background: var(--page-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.55rem 0.875rem;
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
      width: 100%;
    }
    input[type="text"]:focus {
      border-color: var(--primary);
      background: var(--surface);
      box-shadow: 0 0 0 3px rgba(13,110,253,0.12);
    }

    /* ── Buttons ── */
    .btn-search {
      padding: 0.55rem 1.4rem;
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.875rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, box-shadow 0.15s, opacity 0.15s;
      white-space: nowrap;
      letter-spacing: -0.01em;
    }
    .btn-search:hover:not(:disabled) {
      background: #0b5ed7;
      box-shadow: 0 2px 8px rgba(13,110,253,0.3);
    }
    .btn-search:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Clear button (option A) */
    .btn-clear {
      display: none;
      align-items: center;
      gap: 0.3rem;
      padding: 0.3rem 0.75rem;
      background: none;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 0.78rem;
      font-weight: 500;
      font-family: inherit;
      color: var(--muted);
      cursor: pointer;
      transition: background 0.12s, color 0.12s, border-color 0.12s;
      white-space: nowrap;
    }
    .btn-clear:hover { background: var(--border); color: var(--text-sec); border-color: var(--border-hover); }

    .btn-dl {
      padding: 0.38rem 0.9rem;
      background: var(--success);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.78rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, box-shadow 0.15s, opacity 0.15s;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .btn-dl:hover:not(:disabled) {
      background: #157347;
      box-shadow: 0 2px 6px rgba(25,135,84,0.3);
    }
    .btn-dl:disabled { opacity: 0.4; cursor: not-allowed; }

    /* ── Toolbar ── */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.875rem;
      min-height: 1.75rem;
      gap: 0.5rem;
    }
    .toolbar-left { display: flex; align-items: center; gap: 0.625rem; }
    #status { font-size: 0.82rem; color: var(--muted); }
    #status .err { color: var(--danger); }
    #status .ok  { color: var(--success); }
    #status strong { color: var(--text-sec); font-weight: 600; }

    .view-toggle {
      display: flex;
      gap: 2px;
      background: var(--border);
      border-radius: var(--radius-sm);
      padding: 3px;
    }
    .view-toggle button {
      padding: 0.28rem 0.8rem;
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

    /* ── Format badges ── */
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 0.2rem 0.5rem;
      border-radius: 5px;
      font-size: 0.65rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      flex-shrink: 0;
      line-height: 1;
    }
    .badge-epub { background: var(--success-bg); color: var(--success-text); }
    .badge-pdf  { background: var(--warning-bg); color: var(--warning-text); }
    .badge-m4b  { background: #EDE9FE; color: #4C1D95; }
    .badge-mp3  { background: #FEF3C7; color: #78350F; }
    .badge-unk  { background: #E2E8F0; color: #4A5568; }
    .badge-rej  { background: var(--danger-bg); color: var(--danger-text); }

    /* ── Media type toggle ── */
    .media-type-row {
      display: flex;
      align-items: center;
      gap: 0.625rem;
      margin-bottom: 1rem;
    }
    .media-type-label {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--text-sec);
      letter-spacing: 0.02em;
    }
    .media-toggle {
      display: flex;
      gap: 2px;
      background: var(--border);
      border-radius: var(--radius-sm);
      padding: 3px;
    }
    .media-toggle button {
      padding: 0.28rem 0.85rem;
      border: none;
      background: none;
      border-radius: 4px;
      font-size: 0.78rem;
      font-weight: 600;
      font-family: inherit;
      color: var(--muted);
      cursor: pointer;
      transition: all 0.15s;
      white-space: nowrap;
    }
    .media-toggle button.active {
      background: var(--surface);
      color: var(--text);
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* ── Release cards + fade-in ── */
    @keyframes fadeInUp {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .card-list { display: flex; flex-direction: column; gap: 0.625rem; }

    .release-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 1rem 1.125rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      box-shadow: var(--shadow-sm);
      transition: box-shadow 0.15s, border-color 0.15s, transform 0.1s;
      position: relative;
      overflow: hidden;
      animation: fadeInUp 0.18s ease-out both;
    }
    .release-card:nth-child(1)  { animation-delay: 0.00s; }
    .release-card:nth-child(2)  { animation-delay: 0.03s; }
    .release-card:nth-child(3)  { animation-delay: 0.06s; }
    .release-card:nth-child(4)  { animation-delay: 0.09s; }
    .release-card:nth-child(5)  { animation-delay: 0.12s; }
    .release-card:nth-child(n+6){ animation-delay: 0.15s; }

    .release-card::before {
      content: '';
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 3px;
      border-radius: 3px 0 0 3px;
    }
    .release-card.fmt-epub::before { background: var(--success); }
    .release-card.fmt-pdf::before  { background: #B45309; }
    .release-card.fmt-m4b::before  { background: #7C3AED; }
    .release-card.fmt-mp3::before  { background: #D97706; }
    .release-card.fmt-unk::before  { background: #CBD5E1; }

    .release-card:hover {
      box-shadow: var(--shadow-md);
      border-color: var(--border-hover);
      transform: translateY(-1px);
    }

    .card-main {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
    }
    .card-body {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .card-title {
      flex: 1;
      min-width: 0;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text);
      line-height: 1.45;
      word-break: break-word;
    }

    .score-pill {
      font-size: 0.7rem;
      font-weight: 700;
      color: var(--primary);
      background: var(--primary-bg);
      border-radius: 20px;
      padding: 0.15rem 0.55rem;
      white-space: nowrap;
      flex-shrink: 0;
    }

    .card-meta {
      display: flex;
      align-items: center;
      gap: 0.375rem;
      flex-wrap: wrap;
      padding-left: calc(0.75rem + 0.5rem + 1px);
    }
    .meta-chip {
      font-size: 0.7rem;
      color: var(--muted);
      background: var(--page-bg);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.15rem 0.45rem;
      white-space: nowrap;
    }
    .meta-dot {
      width: 3px;
      height: 3px;
      border-radius: 50%;
      background: var(--border-hover);
      flex-shrink: 0;
    }

    /* ── Rejected section (pill badge toggle) ── */
    .rej-toggle {
      margin-top: 1rem;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: var(--page-bg);
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--muted);
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 600;
      font-family: inherit;
      padding: 0.3rem 0.875rem;
      transition: background 0.12s, color 0.12s, border-color 0.12s;
    }
    .rej-toggle:hover { background: var(--border); color: var(--text-sec); border-color: var(--border-hover); }
    .rej-toggle-arrow { transition: transform 0.2s; display: inline-block; font-size: 0.65rem; }
    .rej-body { margin-top: 0.625rem; display: none; }

    .rej-list { display: flex; flex-direction: column; gap: 0.375rem; }
    .rej-item {
      display: flex;
      align-items: center;
      gap: 0.625rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 0.55rem 0.875rem;
      opacity: 0.75;
    }
    .rej-title {
      flex: 1;
      font-size: 0.8rem;
      color: var(--text-sec);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .rej-reason {
      font-size: 0.72rem;
      color: var(--muted);
      white-space: nowrap;
    }

    /* ── Toast ── */
    #toast {
      position: fixed;
      bottom: 1.5rem;
      left: 50%;
      transform: translateX(-50%);
      min-width: 320px;
      max-width: 560px;
      width: max-content;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 0.875rem 1.125rem;
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      box-shadow: 0 6px 24px rgba(0,0,0,0.13), 0 2px 6px rgba(0,0,0,0.07);
      z-index: 9999;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s, transform 0.2s;
      transform: translateX(-50%) translateY(8px);
    }
    #toast.visible {
      opacity: 1;
      pointer-events: auto;
      transform: translateX(-50%) translateY(0);
    }
    #toast.toast-success { border-left: 4px solid var(--success); }
    #toast.toast-error   { border-left: 4px solid var(--danger); }
    .toast-icon { font-size: 1rem; flex-shrink: 0; margin-top: 1px; }
    .toast-icon.ok  { color: var(--success); }
    .toast-icon.err { color: var(--danger); }
    .toast-body { flex: 1; font-size: 0.85rem; line-height: 1.5; color: var(--text); }
    .toast-close {
      background: none; border: none; color: var(--muted);
      cursor: pointer; font-size: 1rem; padding: 0; line-height: 1;
      flex-shrink: 0; opacity: 0.6;
    }
    .toast-close:hover { opacity: 1; }

    /* ── Login screen ── */
    #login-screen {
      position: fixed;
      inset: 0;
      background: linear-gradient(160deg, #E8EEF5 0%, #F7F9FC 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      padding: 1.5rem;
    }
    #login-screen.hidden { display: none; }
    .login-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 2.5rem 2rem 2rem;
      width: 100%;
      max-width: 400px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04);
      text-align: center;
    }
    .login-card .login-icon {
      font-size: 2.5rem;
      display: block;
      margin-bottom: 0.625rem;
    }
    .login-card h2 {
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: 0.25rem;
      letter-spacing: -0.02em;
    }
    .login-card p {
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 1.75rem;
    }
    .login-card label {
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--text-sec);
      letter-spacing: 0.02em;
      display: block;
      text-align: left;
      margin-bottom: 0.35rem;
    }
    input[type="password"] {
      background: var(--page-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.55rem 0.875rem;
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
      width: 100%;
      margin-bottom: 0.875rem;
    }
    input[type="password"]:focus {
      border-color: var(--primary);
      background: var(--surface);
      box-shadow: 0 0 0 3px rgba(13,110,253,0.12);
    }
    .btn-login {
      width: 100%;
      padding: 0.6rem 1rem;
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      transition: background 0.15s, box-shadow 0.15s, opacity 0.15s;
    }
    .btn-login:hover:not(:disabled) {
      background: #0b5ed7;
      box-shadow: 0 2px 8px rgba(13,110,253,0.3);
    }
    .btn-login:disabled { opacity: 0.5; cursor: not-allowed; }
    .login-error {
      margin-top: 0.75rem;
      font-size: 0.8rem;
      color: var(--danger);
      text-align: center;
      min-height: 1.2em;
    }
    .btn-signout {
      padding: 0.35rem 0.85rem;
      background: none;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 0.78rem;
      font-weight: 600;
      font-family: inherit;
      color: var(--muted);
      cursor: pointer;
      transition: background 0.12s, border-color 0.12s, color 0.12s;
    }
    .btn-signout:hover { background: var(--border); color: var(--text); }

    /* ── Empty / error states ── */
    .empty-state {
      text-align: center;
      padding: 3.5rem 1rem;
      color: var(--muted);
    }
    .empty-state .empty-icon {
      font-size: 2.5rem;
      margin-bottom: 0.75rem;
      opacity: 0.4;
    }
    .empty-state p { font-size: 0.875rem; }

    /* ── Section heading ── */
    .section-heading {
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--muted);
      margin-bottom: 0.625rem;
    }

    /* ── Mobile ── */
    @media (max-width: 600px) {
      body {
        background-attachment: scroll;
      }
      header {
        padding: 0.75rem 1rem;
        padding-top: max(0.75rem, env(safe-area-inset-top, 0px));
      }
      header h1 { font-size: 0.9rem; }
      .btn-admin, .btn-signout {
        padding: 0.45rem 0.75rem;
        min-height: 36px;
      }
      main {
        padding: 1.25rem 1rem;
        padding-left: max(1rem, env(safe-area-inset-left, 0px));
        padding-right: max(1rem, env(safe-area-inset-right, 0px));
      }

      /* Prevent iOS input zoom: font-size must be >= 16px */
      input[type="text"],
      input[type="password"] { font-size: 16px; }

      /* Stack search fields + full-width search button */
      .search-row { flex-direction: column; gap: 0.5rem; }
      .field { min-width: 0; }
      .btn-search { width: 100%; padding: 0.75rem 1rem; }

      .card-body { flex-direction: column; align-items: flex-start; }
      .btn-dl {
        align-self: flex-start;
        min-height: 44px;
        padding: 0.55rem 1.1rem;
      }

      /* Toast: anchor to left/right edges instead of center-translate */
      #toast {
        left: 1rem;
        right: 1rem;
        bottom: max(1.5rem, calc(1rem + env(safe-area-inset-bottom, 0px)));
        min-width: 0;
        max-width: none;
        width: auto;
        transform: translateY(8px);
      }
      #toast.visible { transform: translateY(0); }
    }
  </style>
</head>
<body>

<div id="login-screen">
  <div class="login-card">
    <span class="login-icon">📚</span>
    <h2>Book Request Portal</h2>
    <p>Enter the access code to continue</p>
    <label for="inp-password">Access code</label>
    <input type="password" id="inp-password" placeholder="Enter access code" autocomplete="current-password" />
    <button class="btn-login" id="btn-login" onclick="doLogin()">Continue</button>
    <div class="login-error" id="login-error"></div>
  </div>
</div>

<header>
  <h1>Book Request Portal</h1>
  <div class="header-nav">
    <a href="/portal/admin" class="btn-admin">Admin</a>
    <button class="btn-signout" onclick="doSignOut()">Sign out</button>
  </div>
</header>

<main>
  <div class="search-card">
    <h2>Search for Books</h2>
    <div class="media-type-row">
      <span class="media-type-label">Type</span>
      <div class="media-toggle">
        <button id="btn-type-ebook" class="active" onclick="setMediaType('ebook')">📖 Ebook</button>
        <button id="btn-type-audiobook" onclick="setMediaType('audiobook')">🎧 Audiobook</button>
      </div>
    </div>
    <p class="search-hint" id="search-hint">Enter a book title and/or author below. After downloading, a book will appear in the Calibre library within 1–2 minutes.</p>
    <div class="search-row">
      <div class="field">
        <label>Title</label>
        <div class="input-wrap">
          <input type="text" id="inp-title" placeholder="e.g. A Children's Bible" autocomplete="off" oninput="updateInputClears()" />
          <button class="input-clear" id="clear-inp-title" onclick="clearInput('inp-title')" aria-label="Clear title" tabindex="-1">&times;</button>
        </div>
      </div>
      <div class="field">
        <label>Author</label>
        <div class="input-wrap">
          <input type="text" id="inp-author" placeholder="e.g. Lydia Millet" autocomplete="off" oninput="updateInputClears()" />
          <button class="input-clear" id="clear-inp-author" onclick="clearInput('inp-author')" aria-label="Clear author" tabindex="-1">&times;</button>
        </div>
      </div>
      <button class="btn-search" id="btn-search" onclick="fetchReleases()">Search</button>
    </div>
  </div>

  <div class="toolbar">
    <div class="toolbar-left">
      <div id="status"></div>
      <button class="btn-clear" id="btn-clear" onclick="clearSearch()">&#x2715; Clear</button>
    </div>
    <div class="view-toggle" id="view-toggle" style="display:none">
      <button id="btn-basic" class="active" onclick="setView('basic')">Simple</button>
      <button id="btn-advanced" onclick="setView('advanced')">Detailed</button>
    </div>
  </div>

  <div id="results"></div>
</main>

<div id="toast">
  <span class="toast-icon" id="toast-icon"></span>
  <span class="toast-body" id="toast-body"></span>
  <button class="toast-close" onclick="hideToast()" aria-label="Dismiss">&times;</button>
</div>

<script>
  let _accepted = [];
  let _rejected = [];
  let _view = 'basic';
  let _mediaType = 'ebook';

  /* ── Auth ── */
  function showLoginScreen() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-error').textContent = '';
    const pw = document.getElementById('inp-password');
    pw.value = '';
    pw.focus();
  }

  function hideLoginScreen() {
    document.getElementById('login-screen').classList.add('hidden');
    window.scrollTo(0, 0);
  }

  function handle401() {
    document.getElementById('results').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    document.getElementById('btn-clear').style.display = 'none';
    setStatus('');
    showLoginScreen();
  }

  async function doLogin() {
    const pw  = document.getElementById('inp-password').value;
    const btn = document.getElementById('btn-login');
    const err = document.getElementById('login-error');
    if (!pw) return;
    btn.disabled = true;
    btn.textContent = 'Signing in…';
    err.textContent = '';
    try {
      const resp = await fetch('/portal/auth', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_code: pw }),
      });
      if (resp.ok) {
        hideLoginScreen();
      } else {
        err.textContent = 'Incorrect access code.';
        document.getElementById('inp-password').value = '';
        document.getElementById('inp-password').focus();
      }
    } catch (e) {
      err.textContent = 'Could not reach server. Try again.';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Continue';
    }
  }

  async function doSignOut() {
    await fetch('/portal/logout', { method: 'POST', credentials: 'include' });
    document.getElementById('results').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    document.getElementById('btn-clear').style.display = 'none';
    document.getElementById('inp-title').value = '';
    document.getElementById('inp-author').value = '';
    updateInputClears();
    setStatus('');
    _accepted = []; _rejected = [];
    showLoginScreen();
  }

  /* Check session on load */
  (async function checkSession() {
    try {
      const resp = await fetch('/portal/history?limit=1', { credentials: 'include' });
      if (resp.ok) { hideLoginScreen(); } else { showLoginScreen(); }
    } catch (e) { showLoginScreen(); }
  })();

  /* ── Input clear (option B) ── */
  function updateInputClears() {
    ['inp-title', 'inp-author'].forEach(id => {
      const val = document.getElementById(id).value;
      document.getElementById('clear-' + id).classList.toggle('visible', val.length > 0);
    });
  }

  function clearInput(id) {
    document.getElementById(id).value = '';
    document.getElementById('clear-' + id).classList.remove('visible');
    document.getElementById(id).focus();
  }

  /* ── Clear search (option A) ── */
  function clearSearch() {
    document.getElementById('inp-title').value = '';
    document.getElementById('inp-author').value = '';
    updateInputClears();
    document.getElementById('results').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    document.getElementById('btn-clear').style.display = 'none';
    setStatus('');
    _accepted = []; _rejected = [];
  }

  /* ── Media type toggle ── */
  function setMediaType(t) {
    _mediaType = t;
    document.getElementById('btn-type-ebook').classList.toggle('active', t === 'ebook');
    document.getElementById('btn-type-audiobook').classList.toggle('active', t === 'audiobook');
    const hint = t === 'audiobook'
      ? 'Enter a title and/or author below. After downloading, the audiobook will appear in Audiobookshelf within 1–2 minutes.'
      : 'Enter a book title and/or author below. After downloading, a book will appear in the Calibre library within 1–2 minutes.';
    document.getElementById('search-hint').textContent = hint;
    // Clear any previous results when switching type
    document.getElementById('results').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    document.getElementById('btn-clear').style.display = 'none';
    setStatus('');
    _accepted = []; _rejected = [];
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
    if (!title && !author) { setStatus('Enter a title or author to search.', 'err'); return; }

    const btn = document.getElementById('btn-search');
    btn.disabled = true;
    btn.textContent = 'Searching…';
    setStatus('');
    document.getElementById('results').innerHTML = '';
    document.getElementById('view-toggle').style.display = 'none';
    document.getElementById('btn-clear').style.display = 'none';
    _accepted = []; _rejected = [];

    const qs = new URLSearchParams();
    if (title)  qs.set('title', title);
    if (author) qs.set('author', author);
    qs.set('media_type', _mediaType);

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
      document.getElementById('btn-clear').style.display = 'none';
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><p>No releases found for this search. Try a different title or author.</p></div>';
      setStatus('');
      return;
    }

    const label = accepted.length
      ? '<strong>' + accepted.length + '</strong> release' + (accepted.length !== 1 ? 's' : '') + ' found'
      : 'No accepted releases';
    setStatus(label + (rejected.length ? ' &nbsp;&middot;&nbsp; ' + rejected.length + ' filtered out' : ''));

    document.getElementById('view-toggle').style.display = accepted.length ? 'flex' : 'none';
    document.getElementById('btn-clear').style.display = 'inline-flex';

    let html = '';

    if (!accepted.length) {
      html += '<div class="empty-state"><div class="empty-icon">🔍</div><p>No downloadable releases found — ' + rejected.length + ' were filtered out.</p></div>';
    } else {
      html += '<div class="section-heading">' + accepted.length + ' release' + (accepted.length !== 1 ? 's' : '') + ' found</div>';
      html += '<div class="card-list">';
      accepted.forEach((r, i) => {
        const fmt = (r.detected_format || '').toLowerCase();
        const fmtClass = fmt === 'epub' ? 'fmt-epub' : fmt === 'pdf' ? 'fmt-pdf'
                       : fmt === 'm4b'  ? 'fmt-m4b'  : fmt === 'mp3' ? 'fmt-mp3' : 'fmt-unk';
        const badgeCls = fmt === 'epub' ? 'badge-epub' : fmt === 'pdf' ? 'badge-pdf'
                       : fmt === 'm4b'  ? 'badge-m4b'  : fmt === 'mp3' ? 'badge-mp3' : 'badge-unk';

        html += '<div class="release-card ' + fmtClass + '">';
        html += '<div class="card-main">';
        html += '<span class="badge ' + badgeCls + '">' + esc(fmt || '?') + '</span>';
        html += '<div class="card-body">';
        html += '<span class="card-title">' + esc(r.title) + '</span>';
        if (_view === 'advanced') html += '<span class="score-pill">' + r.score + '</span>';
        html += '<button class="btn-dl" onclick="dispatch(' + i + ', this)">Download</button>';
        html += '</div></div>';

        if (_view === 'advanced') {
          const chips = [];
          if (r.indexer)         chips.push(esc(r.indexer));
          if (r.size_mb != null) chips.push(r.size_mb.toFixed(1) + ' MB');
          if (r.seeders != null) chips.push(r.seeders + ' seeds');
          if (r.age_days != null) chips.push(r.age_days + 'd old');

          if (chips.length) {
            html += '<div class="card-meta">';
            chips.forEach((c, ci) => {
              if (ci > 0) html += '<span class="meta-dot"></span>';
              html += '<span class="meta-chip">' + c + '</span>';
            });
            html += '</div>';
          }
        }

        html += '</div>';
      });
      html += '</div>';
    }

    if (rejected.length) {
      html += '<button class="rej-toggle" id="rej-btn" onclick="toggleRejected()">'
            + '<span class="rej-toggle-arrow" id="rej-arrow">&#9654;</span>'
            + ' ' + rejected.length + ' filtered out</button>';
      html += '<div class="rej-body" id="rej-body"><div class="rej-list">';
      rejected.forEach(r => {
        const fmt = (r.detected_format || '').toLowerCase();
        html += '<div class="rej-item">'
              + '<span class="badge badge-rej">' + esc(fmt || '?') + '</span>'
              + '<span class="rej-title" title="' + esc(r.title) + '">' + esc(r.title) + '</span>'
              + '<span class="rej-reason">' + esc(r.reject_reason || '') + '</span>'
              + '</div>';
      });
      html += '</div></div>';
    }

    el.innerHTML = html;
  }

  function toggleRejected() {
    const body  = document.getElementById('rej-body');
    const arrow = document.getElementById('rej-arrow');
    const open  = body.style.display === 'block';
    body.style.display    = open ? 'none' : 'block';
    arrow.style.transform = open ? '' : 'rotate(90deg)';
  }

  /* ── Toast ── */
  let _toastTimer = null;
  function showToast(msg, kind) {
    const toast = document.getElementById('toast');
    const icon  = document.getElementById('toast-icon');
    const body  = document.getElementById('toast-body');
    toast.className = 'toast-' + kind;
    icon.className  = 'toast-icon ' + (kind === 'success' ? 'ok' : 'err');
    icon.textContent = kind === 'success' ? '✓' : '✕';
    body.textContent = msg;
    toast.classList.add('visible');
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(hideToast, 5000);
  }
  function hideToast() {
    document.getElementById('toast').classList.remove('visible');
    clearTimeout(_toastTimer);
  }

  /* ── Dispatch ── */
  async function dispatch(index, btn) {
    const release = _accepted[index];
    const title   = document.getElementById('inp-title').value.trim();
    const author  = document.getElementById('inp-author').value.trim();
    const displayTitle = title || release.title;

    btn.disabled = true;
    btn.textContent = '…';

    try {
      const resp = await fetch('/portal/download', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title:         displayTitle,
          author:        author || '',
          release_title: release.title,
          indexer:       release.indexer,
          protocol:      release.protocol,
          download_url:  release.download_url,
          media_type:    _mediaType,
        }),
      });
      if (resp.status === 401) { handle401(); return; }
      const data = await resp.json();
      if (data.ok) {
        const dest = _mediaType === 'audiobook'
          ? 'Audiobookshelf library'
          : 'Calibre library';
        showToast(displayTitle + ' is being downloaded and should be available in the ' + dest + ' within 1–2 minutes.', 'success');
      } else {
        throw new Error(data.detail || JSON.stringify(data));
      }
    } catch (e) {
      showToast('Download failed: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Download';
    }
  }

  /* ── Helpers ── */
  function setStatus(msg, cls) {
    const el = document.getElementById('status');
    el.innerHTML = msg ? '<span class="' + (cls || '') + '">' + msg + '</span>' : '';
  }

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const active = document.activeElement;
    if (active === document.getElementById('inp-password')) { doLogin(); return; }
    if (active === document.getElementById('inp-title') ||
        active === document.getElementById('inp-author')) { fetchReleases(); }
  });
</script>
</body>
</html>"""
