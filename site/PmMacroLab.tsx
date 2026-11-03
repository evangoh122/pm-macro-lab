import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Pause, Play } from 'lucide-react';

// Architecture page for the prediction-market hedging research project
// (repo: pm-macro-lab). Drop into evangoh-frontend as src/pages/PmMacroLab.tsx
// and add: <Route path="/projects/pm-macro-lab" element={<PmMacroLab />} />.
// Colours use the site's theme tokens from index.css, so it restyles with the
// site. Layout follows the Cocoon AI architecture-diagram design (MIT).

type Tone = 'source' | 'ingest' | 'table' | 'compute' | 'front';

const TONES: Record<Tone, { fill: string; stroke: string }> = {
  source: { fill: 'rgba(38, 42, 49, 0.6)', stroke: 'var(--color-secondary)' },
  ingest: { fill: 'rgba(31, 66, 58, 0.55)', stroke: 'var(--color-bullish)' },
  table: { fill: 'rgba(84, 66, 20, 0.55)', stroke: 'var(--color-accent)' },
  compute: { fill: 'rgba(88, 50, 14, 0.5)', stroke: '#E09A4A' },
  front: { fill: 'rgba(26, 44, 72, 0.55)', stroke: '#6F8FB8' },
};

interface NodeDef {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  tone: Tone;
  group: string;
  title: string;
  sub: [string, string];
  desc: string;
}

const NODES: NodeDef[] = [
  { id: 'polygon', x: 30, y: 80, w: 190, h: 76, tone: 'source', group: 'Source', title: 'Polygon / Massive', sub: ['TLT OHLCV, options chains', 'volatility, contract data'], desc: 'Supplies TLT OHLCV bars, historical options prices, volatility and contract metadata. Underlying ETF and options data only; no prediction-market data comes from here.' },
  { id: 'ibkr', x: 30, y: 200, w: 190, h: 76, tone: 'source', group: 'Source', title: 'IBKR ForecastTrader', sub: ['event contracts, YES/NO', 'quotes, settlement terms'], desc: 'The source of prediction-market quotes: contracts, YES/NO quotes and settlement terms. Full pricing history after expiry is not assumed, so quotes are captured going forward. Access is read-only.' },
  { id: 'fred', x: 30, y: 320, w: 190, h: 76, tone: 'source', group: 'Source', title: 'FRED / ALFRED', sub: ['fed funds, rates, vintages', 'FOMC calendar + outcomes'], desc: 'Federal funds rate, interest rates and macro indicators, with ALFRED vintages so each revision is tied to when it became known. FOMC calendars and outcomes verify that events actually happened.' },
  { id: 'mkt', x: 290, y: 80, w: 230, h: 76, tone: 'ingest', group: 'Ingestion', title: 'Market Data Ingestion', sub: ['backfill + scheduled increments', 'retries, rate limits, dedup'], desc: 'Python module for historical backfills and scheduled incremental pulls. Handles authentication, pagination, retries and rate limits, and writes source metadata and ingestion logs.' },
  { id: 'pm', x: 290, y: 200, w: 230, h: 76, tone: 'ingest', group: 'Ingestion', title: 'Prediction Market Ingestion', sub: ['timestamped quote capture', 'prospective, never backfilled'], desc: 'Captures event-contract quotes with timestamps as they happen, because full history may not exist after contracts expire. Observed data stays labelled apart from reconstructed or simulated data.' },
  { id: 'macro', x: 290, y: 320, w: 230, h: 76, tone: 'ingest', group: 'Ingestion', title: 'Macro Data Ingestion', sub: ['vintage-aware series pulls', 'publication dates preserved'], desc: 'Pulls FRED/ALFRED series with vintage dates and records FOMC events. Keeping publication dates means later revisions cannot leak into earlier periods.' },
  { id: 'bronze', x: 604, y: 200, w: 170, h: 76, tone: 'table', group: 'Lakehouse · Bronze', title: 'Bronze', sub: ['raw API responses,', 'timestamps + metadata'], desc: 'Delta tables holding raw API responses exactly as received, with ingestion timestamps and source metadata. Duplicate detection and failure recovery apply here.' },
  { id: 'silver', x: 834, y: 200, w: 170, h: 76, tone: 'table', group: 'Lakehouse · Silver', title: 'Silver', sub: ['normalized prices,', 'quotes, FOMC, macro'], desc: 'Normalized ETF prices, options quotes, prediction-market contracts, FOMC events and macro observations. Market calendars and contract expiry and settlement timestamps are handled here.' },
  { id: 'gold', x: 1064, y: 200, w: 170, h: 76, tone: 'table', group: 'Lakehouse · Gold', title: 'Gold', sub: ['point-in-time data,', 'no look-ahead bias'], desc: 'Research-ready datasets joining ETF returns, option prices, event probabilities and macro features. Every observation keeps the time it became available; signal time is kept separate from execution time.' },
  { id: 'backtest', x: 1064, y: 420, w: 170, h: 76, tone: 'compute', group: 'Research', title: 'Backtesting Engine', sub: ['4 TLT hedge strategies', 'realistic exec costs'], desc: 'Planned: compares unhedged TLT, a protective put or put spread, an IBKR YES contract on a Fed hike, and a combination. Models spreads, premiums, commissions, slippage and liquidity. A quoted probability is never treated as an executable price.' },
  { id: 'risk', x: 834, y: 420, w: 170, h: 76, tone: 'compute', group: 'Research', title: 'Risk Analytics', sub: ['drawdown, VaR, CVaR', 'hedge cost, basis risk'], desc: 'Planned: returns, volatility, Sharpe, maximum drawdown, VaR and CVaR, hedge cost and effectiveness, event payout versus actual ETF move, basis risk and sensitivity to transaction costs.' },
  { id: 'api', x: 604, y: 420, w: 170, h: 76, tone: 'ingest', group: 'Serving', title: 'FastAPI', sub: ['research endpoints', 'read-only access'], desc: 'Serves research results through FastAPI endpoints with source attribution. Market-data access is read-only; live trading and order submission are out of scope.' },
  { id: 'ui', x: 374, y: 420, w: 170, h: 76, tone: 'front', group: 'Serving', title: 'React Dashboard', sub: ['5-section workbench', 'strategies + provenance'], desc: 'Planned workbench with five sections: Research Overview, Strategy Builder, Backtest Comparison, Basis Risk Analysis, and Data Quality and Provenance (observed, simulated or illustrative).' },
];

