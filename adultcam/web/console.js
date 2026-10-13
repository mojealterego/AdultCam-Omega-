'use strict';
const el = id => document.getElementById(id);
let csrfToken = null;
let principalRole = 'viewer';
let principalSubject = '';
const canOperate = () => principalRole === 'admin' || principalRole === 'operator';
const isAdmin = () => principalRole === 'admin';

const node = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = String(text); if(cls) n.className = cls; return n; };
function note(text, good=true){ const n=el('notice');n.textContent=text;n.className='visible '+(good?'good':'bad'); }
async function api(path, method='GET', data=null, approve=false){
  const headers = {'X-AdultCam-Request':'1'};
  if(method !== 'GET' && csrfToken) headers['X-AdultCam-CSRF'] = csrfToken;
  if(data !== null) headers['Content-Type']='application/json';
  if(approve) headers['X-AdultCam-Confirm']='I_APPROVE';
  const r=await fetch(path,{method,headers,body:data===null?undefined:JSON.stringify(data),cache:'no-store',credentials:'same-origin'});
  const j=await r.json(); if(!r.ok) throw Error(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail));return j;
}
function box(title,sub){let d=node('div',null,'entry');d.append(node('b',title),node('div',sub,'muted'));return d;}
function btn(label,handler,danger=false){let b=node('button',label,danger?'danger':'');b.type='button';b.onclick=async()=>{try{await handler();await load()}catch(e){note(e.message,false)}};return b;}
function renderProfiles(list){let root=el('profiles-list');root.replaceChildren();if(!list.length)root.append(node('p','Brak profili.'));
  for(const p of list){let d=box(p.platform+' · '+p.alias,'Status: '+p.status+' · wpis ręczny');
    let row=node('div',null,'row');if(canOperate())for(const status of ['ONLINE','OFFLINE','UNVERIFIED'])row.append(btn(status,async()=>{await api('/api/profiles/'+p.id+'/observations','POST',{status,source:'MANUAL'});note('Zaktualizowano ręczną obserwację.')}));d.append(row);root.append(d)}
}
function renderSessions(list, unresolved){let root=el('sessions-list');root.replaceChildren();if(!list.length)root.append(node('p','Brak sesji.'));
  for(const s of list){let d=box('#'+s.id+' · '+s.title,'Stan: '+s.state);let row=node('div',null,'row');
    if(canOperate() && s.state==='PREPARE') row.append(btn('Oznacz READY',async()=>{await api('/api/sessions/'+s.id+'/transition','POST',{to_state:'READY'});note('Sesja gotowa.')}));
    if(canOperate() && (s.state==='PREPARE'||s.state==='READY'||s.state==='ENDING'))row.append(btn('Zamknij sesję',async()=>{await api('/api/sessions/'+s.id+'/transition','POST',{to_state:'CLOSED'});note('Sesja zamknięta.')}));
    if(canOperate() && s.state==='READY')row.append(btn('Przygotuj START OBS',()=>prepare('start_stream',s.id)));
    if(canOperate() && s.state==='RECOVERY')row.append(btn('ZATWIERDŹ WYJŚCIE Z RECOVERY',async()=>{
      const phrase=prompt('Potwierdź kontrolę OBS, zgodność celu i uprawnienia uczestników. Wpisz ZATWIERDZAM:');
      if(phrase!=='ZATWIERDZAM')return;
      const result=await api('/api/obs/recovery/approve','POST',{session_id:s.id},true);
      note('Przywrócono stan wewnętrzny: '+result.state+'. Odbiór na platformie nadal NIEZWERYFIKOWANY.');
    }));
    if(canOperate() && (s.state==='LIVE_PUBLIC'||s.state==='RECOVERY'||unresolved.some(x=>x.session_id===s.id)))row.append(btn('Przygotuj STOP OBS',()=>prepare('stop_stream',s.id),true));
    d.append(row);root.append(d);
  }
}
async function prepare(operation,session_id){const a=await api('/api/actions','POST',{operation,session_id,idempotency_key:crypto.randomUUID()});note('Utworzono zamiar #'+a.id+'. Wymaga oddzielnego zatwierdzenia.');}
function renderActions(list){let root=el('actions-list');root.replaceChildren();if(!list.length)root.append(node('p','Brak operacji.'));
  for(const a of list){let d=box('#'+a.id+' · '+a.operation+' (sesja #'+a.session_id+')',a.status+' · ryzyko '+a.risk_class);
    if(canOperate() && a.status==='PENDING_APPROVAL')d.append(btn('ZATWIERDŹ I WYKONAJ',async()=>{
      const phrase=prompt('Operacja może uruchomić/zatrzymać rzeczywiste nadawanie OBS. Wpisz dokładnie ZATWIERDZAM:');
      if(phrase!=='ZATWIERDZAM')return;
      let result=await api('/api/actions/'+a.id+'/approve','POST',null,true);
      note('Potwierdzenie z OBS: '+JSON.stringify(result.receipt));
    },a.operation==='stop_stream'));
    if(a.status==='PENDING_APPROVAL')d.append(btn('ANULUJ ZAMIAR',async()=>{
      await api('/api/actions/'+a.id+'/cancel','POST');
      note('Anulowano niewykonaną operację #'+a.id+'.');
    }));
    if(canOperate() && a.status==='UNKNOWN' && !window.reconciledIds.has(a.id))d.append(btn('UZGODNIJ STAN Z OBS',async()=>{
      const phrase=prompt('Sprawdź najpierw stan OBS. Uzgodnienie odczytuje bieżący stan wyjścia OBS, bez weryfikacji platformy. Wpisz ZATWIERDZAM:');
      if(phrase!=='ZATWIERDZAM')return;
      const r=await api('/api/obs/reconcile','POST',{action_id:a.id},true);
      note('Uzgodnienie stanu OBS: '+r.result_code+'; stan sesji: '+r.session_state+'; dostarczenie na platformę: niezweryfikowane.');
    }));
    root.append(d)}
}
async function refreshRoutes(){
  const select=el('route-session');
  const list=el('routes-list');
  const sid=Number(select.value);
  list.replaceChildren();
  if(!sid)return;
  const result=await api('/api/routes?session_id='+sid);
  for(const item of result.routes){
    const entry=box(item.route_key+' · '+item.platform,item.audience+' · '+item.capability+' · PLAN_ONLY');
    if(canOperate())entry.append(btn('Usuń plan',async()=>{await api('/api/routes/'+item.id,'DELETE')},true));
    list.append(entry);
  }
}
async function evaluateRoutes(audience){
  const sid=Number(el('route-session').value);
  if(!sid)throw Error('Wybierz sesję');
  const result=await api('/api/routes/evaluate?session_id='+sid+'&audience='+audience);
  el('routes-evaluation').textContent=result.decision+' · '+result.owned_receivers_with_fresh_proof+'/'+result.route_count+' · platforma: NIEZWERYFIKOWANA';
}
function renderEvents(list){let root=el('events-list');root.replaceChildren();if(!list.length)root.append(node('p','Brak zdarzeń.'));
  for(const e of list.slice(0,30)){let d=box(e.kind+' · '+e.subject,e.observed_at+' · '+JSON.stringify(e.detail));root.append(d)}
}
async function refreshMonitor(){
  const status=await api('/api/monitor/status');const root=el('monitor-list');root.replaceChildren();
  root.append(box('Ostatni pomiar: '+status.last_result,
      (status.last_checked_at||'Jeszcze nie wykonano')+' · odbiór na platformie: NIEZWERYFIKOWANY'));
  for(const i of status.open_incidents)root.append(box('INCYDENT #'+i.id+' · '+i.reason_code,
    i.subject+' · wystąpienia: '+i.occurrences+' · ostatnio: '+i.last_seen_at));
  if(!status.open_incidents.length)root.append(node('div','Brak otwartych incydentów w lokalnej bazie.','muted'));
}
async function load(){let d=await api('/api/dashboard');el('count-profiles').textContent=d.profiles.length;el('count-sessions').textContent=d.sessions.length;el('count-actions').textContent=d.actions.filter(a=>a.status==='PENDING_APPROVAL').length;el('count-events').textContent=d.events.length;
  el('attestation-status').textContent=d.attestation_current?'Oświadczenie aktualne':'Brak aktualnego oświadczenia';
  window.reconciledIds=new Set(d.actions.filter(a=>a.status==='UNKNOWN').map(a=>a.id).filter(id=>
    !(d.unresolved_obs_actions || []).some(x=>x.id===id)));
  renderProfiles(d.profiles);renderSessions(d.sessions,d.unresolved_obs_actions||[]);renderActions(d.actions);renderEvents(d.events);
  const routeSelect=el('route-session'), selected=routeSelect.value;
  routeSelect.replaceChildren();
  for(const session of d.sessions){
    const option=document.createElement('option');option.value=String(session.id);
    option.textContent='#'+session.id+' · '+session.title;routeSelect.append(option);
  }
  if(d.sessions.some(session=>String(session.id)===selected))routeSelect.value=selected;
  await refreshRoutes();
  await refreshMonitor();
  let r=el('ledger-totals');r.replaceChildren();const totals=Object.entries(d.revenue_by_currency);
  if(!totals.length)r.append(node('p','Nie zapisano transakcji.'));
  for(const [currency,amount] of totals)r.append(box(currency,(amount/100).toFixed(2)+' '+currency));
}
function bindForm(id,make,endpoint){el(id).addEventListener('submit',async ev=>{ev.preventDefault();try{const data=make(new FormData(ev.currentTarget));await api(endpoint,'POST',data);ev.currentTarget.reset();note('Zapisano.');await load()}catch(e){note(e.message,false)}})}
bindForm('profile-form',f=>({platform:f.get('platform'),alias:f.get('alias'),public_url:f.get('public_url')||null}),'/api/profiles');
bindForm('session-form',f=>({title:f.get('title')}),'/api/sessions');
bindForm('attest-form',f=>({adults_verified:f.has('adults_verified'),informed_consent:f.has('informed_consent'),account_authorized:f.has('account_authorized'),terms_checked:f.has('terms_checked')}),'/api/attestations');
bindForm('ledger-form',f=>({platform:f.get('platform'),currency:f.get('currency'),category:f.get('category'),amount_minor:Math.round(parseFloat(f.get('amount'))*100)*(f.get('category')==='REFUND'?-1:1)}),'/api/ledger');
el('obs-check').onclick=async()=>{try{let d=await api('/api/obs/status');el('obs-status').textContent=JSON.stringify(d);note('Odczytano lokalny stan OBS. Nie sprawdzono odbioru na platformie.')}catch(e){note(e.message,false)}};
el('monitor-check').onclick=async()=>{try{const r=await api('/api/monitor/check','POST');await load();note('Pomiar: '+r.outcome+'; '+(r.reason_code||'bez ostrzeżeń'),r.outcome!=='ALERT')}catch(e){note(e.message,false)}};
el('monitor-reload').onclick=async()=>{try{await refreshMonitor();note('Odświeżono stan incydentów.')}catch(e){note(e.message,false)}};
el('obs-audit').onclick=async()=>{try{let d=await api('/api/obs/check','POST');el('obs-status').textContent=JSON.stringify(d);note('Uzgodniono stan sesji z lokalnym wyjściem OBS. Platforma niezweryfikowana.');await load()}catch(e){note(e.message,false)}};
async function displayStrategy(path,kind){try{const r=await api(path);let root=el('strategy-list');root.replaceChildren();for(const slot of r.plan){const head=kind==='10h'?'Godzina '+slot.hour+' · '+slot.goal:'Dzień '+slot.day+' · '+slot.phase;root.append(box(head,kind==='10h'?slot.operator_brief:slot.goal));}note('Wyświetlono szablon '+kind+'.')}catch(e){note(e.message,false)}}
el('strategy-10h').onclick=()=>displayStrategy('/api/strategy/ten-hour','10h');
el('strategy-30d').onclick=()=>displayStrategy('/api/strategy/thirty-day','30d');
el('reload').onclick=async()=>{try{await load();note('Odświeżono.')}catch(e){note(e.message,false)}};
async function refreshOperators(){
  const sessions=(await api('/api/auth/sessions')).sessions;
  const root=el('operators-list');root.replaceChildren();
  if(!sessions.length)root.append(node('p','Brak aktywnych sesji przeglądarkowych.'));
  for(const session of sessions){
    const d=box(session.subject,session.role+' · ważna do '+new Date(session.expires_at*1000).toLocaleString('pl-PL'));
    if(session.subject!==principalSubject)d.append(btn('UNIEWAŻNIJ SESJE',async()=>{
      const phrase=prompt('Potwierdź cofnięcie dostępu temu operatorowi. Wpisz UNIEWAŻNIJ:');
      if(phrase!=='UNIEWAŻNIJ')return;
      const result=await api('/api/auth/sessions/revoke','POST',{subject:session.subject});
      note('Unieważniono sesje: '+result.revoked_sessions);
      await refreshOperators();
    },true));
    root.append(d);
  }
}

async function bootstrap(){
  const me = await api('/api/auth/me');
  principalRole = me.role;
  principalSubject = me.subject;
  el('identity').textContent = me.role.toUpperCase()+' · '+me.subject;
  if(me.source === 'oidc_browser'){
    csrfToken=(await api('/api/auth/csrf')).csrf_token;
    el('logout').hidden=false;
    el('logout').onclick=async()=>{
      try{await api('/auth/logout','POST');window.location.replace('/auth/login')}
      catch(e){note(e.message,false)}
    };
  }
  if(isAdmin()){
    el('operators-card').hidden=false;
    el('operators-reload').onclick=async()=>{try{await refreshOperators()}catch(e){note(e.message,false)}};
    await refreshOperators();
  }
  if(!isAdmin()){
    el('attest-form').closest('section').hidden=true;
    el('ledger-form').closest('section').hidden=true;
  }
  if(!canOperate()){
    for(const id of ['session-form','profile-form','obs-audit','monitor-check'])el(id).hidden=true;
  }
  await load();
}
bootstrap().catch(e=>note(e.message,false));
