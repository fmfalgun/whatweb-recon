(function () {
  function param(name) {
    return new URLSearchParams(window.location.search).get(name);
  }
  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val != null ? String(val) : '—';
  }

  function addESRow(grid, key, val, extraClass) {
    if (!grid) return;
    var row = document.createElement('div');
    row.className = 'es-row';
    var valClass = 'es-val' + (extraClass ? ' ' + extraClass : '');
    row.innerHTML = '<span class="es-key">' + key + '</span>' +
      '<span class="' + valClass + '">' + (val != null && val !== '' ? val : '—') + '</span>';
    grid.appendChild(row);
  }

  var EOL_PHP = /^[2-6]\./;

  document.addEventListener('DOMContentLoaded', function () {
    var domain = param('d');
    if (!domain) { window.location.href = 'tech-board.html'; return; }

    fetch('data/domains/' + domain + '.json')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        setText('domain-name-display', d.domain);
        var contribEl = document.getElementById('contributor-meta');
        if (contribEl) {
          contribEl.textContent = (d.display_name || '') + (d.display_loc ? ' · ' + d.display_loc : '');
        }

        // Stat badges
        setText('val-url-count', d.url_count || 0);
        setText('val-server',    d.server || '—');
        setText('val-cms',       d.cms || 'none');

        var phpText = d.php_version || 'none';
        if (d.php_version && EOL_PHP.test(d.php_version)) phpText += ' ⚠ EOL';
        setText('val-php', phpText);

        setText('queried-at', (d.queried_at || '').slice(0, 10));

        // Security flags grid
        var flagsGrid = document.getElementById('flags-grid');
        var results = d.results || [];
        var xmlrpc     = results.some(function (r) { return r.xmlrpc; });
        var cpanel     = results.some(function (r) { return r.cpanel; });
        var whm        = results.some(function (r) { return r.whm; });
        var phpmyadmin = results.some(function (r) { return r.phpmyadmin; });
        var phppgadmin = results.some(function (r) { return r.phppgadmin; });

        addESRow(flagsGrid, 'xmlrpc.php', xmlrpc     ? 'EXPOSED' : 'not found', xmlrpc     ? 'es-val-bad' : 'es-val-ok');
        addESRow(flagsGrid, 'cPanel',     cpanel     ? 'EXPOSED' : 'not found', cpanel     ? 'es-val-bad' : 'es-val-ok');
        addESRow(flagsGrid, 'WHM',        whm        ? 'EXPOSED' : 'not found', whm        ? 'es-val-bad' : 'es-val-ok');
        addESRow(flagsGrid, 'phpMyAdmin', phpmyadmin ? 'EXPOSED' : 'not found', phpmyadmin ? 'es-val-bad' : 'es-val-ok');
        addESRow(flagsGrid, 'phpPgAdmin', phppgadmin ? 'EXPOSED' : 'not found', phppgadmin ? 'es-val-bad' : 'es-val-ok');
        addESRow(flagsGrid, 'method',     d.method     || '—');
        addESRow(flagsGrid, 'aggression', d.aggression != null ? d.aggression : '—');

        // Results grid — one record-section per URL
        var resultsGrid = document.getElementById('results-grid');
        if (resultsGrid) {
          results.forEach(function (r) {
            var sec = document.createElement('div');
            sec.className = 'record-section';

            var titleText = (r.http_status || '?') + ' · ' + (r.url || '');
            sec.innerHTML = '<div class="record-title">' + titleText + '</div>';

            var list = document.createElement('div');
            list.className = 'record-list';

            function addItem(label, val) {
              if (val == null || val === '' || val === false) return;
              var item = document.createElement('div');
              item.className = 'record-item';
              item.innerHTML = '<span class="record-value"><span style="color:var(--dim);font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;min-width:110px;display:inline-block;">' + label + '</span>' + String(val) + '</span>';
              list.appendChild(item);
            }

            var serverStr = r.server || '';
            if (r.server_os) serverStr += (serverStr ? ' / ' : '') + r.server_os;
            addItem('server',       serverStr || null);
            addItem('php',          r.php_version);
            addItem('cms',          r.cms_detected);
            addItem('title',        r.title);
            addItem('jquery',       r.jquery_version);
            addItem('xmlrpc',       r.xmlrpc ? 'exposed' : null);
            addItem('redirect',     r.redirect_url);

            sec.appendChild(list);
            resultsGrid.appendChild(sec);
          });
        }

        // Plugins list
        var pluginsList = document.getElementById('plugins-list');
        if (pluginsList) {
          var plugins = d.interesting_plugins || [];
          if (!plugins.length) {
            pluginsList.innerHTML = '<p class="empty">No interesting plugins detected.</p>';
          } else {
            plugins.forEach(function (name) {
              var span = document.createElement('span');
              span.className = 'card-stat plugin-warn';
              span.textContent = name;
              pluginsList.appendChild(span);
            });
          }
        }
      })
      .catch(function (err) {
        var box = document.getElementById('error-box');
        var msg = document.getElementById('error-message');
        if (box) box.style.display = 'block';
        if (msg) msg.textContent = 'Failed to load "' + domain + '": ' + err.message;
      });
  });
})();
