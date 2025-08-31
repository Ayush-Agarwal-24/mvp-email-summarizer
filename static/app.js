const state = { emails: [], byId: {}, me: { connected: false }, gfilter: 'unread', gcat: '', search: '' };
const list = document.getElementById("list");
const refresh = document.getElementById("refresh");
const connect = document.getElementById("connect");
const userEl = document.getElementById("user");
const statusEl = document.getElementById("status");
const sumAll = document.getElementById("sumAll");
const extAll = document.getElementById("extAll");
let modalEmailId = null;
function ftime(s){try{return new Date(s).toLocaleString()}catch(e){return""}}
async function req(url,opt){const r=await fetch(url,opt);if(!r.ok)return null;return r.json()}
function setMe(){if(state.me.connected){if(connect)connect.style.display='none';if(userEl)userEl.textContent=state.me.email?('Connected as '+state.me.email):'Connected'}else{if(connect)connect.style.display='inline-block';if(userEl)userEl.textContent=''}}
function passFilter(e){if(state.search){const q=state.search.toLowerCase();const hay=((e.subject||'')+' '+(e.sender||'')+' '+(e.snippet||'')).toLowerCase();if(!hay.includes(q))return false}return true}
function card(e){
    const link='<a class="btn" href="'+(e.gmail_url||'#')+'" target="_blank">Open</a>';
    const details='<button class="btn" data-act="details" data-id="'+e.id+'">Details</button>';
    const summ='<button class="btn" data-act="summ" data-id="'+e.id+'">Summarize</button>';
    const extract='<button class="btn" data-act="extract" data-id="'+e.id+'">Extract Actions</button>';
    const summary = (e.summary && e.summary.summary_text) ? formatSummary(e.summary.summary_text) : '';
    const actions = (e.actions && e.actions.length) ? formatActions(e.actions) : '';
    return `<div class="card">
        <div class="row">
            <div>
                <div class="subject">${e.subject||'(no subject)'}</div>
                <div class="meta">${e.sender||''} · ${ftime(e.received_at)||''}</div>
            </div>
            <div style="display:flex;gap:8px">${details+link}</div>
        </div>
        <div class="summary" id="sum-${e.id}">${summary}</div>
        <div class="actions">${summ+extract}</div>
        <div class="actions-list" id="actions-${e.id}">${actions}</div>
    </div>`;
}
function formatSummary(text) {
    if (!text) return '';
    let out = text.replace(/Please open the mail in your mailbox to learn more/g, '').trim();
    if (window.marked) {
        out = marked.parse(out);
    } else {
        out = out.replace(/^- /gm, '<li>').replace(/\n- /g, '</li><li>');
        if (out.startsWith('<li>')) out = `<ul>${out}</li></ul>`;
    }
    return `<div class="summary-text">${out}</div><div class="summary-footer">Please open the mail in your mailbox to learn more.</div>`;
}
function formatActions(actions) {
    if (!actions || !actions.length) return '';
    let out = '<ul>';
    actions.forEach(a => {
        out += `<li><b>${a.type ? a.type.charAt(0).toUpperCase() + a.type.slice(1) : ''}:</b> ${a.title || ''}${a.when_text ? ' <span class="muted">(' + a.when_text + ')</span>' : ''}</li>`;
    });
    out += '</ul>';
    return `<div class="actions-list">${out}</div>`;
}
async function loadMe(){const me=await req('/api/me');state.me=me||{connected:false};setMe();if(!state.me.connected){if(statusEl)statusEl.textContent='Connect Gmail to start'}}
async function loadEmails(){
    if(!state.me.connected){list.innerHTML='';return}
    if(statusEl)statusEl.textContent='Loading emails...';
    if(refresh)refresh.disabled=true;
    const qs=new URLSearchParams({limit:'10',filter:state.gfilter});
    if(state.gcat)qs.append('category',state.gcat);
    const data=await req('/api/emails?'+qs.toString());
    state.emails=Array.isArray(data)?data:[];
    state.emails.forEach(e=>{state.byId[e.id]=e});
    await Promise.all(state.emails.map(async e => {
        e.summary = await req(`/api/email/${e.id}/summary`);
        e.actions = await req(`/api/email/${e.id}/actions`);
    }));
    if(refresh)refresh.disabled=false;
    render();
    if(statusEl)statusEl.textContent='';
    if(statusEl)statusEl.textContent='Summarizing all emails...';
    await req('/api/summarize_all',{method:'POST'});
    if(statusEl)statusEl.textContent='Extracting actions for all emails...';
    await req('/api/extract_all',{method:'POST'});
    if(statusEl)statusEl.textContent='';
}
async function summarizeOne(id){
    const sEl=document.getElementById('sum-'+id);
    if(sEl)sEl.textContent='Summarizing...';
    const body=JSON.stringify({email_id:id,force:true});
    const res=await req('/api/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body});
    const out=(res&&res.summary_text)||'';
    if(sEl)sEl.innerHTML=formatSummary(out)||'(no summary)';
}
async function extractOne(id){
    const sEl=document.getElementById('actions-'+id);
    if(sEl)sEl.textContent='Extracting actions...';
    const body=JSON.stringify({email_id:id,force:true});
    const res=await req('/api/extract_actions',{method:'POST',headers:{'Content-Type':'application/json'},body});
    if(sEl)sEl.innerHTML=formatActions(res && res.actions ? res.actions : []);
}
function showDetails(id){
    modalEmailId = id;
    const email = state.byId[id];
    if (!email) return;
    const modal = document.getElementById("modal");
    const content = document.getElementById("modal-content");
    if (modal && content) {
        content.innerHTML = `
            <div><b>Sender:</b> ${email.sender || ""}</div>
            <div><b>Subject:</b> ${email.subject || ""}</div>
            <div><b>Summary:</b> ${email.summary ? formatSummary(email.summary.summary_text) : "(no summary)"}</div>
            <div><b>Actions:</b> ${email.actions ? formatActions(email.actions) : "(no actions)"}</div>
            <div><b>Received:</b> ${ftime(email.received_at) || ""}</div>
            <div><b>Gmail URL:</b> <a href="${email.gmail_url || "#"}" target="_blank">Open</a></div>
        `;
        modal.classList.remove("hidden");
    }
}
list.addEventListener('click',function(ev){
    const b=ev.target.closest('button');
    if(!b)return;
    const id=b.getAttribute('data-id');
    const act=b.getAttribute('data-act');
    if(act==='summ')summarizeOne(Number(id));
    if(act==='extract')extractOne(Number(id));
    if(act==='details')showDetails(Number(id));
});
if(sumAll){
    sumAll.addEventListener('click',async function(){
        if(statusEl)statusEl.textContent='Summarizing all emails...';
        await req('/api/summarize_all',{method:'POST'});
        await loadEmails();
        if(statusEl)statusEl.textContent='All emails summarized.';
    });
}
if(extAll){
    extAll.addEventListener('click',async function(){
        if(statusEl)statusEl.textContent='Extracting actions for all emails...';
        await req('/api/extract_all',{method:'POST'});
        await loadEmails();
        if(statusEl)statusEl.textContent='Actions extracted for all emails.';
    });
}
document.addEventListener('DOMContentLoaded',()=>{
    loadMe().then(loadEmails);
    const modal = document.getElementById("modal");
    const closeBtn = document.getElementById("modal-close");
    if (modal && closeBtn) {
        closeBtn.addEventListener("click", () => {
            modal.classList.add("hidden");
            modalEmailId = null;
        });
    }
});
