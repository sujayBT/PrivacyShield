import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Minus, RefreshCw, Clock,
  BarChart2, Shield, AlertTriangle, Activity, Calendar,
  ChevronUp, ChevronDown, Database, Layers, Filter
} from 'lucide-react';
import {
  getHistorySummary, getHistoryTimeline,
  getHistoryBySource, getHistoryRecent, getHistoryDailyAvg
} from '../api';

// ── Helpers ───────────────────────────────────────────────────────────────────
const RISK_COLOR = { CRITICAL:'#dc2626', HIGH:'#ef4444', MEDIUM:'#f59e0b', LOW:'#22c55e', SAFE:'#6b7280' };
const RISK_BG    = { CRITICAL:'rgba(220,38,38,0.1)', HIGH:'rgba(239,68,68,0.08)', MEDIUM:'rgba(245,158,11,0.09)', LOW:'rgba(34,197,94,0.09)', SAFE:'rgba(107,114,128,0.08)' };
const rc = r => RISK_COLOR[r] || '#6b7280';
const rb = r => RISK_BG[r]    || 'transparent';

// ── Mini SVG line chart ───────────────────────────────────────────────────────
function Sparkline({ data, color = '#60a5fa', height = 48, width = 160 }) {
  const vals = data.filter(v => v != null);
  if (vals.length < 2) return null;
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const step  = width / (vals.length - 1);
  const points = vals.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 6) - 3;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg width={width} height={height} style={{ overflow:'visible' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="2.5"
        strokeLinejoin="round" strokeLinecap="round"/>
      {/* last point dot */}
      {(() => {
        const last = points.split(' ').pop().split(',');
        return <circle cx={last[0]} cy={last[1]} r="3.5" fill={color}/>;
      })()}
    </svg>
  );
}

// ── Bar chart (horizontal) ────────────────────────────────────────────────────
function HBar({ label, value, max, color, count }) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div style={{ marginBottom:'10px' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:'4px',
        fontSize:'12px', color:'var(--text-secondary)' }}>
        <span style={{ fontWeight:600, color:'var(--text-primary)' }}>{label}</span>
        <span>{value} avg &nbsp;·&nbsp; {count} scan{count!==1?'s':''}</span>
      </div>
      <div style={{ height:'8px', borderRadius:'99px', background:'var(--border)', overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background:color,
          borderRadius:'99px', transition:'width 0.8s ease' }}/>
      </div>
    </div>
  );
}

