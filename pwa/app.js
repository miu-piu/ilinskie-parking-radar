const $ = (id) => document.getElementById(id);
const state = {data:null, filter:'all', sort:'entry'};
const money = (v) => v == null ? '—' : new Intl.NumberFormat('ru-RU').format(v) + ' ₽';
const timeText = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'}) : '—';

function renderSummary(data){
  const d=data.decision||{};
  $('decision').textContent=d.action||'—';
  $('decisionReason').textContent=d.reason||'—';
  $('cap').textContent=money(data.hard_cap_rub);
  $('bestPremium').textContent=d.premium_number ? `№${d.premium_number}` : '—';
  $('bestPremiumPrice').textContent=money(d.premium_price);
  $('bestCheap').textContent=d.cheap_number ? `№${d.cheap_number}` : '—';
  $('bestCheapPrice').textContent=money(d.cheap_price);
  $('comfortGap').textContent=money(d.comfort_gap);
  $('updated').textContent=`Обновлено ${timeText(data.updated_at)}`;
}

function visibleLots(data){
  let rows=[...(data.lots||[])];
  if(state.filter==='premium') rows=rows.filter(x=>x.group_name==='premium');
  if(state.filter==='cheap') rows=rows.filter(x=>x.group_name!=='premium' && x.under_cap).slice(0,20);
  if(state.filter==='bids') rows=rows.filter(x=>(x.bid_count||0)>0);
  if(state.sort==='bids') rows.sort((a,b)=>(b.bid_count||0)-(a.bid_count||0) || (a.entry_price_rub||1e12)-(b.entry_price_rub||1e12));
  if(state.sort==='level') rows.sort((a,b)=>(a.level||99)-(b.level||99) || (a.entry_price_rub||1e12)-(b.entry_price_rub||1e12));
  if(state.sort==='entry') rows.sort((a,b)=>(a.entry_price_rub||1e12)-(b.entry_price_rub||1e12));
  return rows;
}

function renderLots(data){
  const rows=visibleLots(data);
  $('lotCount').textContent=`${rows.length} из ${(data.lots||[]).length}`;
  $('lots').innerHTML=rows.map(x=>{
    const rise=(x.current_price_rub||0)-(x.start_price_rub||0);
    const premium=x.group_name==='premium';
    const over=!x.under_cap;
    const badges=[premium?'<span class="badge premium">ПРЕМИУМ</span>':'',x.bid_count?`<span class="badge">${x.bid_count} ставок</span>`:''].join('');
    return `<a class="lot ${premium?'premium':''} ${over?'over':''}" href="${x.url}" target="_blank" rel="noopener">
      <div>
        <div class="lot-top"><span class="lot-number">№${x.number??'—'}</span>${badges}</div>
        <div class="meta">уровень ${x.level??'—'} · ${x.area_m2??'—'} м² · старт ${money(x.start_price_rub)}</div>
        <div class="bids">${over?'Выше потолка':'Можно участвовать'} · ПИК ↗</div>
      </div>
      <div class="prices">
        <div class="entry">${money(x.entry_price_rub)}</div>
        <div class="current">цена входа</div>
        <div class="delta ${rise>0?'up':'ok'}">${rise>0?'+'+money(rise):'без роста'}</div>
      </div>
    </a>`;
  }).join('') || '<div class="status">Нет лотов по выбранному фильтру.</div>';
}

function render(data){renderSummary(data);renderLots(data)}

async function load(force=false){
  $('refresh').disabled=true;
  $('status').classList.remove('error');
  $('status').textContent='Обновляю данные ПИК…';
  try{
    const r=await fetch(`/api/lots${force?'?force=true':''}`,{cache:'no-store'});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    if(!data.ok) throw new Error('ПИК не вернул данные');
    state.data=data;
    localStorage.setItem('parking-radar-last',JSON.stringify(data));
    render(data);
    $('status').textContent=data.errors?.length ? `Данные получены, ошибок: ${data.errors.length}` : 'Живые данные ПИК';
  }catch(e){
    $('status').classList.add('error');
    $('status').textContent='Нет свежих данных. Показываю последний сохранённый снимок.';
    const cached=localStorage.getItem('parking-radar-last');
    if(cached){state.data=JSON.parse(cached);render(state.data)}
  }finally{$('refresh').disabled=false}
}

$('refresh').addEventListener('click',()=>load(true));
document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));
  btn.classList.add('active');state.filter=btn.dataset.filter;if(state.data)renderLots(state.data);
}));
$('sort').addEventListener('change',e=>{state.sort=e.target.value;if(state.data)renderLots(state.data)});

if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');
load();
setInterval(()=>{if(!document.hidden)load(false)},30000);
