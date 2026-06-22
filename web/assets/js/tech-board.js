(function () {
  var DATA_URL = 'data/index.json';

  var EOL_PHP = /^[2-6]\./;

  function cmsBadge(cms) {
    if (!cms) return '<span class="card-stat cms-none">no CMS</span>';
    if (cms.toLowerCase().indexOf('wordpress') !== -1) return '<span class="card-stat cms-wp">WordPress</span>';
    return '<span class="card-stat cms-other">' + cms + '</span>';
  }

  function phpBadge(ver) {
    if (!ver) return '<span class="card-stat php-none">no PHP</span>';
    if (EOL_PHP.test(ver)) return '<span class="card-stat php-eol">' + ver + ' ⚠EOL</span>';
    return '<span class="card-stat php-ok">' + ver + '</span>';
  }

  function renderCard(entry) {
    var card = document.createElement('div');
    card.className = 'domain-card';
    card.setAttribute('data-domain', entry.domain);

    var pluginHtml = '';
    (entry.interesting_plugins || []).forEach(function (name) {
      pluginHtml += '<span class="card-stat plugin-warn">' + name + '</span>';
    });

    card.innerHTML =
      '<div class="card-header-row">' +
        '<span class="card-domain">' + entry.domain + '</span>' +
        '<span class="card-date">' + (entry.last_refreshed || entry.queried_at || '').slice(0, 10) + '</span>' +
      '</div>' +
      '<div class="card-stats">' +
        '<span class="card-stat">' + (entry.url_count || 0) + ' URLs</span>' +
        '<span class="card-stat server-stat">' + (entry.server || '—') + '</span>' +
        cmsBadge(entry.cms) +
        phpBadge(entry.php_version) +
        pluginHtml +
      '</div>' +
      '<div class="card-contributor">' +
        '<span class="card-name">' + (entry.display_name || '') + '</span>' +
        '<span>' + (entry.display_loc || '') + '</span>' +
      '</div>';

    card.addEventListener('click', function () {
      window.location.href = 'domain.html?d=' + encodeURIComponent(entry.domain);
    });
    return card;
  }

  function render(domains) {
    var list = document.getElementById('domain-list');
    if (!list) return;
    list.innerHTML = '';
    if (!domains.length) { list.innerHTML = '<p class="empty">No results.</p>'; return; }
    domains.forEach(function (e) { list.appendChild(renderCard(e)); });
  }

  function applySearch(all) {
    var input = document.getElementById('search-input');
    if (!input) return;
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      render(!q ? all : all.filter(function (e) {
        return e.domain.toLowerCase().includes(q);
      }));
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch(DATA_URL)
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        var domains = (data.domains || []).slice().sort(function (a, b) {
          return a.domain.localeCompare(b.domain);
        });

        var statsEl = document.getElementById('db-stats');
        if (statsEl) {
          var withCMS    = domains.filter(function (d) { return d.cms; }).length;
          var withEOLPHP = domains.filter(function (d) { return d.php_version && EOL_PHP.test(d.php_version); }).length;
          statsEl.textContent = domains.length + ' domains · ' + withCMS + ' with CMS · ' + withEOLPHP + ' with EOL PHP';
        }

        render(domains);
        applySearch(domains);
      })
      .catch(function (err) {
        var list = document.getElementById('domain-list');
        if (list) list.innerHTML = '<p class="empty">Failed to load: ' + err.message + '</p>';
      });
  });
})();
