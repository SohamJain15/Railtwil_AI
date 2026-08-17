import React from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Node = { node_id: string; node_type: string; name: string; latitude?: number; longitude?: number };
type Edge = { edge_id: string; from_node: string; to_node: string; length_m: number; track_type: string };
type Train = { train_id: string; train_number?: string; train_type: string; origin: string; destination: string; priority_class: number; status?: string; current_node?: string; delay_seconds?: number; position_m?: number };
type Twin = { simulation_time: number; trains: Record<string, Train>; active_conflicts: any[]; predictions: any[]; recommendations: any[] };
type Scenario = { scenario_id: string; name: string; events: Array<{ event_id:string; target_type:string; target_id:string; delay_seconds:number; reason:string; severity:string }> };
type ValidationRun = { run_id:string; status:string; progress_completed:number; progress_total:number; scenario_ids:string[]; results:Array<{scenario_id:string;seed:number;strategy:string;status:string;metrics:Record<string,number>;safety_status:string;failure?:string}> };
type ValidationSummary = { strategy_runs:number;scenario_count:number;successful:number;failed:number;unsafe_recommendations:number;no_feasible_solution:number;average_delay_reduction_percent:number;average_conflict_reduction_percent:number;average_throughput_change_percent:number;eta_mae:number|null;conflict_f1:number|null };

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [status, setStatus] = React.useState('idle');
  const [twin, setTwin] = React.useState<Twin | null>(null);
  const [trains, setTrains] = React.useState<Train[]>([]);
  const [nodes, setNodes] = React.useState<Node[]>([]);
  const [edges, setEdges] = React.useState<Edge[]>([]);
  const [scenario, setScenario] = React.useState<Scenario | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [speed, setSpeed] = React.useState(1);
  const [events, setEvents] = React.useState<string[]>([]);
  const [mode,setModeState] = React.useState<'DEMO'|'VALIDATION'>('DEMO');
  const [validationId,setValidationId] = React.useState<string|null>(null);
  const [validation,setValidation] = React.useState<ValidationRun|null>(null);
  const [validationSummary,setValidationSummary] = React.useState<ValidationSummary|null>(null);

  const load = React.useCallback(async () => {
    try {
      setError('');
      const responses = await Promise.all([
        fetch(`${API}/api/v1/system/status`), fetch(`${API}/api/v1/trains`),
        fetch(`${API}/api/v1/network`), fetch(`${API}/api/v1/scenarios/active`),
        fetch(`${API}/api/v1/simulation/state`), fetch(`${API}/api/v1/system/mode`),
      ]);
      if (responses.some((response) => !response.ok)) throw new Error('Backend request failed');
      const [system, trainData, network, activeScenario, live, modeData] = await Promise.all(responses.map((response) => response.json()));
      setStatus(system.status); setTrains(trainData.items); setNodes(network.nodes); setEdges(network.edges);
      setScenario(activeScenario); setTwin(live.state); setModeState(modeData.mode);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to connect'); }
  }, []);

  React.useEffect(() => {
    load();
    const socket = new WebSocket(API.replace(/^http/, 'ws') + '/ws/simulation');
    socket.onmessage = (message) => { const data = JSON.parse(message.data); setEvents((current) => [(data.type || data.event_type || 'event'), ...current].slice(0, 6)); load(); };
    return () => socket.close();
  }, [load]);

  React.useEffect(()=>{if(!validationId)return;const poll=async()=>{const response=await fetch(`${API}/api/v1/validation/runs/${validationId}`);if(response.ok){const data=await response.json();setValidation(data);if(data.status==='COMPLETED'){const summary=await fetch(`${API}/api/v1/validation/runs/${validationId}/summary`);if(summary.ok)setValidationSummary(await summary.json())}}};poll();const timer=setInterval(poll,1000);return()=>clearInterval(timer)},[validationId]);

  async function command(action: string) { setBusy(true); try { await fetch(`${API}/api/v1/simulation/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); await load(); } finally { setBusy(false); } }
  async function post(path: string, body: unknown = {}) { setBusy(true); try { await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); await load(); } finally { setBusy(false); } }
  async function triggerScenario() {
    const event = scenario?.events[0];
    if (event) await post('/api/v1/simulation/event', { event_type: 'TRAIN_DELAY', ...event, scenario_id: scenario?.scenario_id });
  }
  async function switchMode(next:'DEMO'|'VALIDATION'){await fetch(`${API}/api/v1/system/mode`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:next})});setModeState(next)}
  async function startValidation(){setBusy(true);try{const response=await fetch(`${API}/api/v1/validation/runs`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const data=await response.json();setValidationId(data.run_id);setValidationSummary(null)}finally{setBusy(false)}}

  const trainRows = twin ? Object.values(twin.trains).slice(0, 10) : trains.slice(0, 10);
  const conflicts = twin?.active_conflicts || [];
  const recommendation = twin?.recommendations?.[0];

  return <main>
    <header><div><p className="eyebrow">RAIL-TWIN / CONTROL CENTRE</p><h1>Vasai Road digital twin</h1><p className="muted">Executable simulation · simulation time {twin ? `${Math.round(twin.simulation_time / 60)} min` : '—'}</p></div><div className="badge">{mode} · SIMULATION DATA</div></header>
    {error && <div className="alert">{error} — start the backend with Docker Compose.</div>}
    <section className="modeBar"><button className={mode==='DEMO'?'selected':''} onClick={()=>switchMode('DEMO')}>Demo mode</button><button className={mode==='VALIDATION'?'selected':''} onClick={()=>switchMode('VALIDATION')}>Validation mode</button><span>Rail-Twin is a decision-support layer. It does not control railway signals or replace railway safety systems.</span></section>
    {mode==='VALIDATION' ? <><ValidationPanel run={validation} summary={validationSummary} runId={validationId} busy={busy} start={startValidation}/>{validationSummary&&<div className="evidenceGrid modelEvidence"><Metric label="ETA MAE" value={validationSummary.eta_mae===null?'Unavailable':`${validationSummary.eta_mae.toFixed(1)}s`}/><Metric label="Conflict F1" value={validationSummary.conflict_f1===null?'Unavailable':validationSummary.conflict_f1.toFixed(3)}/></div>}</> : <>
    <section className="toolbar"><span className={`dot ${status === 'running' ? 'live' : ''}`}></span><span>Simulation {status}</span><label className="scenario">Speed <select value={speed} onChange={(event) => { const next = Number(event.target.value); setSpeed(next); post('/api/v1/simulation/speed', { speed: next }); }}><option value="1">1x</option><option value="5">5x</option><option value="10">10x</option><option value="20">20x</option></select></label><button disabled={busy} onClick={() => command('start')}>Start</button><button disabled={busy} onClick={() => command('pause')}>Pause</button><button disabled={busy} onClick={() => command('resume')}>Resume</button><button disabled={busy} onClick={() => command('reset')}>Reset</button></section>
    <section className="scenarioBar"><div><b>Controlled simulation scenario</b><span>{scenario?.name || 'Loading scenario…'}</span></div><button disabled={busy || !scenario} onClick={triggerScenario}>Trigger disruption</button></section>
    <section className="grid"><article className="card twin"><div className="cardhead"><h2>Digital twin</h2><span className="pill">{nodes.filter((node) => node.node_type === 'platform').length} platforms · live seed</span></div><NetworkMap nodes={nodes} edges={edges} trains={trainRows} /><p className="caption">Tracks, stations, and train state are loaded from the backend seed dataset. SVG provides presentation only.</p></article>
      <article className="card"><div className="cardhead"><h2>Fleet state</h2><span className="pill">{trainRows.length} visible trains</span></div>{trainRows.length ? <div className="table">{trainRows.map((train) => <div className="row" key={train.train_id}><b>{train.train_number || train.train_id}</b><span>{train.status || train.train_type}</span><span>{train.current_node || `${train.origin} → ${train.destination}`}</span><span className="priority">+{Math.round(train.delay_seconds || 0)}s</span></div>)}</div> : <div className="empty">Start a simulation to populate train state.</div>}</article></section>
    <section className="grid three"><Panel title="Predictions" value={twin?.predictions?.length ? `${twin.predictions.length} train predictions` : 'No model output'} action={() => post('/api/v1/predictions/run')} /><Panel title="Conflicts" value={conflicts.length ? `${conflicts.length} detected` : 'No active conflicts'} action={() => post('/api/v1/conflicts/detect')} /><Panel title="Recommendations" value={recommendation ? recommendation.reason : 'No recommendation generated'} action={() => post('/api/v1/optimization/run')} /></section>
    {recommendation && <section className="card recommendation"><div className="cardhead"><h2>Controller decision</h2><span className="pill">{recommendation.safety_status}</span></div><p>{recommendation.reason}</p><button onClick={() => post(`/api/v1/recommendations/${recommendation.recommendation_id}/accept`, { reason: 'Controller accepted computed recommendation' })}>Accept</button><button onClick={() => post(`/api/v1/recommendations/${recommendation.recommendation_id}/reject`, { reason: 'Controller rejected recommendation' })}>Reject</button></section>}
    <section className="card"><div className="cardhead"><h2>Event stream</h2><span className="pill">WebSocket</span></div>{events.length ? <div className="events">{events.map((event, index) => <span key={index}>{event}</span>)}</div> : <div className="empty">Waiting for simulation events.</div>}</section></>}
  </main>;
}

function NetworkMap({ nodes, edges, trains }: { nodes: Node[]; edges: Edge[]; trains: Train[] }) {
  const stations = nodes.filter((node) => node.latitude !== undefined && node.longitude !== undefined);
  if (!stations.length) return <div className="empty">Loading network topology…</div>;
  const lons = stations.map((node) => node.longitude as number), lats = stations.map((node) => node.latitude as number);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons), minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const point = (id: string) => { const node = nodes.find((candidate) => candidate.node_id === id); if (!node?.latitude || node.longitude === undefined) return null; return { x: 35 + ((node.longitude - minLon) / Math.max(maxLon - minLon, .001)) * 830, y: 265 - ((node.latitude - minLat) / Math.max(maxLat - minLat, .001)) * 220 }; };
  return <svg viewBox="0 0 900 300" role="img" aria-label="Seeded railway network schematic">{edges.map((edge) => { const a = point(edge.from_node), b = point(edge.to_node); return a && b ? <line key={edge.edge_id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={edge.track_type === 'freight_loop' ? 'loop' : 'track'} /> : null; })}{stations.map((node) => { const position = point(node.node_id); return position ? <g key={node.node_id}><circle cx={position.x} cy={position.y} r={node.node_id === 'vasai_road' ? 8 : 4} className="node" /><text x={position.x + 7} y={position.y - 7}>{node.name}</text></g> : null; })}{trains.map((train) => { const position = point(train.current_node || train.origin); return position ? <circle key={train.train_id} cx={position.x} cy={position.y + 10} r="5" className={train.delay_seconds ? 'train delayed' : 'train'} /> : null; })}</svg>;
}

function Panel({ title, value, action }: { title: string; value: string; action: () => void }) { return <article className="card panel"><div className="cardhead"><h2>{title}</h2><span className="pill">BACKEND</span></div><p className="muted">{value}</p><button onClick={action}>Run</button></article>; }
function ValidationPanel({run,summary,runId,busy,start}:{run:ValidationRun|null;summary:ValidationSummary|null;runId:string|null;busy:boolean;start:()=>void}){const percent=run?.progress_total?Math.round(run.progress_completed/run.progress_total*100):0;return <section className="validation"><div className="validationHead"><div><p className="eyebrow">CONTROLLED EVIDENCE MODE</p><h2>Validation summary</h2><p className="muted">Seven scenarios · ten deterministic seeds · three intervention strategies</p></div><button disabled={busy||run?.status==='RUNNING'} onClick={start}>Run validation suite</button></div>{run&&<><div className="progress"><span style={{width:`${percent}%`}}></span></div><p className="muted">{run.status} · {run.progress_completed}/{run.progress_total} strategy runs ({percent}%)</p></>}{summary&&<div className="evidenceGrid"><Metric label="Simulation runs" value={summary.strategy_runs}/><Metric label="Scenarios" value={summary.scenario_count}/><Metric label="Delay reduction" value={`${summary.average_delay_reduction_percent.toFixed(1)}%`}/><Metric label="Conflict reduction" value={`${summary.average_conflict_reduction_percent.toFixed(1)}%`}/><Metric label="Throughput change" value={`${summary.average_throughput_change_percent.toFixed(1)}%`}/><Metric label="Failed / unsafe" value={`${summary.failed} / ${summary.unsafe_recommendations}`}/></div>}{run?.results?.length?<div className="resultTable"><div className="resultRow resultHeader"><span>Scenario</span><span>Seed</span><span>Strategy</span><span>Delay</span><span>Conflicts</span><span>Status</span></div>{run.results.slice(-30).map((item,index)=><div className="resultRow" key={`${item.scenario_id}-${item.seed}-${item.strategy}-${index}`}><span>{item.scenario_id}</span><span>{item.seed}</span><span>{item.strategy}</span><span>{item.metrics.total_delay_minutes?.toFixed?.(1)??'—'} min</span><span>{item.metrics.number_of_conflicts??'—'}</span><span>{item.status}{item.safety_status==='UNSAFE'?' · UNSAFE':''}</span></div>)}</div>:<div className="empty">Start validation to generate evidence from actual simulation runs.</div>}{runId&&<div className="exports"><a href={`${API}/api/v1/validation/runs/${runId}/export?format=csv`}>Export CSV</a><a href={`${API}/api/v1/validation/runs/${runId}/export?format=json`}>Export JSON</a><a href={`${API}/api/v1/validation/runs/${runId}/export?format=markdown`}>Export Markdown</a></div>}</section>}
function Metric({label,value}:{label:string;value:string|number}){return <div className="metric"><span>{label}</span><b>{value}</b></div>}
createRoot(document.getElementById('root')!).render(<App />);
