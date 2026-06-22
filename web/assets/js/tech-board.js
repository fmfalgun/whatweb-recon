(function () {
  var DATA_URL = 'data/index.json';

  function init() {
    fetch(DATA_URL)
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) { render(data); })
      .catch(function (e) { showError('Failed to load data: ' + e.message); });
  }

  function render(data) {
    var domains = (data.domains || []).slice().sort(function (a, b) {
      return a.domain.localeCompare(b.domain);
    });

    document.getElementById('stat-domains').textContent = domains.length;
    var cmsCount = domains.filter(function (d) { return d.cms; }).length;
    var eolCount = domains.filter(function (d) {
      return d.php_version && /^[2-6]\./.test(d.php_version);
    }).length;
    document.getElementById('stat-cms').textContent = cmsCount;
    document.getElementById('stat-eol').textContent = eolCount;

    var grid = document.getElementById('tech-board-grid');
    grid.innerHTML = '';
    domains.forEach(function (d) { grid.appendChild(makeCard(d)); });

    var searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', function () {
        var q = this.value.toLowerCase().trim();
        var cards = grid.querySelectorAll('.tech-card');
        cards.forEach(function (card) {
          var match = card.dataset.domain.includes(q) ||
            (card.dataset.server || '').toLowerCase().includes(q) ||
            (card.dataset.cms || '').toLowerCase().includes(q);
          card.style.display = q && !match ? 'none' : '';
        });
      });
    }
  }

  function makeCard(d) {
    var art = document.createElement('article');
    art.className = 'tech-card';
    art.dataset.domain = d.domain;
    art.dataset.server = d.server || '';
    art.dataset.cms    = d.cms    || '';

    var cmsClass   = d.cms ? (d.cms === 'WordPress' ? 'cms-wordpress' : 'cms-other') : 'cms-none';
    var cmsLabel   = d.cms || 'none';
    var phpClass   = !d.php_version ? 'php-none' : (/^[2-6]\./.test(d.php_version) ? 'php-eol' : 'php-ok');
    var phpLabel   = d.php_version || '—';
    var methodClass = (d.method === 'whatweb') ? 'method-whatweb' : 'method-fallback';

    var pluginTags = '';
    (d.interesting_plugins || []).forEach(function (p) {
      pluginTags += '<span class="plugin-tag plugin-warn">' + esc(p) + '</span>';
    });

    art.innerHTML = [
      '<div class="tech-card-header">',
      '  <a class="tech-card-domain" href="domain.html?d=' + esc(d.domain) + '">' + esc(d.domain) + '</a>',
      '  <span class="method-badge ' + methodClass + '">' + esc(d.method || 'whatweb') + '</span>',
      '</div>',
      '<div class="tech-card-meta">',
      '  <span class="meta-item"><span class="meta-label">server</span><span class="server-badge">' + esc(d.server || '—') + '</span></span>',
      '  <span class="meta-item"><span class="meta-label">cms</span><span class="cms-badge ' + cmsClass + '">' + esc(cmsLabel) + '</span></span>',
      '  <span class="meta-item"><span class="meta-label">php</span><span class="php-badge ' + phpClass + '">' + esc(phpLabel) + '</span></span>',
      '  <span class="meta-item"><span class="meta-label">urls</span><span class="url-count">' + (d.url_count || 0) + '</span></span>',
      '</div>',
      pluginTags ? '<div class="plugin-tags">' + pluginTags + '</div>' : '',
      '<div class="tech-card-footer">',
      '  <span class="submitter">' + esc(d.display_name || '') + (d.display_loc ? ' \xb7 ' + esc(d.display_loc) : '') + '</span>',
      '  <a href="domain.html?d=' + esc(d.domain) + '" class="card-detail-link">Detail →</a>',
      '</div>',
    ].join('\n');

    return art;
  }

  function showError(msg) {
    var box = document.getElementById('error-box');
    var span = document.getElementById('error-message');
    if (box && span) { span.textContent = msg; box.style.display = 'block'; }
  }

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
