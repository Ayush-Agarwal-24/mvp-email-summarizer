const state = { emails: [], byId: {}, me: { connected: false }, gfilter: 'unread', gcat: '', search: '' };
const list = document.getElementById("list");
const refresh = document.getElementById("refresh");
const connect = document.getElementById("connect");
const userEl = document.getElementById("user");
const statusEl = document.getElementById("status");
let modalEmailId = null;
function ftime(s){try{return new Date(s).toLocaleString()}catch(e){return""}}
async function req(url,opt){const r=await fetch(url,opt);if(!r.ok)return null;return r.json()}
function setMe(){if(state.me.connected){if(connect)connect.style.display='none';if(userEl)userEl.textContent=state.me.email?('Connected as '+state.me.email):'Connected'}else{if(connect)connect.style.display='inline-block';if(userEl)userEl.textContent=''}}
function passFilter(e){if(state.search){const q=state.search.toLowerCase();const hay=((e.subject||'')+' '+(e.sender||'')+' '+(e.snippet||'')).toLowerCase();if(!hay.includes(q))return false}return true}
function card(e){const link='<a class="btn" href="'+(e.gmail_url||'#')+'" target="_blank">Open</a>';const details='<button class="btn" data-act="details" data-id="'+e.id+'">Details</button>';const summ='<button class="btn" data-act="summ" data-id="'+e.id+'">Summarize</button>';return '<div class="card"><div class="row"><div><div class="subject">'+(e.subject||'(no subject)')+'</div><div class="meta">'+(e.sender||'')+' · '+(ftime(e.received_at)||'')+'</div></div><div style="display:flex;gap:8px">'+details+link+'</div></div><div class="summary" id="sum-'+e.id+'"></div><div class="actions">'+summ+'</div></div>'}
function render(){let arr=state.emails.filter(passFilter);arr=arr.slice().sort(function(a,b){const ad=a.received_at?new Date(a.received_at).getTime():0;const bd=b.received_at?new Date(b.received_at).getTime():0;return bd-ad});const rows=arr.map(card).join("");list.innerHTML=rows}
async function loadMe(){const me=await req('/api/me');state.me=me||{connected:false};setMe();if(!state.me.connected){if(statusEl)statusEl.textContent='Connect Gmail to start'}}
async function loadEmails(){if(!state.me.connected){list.innerHTML='';return}if(statusEl)statusEl.textContent='Loading emails...';if(refresh)refresh.disabled=true;const qs=new URLSearchParams({limit:'50',filter:state.gfilter});if(state.gcat)qs.append('category',state.gcat);const data=await req('/api/emails?'+qs.toString());state.emails=Array.isArray(data)?data:[];state.emails.forEach(e=>{state.byId[e.id]=e});if(refresh)refresh.disabled=false;render();if(statusEl)statusEl.textContent=''}
async function summarizeOne(id){const sEl=document.getElementById('sum-'+id);if(sEl)sEl.textContent='Summarizing...';const body=JSON.stringify({email_id:id,force:true});const res=await req('/api/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body});const out=(res&&res.summary_text)||'';if(sEl)sEl.textContent=out||'(no summary)'}
list.addEventListener('click',function(ev){const b=ev.target.closest('button');if(!b)return;const id=b.getAttribute('data-id');const act=b.getAttribute('data-act');if(act==='summ')summarizeOne(Number(id))});
document.addEventListener('DOMContentLoaded',()=>{loadMe().then(loadEmails)});