// ── Timeline scatter/line chart ───────────────────────────────────────────────
function TimelineChart({ points, dailyAvg }) {
  if (!points || points.length === 0)
    return <div style={{ padding:'40px', textAlign:'center', color:'var(--text-secondary)', fontSize:'13px' }}>No scan data in this period.</div>;

  const W = 700, H = 200, PAD = { t:16, r:20, b:36, l:44 };
  const cW = W - PAD.l - PAD.r, cH = H - PAD.t - PAD.b;

  // x axis: date range
  const dates = points.map(p => new Date(p.datetime || p.date));
  const minD = Math.min(...dates.map(d => d.getTime()));
  const maxD = Math.max(...dates.map(d => d.getTime()));
  const rangeD = maxD - minD || 1;

  const xOf = d => PAD.l + ((new Date(d).getTime() - minD) / rangeD) * cW;
  const yOf = s => PAD.t + cH - (Math.min(s, 100) / 100) * cH;

  // Grid lines
  const yLines = [0, 25, 50, 75, 100];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', maxHeight:220 }}>
      {/* Grid */}
      {yLines.map(v => (
        <g key={v}>
          <line x1={PAD.l} y1={yOf(v)} x2={W-PAD.r} y2={yOf(v)}
            stroke="var(--border)" strokeWidth="1" strokeDasharray="4 3"/>
          <text x={PAD.l-6} y={yOf(v)+4} textAnchor="end" fontSize="9"
            fill="var(--text-secondary)">{v}</text>
        </g>
      ))}

      {/* Daily avg line */}
      {dailyAvg && (() => {
        const avgs = dailyAvg.filter(d => d.avg_score != null);
        if (avgs.length < 2) return null;
        const pts = avgs.map(d => {
          const x = PAD.l + ((new Date(d.date).getTime() - minD) / rangeD) * cW;
          const y = yOf(d.avg_score);
          return `${x},${y}`;
        }).join(' ');
        return <polyline points={pts} fill="none" stroke="rgba(251,191,36,0.6)"
          strokeWidth="2" strokeDasharray="5 3" strokeLinejoin="round"/>;
      })()}

      {/* Dots */}
      {points.map((p, i) => (
        <circle key={i} cx={xOf(p.datetime || p.date)} cy={yOf(p.score)}
          r="5" fill={p.risk_color || '#60a5fa'}
          stroke="var(--card-bg)" strokeWidth="1.5" style={{ cursor:'pointer' }}>
          <title>{p.filename} — Score: {p.score} ({p.risk_level}) — {p.date}</title>
        </circle>
      ))}

      {/* X axis labels */}
      {(() => {
        const step = Math.ceil(points.length / 6);
        return points.filter((_, i) => i % step === 0).map((p, i) => (
          <text key={i} x={xOf(p.datetime || p.date)} y={H - 6}
            textAnchor="middle" fontSize="9" fill="var(--text-secondary)">
            {p.date}
          </text>
        ));
      })()}

      {/* Legend */}
      <g>
        <circle cx={PAD.l+8} cy={PAD.t+8} r="4" fill="#dc2626"/>
        <text x={PAD.l+16} y={PAD.t+12} fontSize="9" fill="var(--text-secondary)">CRITICAL</text>
        <circle cx={PAD.l+70} cy={PAD.t+8} r="4" fill="#f59e0b"/>
        <text x={PAD.l+78} y={PAD.t+12} fontSize="9" fill="var(--text-secondary)">MEDIUM</text>
        <circle cx={PAD.l+135} cy={PAD.t+8} r="4" fill="#22c55e"/>
        <text x={PAD.l+143} y={PAD.t+12} fontSize="9" fill="var(--text-secondary)">LOW</text>
        <line x1={PAD.l+190} y1={PAD.t+8} x2={PAD.l+210} y2={PAD.t+8}
          stroke="rgba(251,191,36,0.8)" strokeWidth="2" strokeDasharray="4 2"/>
        <text x={PAD.l+214} y={PAD.t+12} fontSize="9" fill="var(--text-secondary)">Daily Avg</text>
      </g>
    </svg>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color = 'var(--accent)', accent }) {
  return (
    <div style={{ padding:'18px 20px', borderRadius:'12px', border:'1px solid var(--border)',
      background:'var(--card-bg)', display:'flex', gap:'14px', alignItems:'flex-start' }}>
      <div style={{ width:'38px', height:'38px', borderRadius:'10px', flexShrink:0,
        background:`${color}18`, border:`1px solid ${color}33`,
        display:'flex', alignItems:'center', justifyContent:'center' }}>
        <Icon size={17} color={color}/>
      </div>
      <div>
        <div style={{ fontSize:'11px', color:'var(--text-secondary)', fontWeight:600,
          textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:'3px' }}>{label}</div>
        <div style={{ fontSize:'22px', fontWeight:800, color: accent || 'var(--text-primary)',
          lineHeight:1.1 }}>{value}</div>
        {sub && <div style={{ fontSize:'11px', color:'var(--text-secondary)', marginTop:'3px' }}>{sub}</div>}
      </div>
    </div>
  );
}

