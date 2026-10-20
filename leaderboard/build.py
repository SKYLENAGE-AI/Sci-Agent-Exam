#!/usr/bin/env python3
"""Build the Sci-Agent-Exam leaderboard webpage from data/leaderboard.json.

Usage:
    python3 build.py                 # writes ./index.html
    python3 build.py out.html        # writes ./out.html

The page is a single self-contained HTML file (no external assets, no network,
no build step beyond this script). All numbers, model metadata, field / task-type
metadata, cost data, and copy are read from data/leaderboard.json, so updating the
board is a matter of editing that one JSON file and re-running this script.

The page has four views, switched by a top nav and deep-linkable via ?view=:
    leaderboard  sortable ranking table (Prog / LLM / Combined / Pass@0.95 +
                 per-run Out-tok / Cost / Turns efficiency columns)
    matrix       models x categories heatmap
    pareto       quality vs cost / tokens / time scatter with a Pareto frontier
    domains      multi-model radar (spider) chart across categories
All charts are hand-drawn inline SVG / CSS grid; there are zero JS dependencies.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "leaderboard.json"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "index.html"

d = json.loads(DATA.read_text(encoding="utf-8"))
meta = d["meta"]

# The data object injected verbatim into the page. json.dumps keeps it valid JS.
DATA_JS = json.dumps(
    {"models": d["models"], "fields": d["fields"],
     "task_types": d["task_types"], "scores": d["scores"]},
    ensure_ascii=False, separators=(",", ":"))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sci-Agent-Exam · Leaderboard</title>
<style>
  :root{
    --bg:#070a0f; --panel:#0d131c; --panel-2:#111a26; --line:#1d2a3a;
    --txt:#e8eef6; --muted:#7d8ea4;
    --accent:#f08a5d; --accent-2:#38e8c6; --accent-3:#6ea8ff;
    --prog:#6ea8ff; --judge:#c98bff; --comb:#f0b45d; --pass:#4ee39b;
    --gold:#ffcf5c; --silver:#cfe0f0; --bronze:#e0975a;
    --grid: 44px minmax(0,1fr) 58px 48px 48px 54px 58px 58px 54px 50px;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:
      radial-gradient(1200px 600px at 80% -10%, rgba(56,232,198,.08), transparent 60%),
      radial-gradient(1000px 500px at 10% 0%, rgba(240,138,93,.10), transparent 55%),
      var(--bg);
    color:var(--txt);
    font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    min-height:100vh;-webkit-font-smoothing:antialiased;
  }
  body::before{
    content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
    background-image:
      linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),
      linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
    background-size:38px 38px;
    mask-image:radial-gradient(circle at 50% 20%, #000 0%, transparent 80%);
  }
  .wrap{position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:40px 22px 80px}

  header{text-align:center;margin-bottom:22px}
  .kicker{font-size:12px;letter-spacing:.42em;text-transform:uppercase;color:var(--accent-2);opacity:.85;margin-bottom:14px}
  .kicker .blink{animation:blink 1.1s steps(2,start) infinite}
  @keyframes blink{to{opacity:0}}
  h1{margin:0;font-size:clamp(30px,6vw,58px);line-height:1.02;font-weight:800;letter-spacing:-.02em;
     background:linear-gradient(100deg,#fff 10%,var(--accent) 45%,var(--accent-2) 90%);
     -webkit-background-clip:text;background-clip:text;color:transparent;text-shadow:0 0 40px rgba(240,138,93,.18)}
  .sub{margin:14px auto 0;max-width:660px;color:var(--muted);font-size:14px;line-height:1.6}
  .stats{display:flex;gap:26px;justify-content:center;margin-top:22px;flex-wrap:wrap}
  .stat b{display:block;font-size:22px;color:var(--txt)}
  .stat span{font-size:11px;color:var(--muted);letter-spacing:.12em;text-transform:uppercase}

  /* view switcher */
  .nav{display:flex;gap:7px;justify-content:center;margin:26px 0 24px;flex-wrap:wrap}
  .navbtn{padding:9px 17px;border:1px solid var(--line);border-radius:10px;background:var(--panel);
    color:var(--muted);font-family:inherit;font-size:13px;letter-spacing:.03em;cursor:pointer;transition:.18s}
  .navbtn:hover{color:var(--txt);border-color:var(--accent-2);transform:translateY(-1px)}
  .navbtn.on{color:#071016;font-weight:700;border-color:transparent;
    background:linear-gradient(100deg,var(--accent),var(--accent-2));box-shadow:0 6px 22px rgba(56,232,198,.22)}
  .view{display:none}
  .view.on{display:block;animation:fade .35s ease}
  @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

  .filters{margin:6px 0 10px}
  .flabel{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--muted);margin:0 0 10px 2px}
  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
  .chip{display:inline-flex;align-items:center;gap:7px;padding:8px 13px;border:1px solid var(--line);
    border-radius:999px;background:var(--panel);color:var(--muted);font-size:13px;cursor:pointer;
    transition:.18s ease;white-space:nowrap;user-select:none;font-family:inherit}
  .chip .ic{font-size:14px;filter:grayscale(.3)}
  .chip:hover{border-color:var(--accent-2);color:var(--txt);transform:translateY(-1px)}
  .chip.active{color:#071016;font-weight:700;border-color:transparent;
    background:linear-gradient(100deg,var(--accent),var(--accent-2));box-shadow:0 6px 22px rgba(56,232,198,.22)}
  .chip.active .ic{filter:none}
  .chip.hero.active{background:linear-gradient(100deg,var(--gold),var(--accent))}

  .board{margin-top:6px;border:1px solid var(--line);border-radius:16px;overflow:hidden;
    background:linear-gradient(180deg,var(--panel),#0a0f16);box-shadow:0 20px 60px rgba(0,0,0,.45)}
  .board-head{display:flex;align-items:center;justify-content:space-between;gap:12px;
    padding:15px 18px;border-bottom:1px solid var(--line);background:var(--panel-2)}
  .board-head .title{display:flex;align-items:center;gap:10px;font-size:15px;font-weight:700}
  .board-head .title .dot{width:9px;height:9px;border-radius:50%;background:var(--accent-2);box-shadow:0 0 10px var(--accent-2)}
  .board-head .meta{font-size:12px;color:var(--muted)}
  .board-head .meta b{color:var(--accent-2)}

  /* sortable header row */
  .hrow{display:grid;grid-template-columns:var(--grid);gap:12px;align-items:end;
    padding:12px 32px 10px 32px;border-bottom:1px dashed var(--line);
    font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
  .hrow .hlbl{grid-column:2}
  .sortbtn{justify-self:end;text-align:right;cursor:pointer;background:none;border:none;
    color:var(--muted);font-family:inherit;font-size:11px;letter-spacing:.06em;text-transform:uppercase;
    padding:4px 2px;border-radius:6px;transition:.15s;white-space:nowrap}
  .sortbtn:hover{color:var(--txt)}
  .sortbtn .arw{opacity:.35;margin-left:3px}
  .sortbtn.on{color:var(--txt);font-weight:700}
  .sortbtn.on.c{color:var(--comb)} .sortbtn.on.p{color:var(--prog)} .sortbtn.on.j{color:var(--judge)} .sortbtn.on.r{color:var(--pass)}
  .sortbtn.on.eff{color:var(--accent)}
  .sortbtn.on .arw{opacity:1}
  .colhint{grid-column:3;justify-self:end;align-self:end;font-size:10px;opacity:.5}

  .rows{position:relative;padding:8px 18px 14px}
  .row{display:grid;grid-template-columns:var(--grid);gap:12px;align-items:center;
    padding:13px 14px;border-radius:11px;transition:background .18s ease}
  .row:hover{background:rgba(255,255,255,.025)}
  .rank{font-size:17px;font-weight:800;color:var(--muted);text-align:center}
  .row.top1 .rank,.row.top2 .rank,.row.top3 .rank{font-size:20px}
  .row.top1{background:linear-gradient(90deg,rgba(255,207,92,.10),transparent 55%)}
  .row.top1 .rank{color:var(--gold);text-shadow:0 0 16px rgba(255,207,92,.5)}
  .row.top2 .rank{color:var(--silver)}
  .row.top3 .rank{color:var(--bronze)}

  .model{display:flex;align-items:center;gap:11px;min-width:0}
  .pdot{width:11px;height:11px;border-radius:50%;flex:0 0 auto;box-shadow:0 0 10px currentColor}
  .mname{font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .prov{font-size:11px;color:var(--muted)}

  .barwrap{height:9px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden}
  .bar{height:100%;width:0;border-radius:999px;transition:width .7s cubic-bezier(.22,1,.36,1)}
  .bar.c{background:linear-gradient(90deg,var(--accent),var(--comb))}
  .bar.p{background:linear-gradient(90deg,var(--accent-3),var(--accent-2))}
  .bar.j{background:linear-gradient(90deg,#8b6cff,var(--judge))}
  .bar.r{background:linear-gradient(90deg,#1cbf9c,var(--pass))}
  .bar.eff{background:linear-gradient(90deg,#4b5a6e,#9fb3c9)}

  .val{font-size:15px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums;color:var(--muted);transition:.2s}
  .val.active{font-size:18px;font-weight:800;color:var(--txt)}
  .val.c.active{color:var(--comb)} .val.p.active{color:var(--prog)} .val.j.active{color:var(--judge)} .val.r.active{color:var(--pass)}
  .val.r{color:var(--pass);opacity:.55} .val.r.active{opacity:1}
  .val.eff{font-size:13px;opacity:.8} .val.eff.active{color:var(--accent);opacity:1}

  /* shared chart scaffolding (matrix / pareto / domains) */
  .panel-card{border:1px solid var(--line);border-radius:16px;
    background:linear-gradient(180deg,var(--panel),#0a0f16);box-shadow:0 20px 60px rgba(0,0,0,.45);padding:20px 18px}
  .ctrls{display:flex;gap:22px;flex-wrap:wrap;align-items:center;margin:0 2px 18px}
  .ctrl{display:flex;align-items:center;gap:9px}
  .ctrl .lab{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted)}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:var(--panel)}
  .seg button{padding:6px 11px;background:none;border:none;border-right:1px solid var(--line);color:var(--muted);
    font-family:inherit;font-size:12px;cursor:pointer;transition:.15s;white-space:nowrap}
  .seg button:last-child{border-right:none}
  .seg button:hover{color:var(--txt)}
  .seg button.on{color:#071016;font-weight:700;background:linear-gradient(100deg,var(--accent),var(--accent-2))}
  .cap{font-size:12px;color:var(--muted);margin:14px 4px 0;line-height:1.65}
  .cap b{color:var(--accent-2)}

  /* matrix */
  .mx{overflow-x:auto;margin:0 -4px}
  .mxgrid{display:grid;gap:3px;min-width:560px;padding:0 4px}
  .mxh{font-size:14px;text-align:center;padding:5px 2px;white-space:nowrap}
  .mxh.lbl{font-size:10px;color:var(--muted);letter-spacing:.14em;text-transform:uppercase}
  .mxrh{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;white-space:nowrap;padding:0 10px 0 2px}
  .mxrh .pdot{width:9px;height:9px}
  .mxc{text-align:center;padding:10px 2px;border-radius:6px;font-size:12px;font-variant-numeric:tabular-nums;font-weight:700;cursor:default}
  .mxcol0{position:sticky;left:0;z-index:1;background:linear-gradient(90deg,var(--panel) 80%,transparent)}

  /* svg charts */
  svg.chart{width:100%;height:auto;display:block;font-family:inherit;overflow:visible}
  .axl{fill:var(--muted);font-size:12px}
  .axt{fill:var(--muted);font-size:10px;font-variant-numeric:tabular-nums}
  .grln{stroke:var(--line);stroke-width:1;opacity:.6}
  .axis{stroke:var(--line);stroke-width:1.2}
  .frln{stroke:var(--accent-2);stroke-width:1.6;stroke-dasharray:5 3;fill:none;opacity:.85}
  .ptlbl{fill:var(--txt);font-size:10px;font-weight:600}
  .rgrid{stroke:var(--line);fill:none;opacity:.5}
  .rspoke{stroke:var(--line);opacity:.5}
  .rlbl{fill:var(--muted);font-size:10.5px}
  svg .pt{cursor:pointer;transition:r .15s}
  svg .pt:hover{r:8}

  .legrow{display:flex;flex-wrap:wrap;gap:7px;margin:2px 2px 16px}
  .legbtn{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border:1px solid var(--line);
    border-radius:999px;background:var(--panel);color:var(--muted);font-family:inherit;font-size:12px;cursor:pointer;transition:.15s}
  .legbtn:hover{color:var(--txt)}
  .legbtn.on{color:var(--txt);border-color:var(--accent-2);background:var(--panel-2)}
  .legbtn .dot{width:9px;height:9px;border-radius:50%;opacity:.35}
  .legbtn.on .dot{opacity:1;box-shadow:0 0 8px currentColor}

  footer{margin-top:30px;text-align:center;color:var(--muted);font-size:12px;line-height:1.8}
  footer code{color:var(--accent-2)}
  footer .leg{display:inline-flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-top:6px}
  footer .leg i{font-style:normal}
  .sw{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}

  @media(max-width:680px){
    :root{--grid:30px minmax(0,1fr) 42px 42px 42px 46px}
    .barwrap,.colhint{display:none}
    .val.eff,.sortbtn.eff{display:none}
    .prov{display:none}
    .mname{font-size:13px}
    .hrow,.rows{padding-left:14px;padding-right:14px}
    .val{font-size:13px} .val.active{font-size:14px}
    .ctrls{gap:14px}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">Scientific Agent Benchmark<span class="blink">_</span></div>
    <h1>SCI&#8209;AGENT&#8209;EXAM</h1>
    <p class="sub">__SUBTITLE__</p>
    <div class="stats">
      <div class="stat"><b>__NTASKS__</b><span>Tasks</span></div>
      <div class="stat"><b>__NFIELDS__</b><span>Fields</span></div>
      <div class="stat"><b>__NTYPES__</b><span>Task Types</span></div>
      <div class="stat"><b>__NMODELS__</b><span>Agents</span></div>
    </div>
  </header>

  <nav class="nav" id="nav">
    <button class="navbtn" data-v="leaderboard">▤ Leaderboard</button>
    <button class="navbtn" data-v="matrix">▦ Matrix</button>
    <button class="navbtn" data-v="pareto">◴ Pareto</button>
    <button class="navbtn" data-v="domains">◈ Domains</button>
  </nav>

  <!-- ===================== LEADERBOARD ===================== -->
  <section class="view" id="view-leaderboard">
    <div class="filters">
      <p class="flabel">◢ Scientific Fields</p>
      <div class="chips" id="fieldChips"></div>
      <p class="flabel">◢ Research Task Types</p>
      <div class="chips" id="taskChips"></div>
    </div>
    <div class="board">
      <div class="board-head">
        <div class="title"><span class="dot"></span><span id="boardTitle">Overall</span></div>
        <div class="meta"><b id="nTasks">__NTASKS__</b> tasks · sorted by <b id="sortName">Combined</b></div>
      </div>
      <div class="hrow">
        <div class="colhint">score bar ▸</div>
        <button class="sortbtn p" data-m="p">Prog.<span class="arw">▼</span></button>
        <button class="sortbtn j" data-m="j">LLM<span class="arw">▼</span></button>
        <button class="sortbtn c on" data-m="c">Combined<span class="arw">▼</span></button>
        <button class="sortbtn r" data-m="r">Pass@95<span class="arw">▼</span></button>
        <button class="sortbtn eff" data-m="tok">Out-tok<span class="arw">▼</span></button>
        <button class="sortbtn eff" data-m="cost">Cost<span class="arw">▼</span></button>
        <button class="sortbtn eff" data-m="turn">Turns<span class="arw">▼</span></button>
      </div>
      <div class="rows" id="rows"></div>
    </div>
  </section>

  <!-- ===================== MATRIX ===================== -->
  <section class="view" id="view-matrix">
    <div class="ctrls">
      <div class="ctrl"><span class="lab">Metric</span>
        <div class="seg" id="mxMetric">
          <button data-k="p">Prog</button><button data-k="j">LLM</button>
          <button data-k="c" class="on">Combined</button><button data-k="r">Pass@95</button>
        </div></div>
      <div class="ctrl"><span class="lab">Columns</span>
        <div class="seg" id="mxAxis">
          <button data-k="fields" class="on">Fields</button><button data-k="tasks">Task types</button>
        </div></div>
    </div>
    <div class="panel-card">
      <div class="mx"><div class="mxgrid" id="mxgrid"></div></div>
    </div>
    <p class="cap">Rows are the 10 agents in <b>overall-Combined</b> order; each cell is the macro-averaged
      score (×100) for the selected metric, shaded by value within the grid. Hover a cell for the exact number.</p>
  </section>

  <!-- ===================== PARETO ===================== -->
  <section class="view" id="view-pareto">
    <div class="ctrls">
      <div class="ctrl"><span class="lab">Y · quality</span>
        <div class="seg" id="pxY">
          <button data-k="c" class="on">Combined</button><button data-k="p">Prog</button>
          <button data-k="j">LLM</button><button data-k="r">Pass@95</button>
        </div></div>
      <div class="ctrl"><span class="lab">X · axis</span>
        <div class="seg" id="pxX">
          <button data-k="usd" class="on">Cost $</button><button data-k="out_tok">Tokens</button>
          <button data-k="min">Time</button><button data-k="p">Prog</button><button data-k="j">LLM</button>
        </div></div>
    </div>
    <div class="panel-card">
      <div id="pxSub" class="cap" style="margin:0 2px 8px"></div>
      <div class="chartwrap"><svg class="chart" id="pareto" viewBox="0 0 760 468" role="img"></svg></div>
    </div>
    <p class="cap">Each point is an agent on the 120-task peer subset. The dashed line is the <b>Pareto frontier</b>
      — agents no other agent beats on both axes. For Cost / Tokens / Time, cheaper-and-stronger is up-and-left;
      <b id="pxRef"></b> is the reference model (hollow), excluded from the frontier.
      Cost / token / time are per-run, harness-billed. <b>__COSTNOTE__</b></p>
  </section>

  <!-- ===================== DOMAINS ===================== -->
  <section class="view" id="view-domains">
    <div class="ctrls">
      <div class="ctrl"><span class="lab">Metric</span>
        <div class="seg" id="rdMetric">
          <button data-k="p">Prog</button><button data-k="j">LLM</button>
          <button data-k="c" class="on">Combined</button><button data-k="r">Pass@95</button>
        </div></div>
      <div class="ctrl"><span class="lab">Axes</span>
        <div class="seg" id="rdAxis">
          <button data-k="fields" class="on">Fields</button><button data-k="tasks">Task types</button>
        </div></div>
    </div>
    <div class="legrow" id="rdLegend"></div>
    <div class="panel-card">
      <div class="chartwrap"><svg class="chart" id="radar" viewBox="0 0 560 540" role="img"></svg></div>
    </div>
    <p class="cap">Each axis is one category (0–100 for the selected metric); each polygon is one agent.
      Toggle agents in the legend above — defaults to the overall top 3. Spokes mark the category scores.</p>
  </section>

  <footer>
    Scores are ×100, macro-averaged over tasks (__HARNESS__). <b>__FORMULA__</b>.<br>
    <b>Pass@0.95</b>: __PASSNOTE__<br>
    <b>Out-tok / Cost / Turns</b>: per-run means over the trajectory set — output tokens, USD, agent turns
    (lower = leaner, not a quality signal; click to sort cheapest-first).<br>
    <span class="leg">
      <i><span class="sw" style="background:var(--prog)"></span>Programmatic (execution)</i>
      <i><span class="sw" style="background:var(--judge)"></span>LLM-Judge (presentation)</i>
      <i><span class="sw" style="background:var(--comb)"></span>Combined</i>
      <i><span class="sw" style="background:var(--pass)"></span>Pass@0.95</i>
      <i><span class="sw" style="background:#9fb3c9"></span>Efficiency (per run)</i>
    </span><br>
    Switch views above · deep-link with <code>?view=matrix|pareto|domains</code>.
  </footer>
</div>

<script>
const DATA = __DATA__;
const MODELS = {}; DATA.models.forEach(m=>{MODELS[m.id]=m;});
const MODEL_ORDER = DATA.models.map(m=>m.id);
const COST = {}; DATA.models.forEach(m=>{COST[m.id]=m.cost||{};});
const FIELDS = DATA.fields, TASKTYPES = DATA.task_types, S = DATA.scores;

const ALLCATS = {};
[...FIELDS,...TASKTYPES].forEach(c=>{ALLCATS[c.key]=c;});
const METRIC_NAME = {p:"Programmatic", j:"LLM-Judge", c:"Combined", r:"Pass@0.95",
                     tok:"Out-tokens", cost:"Cost", turn:"Turns"};
const MCOLOR = {p:"#6ea8ff", j:"#c98bff", c:"#f0b45d", r:"#4ee39b"};
const SCOREM = new Set(["p","j","c","r"]);
const EFFM = new Set(["tok","cost","turn"]);
const EFFKEY = {tok:"out_tok", cost:"usd", turn:"turns"};   // table col -> cost field
const hx = h=>{h=h.replace('#','');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];};
const fieldCats = ()=>FIELDS.filter(f=>f.key!=='overall');
const esc = s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function overallSorted(){ return MODEL_ORDER.slice().sort((a,b)=>S[b].overall.c-S[a].overall.c); }
// one accessor: score metrics come from S[id][cat]; efficiency metrics from the per-model cost block (category-agnostic)
function getVal(id, catKey, k){
  if(EFFM.has(k)){ const c=COST[id]; return c && c[EFFKEY[k]]!=null ? c[EFFKEY[k]] : null; }
  return S[id][catKey][k];
}
function fmtVal(k,v){
  if(v==null) return "—";
  if(SCOREM.has(k)) return (v*100).toFixed(1)+(k==="r"?"%":"");
  if(k==="tok") return v>=1000 ? (v/1000).toFixed(0)+"k" : String(Math.round(v));
  if(k==="cost") return "$"+v.toFixed(1);
  return v.toFixed(0);
}

/* ---------------- leaderboard (table) ---------------- */
let cat = "overall", metric = "c", dir = "desc";
const rowsEl = document.getElementById("rows");
function renderBoard(){
  const m = ALLCATS[cat];
  document.getElementById("boardTitle").textContent = (m.hero?"":m.ic+" ")+m.label;
  document.getElementById("nTasks").textContent = m.n;
  document.getElementById("sortName").textContent = METRIC_NAME[metric];
  document.querySelectorAll("#view-leaderboard .chip").forEach(ch=>ch.classList.toggle("active", ch.dataset.key===cat));
  document.querySelectorAll("#view-leaderboard .sortbtn").forEach(b=>{
    const on = b.dataset.m===metric;
    b.classList.toggle("on", on);
    b.querySelector(".arw").textContent = (on && dir==="asc") ? "▲" : "▼";
  });
  const ids = MODEL_ORDER.slice().sort((a,b)=>{
    let va = getVal(a,cat,metric), vb = getVal(b,cat,metric);
    if(va==null && vb==null) return 0;
    if(va==null) return 1;
    if(vb==null) return -1;
    return dir==="asc" ? va-vb : vb-va;
  });
  const vals = ids.map(id=>getVal(id,cat,metric)).filter(v=>v!=null);
  const max = vals.length ? Math.max(...vals) : 1;
  rowsEl.innerHTML = "";
  ids.forEach((id,i)=>{
    const mo = MODELS[id];
    const row = document.createElement("div");
    row.className = "row" + (i<3?` top${i+1}`:"");
    const medal = i===0?"🥇":i===1?"🥈":i===2?"🥉":(i+1);
    const cell = (k)=>{
      const eff = EFFM.has(k);
      return `<div class="val ${eff?"eff ":""}${k}${k===metric?" active":""}">${fmtVal(k,getVal(id,cat,k))}</div>`;
    };
    const barClass = EFFM.has(metric) ? "eff" : metric;
    const mv = getVal(id,cat,metric);
    const bw = (mv==null) ? 0 : (mv/max*100);
    row.innerHTML = `
      <div class="rank">${medal}</div>
      <div class="model">
        <span class="pdot" style="color:${mo.color};background:${mo.color}"></span>
        <span class="mname" style="color:${i<3?mo.color:'var(--txt)'}">${esc(mo.name)}</span>
        <span class="prov">${esc(mo.prov)}</span>
      </div>
      <div class="barwrap"><div class="bar ${barClass}" data-w="${bw.toFixed(1)}"></div></div>
      ${cell("p")}${cell("j")}${cell("c")}${cell("r")}${cell("tok")}${cell("cost")}${cell("turn")}`;
    rowsEl.appendChild(row);
  });
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    rowsEl.querySelectorAll(".bar").forEach(b=> b.style.width = b.dataset.w+"%");
  }));
}
function makeChip(c){
  const el = document.createElement("button");
  el.className = "chip"+(c.hero?" hero":"");
  el.dataset.key = c.key;
  el.innerHTML = `<span class="ic">${c.ic}</span>${esc(c.label)}`;
  el.addEventListener("click",()=>{ cat=c.key; renderBoard(); });
  return el;
}
FIELDS.forEach(c=>document.getElementById("fieldChips").appendChild(makeChip(c)));
TASKTYPES.forEach(c=>document.getElementById("taskChips").appendChild(makeChip(c)));
document.querySelectorAll("#view-leaderboard .sortbtn").forEach(b=>{
  b.addEventListener("click",()=>{
    const m = b.dataset.m;
    if(m===metric){ dir = dir==="desc"?"asc":"desc"; }
    else { metric = m; dir = EFFM.has(m) ? "asc" : "desc"; }
    renderBoard();
  });
});

/* ---------------- matrix (heatmap) ---------------- */
let mxMetric="c", mxAxis="fields";
function renderMatrix(){
  const cats = mxAxis==="fields" ? fieldCats() : TASKTYPES;
  const ids = overallSorted();
  const [r,g,b] = hx(MCOLOR[mxMetric]);
  let mx=0; ids.forEach(id=>cats.forEach(c=>{mx=Math.max(mx,S[id][c.key][mxMetric]);}));
  const grid = document.getElementById("mxgrid");
  grid.style.gridTemplateColumns = `minmax(118px,1.3fr) repeat(${cats.length},minmax(40px,1fr))`;
  let html = `<div class="mxh lbl mxcol0" style="text-align:left">Agent ╲ ${mxAxis==="fields"?"Field":"Task type"}</div>`;
  html += cats.map(c=>`<div class="mxh" title="${esc(c.label)}">${c.ic}</div>`).join("");
  ids.forEach(id=>{
    const mo = MODELS[id];
    html += `<div class="mxrh mxcol0"><span class="pdot" style="color:${mo.color};background:${mo.color}"></span>${esc(mo.name)}</div>`;
    cats.forEach(c=>{
      const v = S[id][c.key][mxMetric], norm = mx? v/mx : 0, a = (0.07+0.86*norm).toFixed(3);
      const dark = norm>0.52;
      const disp = (v*100).toFixed(mxMetric==="r"?1:0);
      html += `<div class="mxc" title="${esc(mo.name)} · ${esc(c.label)} — ${METRIC_NAME[mxMetric]} ${(v*100).toFixed(1)}${mxMetric==="r"?"%":""}" `+
              `style="background:rgba(${r},${g},${b},${a});color:${dark?'#071016':'var(--muted)'}">${disp}</div>`;
    });
  });
  grid.innerHTML = html;
}

/* ---------------- pareto (scatter + frontier) ---------------- */
let pxY="c", pxX="usd";
const YAX = {
  c:{lbl:"Combined (%)",      get:id=>S[id].overall.c*100},
  p:{lbl:"Programmatic (%)",  get:id=>S[id].overall.p*100},
  j:{lbl:"LLM-Judge (%)",     get:id=>S[id].overall.j*100},
  r:{lbl:"Pass@0.95 (%)",     get:id=>S[id].overall.r*100},
};
const XAX = {
  usd:    {lbl:"Cost (USD / run)",   low:true,  get:id=>COST[id].usd,     fmt:v=>"$"+(v<10?v.toFixed(1):v.toFixed(0))},
  out_tok:{lbl:"Output tokens / run",low:true,  get:id=>COST[id].out_tok, fmt:v=>(v/1000).toFixed(0)+"k"},
  min:    {lbl:"Time (min / run)",   low:true,  get:id=>COST[id].min,     fmt:v=>v.toFixed(0)+"m"},
  p:      {lbl:"Programmatic (%)",   low:false, get:id=>S[id].overall.p*100, fmt:v=>v.toFixed(0)},
  j:      {lbl:"LLM-Judge (%)",      low:false, get:id=>S[id].overall.j*100, fmt:v=>v.toFixed(0)},
};
function frontier(ids, xa, ya){
  const pts = ids.map(id=>({id, x:xa.get(id), y:ya.get(id)}));
  const betterX = (a,b)=> xa.low ? a<=b : a>=b;
  const strict  = (o,c)=> (xa.low? o.x<c.x : o.x>c.x) || o.y>c.y;
  const keep = pts.filter(c=> !pts.some(o=> o!==c && betterX(o.x,c.x) && o.y>=c.y && strict(o,c)));
  keep.sort((a,b)=>a.x-b.x);
  return keep;
}
function renderPareto(){
  const xa = XAX[pxX], ya = YAX[pxY];
  const W=760,H=468,L=68,R=26,T=24,B=56;
  const ids = MODEL_ORDER;
  const xs = ids.map(xa.get), ys = ids.map(ya.get);
  let x0=Math.min(...xs), x1=Math.max(...xs), y0=Math.min(...ys), y1=Math.max(...ys);
  const px=(x1-x0||1)*0.10, py=(y1-y0||1)*0.12;
  x0-=px; x1+=px; y0=Math.max(0,y0-py); y1+=py;
  const X=v=>L+(v-x0)/(x1-x0)*(W-L-R);
  const Y=v=>T+(1-(v-y0)/(y1-y0))*(H-T-B);
  const ticks=(a,b,n)=>{const o=[];for(let i=0;i<=n;i++)o.push(a+(b-a)*i/n);return o;};
  let g="";
  ticks(y0,y1,5).forEach(t=>{ g+=`<line class="grln" x1="${L}" y1="${Y(t).toFixed(1)}" x2="${W-R}" y2="${Y(t).toFixed(1)}"/>`+
      `<text class="axt" x="${L-8}" y="${(Y(t)+3).toFixed(1)}" text-anchor="end">${t.toFixed(0)}</text>`; });
  ticks(x0,x1,5).forEach(t=>{ g+=`<text class="axt" x="${X(t).toFixed(1)}" y="${H-B+16}" text-anchor="middle">${xa.fmt(t)}</text>`; });
  g+=`<line class="axis" x1="${L}" y1="${T}" x2="${L}" y2="${H-B}"/><line class="axis" x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}"/>`;
  g+=`<text class="axl" x="${(L+(W-R))/2}" y="${H-10}" text-anchor="middle">${esc(xa.lbl)}${xa.low?"  ◂ better":""}</text>`;
  g+=`<text class="axl" transform="translate(16,${(T+(H-B))/2}) rotate(-90)" text-anchor="middle">${esc(ya.lbl)}  ▸ better</text>`;
  const fids = ids.filter(id=>!MODELS[id].ref);
  const fr = frontier(fids, xa, ya);
  if(fr.length>1){ g+=`<polyline class="frln" points="${fr.map(p=>`${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(" ")}"/>`; }
  const onf = new Set(fr.map(p=>p.id));
  ids.forEach(id=>{
    const mo=MODELS[id], x=X(xa.get(id)), y=Y(ya.get(id)), ref=!!mo.ref;
    const tip=`${mo.name} — ${ya.lbl.replace(' (%)','')} ${ya.get(id).toFixed(1)} · ${xa.lbl.replace(/ \(.*/,'')} ${xa.fmt(xa.get(id))} · $/pt ${COST[id].dpp}`;
    if(ref){
      g+=`<circle class="pt" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="none" stroke="${mo.color}" stroke-width="2"><title>${esc(tip)} · reference</title></circle>`;
    } else {
      g+=`<circle class="pt" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${onf.has(id)?6.5:5.5}" fill="${mo.color}" `+
         `stroke="${onf.has(id)?'#fff':'none'}" stroke-width="${onf.has(id)?1.4:0}" fill-opacity="${onf.has(id)?1:.78}"><title>${esc(tip)}</title></circle>`;
    }
    g+=`<text class="ptlbl" x="${(x+9).toFixed(1)}" y="${(y+3).toFixed(1)}">${esc(mo.name)}</text>`;
  });
  document.getElementById("pareto").innerHTML=g;
  document.getElementById("pxSub").innerHTML = `<b style="color:var(--accent-2)">${esc(ya.lbl)}</b> vs. <b style="color:var(--accent-2)">${esc(xa.lbl)}</b> · 120 tasks`;
  const ref=MODEL_ORDER.find(id=>MODELS[id].ref); if(ref) document.getElementById("pxRef").textContent=MODELS[ref].name;
}

/* ---------------- domains (radar) ---------------- */
let rdMetric="c", rdAxis="fields";
let rdSel = new Set(overallSorted().slice(0,3));
function renderRadarLegend(){
  const leg=document.getElementById("rdLegend"); leg.innerHTML="";
  overallSorted().forEach(id=>{
    const mo=MODELS[id], on=rdSel.has(id);
    const el=document.createElement("button");
    el.className="legbtn"+(on?" on":"");
    el.style.color=mo.color;
    el.innerHTML=`<span class="dot" style="background:${mo.color}"></span><span style="color:${on?'var(--txt)':'var(--muted)'}">${esc(mo.name)}</span>`;
    el.addEventListener("click",()=>{ if(rdSel.has(id)) rdSel.delete(id); else rdSel.add(id); renderRadarLegend(); renderRadar(); });
    leg.appendChild(el);
  });
}
function renderRadar(){
  const cats = rdAxis==="fields" ? fieldCats() : TASKTYPES;
  const N=cats.length, W=560,H=540,cx=W/2,cy=H/2+8,Rr=Math.min(cx,cy)-78;
  const ang=i=>(i/N)*2*Math.PI - Math.PI/2;
  const px=(i,rad)=>[cx+Math.cos(ang(i))*rad, cy+Math.sin(ang(i))*rad];
  let g="";
  [0.25,0.5,0.75,1].forEach(f=>{
    const pts=cats.map((_,i)=>px(i,Rr*f).map(n=>n.toFixed(1)).join(",")).join(" ");
    g+=`<polygon class="rgrid" points="${pts}"/>`;
  });
  g+=`<text class="axt" x="${cx+3}" y="${(cy-Rr+3).toFixed(1)}">100</text>`;
  g+=`<text class="axt" x="${cx+3}" y="${(cy-Rr*0.5+3).toFixed(1)}">50</text>`;
  cats.forEach((c,i)=>{
    const [ex,ey]=px(i,Rr);
    g+=`<line class="rspoke" x1="${cx}" y1="${cy}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}"/>`;
    const [lx,ly]=px(i,Rr+18); const a=ang(i);
    const anc = Math.abs(Math.cos(a))<0.35 ? "middle" : (Math.cos(a)>0 ? "start":"end");
    g+=`<text class="rlbl" x="${lx.toFixed(1)}" y="${(ly+3).toFixed(1)}" text-anchor="${anc}">${c.ic} ${esc(c.label)}</text>`;
  });
  overallSorted().filter(id=>rdSel.has(id)).forEach(id=>{
    const mo=MODELS[id];
    const pts=cats.map((c,i)=>px(i,Rr*S[id][c.key][rdMetric]).map(n=>n.toFixed(1)).join(",")).join(" ");
    g+=`<polygon points="${pts}" fill="${mo.color}" fill-opacity="0.13" stroke="${mo.color}" stroke-width="2" stroke-opacity="0.9"/>`;
    cats.forEach((c,i)=>{ const [vx,vy]=px(i,Rr*S[id][c.key][rdMetric]);
      g+=`<circle class="pt" cx="${vx.toFixed(1)}" cy="${vy.toFixed(1)}" r="3" fill="${mo.color}"><title>${esc(mo.name)} · ${esc(c.label)}: ${(S[id][c.key][rdMetric]*100).toFixed(1)}${rdMetric==="r"?"%":""}</title></circle>`; });
  });
  document.getElementById("radar").innerHTML=g;
}

/* ---------------- segmented-control wiring ---------------- */
function seg(elId, apply){
  document.querySelectorAll("#"+elId+" button").forEach(b=>{
    b.addEventListener("click",()=>{
      document.querySelectorAll("#"+elId+" button").forEach(x=>x.classList.remove("on"));
      b.classList.add("on"); apply(b.dataset.k);
    });
  });
}
seg("mxMetric", k=>{mxMetric=k; renderMatrix();});
seg("mxAxis",   k=>{mxAxis=k;   renderMatrix();});
seg("pxY",      k=>{pxY=k;      renderPareto();});
seg("pxX",      k=>{pxX=k;      renderPareto();});
seg("rdMetric", k=>{rdMetric=k; renderRadar();});
seg("rdAxis",   k=>{rdAxis=k;   renderRadar();});

/* ---------------- view router ---------------- */
const VIEWS = ["leaderboard","matrix","pareto","domains"];
const RENDER = {leaderboard:renderBoard, matrix:renderMatrix, pareto:renderPareto,
                domains:()=>{renderRadarLegend();renderRadar();}};
let view = "leaderboard";
function setView(v, push){
  if(!VIEWS.includes(v)) v="leaderboard";
  view=v;
  VIEWS.forEach(x=>document.getElementById("view-"+x).classList.toggle("on", x===v));
  document.querySelectorAll(".navbtn").forEach(b=>b.classList.toggle("on", b.dataset.v===v));
  RENDER[v]();
  if(push!==false){ const u=new URL(location); u.searchParams.set("view",v); history.replaceState(null,"",u); }
}
document.querySelectorAll(".navbtn").forEach(b=> b.addEventListener("click",()=>setView(b.dataset.v)));

const q = new URLSearchParams(location.search).get("view");
renderBoard();                          // table ready underneath
setView(VIEWS.includes(q)?q:"leaderboard", false);
</script>
</body>
</html>
"""

html = (TEMPLATE
        .replace("__DATA__", DATA_JS)
        .replace("__SUBTITLE__", meta["subtitle"])
        .replace("__NTASKS__", str(meta["n_tasks"]))
        .replace("__NFIELDS__", str(meta["n_fields"]))
        .replace("__NTYPES__", str(meta["n_task_types"]))
        .replace("__NMODELS__", str(meta["n_models"]))
        .replace("__HARNESS__", meta["harness"])
        .replace("__FORMULA__", meta["combined_formula"])
        .replace("__PASSNOTE__", meta["pass_note"])
        .replace("__COSTNOTE__", meta.get("cost_note", "")))

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html):,} bytes) from {DATA.name}")
