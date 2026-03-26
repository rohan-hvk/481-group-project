import json
from pathlib import Path
import pandas as pd
import numpy as np

SRC = Path('/mnt/data/final_formatted.json')
OUT_DIR = Path('/mnt/data/trading_viz')
OUT_JSON = OUT_DIR / 'processed_trading_data.json'
OUT_HTML = OUT_DIR / 'trading_greeks_explorer.html'

with SRC.open() as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df['mbo_size'] = df['MBO'].apply(lambda x: int(sum(x)) if isinstance(x, list) and len(x) > 0 else 1)
df['side_sign'] = df['Side'].map({'Bid': 1, 'Ask': -1}).fillna(0)
df['gamma_mid'] = (df['call_gamma'] + df['put_gamma']) / 2.0
df['delta_abs_mid'] = (df['call_delta'].abs() + df['put_delta'].abs()) / 2.0
df['vega_mid'] = (df['call_vega'] + df['put_vega']) / 2.0
df['vanna_mid'] = (df['call_vanna'] + df['put_vanna']) / 2.0
df['vomma_mid'] = (df['call_vomma'] + df['put_vomma']) / 2.0

df['signed_gamma_proxy'] = df['side_sign'] * df['mbo_size'] * df['gamma_mid']
df['signed_delta_proxy'] = df['side_sign'] * df['mbo_size'] * df['delta_abs_mid']
df['weighted_vega'] = df['mbo_size'] * df['vega_mid']
df['weighted_vanna'] = df['mbo_size'] * df['vanna_mid']
df['weighted_vomma'] = df['mbo_size'] * df['vomma_mid']

by_strike = df.groupby(['timestamp', 'spx_strike']).agg(
    bid_gamma=('signed_gamma_proxy', lambda s: float(s[s > 0].sum())),
    ask_gamma=('signed_gamma_proxy', lambda s: float(-s[s < 0].sum())),
    net_gamma=('signed_gamma_proxy', 'sum'),
    delta_proxy=('signed_delta_proxy', 'sum'),
    volume_proxy=('mbo_size', 'sum'),
).reset_index()

by_time = df.groupby('timestamp').agg(
    current_es=('current_es_price', 'mean'),
    spx_price=('spx_price', 'mean'),
    t=('t', 'mean'),
    total_rows=('spx_strike', 'size'),
    total_volume_proxy=('mbo_size', 'sum'),
    net_gamma=('signed_gamma_proxy', 'sum'),
    net_delta_proxy=('signed_delta_proxy', 'sum'),
    total_bid_gamma=('signed_gamma_proxy', lambda s: float(s[s > 0].sum())),
    total_ask_gamma=('signed_gamma_proxy', lambda s: float(-s[s < 0].sum())),
    avg_vanna=('weighted_vanna', lambda s: float(s.sum() / max(df.loc[s.index, 'mbo_size'].sum(), 1))),
    avg_vomma=('weighted_vomma', lambda s: float(s.sum() / max(df.loc[s.index, 'mbo_size'].sum(), 1))),
    avg_vega=('weighted_vega', lambda s: float(s.sum() / max(df.loc[s.index, 'mbo_size'].sum(), 1))),
).reset_index()

strikes = sorted(int(x) for x in by_strike['spx_strike'].unique())
strike_index = {s: i for i, s in enumerate(strikes)}

snapshots = []
heatmap_rows = []
for _, row in by_time.iterrows():
    ts = row['timestamp']
    subset = by_strike[by_strike['timestamp'] == ts].sort_values('spx_strike')
    bid = [0.0] * len(strikes)
    ask = [0.0] * len(strikes)
    net = [0.0] * len(strikes)
    vol = [0] * len(strikes)
    for _, srow in subset.iterrows():
        idx = strike_index[int(srow['spx_strike'])]
        bid[idx] = round(float(srow['bid_gamma']), 6)
        ask[idx] = round(float(srow['ask_gamma']), 6)
        net[idx] = round(float(srow['net_gamma']), 6)
        vol[idx] = int(srow['volume_proxy'])
    heatmap_rows.append(net)
    snapshots.append({
        'timestamp': ts.isoformat(),
        'label': ts.strftime('%H:%M:%S.%f')[:-3],
        'current_es': round(float(row['current_es']) / 100.0, 2),
        'spx_price': round(float(row['spx_price']), 2),
        'days_to_expiry': round(float(row['t']) * 365.0, 2),
        'total_rows': int(row['total_rows']),
        'total_volume_proxy': int(row['total_volume_proxy']),
        'net_gamma': round(float(row['net_gamma']), 6),
        'net_delta_proxy': round(float(row['net_delta_proxy']), 3),
        'total_bid_gamma': round(float(row['total_bid_gamma']), 6),
        'total_ask_gamma': round(float(row['total_ask_gamma']), 6),
        'avg_vanna': round(float(row['avg_vanna']), 6),
        'avg_vomma': round(float(row['avg_vomma']), 6),
        'avg_vega': round(float(row['avg_vega']), 6),
        'bid_gamma': bid,
        'ask_gamma': ask,
        'net_gamma_profile': net,
        'volume_profile': vol,
    })

