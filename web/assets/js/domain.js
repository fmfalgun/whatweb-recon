(function () {
  var params = new URLSearchParams(window.location.search);
  var d = params.get('d');

  if (!d) {
    showError('No domain specified. Add ?d=nmap.org to the URL.');
    return;
  }

  fetch('data/domains/' + encodeURIComponent(d) + '.json')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) { render(data); })
    .catch(function (e) { showError('Failed to load: ' + e.message); });

  function render(data) {
    var titleEl = document.getElementById('domain-title');
    if (titleEl) titleEl.textContent = data.domain || d;
    var qEl = document.getElementById('queried-at');
    if (qEl) qEl.textContent = (data.queried_at || '').slice(0, 10);

    setText('stat-url-count', data.url_count || 0);
    setText('stat-server', data.server || '—');
    setText('stat-cms', data.cms || 'none');
    var phpText = data.php_version || 'none';
    if (data.php_version && /^[2-6]\./.test(data.php_version)) phpText += ' ⚠ EOL';
    setText('stat-php', phpText);

    renderFlags(data);
    renderTable(data.results || []);
    renderPlugins(data.interesting_plugins || []);
  }

  function renderFlags(data) {
    var container = document.getElementById('exposure-flags-row');
    if (!container) return;
    var CHECKS = [
      { key: 'xmlrpc',     label: 'xmlrpc.php',  level: 'exposed' },
      { key: 'cpanel',     label: 'cPanel',       level: 'exposed' },
      { key: 'whm',        label: 'WHM',          level: 'exposed' },
      { key: 'phpmyadmin', label: 'phpMyAdmin',   level: 'exposed' },
      { key: 'phppgadmin', label: 'phpPgAdmin',   level: 'exposed' },
    ];
    var found = {};
    (data.results || []).forEach(function (r) {
      CHECKS.forEach(function (c) { if (r[c.key]) found[c.key] = true; });
    });
    CHECKS.forEach(function (c) {
      var el = document.createElement('span');
      el.className = 'flag-badge ' + (found[c.key] ? 'flag-exposed' : 'flag-safe');
      el.textContent = (found[c.key] ? '⚠ ' : '✓ ') + c.label;
      container.appendChild(el);
    });
  }

  function renderTable(results) {
    var tbody = document.getElementById('results-tbody');
    if (!tbody) return;
    results.forEach(function (r) {
      var tr = document.createElement('tr');
      var statusClass = r.http_status >= 200 && r.http_status < 300 ? 'status-2xx' :
                        r.http_status >= 300 && r.http_status < 400 ? 'status-3xx' : 'status-other';
      var cmsText = r.cms_detected ? (r.cms_detected + (r.cms_version ? ' ' + r.cms_version : '')) : '—';
      var serverText = r.server ? (r.server + (r.server_os ? ' / ' + r.server_os : '')) : (r.redirect_url ? '→ ' + r.redirect_url : '—');
      tr.innerHTML = [
        '<td class="td-url">' + esc(r.url) + '</td>',
        '<td class="td-status ' + statusClass + '">' + (r.http_status || '—') + '</td>',
        '<td class="td-server">' + esc(serverText) + '</td>',
        '<td class="td-cms">' + esc(cmsText) + '</td>',
        '<td class="td-php ' + (r.php_version && /^[2-6]\./.test(r.php_version) ? 'php-eol-cell' : '') + '">' + esc(r.php_version || '—') + '</td>',
        '<td class="td-jquery">' + esc(r.jquery_version || '—') + '</td>',
      ].join('');
      tbody.appendChild(tr);
    });
  }

  function renderPlugins(plugins) {
    var container = document.getElementById('plugins-list');
    if (!container) return;
    if (!plugins.length) {
      container.innerHTML = '<span class="empty">No interesting plugins detected.</span>';
      return;
    }
    plugins.forEach(function (p) {
      var tag = document.createElement('span');
      tag.className = 'plugin-tag plugin-warn';
      tag.textContent = p;
      container.appendChild(tag);
    });
  }

  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function showError(msg) {
    var box = document.getElementById('error-box');
    var span = document.getElementById('error-message');
    if (box && span) { span.textContent = msg; box.style.display = 'block'; }
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
