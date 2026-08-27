/* מעקב סקרים 2026 — לוגיקת צד לקוח */
const App = (() => {
  'use strict';

  let chart = null;
  let currentDays = 120;

  // באתר סטטי אין שרת: הנתונים נקראים מקבצי JSON שנבנו מראש, ואין
  // בדיקת סקרים חיה. אותו קוד משרת את שני המצבים.
  const BASE = document.body.dataset.base || '/';
  const STATIC = document.body.dataset.static === '1';

  const chartUrl = (kind, arg) => STATIC
    ? `${BASE}api/chart-${kind}-${arg}.json`
    : (kind === 'average' ? `/api/chart/average${arg === 'all' ? '' : '?days=' + arg}`
                          : `/api/chart/${kind}?limit=40`);

  // ---------- כלים ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  function toast(message, kind = 'info', ms = 6000) {
    const el = $('#toast');
    el.textContent = message;
    el.className = `toast toast--${kind} is-open`;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => {
      el.classList.remove('is-open');
      setTimeout(() => { el.hidden = true; }, 250);
    }, ms);
  }

  // ---------- גרפים ----------
  const chartOptions = () => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          usePointStyle: true, pointStyle: 'line', boxWidth: 26,
          padding: 12, font: { family: 'inherit', size: 12 },
          color: getComputedStyle(document.body).getPropertyValue('--text').trim(),
        },
      },
      tooltip: {
        rtl: true, textDirection: 'rtl',
        itemSort: (a, b) => b.parsed.y - a.parsed.y,
        callbacks: {
          label: (c) => ` ${c.dataset.label}: ${c.parsed.y}`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: { display: true, text: 'מנדטים' },
        grid: { color: 'rgba(128,128,128,.16)' },
      },
      x: {
        // ציר הזמן משמאל לימין (ישן -> חדש), כמו בגרפי הסקרים של הערוצים
        // עצמם. להיפוך לכיוון הקריאה בעברית: הוסף reverse: true.
        grid: { display: false },
        ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 },
      },
    },
    elements: {
      line: { tension: 0.25, borderWidth: 2.5 },
      point: { radius: 0, hoverRadius: 5, hitRadius: 12 },
    },
  });

  function render(canvasId, payload) {
    const ctx = $(`#${canvasId}`);
    if (!ctx) return;
    if (chart) chart.destroy();

    if (!payload.labels.length) {
      toast('אין עדיין נתונים להצגה בגרף', 'warn');
      return;
    }

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: payload.labels.map(shortDate),
        datasets: payload.series.map((s) => ({
          label: s.name,
          data: s.data,
          borderColor: s.color,
          backgroundColor: s.color,
          spanGaps: true,
          // מפלגות זעירות מתחילות מוסתרות כדי לא להעמיס את הגרף
          hidden: (s.last ?? 0) < 4,
        })),
      },
      options: chartOptions(),
    });
  }

  function shortDate(iso) {
    const [y, m, d] = iso.split('-');
    return `${+d}.${+m}`;
  }

  async function loadAverage(days) {
    const res = await fetch(chartUrl('average', days || 'all'));
    render('avgChart', await res.json());
  }

  async function loadSource(key) {
    const res = await fetch(chartUrl(key, 'all'));
    render('srcChart', await res.json());
  }

  // ---------- ריענון ----------
  function setBusy(btn, busy) {
    if (!btn) return;
    btn.classList.toggle('is-busy', busy);
    btn.disabled = busy;
  }

  async function doRefresh(btn, source) {
    setBusy(btn, true);
    const label = btn && $('.btn__label', btn);
    const original = label && label.textContent;
    if (label) label.textContent = 'בודק באתרים...';

    try {
      const url = source ? `/api/refresh?source=${source}` : '/api/refresh';
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();

      if (data.error) { toast('שגיאה: ' + data.error, 'error', 9000); return; }

      // בדיקה כבר רצה (בדרך כלל האוטומטית שעלתה עם האפליקציה) — לא
      // מפעילים שנייה, רק נצמדים לזו שרצה
      if (data.busy) {
        toast(data.summary, 'info');
        showBar('בודק סקרים חדשים בכל האתרים…');
        await pollUntilDone();
        return;
      }

      const kind = data.new?.length ? 'ok' : (data.errors?.length ? 'warn' : 'info');
      toast(data.summary, kind, 9000);
      fetch('/api/refresh-status')
        .then((r) => r.json()).then((s) => renderLastCheck(s.last_check))
        .catch(() => {});

      // רק אם באמת השתנה משהו יש טעם לרענן את העמוד
      if (data.new?.length || data.results?.some((r) => r.status === 'updated')) {
        setTimeout(() => window.location.reload(), 1400);
      }
    } catch (err) {
      toast('הבדיקה נכשלה: ' + err.message, 'error', 9000);
    } finally {
      setBusy(btn, false);
      if (label && original) label.textContent = original;
    }
  }

  // ---------- מתי נבדק לאחרונה ----------
  // הזמן נשמר ב-UTC ומוצג בשעון המקומי. מוצג בכותרת בכל עמוד, כך שתמיד
  // אפשר לדעת עד כמה הנתונים טריים — גם בלי להריץ בדיקה.
  function renderLastCheck(iso) {
    const el = $('#lastCheck');
    if (!el) return;
    if (iso) el.dataset.iso = iso;
    const value = el.dataset.iso;
    if (!value) { el.textContent = 'עוד לא בוצעה בדיקה'; return; }

    const d = new Date(value);
    if (isNaN(d)) { el.textContent = ''; return; }
    const date = d.toLocaleDateString('he-IL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const time = d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

    const mins = Math.round((Date.now() - d) / 60000);
    let ago = '';
    if (mins < 1) ago = 'ממש עכשיו';
    else if (mins < 60) ago = `לפני ${mins} דק'`;
    else if (mins < 60 * 24) ago = `לפני ${Math.round(mins / 60)} שע'`;
    else ago = `לפני ${Math.round(mins / 1440)} ימים`;

    el.textContent = `נבדק לאחרונה: ${date}, ${time}`;
    el.title = ago;
    el.classList.toggle('is-stale', mins > 60 * 12);
  }

  // ---------- הבדיקה שרצה עם עליית האפליקציה ----------
  // השרת מתחיל לבדוק סקרים ברקע ברגע שהוא עולה, כדי שהעמוד ייפתח מיד.
  // כאן עוקבים אחרי הבדיקה, ומרעננים את העמוד רק אם באמת השתנה משהו.
  function showBar(text) {
    const bar = $('#autobar');
    if (!bar) return;
    $('#autobarText').textContent = text;
    bar.hidden = false;
    requestAnimationFrame(() => bar.classList.add('is-open'));
    bar.setAttribute('role', 'status');
  }

  function hideBar() {
    const bar = $('#autobar');
    if (!bar) return;
    bar.classList.remove('is-open');
    setTimeout(() => { bar.hidden = true; }, 300);
  }

  // עוקב אחרי בדיקה שרצה בשרת עד שהיא נגמרת, ואז מגיב בהתאם
  async function pollUntilDone() {
    for (let i = 0; i < 120; i++) {          // עד ~3 דקות, ואז מוותרים
      let s;
      try {
        s = await (await fetch('/api/refresh-status')).json();
      } catch {
        hideBar();
        return;                              // השרת ירד — לא מציקים למשתמש
      }

      if (s.state !== 'running') {
        hideBar();
        renderLastCheck(s.last_check);
        if (s.changed) {
          showBar(s.summary + ' — מרענן…');
          setTimeout(() => window.location.reload(), 1200);
        } else {
          toast(s.summary || 'אין סקרים חדשים',
                s.state === 'error' ? 'warn' : 'info');
        }
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
    hideBar();
  }

  async function watchStartupRefresh() {
    if (STATIC) return;
    const bar = $('#autobar');
    // אם הבדיקה כבר הסתיימה כשהעמוד רונדר, הנתונים שמוצגים כבר טריים
    if (!bar || bar.dataset.state !== 'running') return;
    showBar('בודק סקרים חדשים בכל האתרים…');
    await pollUntilDone();
  }

  // ---------- אתחול ----------
  function wireCommon() {
    renderLastCheck();
    if (STATIC) { wireChartToggle(); return; }
    setInterval(() => renderLastCheck(), 60000);
    const btn = $('#refreshBtn');
    if (btn) {
      btn.addEventListener('click', () => doRefresh(btn, btn.dataset.source || ''));
    }
    $$('.refresh-one').forEach((b) => {
      b.addEventListener('click', (e) => {
        e.preventDefault();
        doRefresh(b, b.dataset.source);
      });
    });
    wireChartToggle();
  }

  function wireChartToggle() {
    const toggle = $('#toggleAll');
    if (toggle) {
      toggle.addEventListener('click', () => {
        if (!chart) return;
        const anyHidden = chart.data.datasets.some((_, i) => !chart.isDatasetVisible(i));
        chart.data.datasets.forEach((_, i) => chart.setDatasetVisibility(i, anyHidden));
        chart.update();
      });
    }
  }

  function initAverageChart() {
    wireCommon();
    watchStartupRefresh();
    loadAverage(currentDays);
    const sel = $('#rangeSel');
    if (sel) {
      $$('button', sel).forEach((b) => b.addEventListener('click', () => {
        $$('button', sel).forEach((x) => x.classList.remove('is-active'));
        b.classList.add('is-active');
        currentDays = b.dataset.days ? +b.dataset.days : null;
        loadAverage(currentDays);
      }));
    }
  }

  function initSourceChart(key) {
    wireCommon();
    watchStartupRefresh();
    loadSource(key);
  }

  return { initAverageChart, initSourceChart, toast };
})();
