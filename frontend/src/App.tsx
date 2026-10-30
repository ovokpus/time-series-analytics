import { useCallback, useEffect, useMemo, useState } from 'react'

type Health = { influxdb: boolean; air_quality_data: string | null; weather_source: string; weather_city: string
  last_weather: { fields: { temp_c: number; wind_kph: number }; time: string; source: string } | null
  last_weather_error: string | null; grafana_url: string }
type Pt = { t: string; v: number }
type Anom = { t: string; value: number; baseline: number; z: number }
type WPt = { t: string; temp_c: number; wind_kph: number; source: string }

const j = (u: string, init?: RequestInit) => fetch(u, init).then(async r => { const b = await r.json(); if (!r.ok) throw new Error(b.detail ?? r.statusText); return b })

function Chart({ points, anomalies, unit }: { points: Pt[]; anomalies: Anom[]; unit: string }) {
  const W = 900, H = 260, P = 36
  const g = useMemo(() => {
    if (!points.length) return null
    const xs = points.map(p => +new Date(p.t)), ys = points.map(p => p.v)
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(...ys, ...anomalies.map(a => a.value)) * 1.05
    const X = (t: number) => P + (t - x0) / (x1 - x0 || 1) * (W - 2 * P), Y = (v: number) => H - P - (v - y0) / (y1 - y0 || 1) * (H - 2 * P)
    return { X, Y, y0, y1, x0, x1, d: points.map((p, i) => `${i ? 'L' : 'M'}${X(+new Date(p.t)).toFixed(1)},${Y(p.v).toFixed(1)}`).join('') }
  }, [points, anomalies])
  if (!g) return <div className="empty">No data in range.</div>
  const ticks = [0, .25, .5, .75, 1].map(f => g.y0 + f * (g.y1 - g.y0))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart">
      {ticks.map(v => <g key={v}><line x1={P} x2={W - P} y1={g.Y(v)} y2={g.Y(v)} className="grid" /><text x={4} y={g.Y(v) + 4}>{v.toFixed(0)}</text></g>)}
      <text x={W - P} y={H - 8} textAnchor="end">{new Date(g.x1).toLocaleDateString()}</text>
      <text x={P} y={H - 8}>{new Date(g.x0).toLocaleDateString()}</text>
      <text x={P} y={14}>{unit}</text>
      <path d={g.d} className="line" />
      {anomalies.map(a => <circle key={a.t} cx={g.X(+new Date(a.t))} cy={g.Y(a.value)} r={5} className="anom"><title>{`${a.t}: ${a.value} (z=${a.z})`}</title></circle>)}
    </svg>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [stations, setStations] = useState<string[]>([])
  const [fields, setFields] = useState<string[]>([])
  const [station, setStation] = useState('')
  const [field, setField] = useState('PM2.5')
  const [range, setRange] = useState('-30d')
  const [threshold, setThreshold] = useState(3)
  const [points, setPoints] = useState<Pt[]>([])
  const [anoms, setAnoms] = useState<{ anomalies: Anom[]; points_scanned: number } | null>(null)
  const [summary, setSummary] = useState<Record<string, { mean: number; max: number; count: number }>>({})
  const [weather, setWeather] = useState<WPt[]>([])
  const [werr, setWerr] = useState('')

  const loadHealth = useCallback(() => j('/health').then(setHealth), [])
  const loadWeather = useCallback(() => j('/api/weather?start=-24h').then(r => setWeather(r.points)), [])
  useEffect(() => { loadHealth(); loadWeather(); j('/api/stations').then(r => { setStations(r.stations); setFields(r.fields); setStation(r.stations[0] ?? '') }) }, [loadHealth, loadWeather])
  useEffect(() => {
    if (!station) return
    const q = `station=${station}&field=${encodeURIComponent(field)}&start=${range}`
    j(`/api/series?${q}&every=1h`).then(r => setPoints(r.points))
    j(`/api/anomalies?${q}&threshold=${threshold}`).then(setAnoms)
    j(`/api/summary?field=${encodeURIComponent(field)}&start=${range}`).then(r => setSummary(r.stations))
  }, [station, field, range, threshold])

  const collect = () => { setWerr(''); j('/api/weather/collect', { method: 'POST' }).then(() => { loadWeather(); loadHealth() }).catch(e => setWerr(String(e.message))) }
  const synthetic = health?.air_quality_data === 'synthetic'
  const latest = weather[weather.length - 1]
  const unit = field.startsWith('PM') ? 'µg/m³' : field === 'TEMP' || field === 'DEWP' ? '°C' : field === 'WSPM' ? 'm/s' : field

  return (
    <div className="page">
      <header>
        <div><h1>📈 Time-Series Analytics</h1><div className="hint">InfluxDB 2 · Flux · FastAPI · Grafana</div></div>
        <div className="badges">
          <span className={`badge ${health?.influxdb ? 'ok' : 'bad'}`}>InfluxDB {health?.influxdb ? 'up' : 'down'}</span>
          {health?.air_quality_data && <span className={`badge ${synthetic ? 'warn' : 'ok'}`}>Air quality: {synthetic ? 'SYNTHETIC data' : 'real UCI PRSA'}</span>}
          {health && <span className="badge ok">Weather: {health.weather_source}</span>}
          {health && <><a className="badge link" href={`${health.grafana_url}/d/air-quality`} target="_blank">Grafana: air quality ↗</a>
            <a className="badge link" href={`${health.grafana_url}/d/live-weather`} target="_blank">Grafana: live weather ↗</a></>}
        </div>
      </header>
      {synthetic && <div className="banner">The air-quality series are <b>synthetic</b> (generated in the UCI Beijing PRSA schema, with injected pollution spikes), because the real CSVs aren't in the repo. Put them in <code>data/PRSA_Data_20130301-20170228/</code> and re-seed to use real data.</div>}

      <section className="card">
        <div className="controls">
          <label>Station <select value={station} onChange={e => setStation(e.target.value)}>{stations.map(s => <option key={s}>{s}</option>)}</select></label>
          <label>Field <select value={field} onChange={e => setField(e.target.value)}>{fields.map(f => <option key={f}>{f}</option>)}</select></label>
          <label>Range <select value={range} onChange={e => setRange(e.target.value)}>{['-24h', '-7d', '-30d'].map(r => <option key={r}>{r}</option>)}</select></label>
          <label>Anomaly |z| ≥ <input type="number" min={1} max={10} step={0.5} value={threshold} onChange={e => setThreshold(+e.target.value)} /></label>
        </div>
        <h3>{station} · {field} (hourly mean) <span className="hint">red dots = rolling 24h z-score anomalies</span></h3>
        <Chart points={points} anomalies={anoms?.anomalies ?? []} unit={unit} />
      </section>

      <div className="cols">
        <section className="card">
          <h3>Anomalies <span className="hint">{anoms ? `${anoms.anomalies.length} of ${anoms.points_scanned} hourly points` : ''}</span></h3>
          <table><thead><tr><th>Time (UTC)</th><th>Value</th><th>24h baseline</th><th>z</th></tr></thead>
            <tbody>{anoms?.anomalies.slice(-12).reverse().map(a => <tr key={a.t}><td>{a.t.slice(0, 16).replace('T', ' ')}</td><td>{a.value}</td><td>{a.baseline}</td><td className={a.z > 0 ? 'up' : 'down'}>{a.z}</td></tr>)}</tbody></table>
        </section>
        <section className="card">
          <h3>Stations · {field} over {range}</h3>
          <table><thead><tr><th>Station</th><th>Mean</th><th>Max</th><th>Points</th></tr></thead>
            <tbody>{Object.entries(summary).map(([s, v]) => <tr key={s} className={s === station ? 'sel' : ''}><td>{s}</td><td>{v.mean}</td><td>{v.max}</td><td>{v.count}</td></tr>)}</tbody></table>
        </section>
        <section className="card">
          <h3>Live weather · {health?.weather_city}</h3>
          {latest ? <div className="big"><span>{latest.temp_c?.toFixed(1)} °C</span><span>{latest.wind_kph?.toFixed(1)} km/h</span></div> : <div className="empty">No observations yet.</div>}
          <div className="hint">{weather.length} real observation(s) in the last 24h{latest ? `, latest ${new Date(latest.t).toLocaleString()} from ${latest.source}` : ''}. Polled every few minutes.</div>
          <button onClick={collect}>Collect now</button>
          {(werr || health?.last_weather_error) && <div className="err">{werr || health?.last_weather_error}</div>}
        </section>
      </div>
    </div>
  )
}