interface EdgeDef {
  id: string;
  from: string;
  to: string;
  d: string;
  label?: string;
  lx?: number;
  ly?: number;
  anchor?: 'start' | 'middle';
  desc: string;
}

const EDGES: EdgeDef[] = [
  { id: 'e1', from: 'polygon', to: 'mkt', d: 'M220,118 L290,118', label: 'REST', lx: 255, ly: 111, desc: 'Market data requests: TLT bars, options chains and contract metadata.' },
  { id: 'e2', from: 'ibkr', to: 'pm', d: 'M220,238 L290,238', label: 'quotes', lx: 255, ly: 231, desc: 'YES/NO quotes and settlement terms for event contracts, polled with timestamps.' },
  { id: 'e3', from: 'fred', to: 'macro', d: 'M220,358 L290,358', label: 'series', lx: 255, ly: 351, desc: 'Macro series and their vintages, plus FOMC calendar and outcome data.' },
  { id: 'e4', from: 'mkt', to: 'bronze', d: 'M520,118 C562,118 562,238 604,238', desc: 'Raw market-data responses land in Bronze with timestamps and source metadata.' },
  { id: 'e5', from: 'pm', to: 'bronze', d: 'M520,238 L604,238', label: 'append', lx: 562, ly: 231, desc: 'Timestamped quotes are appended to Bronze. Prior quotes are never overwritten.' },
  { id: 'e6', from: 'macro', to: 'bronze', d: 'M520,358 C562,358 562,238 604,238', desc: 'Macro observations and FOMC events land in Bronze with vintage and publication dates.' },
  { id: 'e7', from: 'bronze', to: 'silver', d: 'M774,238 L834,238', label: 'clean', lx: 804, ly: 231, desc: 'Raw records are validated, de-duplicated and normalized into typed tables.' },
  { id: 'e8', from: 'silver', to: 'gold', d: 'M1004,238 L1064,238', label: 'join', lx: 1034, ly: 231, desc: 'Silver tables are joined point in time, so each row uses only data available at that moment.' },
  { id: 'e9', from: 'gold', to: 'backtest', d: 'M1149,276 L1149,420', label: 'features', lx: 1159, ly: 352, anchor: 'start', desc: 'Point-in-time returns, option prices, event probabilities and macro features feed the strategies.' },
  { id: 'e10', from: 'backtest', to: 'risk', d: 'M1064,458 L1004,458', label: 'paths', lx: 1034, ly: 451, desc: 'Portfolio paths for each strategy pass to the risk calculations.' },
  { id: 'e11', from: 'risk', to: 'api', d: 'M834,458 L774,458', label: 'metrics', lx: 804, ly: 451, desc: 'Computed risk and hedge-effectiveness metrics are exposed through the API.' },
  { id: 'e12', from: 'api', to: 'ui', d: 'M604,458 L544,458', label: 'JSON', lx: 574, ly: 451, desc: 'The dashboard reads research results over HTTP as JSON.' },
];

