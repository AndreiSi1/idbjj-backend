"""Админ-панель ID BJJ — заменяет кабинет Salebot.

- GET  /admin                 — HTML-дашборд (KPI, графики, пояса, лиды, рассылки, переписка)
- GET  /admin/metrics         — JSON для дашборда
- GET  /admin/leads           — заявки из «Связаться с тренером»
- POST /admin/broadcast       — рассылка (только Telegram; в MAX запрещено)
- GET  /admin/inbox           — список диалогов
- GET  /admin/inbox/{uid}     — история переписки с пользователем
- POST /admin/inbox/{uid}/reply — ответить пользователю в его канал

Auth: HTTP Basic (settings.admin_user / admin_password). Пустой пароль → 503.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Message, User
from app.deps import DB
from app.services import broadcast, messenger, metrics

security = HTTPBasic(auto_error=True)


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    if not settings.admin_password:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "admin panel not configured")
    ok_user = secrets.compare_digest(credentials.username, settings.admin_user)
    ok_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


AdminAuth = Depends(require_admin)
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[AdminAuth])


class BroadcastIn(BaseModel):
    text: str


class ReplyIn(BaseModel):
    text: str


@router.get("/metrics")
async def get_metrics(session: AsyncSession = DB) -> dict:
    return await metrics.dashboard(session)


@router.get("/leads")
async def get_leads(session: AsyncSession = DB) -> dict:
    return {"leads": await metrics.recent_leads(session, limit=100)}


@router.post("/broadcast")
async def post_broadcast(body: BroadcastIn, session: AsyncSession = DB) -> dict:
    """Рассылка только в Telegram (в MAX запрещена правилами платформы)."""
    if not body.text.strip():
        raise HTTPException(400, "empty text")
    recipients = int(
        (
            await session.execute(
                select(func.count(User.id)).where(
                    User.channel == "telegram", User.consent_at.is_not(None)
                )
            )
        ).scalar_one()
        or 0
    )
    sent = await broadcast.broadcast(session, body.text)
    return {"recipients": recipients, "sent": sent, "channel": "telegram"}


@router.get("/inbox")
async def inbox(session: AsyncSession = DB) -> dict:
    last_at = func.max(Message.created_at).label("last_at")
    rows = (
        await session.execute(
            select(User.id, User.ext_id, User.channel, User.full_name, User.username, last_at)
            .join(Message, Message.user_id == User.id)
            .group_by(User.id, User.ext_id, User.channel, User.full_name, User.username)
            .order_by(last_at.desc())
        )
    ).all()
    return {
        "conversations": [
            {
                "user_id": r.id,
                "channel": r.channel,
                "name": r.full_name or r.username or f"id{r.ext_id}",
                "last_at": r.last_at.isoformat() if r.last_at else None,
            }
            for r in rows
        ]
    }


@router.get("/inbox/{user_id}")
async def conversation(user_id: int, session: AsyncSession = DB) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    rows = (
        await session.execute(
            select(Message).where(Message.user_id == user_id).order_by(Message.created_at)
        )
    ).scalars().all()
    return {
        "user_id": user_id,
        "channel": user.channel,
        "name": user.full_name or user.username or f"id{user.ext_id}",
        "messages": [
            {"direction": m.direction, "text": m.text, "at": m.created_at.isoformat() if m.created_at else None}
            for m in rows
        ],
    }


@router.post("/inbox/{user_id}/reply")
async def reply(user_id: int, body: ReplyIn, session: AsyncSession = DB) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    if not body.text.strip():
        raise HTTPException(400, "empty text")
    ok = await messenger.send_message(user.channel, user.ext_id, body.text)
    if ok:
        session.add(Message(user_id=user_id, direction="out", text=body.text))
        await session.flush()
    return {"ok": ok}


@router.get("", response_class=HTMLResponse)
async def dashboard_page() -> str:
    return _PAGE


_PAGE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ID BJJ — панель</title>
<script src="/static/chart.min.js"></script>
<style>
  :root{--bg:#fff;--ink:#0a0a0a;--mut:#6b7280;--line:#e5e7eb;--soft:#f5f5f5}
  *{box-sizing:border-box}
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
  header{padding:18px 24px;border-bottom:1px solid var(--line);font-size:18px;font-weight:800;letter-spacing:.04em}
  header b{border:2px solid var(--ink);padding:1px 7px;margin-right:8px}
  nav{display:flex;gap:6px;padding:14px 24px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  nav button{background:#fff;color:var(--ink);border:1px solid var(--line);padding:8px 14px;border-radius:8px;cursor:pointer;font-weight:600}
  nav button.active{background:var(--ink);color:#fff;border-color:var(--ink)}
  main{padding:24px;max-width:1100px;margin:0 auto}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .card{border:1px solid var(--line);border-radius:12px;padding:16px}
  .card .n{font-size:28px;font-weight:800}
  .card .l{color:var(--mut);font-size:13px;margin-top:4px}
  table{width:100%;border-collapse:collapse;margin-top:12px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);font-size:14px}
  th{color:var(--mut);font-weight:600}
  .hidden{display:none}
  textarea,select,input{width:100%;background:#fff;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px;box-sizing:border-box;font:inherit}
  .btn{background:var(--ink);color:#fff;border:0;padding:10px 16px;border-radius:8px;cursor:pointer;margin-top:8px;font-weight:600}
  .row{display:flex;gap:16px;flex-wrap:wrap}
  .box{border:1px solid var(--line);border-radius:12px;padding:16px;flex:1;min-width:320px;margin-top:16px}
  .mut{color:var(--mut)}
  .note{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:13px;color:var(--mut);margin:10px 0}
</style></head><body>
<header><b>ID</b>BJJ — панель управления</header>
<nav>
  <button data-tab="dash" class="active">Дашборд</button>
  <button data-tab="leads">Лиды</button>
  <button data-tab="bc">Рассылка</button>
  <button data-tab="inbox">Переписка</button>
</nav>
<main>
  <section id="dash">
    <div class="cards" id="kpis"></div>
    <div class="row">
      <div class="box"><canvas id="growth"></canvas></div>
      <div class="box" style="max-width:360px"><canvas id="belts"></canvas></div>
    </div>
    <div class="row">
      <div class="box" style="max-width:480px">
        <div class="mut" style="font-weight:700;margin-bottom:4px">Источники трафика (deep-link ?start=)</div>
        <table id="sources-t"></table>
      </div>
    </div>
  </section>

  <section id="leads" class="hidden"><table id="leads-t"></table></section>

  <section id="bc" class="hidden">
    <h3>Рассылка</h3>
    <div class="note">⚠️ Рассылки идут только в Telegram (с согласием). В MAX проактивные сообщения запрещены правилами платформы.</div>
    <textarea id="bc-text" rows="4" placeholder="Текст сообщения..."></textarea>
    <button class="btn" onclick="sendBroadcast()">Отправить в Telegram</button>
    <p id="bc-res" class="mut"></p>
  </section>

  <section id="inbox" class="hidden">
    <div class="row">
      <div style="flex:1;min-width:260px"><table id="convos"></table></div>
      <div style="flex:2;min-width:320px"><div id="thread" class="mut">Выберите диалог</div></div>
    </div>
  </section>
</main>
<script>
const $=s=>document.querySelector(s);
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'})[c]);
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  ['dash','leads','bc','inbox'].forEach(t=>$('#'+t).classList.add('hidden'));
  $('#'+b.dataset.tab).classList.remove('hidden');
  if(b.dataset.tab==='leads')loadLeads();
  if(b.dataset.tab==='inbox')loadInbox();
});
async function api(p,opt){const r=await fetch(p,opt);return r.json();}

let gChart,bChart;
async function loadDash(){
  const d=await api('/admin/metrics');const s=d.summary;
  const kpi=[['Пользователи',s.total_users],['MAX',s.max_users],['Telegram',s.telegram_users],
    ['С согласием',s.with_consent],['Анкета тренера',s.trainer_profiles],['Анкета диеты',s.diet_profiles],
    ['Лиды',s.leads_total],['Входящих',s.messages_in],['Исходящих',s.messages_out]];
  $('#kpis').innerHTML=kpi.map(k=>`<div class="card"><div class="n">${k[1]}</div><div class="l">${k[0]}</div></div>`).join('');
  const labels=d.growth.users.map(x=>x.date);
  gChart&&gChart.destroy();
  gChart=new Chart($('#growth'),{type:'line',data:{labels,datasets:[
    series('Пользователи',d.growth.users,'#0a0a0a'),series('Лиды',d.growth.leads,'#9ca3af'),
    series('Сообщения',d.growth.messages,'#d1d5db')]},
    options:{plugins:{title:{display:true,text:'Рост по дням'},legend:{labels:{color:'#374151'}}},scales:scales()}});
  bChart&&bChart.destroy();
  bChart=new Chart($('#belts'),{type:'doughnut',data:{labels:d.belts.map(b=>b.label),
    datasets:[{data:d.belts.map(b=>b.count),backgroundColor:['#e5e7eb','#3b82f6','#8b5cf6','#92400e','#111827','#9ca3af']}]},
    options:{plugins:{title:{display:true,text:'Пояса'},legend:{position:'bottom'}}}});
  const src=d.sources||[];
  $('#sources-t').innerHTML='<tr><th>Источник</th><th>Юзеров</th></tr>'+
    (src.map(x=>`<tr><td>${esc(x.source)}</td><td>${x.count}</td></tr>`).join('')||'<tr><td class="mut">Пусто</td></tr>');
}
function series(label,arr,color){return{label,data:arr.map(x=>x.count),borderColor:color,backgroundColor:color,tension:.3};}
function scales(){return{x:{ticks:{color:'#6b7280'}},y:{ticks:{color:'#6b7280'},beginAtZero:true}};}

async function loadLeads(){
  const d=await api('/admin/leads');
  $('#leads-t').innerHTML='<tr><th>#</th><th>Тип</th><th>Имя</th><th>Канал</th><th>Источник</th><th>Телефон</th><th>Дата</th></tr>'+
    (d.leads.map(l=>`<tr><td>${l.id}</td><td>${esc(l.kind)}</td><td>${esc(l.name)}</td><td>${l.channel}</td><td>${esc(l.source||'—')}</td><td>${esc(l.phone||'')}</td><td class="mut">${(l.at||'').slice(0,16).replace('T',' ')}</td></tr>`).join('')||'<tr><td class="mut">Пусто</td></tr>');
}
async function sendBroadcast(){
  const r=await api('/admin/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:$('#bc-text').value})});
  $('#bc-res').textContent=r.detail?('Ошибка: '+r.detail):`Отправлено ${r.sent} из ${r.recipients} (Telegram)`;
}
async function loadInbox(){
  const d=await api('/admin/inbox');
  $('#convos').innerHTML=d.conversations.map(c=>
    `<tr style="cursor:pointer" onclick="openThread(${c.user_id})"><td>${esc(c.name)}</td><td class="mut">${c.channel}</td><td class="mut">${(c.last_at||'').slice(0,16).replace('T',' ')}</td></tr>`).join('')||'<tr><td class="mut">Пусто</td></tr>';
}
let curUid=null;
async function openThread(uid){
  curUid=uid;const d=await api('/admin/inbox/'+uid);
  $('#thread').innerHTML=`<h3>${esc(d.name)} <span class="mut" style="font-size:13px">(${d.channel})</span></h3>`+d.messages.map(m=>{
    const out=m.direction==='out';
    return `<div style="margin:6px 0;text-align:${out?'right':'left'}"><span style="background:${out?'#0a0a0a':'#f0f0f0'};color:${out?'#fff':'#0a0a0a'};max-width:74%;padding:7px 11px;border-radius:12px;display:inline-block;text-align:left;white-space:pre-wrap;line-height:1.35">${esc(m.text)}</span></div>`;}).join('')+
    `<textarea id="rep" rows="2" placeholder="Ответить..."></textarea><button class="btn" onclick="sendReply()">Ответить</button>`;
}
async function sendReply(){
  await api('/admin/inbox/'+curUid+'/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('#rep').value})});
  openThread(curUid);loadInbox();
}
loadDash();
</script></body></html>"""