// ── Recent scans table ────────────────────────────────────────────────────────
function RecentTable({ rows }) {
  const [sort, setSort] = useState({ col:'date', dir:-1 });
  const sorted = [...rows].sort((a, b) => {
    const va = a[sort.col], vb = b[sort.col];
    return typeof va === 'number' ? (va - vb) * sort.dir : String(va).localeCompare(String(vb)) * sort.dir;
  });
  const toggle = col => setSort(s => ({ col, dir: s.col === col ? -s.dir : -1 }));
  const Th = ({ col, label }) => (
    <th onClick={() => toggle(col)} style={{ cursor:'pointer', padding:'10px 12px',
      fontSize:'10px', fontWeight:700, textTransform:'uppercase', letterSpacing:'0.06em',
      color:'var(--text-secondary)', textAlign:'left', userSelect:'none',
      borderBottom:'1px solid var(--border)', whiteSpace:'nowrap' }}>
      {label} {sort.col===col ? (sort.dir>0?'↑':'↓') : ''}
    </th>
  );
  return (
    <div style={{ overflowX:'auto' }}>
      <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'12px' }}>
        <thead>
          <tr style={{ background:'var(--bg)' }}>
            <Th col="scan_id"      label="#"/>
            <Th col="date"         label="Date"/>
            <Th col="filename"     label="File / Source"/>
            <Th col="source_label" label="Scanner"/>
            <Th col="score"        label="Score"/>
            <Th col="risk_level"   label="Risk"/>
            <Th col="finding_count"label="Findings"/>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={r.scan_id} style={{ background: i%2===0?'transparent':'rgba(0,0,0,0.02)',
              borderBottom:'1px solid var(--border)' }}>
              <td style={{ padding:'9px 12px', color:'var(--text-secondary)' }}>#{r.scan_id}</td>
              <td style={{ padding:'9px 12px', color:'var(--text-secondary)', whiteSpace:'nowrap' }}>{r.date}</td>
              <td style={{ padding:'9px 12px', maxWidth:'200px', overflow:'hidden',
                textOverflow:'ellipsis', whiteSpace:'nowrap', color:'var(--text-primary)' }}
                title={r.filename}>{r.filename}</td>
              <td style={{ padding:'9px 12px' }}>
                <span style={{ fontSize:'10px', padding:'2px 8px', borderRadius:'20px',
                  background:`${r.source_color}18`, color:r.source_color,
                  border:`1px solid ${r.source_color}33`, fontWeight:600 }}>
                  {r.source_label}
                </span>
              </td>
              <td style={{ padding:'9px 12px', fontWeight:700, color:r.risk_color }}>{r.score}</td>
              <td style={{ padding:'9px 12px' }}>
                <span style={{ fontSize:'10px', padding:'2px 8px', borderRadius:'20px',
                  background:rb(r.risk_level), color:rc(r.risk_level),
                  border:`1px solid ${rc(r.risk_level)}33`, fontWeight:700 }}>
                  {r.risk_level}
                </span>
              </td>
              <td style={{ padding:'9px 12px', color:'var(--text-secondary)' }}>{r.finding_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ScoreHistoryPage() {
  const [summary,   setSummary]   = useState(null);
  const [timeline,  setTimeline]  = useState(null);
  const [bySource,  setBySource]  = useState(null);
  const [recent,    setRecent]    = useState([]);
  const [dailyAvg,  setDailyAvg]  = useState(null);
  const [days,      setDays]      = useState(30);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');

  const load = useCallback(async (d) => {
    setLoading(true); setError('');
    try {
      const [sum, tl, bs, rc2, da] = await Promise.all([
        getHistorySummary(),
        getHistoryTimeline(d),
        getHistoryBySource(),
        getHistoryRecent(50),
        getHistoryDailyAvg(d),
      ]);
      setSummary(sum);
      setTimeline(tl);
      setBySource(bs);
      setRecent(rc2);
      setDailyAvg(da);
    } catch(e) {
      setError(e?.response?.data?.detail || 'Failed to load history data.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(days); }, [days, load]);

  const trendIcon = summary?.trend === 'worsening'
    ? <TrendingUp size={14} color="#dc2626"/>
    : summary?.trend === 'improving'
    ? <TrendingDown size={14} color="#22c55e"/>
    : <Minus size={14} color="#6b7280"/>;

  const trendColor = { worsening:'#dc2626', improving:'#22c55e', stable:'#6b7280' }[summary?.trend] || '#6b7280';

  const sparkScores = (timeline?.points || []).map(p => p.score);

  return (
    <div style={{ padding:'28px', maxWidth:'1000px', margin:'0 auto',
      fontFamily:'"Inter","Segoe UI",sans-serif', color:'var(--text-primary)' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom:'28px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:'12px', marginBottom:'6px' }}>
          <div style={{ width:'40px', height:'40px', borderRadius:'10px',
            background:'rgba(96,165,250,0.1)', border:'1px solid rgba(96,165,250,0.3)',
            display:'flex', alignItems:'center', justifyContent:'center' }}>
            <Activity size={20} color='#60a5fa'/>
          </div>
          <h1 style={{ margin:0, fontSize:'22px', fontWeight:700 }}>Score History</h1>
        </div>
        <p style={{ margin:0, fontSize:'13px', color:'var(--text-secondary)', lineHeight:'1.5' }}>
          Track your privacy risk score over time across all scanners — Upload, URL, Social, Metadata, Screen Monitor, and Attack Simulation.
        </p>
      </div>

      {/* ── Controls ── */}
      <div style={{ display:'flex', gap:'10px', marginBottom:'24px', alignItems:'center', flexWrap:'wrap' }}>
        <div style={{ fontSize:'11px', fontWeight:700, color:'var(--text-secondary)',
          textTransform:'uppercase', letterSpacing:'0.05em' }}>
          <Filter size={11} style={{ marginRight:4 }}/>Time Range:
        </div>
        {[7, 14, 30, 90].map(d => (
          <button key={d} onClick={() => setDays(d)}
            style={{ padding:'6px 14px', borderRadius:'20px', border:'1px solid var(--border)',
              background: days===d ? '#60a5fa' : 'none',
              color: days===d ? '#fff' : 'var(--text-secondary)',
              cursor:'pointer', fontSize:'12px', fontWeight:600,
              transition:'all .2s' }}>
            {d}d
          </button>
        ))}
        <button onClick={() => load(days)}
          style={{ marginLeft:'auto', padding:'6px 14px', borderRadius:'20px',
            border:'1px solid var(--border)', background:'none',
            color:'var(--text-secondary)', cursor:'pointer',
            display:'flex', alignItems:'center', gap:'5px', fontSize:'12px' }}>
          <RefreshCw size={12} style={{ animation:loading?'spin 1s linear infinite':'none' }}/> Refresh
        </button>
      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg);}}`}</style>

      {/* ── Error ── */}
      {error && (
        <div style={{ padding:'12px 16px', borderRadius:'10px', marginBottom:'20px',
          background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.25)',
          color:'#ef4444', display:'flex', gap:'8px', alignItems:'center', fontSize:'13px' }}>
          <AlertTriangle size={14}/> {error}
        </div>
      )}

      {loading && !summary && (
        <div style={{ padding:'60px', textAlign:'center', color:'var(--text-secondary)', fontSize:'13px' }}>
          <div style={{ width:28,height:28,border:'2px solid var(--border)',borderTopColor:'#60a5fa',
            borderRadius:'50%',animation:'spin 1s linear infinite',margin:'0 auto 12px'}}/>
          Loading history…
        </div>
      )}

      {summary && (
        <>
          {/* ── Summary Stat Cards ── */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(190px,1fr))',
            gap:'14px', marginBottom:'24px' }}>
            <StatCard icon={BarChart2}  label="Avg Score"     value={summary.avg_score}
              color='#60a5fa' accent={rc(summary.most_common_risk)}
              sub={`${summary.total_scans} total scans`}/>
            <StatCard icon={TrendingUp} label="Peak Score"    value={summary.max_score}
              color='#dc2626' accent='#dc2626' sub="Highest risk recorded"/>
            <StatCard icon={Shield}     label="Best Score"    value={summary.min_score}
              color='#22c55e' accent='#22c55e' sub="Lowest risk recorded"/>
            <StatCard icon={Database}   label="Findings"      value={summary.total_findings.toLocaleString()}
              color='#f59e0b' sub={`Across all ${summary.total_scans} scans`}/>
            <div style={{ padding:'18px 20px', borderRadius:'12px', border:'1px solid var(--border)',
              background:'var(--card-bg)', display:'flex', gap:'14px', alignItems:'flex-start' }}>
              <div style={{ width:'38px', height:'38px', borderRadius:'10px', flexShrink:0,
                background:`${trendColor}18`, border:`1px solid ${trendColor}33`,
                display:'flex', alignItems:'center', justifyContent:'center' }}>
                {trendIcon}
              </div>
              <div>
                <div style={{ fontSize:'11px', color:'var(--text-secondary)', fontWeight:600,
                  textTransform:'uppercase', letterSpacing:'0.05em', marginBottom:'3px' }}>Trend</div>
                <div style={{ fontSize:'16px', fontWeight:800, color:trendColor, textTransform:'capitalize', lineHeight:1.1 }}>
                  {summary.trend} {summary.trend_value > 0 ? '+' : ''}{summary.trend_value}
                </div>
                <div style={{ fontSize:'11px', color:'var(--text-secondary)', marginTop:'3px' }}>
                  vs earlier period
                </div>
              </div>
            </div>
          </div>

          {/* ── Sparkline preview ── */}
          {sparkScores.length >= 2 && (
            <div style={{ padding:'14px 20px', borderRadius:'12px', border:'1px solid var(--border)',
              background:'var(--card-bg)', marginBottom:'20px',
              display:'flex', alignItems:'center', gap:'20px' }}>
              <div style={{ fontSize:'12px', color:'var(--text-secondary)', flexShrink:0 }}>
                Score trend ({days}d)
              </div>
              <Sparkline data={sparkScores} color='#60a5fa' width={Math.min(sparkScores.length*18, 400)} height={44}/>
              <div style={{ marginLeft:'auto', fontSize:'11px', color:'var(--text-secondary)' }}>
                Most common risk: <strong style={{ color:rc(summary.most_common_risk) }}>
                  {summary.most_common_risk}
                </strong>
              </div>
            </div>
          )}

          {/* ── Timeline Chart ── */}
          <div style={{ padding:'20px', borderRadius:'12px', border:'1px solid var(--border)',
            background:'var(--card-bg)', marginBottom:'20px' }}>
            <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'16px' }}>
              <Activity size={14} color='#60a5fa'/>
              <span style={{ fontWeight:700, fontSize:'14px' }}>Score Timeline — Last {days} Days</span>
              <span style={{ fontSize:'11px', color:'var(--text-secondary)', marginLeft:'auto' }}>
                {timeline?.total || 0} scans shown
              </span>
            </div>
            <TimelineChart points={timeline?.points || []} dailyAvg={dailyAvg?.daily || []}/>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'20px', marginBottom:'20px' }}>

            {/* Risk Distribution */}
            <div style={{ padding:'20px', borderRadius:'12px', border:'1px solid var(--border)',
              background:'var(--card-bg)' }}>
              <div style={{ fontWeight:700, fontSize:'14px', marginBottom:'16px',
                display:'flex', alignItems:'center', gap:'8px' }}>
                <Layers size={14} color='#a855f7'/> Risk Distribution
              </div>
              {Object.entries(summary.risk_distribution)
                .sort((a,b) => (RISK_COLOR[b[0]]?.length||0) - (RISK_COLOR[a[0]]?.length||0))
                .map(([risk, count]) => (
                <div key={risk} style={{ display:'flex', alignItems:'center', gap:'10px', marginBottom:'10px' }}>
                  <span style={{ fontSize:'11px', padding:'2px 8px', borderRadius:'20px', fontWeight:700,
                    background:rb(risk), color:rc(risk), border:`1px solid ${rc(risk)}33`,
                    minWidth:'70px', textAlign:'center' }}>{risk}</span>
                  <div style={{ flex:1, height:'8px', borderRadius:'99px',
                    background:'var(--border)', overflow:'hidden' }}>
                    <div style={{ height:'100%', borderRadius:'99px', background:rc(risk),
                      width:`${(count/summary.total_scans)*100}%`, transition:'width 0.8s ease' }}/>
                  </div>
                  <span style={{ fontSize:'12px', color:'var(--text-secondary)',
                    minWidth:'24px', textAlign:'right' }}>{count}</span>
                </div>
              ))}
            </div>

            {/* By Source */}
            <div style={{ padding:'20px', borderRadius:'12px', border:'1px solid var(--border)',
              background:'var(--card-bg)' }}>
              <div style={{ fontWeight:700, fontSize:'14px', marginBottom:'16px',
                display:'flex', alignItems:'center', gap:'8px' }}>
                <BarChart2 size={14} color='#f59e0b'/> Avg Score by Scanner
              </div>
              {(bySource?.sources || []).map(s => (
                <HBar key={s.source} label={s.label} value={s.avg_score}
                  max={100} color={s.color} count={s.count}/>
              ))}
              {(!bySource?.sources?.length) && (
                <div style={{ fontSize:'12px', color:'var(--text-secondary)' }}>No data yet.</div>
              )}
            </div>
          </div>

          {/* ── Recent Scans Table ── */}
          {recent.length > 0 && (
            <div style={{ borderRadius:'12px', border:'1px solid var(--border)',
              background:'var(--card-bg)', overflow:'hidden', marginBottom:'20px' }}>
              <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)',
                fontWeight:700, fontSize:'14px', display:'flex', alignItems:'center', gap:'8px' }}>
                <Clock size={14} color='#06b6d4'/> Recent Scan History
                <span style={{ marginLeft:'auto', fontSize:'11px', color:'var(--text-secondary)',
                  fontWeight:400 }}>Click column headers to sort</span>
              </div>
              <RecentTable rows={recent}/>
            </div>
          )}

          {/* Connected workflow notice */}
          <div style={{ padding:'14px 18px', borderRadius:'10px',
            background:'rgba(96,165,250,0.06)', border:'1px solid rgba(96,165,250,0.2)',
            display:'flex', gap:'10px', alignItems:'flex-start', fontSize:'12px',
            color:'var(--text-secondary)', lineHeight:'1.6' }}>
            <Activity size={14} color='#60a5fa' style={{ flexShrink:0, marginTop:'1px' }}/>
            <span>
              <strong style={{ color:'var(--text-primary)' }}>Connected Workflow:</strong> Every scan across&nbsp;
              <strong>Upload &amp; Scan</strong>, <strong>URL Scanner</strong>, <strong>Social Scanner</strong>,&nbsp;
              <strong>Metadata Scanner</strong>, <strong>Screen Monitor</strong>, and <strong>Cloud Scanner</strong>&nbsp;
              automatically appears here. Use <strong>Attack Simulation</strong> to understand what the scores mean in real-world threat terms.
            </span>
          </div>
        </>
      )}
    </div>
  );
}