payload = {
    'metadata': {
        'record_count': int(len(df)),
        'snapshot_count': int(len(snapshots)),
        'strike_count': int(len(strikes)),
        'start_timestamp': snapshots[0]['timestamp'],
        'end_timestamp': snapshots[-1]['timestamp'],
        'notes': [
            'This file is an aggregated view of the raw JSON to keep the browser fast.',
            'Gamma/Delta values shown are quote-side proxies weighted by summed MBO size.',
            'Bid values are positive, Ask values are negative in the net profile.'
        ]
    },
    'strikes': strikes,
    'time_labels': [s['label'] for s in snapshots],
    'timestamps': [s['timestamp'] for s in snapshots],
    'heatmap_net_gamma': heatmap_rows,
    'snapshots': snapshots,
}

with OUT_JSON.open('w') as f:
    json.dump(payload, f)

html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Trading Greeks Explorer</title>
  <script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
  <style>
    :root {
      --bg: #0d1117;
      --panel: #161b22;
      --panel-2: #11161d;
      --border: #30363d;
      --text: #c9d1d9;
      --muted: #8b949e;
      --accent: #58a6ff;
      --green: #2ea043;
      --red: #f85149;
      --amber: #d29922;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 18px;
    }
    .app { display: grid; grid-template-columns: 340px 1fr; gap: 18px; min-height: calc(100vh - 36px); }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 10px 24px rgba(0,0,0,.22);
    }
    .sidebar { display: flex; flex-direction: column; gap: 16px; }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 1.25rem; color: #fff; }
    .sub { color: var(--muted); font-size: .92rem; line-height: 1.45; }
    .control-block { margin-top: 8px; display: grid; gap: 10px; }
    label { font-size: .85rem; color: var(--muted); display: flex; justify-content: space-between; gap: 12px; }
    input[type=range] { width: 100%; accent-color: var(--accent); }
    .play-row { display: flex; gap: 10px; align-items: center; }
    button, select {
      background: var(--panel-2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      cursor: pointer;
    }
    button:hover, select:hover { border-color: #4c5561; }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
    .card {
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      min-height: 96px;
    }
    .card .k { font-size: .74rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
    .card .v { font-size: 1.45rem; font-weight: 700; margin-top: 8px; }
    .small { font-size: .82rem; color: var(--muted); margin-top: 6px; }
    .main { display: flex; flex-direction: column; gap: 14px; }
    .chart-grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
    .chart-panel { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 10px; }
    .chart-title { padding: 8px 8px 0 8px; color: #fff; font-size: .98rem; }
    #snapshotChart, #heatmapChart { width: 100%; height: 360px; }
    .legend-note { font-size: .8rem; color: var(--muted); padding: 0 8px 8px 8px; }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: .75rem; border: 1px solid var(--border); background: var(--panel-2); }
    .pos { color: var(--green); }
    .neg { color: var(--red); }
    .warn { color: var(--amber); }
    .meta-list { display: grid; gap: 8px; font-size: .9rem; color: var(--text); }
    .meta-item { display: flex; justify-content: space-between; gap: 12px; }
    .meta-item span:last-child { color: var(--muted); text-align: right; }
    @media (max-width: 1100px) {
      .app { grid-template-columns: 1fr; }
      .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 680px) {
      .cards { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="panel">
        <h1>Timestamp-based Greeks Explorer</h1>
        <p class="sub" style="margin-top:8px;">
          I switched the prototype from hypothetical sliders to a timestamp scrubber because your real dataset is already a one-minute time series with hundreds of snapshots and a full strike ladder. That makes time the strongest storytelling axis.
        </p>
      </div>

      <div class="panel">
        <h2 style="font-size:1rem; margin-bottom:12px;">Playback</h2>
        <div class="control-block">
          <label>
            <span>Snapshot</span>
            <strong id="timeLabel">--</strong>
          </label>
          <input id="timeSlider" type="range" min="0" max="0" value="0" step="1" />
          <div class="play-row">
            <button id="playBtn">Play</button>
            <select id="speedSelect">
              <option value="120">1x</option>
              <option value="60">2x</option>
              <option value="30">4x</option>
            </select>
            <span class="pill" id="snapshotIndex">0 / 0</span>
          </div>
        </div>
      </div>

      <div class="panel">
        <h2 style="font-size:1rem; margin-bottom:12px;">Snapshot metadata</h2>
        <div class="meta-list">
          <div class="meta-item"><span>Current ES</span><span id="metaEs">--</span></div>
          <div class="meta-item"><span>SPX price</span><span id="metaSpx">--</span></div>
          <div class="meta-item"><span>Days to expiry</span><span id="metaDte">--</span></div>
          <div class="meta-item"><span>Records in snapshot</span><span id="metaRows">--</span></div>
          <div class="meta-item"><span>Volume proxy</span><span id="metaVol">--</span></div>
          <div class="meta-item"><span>Avg vanna / vomma</span><span id="metaVV">--</span></div>
        </div>
      </div>

      <div class="panel">
        <h2 style="font-size:1rem; margin-bottom:10px;">How to read it</h2>
        <p class="sub">
          Blue bars show bid-side gamma proxy, red bars show ask-side gamma proxy, and the gold line is the net gamma profile by strike for the selected timestamp. The heatmap below lets you spot where net pressure was persistent through time.
        </p>
      </div>
    </aside>

    <main class="main">
      <section class="cards">
        <div class="card">
          <div class="k">Net gamma proxy</div>
          <div class="v" id="netGammaCard">--</div>
          <div class="small">Signed by quote side and MBO size</div>
        </div>
        <div class="card">
          <div class="k">Net delta proxy</div>
          <div class="v" id="netDeltaCard">--</div>
          <div class="small">Absolute delta weighted by side</div>
        </div>
        <div class="card">
          <div class="k">Dominant pressure</div>
          <div class="v" id="pressureCard">--</div>
          <div class="small" id="pressureSub">--</div>
        </div>
      </section>

      <section class="chart-grid">
        <div class="chart-panel">
          <div class="chart-title">Strike snapshot</div>
          <div class="legend-note">Scrub through time to see how bid/ask gamma concentration moves across strikes.</div>
          <div id="snapshotChart"></div>
        </div>
        <div class="chart-panel">
          <div class="chart-title">Net gamma heatmap through time</div>
          <div class="legend-note">Rows are timestamps, columns are strikes. Brighter regions show more persistent net pressure.</div>
          <div id="heatmapChart"></div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const fmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
    const slider = document.getElementById('timeSlider');
    const playBtn = document.getElementById('playBtn');
    const speedSelect = document.getElementById('speedSelect');
    let dataset = null;
    let currentIndex = 0;
    let timer = null;

    function setText(id, value, className = '') {
      const el = document.getElementById(id);
      el.textContent = value;
      if (className) el.className = `v ${className}`;
    }

    function metricClass(value) {
      if (value > 0) return 'pos';
      if (value < 0) return 'neg';
      return 'warn';
    }

    function render(index) {
      currentIndex = index;
      const snap = dataset.snapshots[index];
      document.getElementById('timeLabel').textContent = snap.label;
      document.getElementById('snapshotIndex').textContent = `${index + 1} / ${dataset.snapshots.length}`;
      document.getElementById('metaEs').textContent = fmt.format(snap.current_es);
      document.getElementById('metaSpx').textContent = fmt.format(snap.spx_price);
      document.getElementById('metaDte').textContent = fmt.format(snap.days_to_expiry);
      document.getElementById('metaRows').textContent = fmt.format(snap.total_rows);
      document.getElementById('metaVol').textContent = fmt.format(snap.total_volume_proxy);
      document.getElementById('metaVV').textContent = `${fmt.format(snap.avg_vanna)} / ${fmt.format(snap.avg_vomma)}`;

      setText('netGammaCard', fmt.format(snap.net_gamma), metricClass(snap.net_gamma));
      setText('netDeltaCard', fmt.format(snap.net_delta_proxy), metricClass(snap.net_delta_proxy));

      const dominant = Math.abs(snap.total_bid_gamma) >= Math.abs(snap.total_ask_gamma) ? 'Bid-dominant' : 'Ask-dominant';
      const dominantClass = dominant === 'Bid-dominant' ? 'pos' : 'neg';
      setText('pressureCard', dominant, dominantClass);
      document.getElementById('pressureSub').textContent = `Bid ${fmt.format(snap.total_bid_gamma)} vs Ask ${fmt.format(snap.total_ask_gamma)}`;

      Plotly.react('snapshotChart', [
        {
          x: dataset.strikes,
          y: snap.bid_gamma,
          type: 'bar',
          name: 'Bid gamma proxy',
          marker: { color: 'rgba(46,160,67,0.72)' },
        },
        {
          x: dataset.strikes,
          y: snap.ask_gamma.map(v => -v),
          type: 'bar',
          name: 'Ask gamma proxy',
          marker: { color: 'rgba(248,81,73,0.72)' },
        },
        {
          x: dataset.strikes,
          y: snap.net_gamma_profile,
          type: 'scatter',
          mode: 'lines',
          name: 'Net gamma proxy',
          line: { color: '#d29922', width: 2 },
          yaxis: 'y2'
        }
      ], {
        barmode: 'relative',
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#c9d1d9' },
        margin: { t: 10, l: 50, r: 50, b: 45 },
        xaxis: { title: 'SPX Strike', gridcolor: '#30363d' },
        yaxis: { title: 'Bid / Ask Gamma Proxy', gridcolor: '#30363d' },
        yaxis2: {
          title: 'Net Gamma Proxy',
          overlaying: 'y',
          side: 'right',
          showgrid: false,
          zeroline: false
        },
        legend: { orientation: 'h', y: 1.12 },
        hovermode: 'x unified'
      }, { responsive: true });

      Plotly.react('heatmapChart', [{
        x: dataset.strikes,
        y: dataset.time_labels,
        z: dataset.heatmap_net_gamma,
        type: 'heatmap',
        colorscale: [
          [0, '#7f1d1d'],
          [0.5, '#111827'],
          [1, '#14532d']
        ],
        zmid: 0,
        hovertemplate: 'Time %{y}<br>Strike %{x}<br>Net gamma %{z:.4f}<extra></extra>'
      }, {
        x: [dataset.strikes[0], dataset.strikes[dataset.strikes.length - 1]],
        y: [snap.label, snap.label],
        type: 'scatter',
        mode: 'lines',
        line: { color: '#58a6ff', width: 2 },
        name: 'Selected timestamp',
        hoverinfo: 'skip'
      }], {
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#c9d1d9' },
        margin: { t: 10, l: 80, r: 20, b: 45 },
        xaxis: { title: 'SPX Strike', gridcolor: '#30363d' },
        yaxis: { title: 'Timestamp', automargin: true },
        showlegend: false,
      }, { responsive: true });
    }

    function togglePlay() {
      if (timer) {
        clearInterval(timer);
        timer = null;
        playBtn.textContent = 'Play';
        return;
      }
      playBtn.textContent = 'Pause';
      timer = setInterval(() => {
        const next = (currentIndex + 1) % dataset.snapshots.length;
        slider.value = next;
        render(next);
      }, Number(speedSelect.value));
    }

    slider.addEventListener('input', e => render(Number(e.target.value)));
    playBtn.addEventListener('click', togglePlay);
    speedSelect.addEventListener('change', () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
        playBtn.textContent = 'Play';
        togglePlay();
      }
    });

    fetch('processed_trading_data.json')
      .then(r => r.json())
      .then(data => {
        dataset = data;
        slider.max = dataset.snapshots.length - 1;
        render(0);
      })
      .catch(err => {
        document.body.innerHTML = `<pre style="color:#f85149;white-space:pre-wrap;">Could not load processed_trading_data.json\n\n${err}</pre>`;
      });
  </script>
</body>
</html>'''

with OUT_HTML.open('w') as f:
    f.write(html)

print(f'Wrote {OUT_JSON}')
print(f'Wrote {OUT_HTML}')
print(f'JSON size: {OUT_JSON.stat().st_size / 1024 / 1024:.2f} MB')