const BY_ID: Record<string, NodeDef> = Object.fromEntries(NODES.map((n) => [n.id, n]));
const LEGEND: [Tone, string][] = [
  ['source', 'Source'],
  ['ingest', 'Ingestion / API'],
  ['table', 'Lakehouse table'],
  ['compute', 'Research compute'],
  ['front', 'Frontend'],
];

const CARDS: [string, string[]][] = [
  ['Data sources', ['Polygon / Massive: TLT bars, options, volatility', 'IBKR ForecastTrader: event-contract quotes', 'FRED / ALFRED: macro series and vintages', 'Federal Reserve: FOMC calendar and outcomes']],
  ['Lakehouse layers', ['Bronze: raw responses with timestamps', 'Silver: normalized prices, quotes, events', 'Gold: point-in-time research datasets', 'Signal time kept apart from execution time']],
  ['Strategies compared', ['Long TLT, unhedged', 'Long TLT + protective put or put spread', 'Long TLT + IBKR YES contract on a Fed hike', 'Long TLT + options and event contracts combined']],
];

export default function PmMacroLab() {
  const navigate = useNavigate();
  const svgRef = useRef<SVGSVGElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    document.title = 'Prediction Market Hedging Platform - Architecture';
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) setPaused(true);
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    if (paused) svg.pauseAnimations();
    else svg.unpauseAnimations();
  }, [paused]);

  const focus = hovered ?? selected;
  const related = useMemo(() => {
    const nodes = new Set<string>();
    const edges = new Set<string>();
    if (!focus) return { nodes, edges };
    if (BY_ID[focus]) {
      nodes.add(focus);
      EDGES.forEach((e) => {
        if (e.from === focus || e.to === focus) {
          edges.add(e.id);
          nodes.add(e.from);
          nodes.add(e.to);
        }
      });
    } else {
      const e = EDGES.find((x) => x.id === focus);
      if (e) {
        edges.add(e.id);
        nodes.add(e.from);
        nodes.add(e.to);
      }
    }
    return { nodes, edges };
  }, [focus]);

  const panel = useMemo(() => {
    if (!focus) {
      return {
        tag: 'Overview',
        title: 'Three providers, one point-in-time lakehouse',
        body: 'Polygon/Massive supplies ETF and options data, IBKR supplies prediction-market quotes, and FRED/ALFRED supplies macro series. Each has its own ingestion module. Everything lands raw in Bronze, is normalized in Silver, and becomes research-ready, point-in-time data in Gold. The backtesting engine compares four TLT hedge strategies, risk analytics measures them, and FastAPI serves the results to the dashboard.',
        links: 'Select a component to see what it receives and sends.',
      };
    }
    const n = BY_ID[focus];
    if (n) {
      const ins = EDGES.filter((e) => e.to === focus).map((e) => BY_ID[e.from].title);
      const outs = EDGES.filter((e) => e.from === focus).map((e) => BY_ID[e.to].title);
      return {
        tag: n.group,
        title: n.title,
        body: n.desc,
        links: `Receives from: ${ins.join(', ') || 'none'}  ·  Sends to: ${outs.join(', ') || 'none'}`,
      };
    }
    const e = EDGES.find((x) => x.id === focus);
    if (!e) return { tag: '', title: '', body: '', links: '' };
    return { tag: 'Data flow', title: `${BY_ID[e.from].title} → ${BY_ID[e.to].title}`, body: e.desc, links: '' };
  }, [focus]);

  const toggle = (key: string) => setSelected((s) => (s === key ? null : key));
  const dim = (on: boolean) => (focus && !on ? 0.2 : 1);

  return (
    <div className="min-h-screen bg-background text-primary font-sans selection:bg-accent/20 selection:text-white flex flex-col">
      <header className="border-b border-border/40 bg-background/72 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-secondary hover:text-primary transition-colors bg-transparent border-0 cursor-pointer font-medium text-sm"
          >
            <ArrowLeft size={16} />
            Back to portfolio
          </button>
          <span className="text-xs font-semibold px-2.5 py-0.5 rounded-md border border-accent/25 bg-accent/8 text-accent-bright">
            Design stage
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-12 md:py-16 flex flex-col gap-10">
        <section>
          <div className="flex items-center gap-3 mb-6">
            <span className="editorial-rule" />
            <span className="editorial-kicker">Prediction Market Hedging</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-semibold tracking-tight leading-[1.02] text-primary m-0 max-w-3xl text-balance">
            Can an event contract hedge a bond position?
          </h1>
          <p className="text-secondary text-base leading-8 font-light mt-6 max-w-3xl text-pretty">
            A research platform that tests whether Interactive Brokers event contracts, such as a
            contract that pays on a Fed hike, hedge a long TLT position better than options. Three
            data providers flow through a Databricks Delta lakehouse and a backtesting engine to a
            research dashboard. Paper research only; the architecture below is a design, not a
            running system.
          </p>
        </section>

        <section className="rounded-2xl border border-border-subtle bg-surface/75 p-4 sm:p-6">
          <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
            <p className="text-xs font-mono text-muted m-0">Hover, focus or tap any component or arrow.</p>
            <button
              type="button"
              onClick={() => setPaused((p) => !p)}
              aria-pressed={paused}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-elevated/90 px-3 py-1.5 text-xs text-secondary hover:text-primary hover:border-muted transition-colors cursor-pointer"
            >
              {paused ? <Play size={12} /> : <Pause size={12} />}
              {paused ? 'Resume' : 'Pause'}
            </button>
          </div>

          <div className="overflow-x-auto">
            <svg
              ref={svgRef}
              viewBox="0 0 1290 580"
              className="block w-full min-w-[960px]"
              role="img"
              aria-label="Architecture diagram. Polygon, IBKR and FRED feed three ingestion modules, which write to Bronze, Silver and Gold Delta tables. Gold feeds the backtesting engine, then risk analytics, FastAPI and the React dashboard."
              onClick={() => setSelected(null)}
            >
              <defs>
                {(Object.keys(TONES) as Tone[]).map((t) => (
                  <marker key={t} id={`pm-ah-${t}`} markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto" markerUnits="userSpaceOnUse">
                    <polygon points="0 0, 10 3.5, 0 7" fill={TONES[t].stroke} />
                  </marker>
                ))}
                <pattern id="pm-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--color-border-subtle)" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="1290" height="580" fill="var(--color-background)" />
              <rect width="1290" height="580" fill="url(#pm-grid)" />

              <g fontSize="8" letterSpacing="0.6" fill="var(--color-muted)">
                <text x="30" y="66">SOURCES</text>
                <text x="290" y="66">INGESTION · PYTHON</text>
                <text x="374" y="410">RESEARCH AND SERVING · PYTHON · FASTAPI · REACT</text>
              </g>

              <rect x="584" y="160" width="670" height="140" rx="12" fill="rgba(241, 215, 122, 0.05)" stroke="var(--color-accent-bright)" strokeWidth="1" strokeDasharray="8,4" />
              <text x="596" y="178" fill="var(--color-accent-bright)" fontSize="10" fontWeight="600">
                Databricks Lakehouse · Delta Lake
              </text>

              <rect x="30" y="420" width="300" height="76" rx="6" fill="transparent" stroke="var(--color-border-subtle)" />
              <text x="44" y="444" fill="var(--color-primary)" fontSize="9" fontWeight="600">Reading the motion</text>
              <text x="44" y="462" fill="var(--color-secondary)" fontSize="8">Moving dots are batches of records.</text>
              <text x="44" y="476" fill="var(--color-secondary)" fontSize="8">Animation shows architecture,</text>
              <text x="44" y="488" fill="var(--color-secondary)" fontSize="8">not live API traffic.</text>

              {EDGES.map((e) => {
                const tone = BY_ID[e.from].tone;
                const c = TONES[tone].stroke;
                const on = related.edges.has(e.id);
                return (
                  <g
                    key={e.id}
                    style={{ opacity: dim(on), transition: 'opacity .15s', cursor: 'pointer' }}
                    onPointerEnter={() => setHovered(e.id)}
                    onPointerLeave={() => setHovered(null)}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      toggle(e.id);
                    }}
                  >
                    <path
                      id={`pm-${e.id}`}
                      d={e.d}
                      fill="none"
                      stroke={c}
                      strokeWidth={on ? 2.6 : 1.5}
                      strokeOpacity={on ? 1 : 0.75}
                      strokeDasharray="5,4"
                      markerEnd={`url(#pm-ah-${tone})`}
                    />
                    <path d={e.d} fill="none" stroke="transparent" strokeWidth="18" />
                    {[0, 1].map((i) => (
                      <circle key={i} r="3" fill={c}>
                        <animateMotion dur="3s" begin={`${-i * 1.5}s`} repeatCount="indefinite">
                          <mpath href={`#pm-${e.id}`} />
                        </animateMotion>
                      </circle>
                    ))}
                    {e.label && (
                      <text x={e.lx} y={e.ly} textAnchor={e.anchor ?? 'middle'} fill="var(--color-secondary)" fontSize="8">
                        {e.label}
                      </text>
                    )}
                  </g>
                );
              })}

              {NODES.map((n) => {
                const t = TONES[n.tone];
                const on = related.nodes.has(n.id);
                return (
                  <g
                    key={n.id}
                    tabIndex={0}
                    role="button"
                    aria-label={`${n.title}. ${n.desc.split('. ')[0]}`}
                    style={{ opacity: dim(on), transition: 'opacity .15s', cursor: 'pointer' }}
                    onPointerEnter={() => setHovered(n.id)}
                    onPointerLeave={() => setHovered(null)}
                    onFocus={() => setHovered(n.id)}
                    onBlur={() => setHovered(null)}
                    onKeyDown={(ev) => {
                      if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault();
                        toggle(n.id);
                      }
                    }}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      toggle(n.id);
                    }}
                  >
                    <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6" fill="var(--color-surface)" />
                    <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6" fill={t.fill} stroke={t.stroke} strokeWidth={on ? 2.2 : 1.5} />
                    <text x={n.x + n.w / 2} y={n.y + 28} textAnchor="middle" fill="var(--color-primary)" fontSize="11" fontWeight="600">
                      {n.title}
                    </text>
                    {n.sub.map((s, i) => (
                      <text key={s} x={n.x + n.w / 2} y={n.y + 47 + i * 14} textAnchor="middle" fill="var(--color-secondary)" fontSize="9">
                        {s}
                      </text>
                    ))}
                  </g>
                );
              })}

              <g transform="translate(30 548)" fontSize="8" fill="var(--color-secondary)">
                <text y="8" fill="var(--color-primary)" fontSize="10" fontWeight="600">Legend</text>
                {LEGEND.map(([tone, label], i) => (
                  <g key={label} transform={`translate(${70 + i * 130} 0)`}>
                    <rect width="16" height="10" rx="2" fill={TONES[tone].fill} stroke={TONES[tone].stroke} />
                    <text x="22" y="8">{label}</text>
                  </g>
                ))}
              </g>
            </svg>
          </div>

          <div className="mt-4 rounded-xl border border-border-subtle bg-surface-elevated/60 p-5 min-h-[150px]" aria-live="polite">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted">{panel.tag}</span>
            <h2 className="text-base font-semibold text-primary mt-1 mb-2">{panel.title}</h2>
            <p className="text-sm text-secondary leading-7 font-light m-0 max-w-[90ch]">{panel.body}</p>
            {panel.links && <p className="text-xs font-mono text-muted mt-3 mb-0">{panel.links}</p>}
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {CARDS.map(([title, items]) => (
            <div key={title} className="rounded-xl border border-border-subtle bg-surface/75 p-5">
              <h3 className="text-sm font-semibold text-primary mt-0 mb-3">{title}</h3>
              <ul className="list-none p-0 m-0 flex flex-col gap-1.5 text-xs text-secondary leading-6">
                {items.map((i) => (
                  <li key={i}>• {i}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <p className="text-xs text-muted text-center leading-6 m-0">
          Research only, read-only data access, no live trading. Layout follows the Cocoon AI
          architecture-diagram design (MIT).
        </p>
      </main>
    </div>
  );
}
