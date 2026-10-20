#!/usr/bin/env python3
"""Build the Sci-Agent-Exam leaderboard webpage from data/leaderboard.json.

Usage:
    python3 build.py                 # writes ./index.html
    python3 build.py out.html        # writes ./out.html

The page is a single self-contained HTML file (no external assets, no network,
no build step beyond this script). All numbers, model metadata, field / task-type
metadata, and copy are read from data/leaderboard.json, so updating the board is a
matter of editing that one JSON file and re-running this script.
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
    --grid: 46px minmax(0,1fr) 92px 60px 60px 60px 68px;
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

  header{text-align:center;margin-bottom:30px}
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

  .filters{margin:34px 0 10px}
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

  .board{margin-top:18px;border:1px solid var(--line);border-radius:16px;overflow:hidden;
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

  .val{font-size:15px;font-weight:700;text-align:right;font-variant-numeric:tabular-nums;color:var(--muted);transition:.2s}
  .val.active{font-size:18px;font-weight:800;color:var(--txt)}
  .val.c.active{color:var(--comb)} .val.p.active{color:var(--prog)} .val.j.active{color:var(--judge)} .val.r.active{color:var(--pass)}
  .val.r{color:var(--pass);opacity:.55} .val.r.active{opacity:1}

  footer{margin-top:30px;text-align:center;color:var(--muted);font-size:12px;line-height:1.8}
  footer code{color:var(--accent-2)}
  footer .leg{display:inline-flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-top:6px}
  footer .leg i{font-style:normal}
  .sw{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}

  @media(max-width:680px){
    :root{--grid:30px minmax(0,1fr) 42px 42px 42px 46px}
    .barwrap,.colhint{display:none}
    .prov{display:none}
    .mname{font-size:13px}
    .hrow,.rows{padding-left:14px;padding-right:14px}
    .val{font-size:13px} .val.active{font-size:14px}
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
    </div>
    <div class="rows" id="rows"></div>
  </div>

  <footer>
    Scores are ×100, macro-averaged over tasks (__HARNESS__). <b>__FORMULA__</b>.<br>
    <b>Pass@0.95</b>: __PASSNOTE__<br>
    <span class="leg">
      <i><span class="sw" style="background:var(--prog)"></span>Programmatic (execution)</i>
      <i><span class="sw" style="background:var(--judge)"></span>LLM-Judge (presentation)</i>
      <i><span class="sw" style="background:var(--comb)"></span>Combined</i>
      <i><span class="sw" style="background:var(--pass)"></span>Pass@0.95</i>
    </span><br>
    Click a field / task type to filter · click a column header to sort (click again to flip order).
  </footer>
</div>

<script>
const DATA = __DATA__;
const MODELS = {}; DATA.models.forEach(m=>{MODELS[m.id]=m;});
const MODEL_ORDER = DATA.models.map(m=>m.id);
const FIELDS = DATA.fields, TASKTYPES = DATA.task_types, S = DATA.scores;

const ALLCATS = {};
[...FIELDS,...TASKTYPES].forEach(c=>{ALLCATS[c.key]=c;});
const METRIC_NAME = {p:"Programmatic", j:"LLM-Judge", c:"Combined", r:"Pass@0.95"};

let cat = "overall", metric = "c", dir = "desc";
const rowsEl = document.getElementById("rows");

function render(){
  const meta = ALLCATS[cat];
  document.getElementById("boardTitle").textContent = (meta.hero?"":meta.ic+" ")+meta.label;
  document.getElementById("nTasks").textContent = meta.n;
  document.getElementById("sortName").textContent = METRIC_NAME[metric];

  document.querySelectorAll(".chip").forEach(ch=>ch.classList.toggle("active", ch.dataset.key===cat));
  document.querySelectorAll(".sortbtn").forEach(b=>{
    const on = b.dataset.m===metric;
    b.classList.toggle("on", on);
    b.querySelector(".arw").textContent = (on && dir==="asc") ? "▲" : "▼";
  });

  const ids = MODEL_ORDER.slice().sort((a,b)=>{
    const dd = S[a][cat][metric]-S[b][cat][metric];
    return dir==="asc" ? dd : -dd;
  });
  const max = Math.max(...ids.map(id=>S[id][cat][metric]));

  rowsEl.innerHTML = "";
  ids.forEach((id,i)=>{
    const m = MODELS[id], s = S[id][cat];
    const row = document.createElement("div");
    row.className = "row" + (i<3?` top${i+1}`:"");
    const medal = i===0?"🥇":i===1?"🥈":i===2?"🥉":(i+1);
    const cell = (k)=>`<div class="val ${k}${k===metric?" active":""}">${(s[k]*100).toFixed(1)}${k==="r"?"%":""}</div>`;
    row.innerHTML = `
      <div class="rank">${medal}</div>
      <div class="model">
        <span class="pdot" style="color:${m.color};background:${m.color}"></span>
        <span class="mname" style="color:${i<3?m.color:'var(--txt)'}">${m.name}</span>
        <span class="prov">${m.prov}</span>
      </div>
      <div class="barwrap"><div class="bar ${metric}" data-w="${(s[metric]/max*100).toFixed(1)}"></div></div>
      ${cell("p")}${cell("j")}${cell("c")}${cell("r")}`;
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
  el.innerHTML = `<span class="ic">${c.ic}</span>${c.label}`;
  el.addEventListener("click",()=>{ cat=c.key; render(); });
  return el;
}
FIELDS.forEach(c=>document.getElementById("fieldChips").appendChild(makeChip(c)));
TASKTYPES.forEach(c=>document.getElementById("taskChips").appendChild(makeChip(c)));

document.querySelectorAll(".sortbtn").forEach(b=>{
  b.addEventListener("click",()=>{
    const m = b.dataset.m;
    if(m===metric){ dir = dir==="desc"?"asc":"desc"; }
    else { metric = m; dir = "desc"; }
    render();
  });
});

render();
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
        .replace("__PASSNOTE__", meta["pass_note"]))

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({len(html):,} bytes) from {DATA.name}")
