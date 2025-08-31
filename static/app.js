const state = { emails: [], byId: {}, me: { connected: false }, gfilter: 'unread', gcat: '', search: '', filterType: 'all' };
const list = document.getElementById("list");
const refresh = document.getElementById("refresh");
const connect = document.getElementById("connect");
const userEl = document.getElementById("user");
const statusEl = document.getElementById("status");
const sumAll = document.getElementById("sumAll");
const extAll = document.getElementById("extAll");
const markAll = document.getElementById("markAll");
const searchInput = document.getElementById("search");
const logoutBtn = document.getElementById("logout");
let modalEmailId = null;
function ftime(s){try{return new Date(s).toLocaleString()}catch(e){return""}}
async function req(url,opt){const r=await fetch(url,opt);if(!r.ok)return null;return r.json()}
function setMe(){if(state.me.connected){if(connect)connect.style.display='none';if(userEl)userEl.textContent=state.me.email?('Connected as '+state.me.email):'Connected'}else{if(connect)connect.style.display='inline-block';if(userEl)userEl.textContent=''}}
function passFilter(e){
    if(state.search){
        const q=state.search.toLowerCase();
        const hay=((e.subject||'')+' '+(e.sender||'')+' '+(e.snippet||'')).toLowerCase();
        if(!hay.includes(q))return false;
    }
    if(state.filterType && state.filterType !== 'all'){
        if(state.filterType === 'tasks' && (!e.actions || !e.actions.some(a=>a.type==='tasks'))) return false;
        if(state.filterType === 'meetings' && (!e.actions || !e.actions.some(a=>a.type==='meetings'))) return false;
        if(state.filterType === 'deadlines' && (!e.actions || !e.actions.some(a=>a.type==='deadlines'))) return false;
        if(state.filterType === 'contacts' && (!e.actions || !e.actions.some(a=>a.type==='contacts'))) return false;
        if(state.filterType === 'links' && (!e.actions || !e.actions.some(a=>a.type==='links'))) return false;
        if(state.filterType === 'phone_numbers' && (!e.actions || !e.actions.some(a=>a.type==='phone_numbers'))) return false;
        if(state.filterType === 'locations' && (!e.actions || !e.actions.some(a=>a.type==='locations'))) return false;
        if(state.filterType === 'follow_ups' && (!e.actions || !e.actions.some(a=>a.type==='follow_ups'))) return false;
    }
    return true;
}
function groupActionsByType(actions) {
    const types = ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"];
    const grouped = {};
    actions.forEach(a => {
        if (!grouped[a.type]) grouped[a.type] = [];
        grouped[a.type].push(a);
    });
    return types.map(type => ({ type, items: grouped[type] || [] })).filter(g => g.items.length > 0);
}
function card(e){
    const link='<a class="btn" href="'+(e.gmail_url||'#')+'" target="_blank">Open</a>';
    const details='<button class="btn" data-act="details" data-id="'+e.id+'">Details</button>';
    const summ='<button class="btn" data-act="summ" data-id="'+e.id+'">Summarize</button>';
    const extract='<button class="btn" data-act="extract" data-id="'+e.id+'">Extract Actions</button>';
    const summary = (e.summary && e.summary.summary_text) ? `<div class="label">Summary</div>${formatSummary(e.summary.summary_text)}` : '';
    const actions = (e.actions && e.actions.length) ? formatGroupedActions(e.actions) : '';
    return `<div class="card">
        <div class="row">
            <div>
                <div class="subject">${e.subject||'(no subject)'}</div>
                <div class="meta">${e.sender||''} · ${ftime(e.received_at)||''}</div>
            </div>
            <div style="display:flex;gap:8px">${details+link}</div>
        </div>
        <div id="summary-actions-${e.id}">
            ${summary}
            ${actions}
        </div>
        <div class="actions">${summ+extract}</div>
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
        out += `<li><b>${a.type ? a.type.charAt(0).toUpperCase() + a.type.slice(1) : ''}:</b> ${a.title || ''}${a.when_text ? ' <span class="muted">(' + a.when_text + ')</span>' : ''}${a.value && !a.title ? a.value : ''}</li>`;
    });
    out += '</ul>';
    return `<div class="actions-list">${out}</div>`;
}
function formatGroupedActions(actions) {
    const groups = groupActionsByType(actions);
    if (!groups.length) return '';
    return groups.map(g => {
        const label = g.type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        return `<div class="label">${label}</div>${formatActions(g.items)}`;
    }).join("");
}
function render(){
    let arr=state.emails.filter(passFilter);
    console.log("Rendering emails after filter:", arr.map(e => ({
        id: e.id,
        actions: e.actions
    })));
    arr=arr.slice().sort(function(a,b){
        const ad=a.received_at?new Date(a.received_at).getTime():0;
        const bd=b.received_at?new Date(b.received_at).getTime():0;
        return bd-ad;
    });
    const rows=arr.map(card).join("");
    list.innerHTML=rows;
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
    render();
    if(refresh)refresh.disabled=false;
    if(statusEl)statusEl.textContent='';
}
async function summarizeAll(){
    if(statusEl)statusEl.textContent='Summarizing all emails...';
    const summaries = await req('/api/summarize_all',{method:'POST'});
    if (Array.isArray(summaries)) {
        summaries.forEach(s => {
            const email = state.emails.find(e => e.id === s.email_id);
            if (email) email.summary = s;
        });
    }
    render();
    if(statusEl)statusEl.textContent='';
}
async function extractAll(){
    if(statusEl)statusEl.textContent='Extracting actions for all emails...';
    const actionsArr = await req('/api/extract_all',{method:'POST'});
    if (Array.isArray(actionsArr)) {
        actionsArr.forEach(a => {
            const email = state.emails.find(e => e.id === a.email_id);
            if (!email) {
                console.warn("extractAll: No email found for email_id", a.email_id);
                return;
            }
            if (typeof a.actions === "object" && a.actions !== null) {
                email.actions = [].concat(
                    (a.actions.tasks || []).map(t => ({...t, type: "tasks"})),
                    (a.actions.meetings || []).map(m => ({...m, type: "meetings"})),
                    (a.actions.deadlines || []).map(d => ({...d, type: "deadlines"})),
                    (a.actions.contacts || []).map(c => ({...c, type: "contacts"})),
                    (a.actions.links || []).map(l => ({...l, type: "links"})),
                    (a.actions.phone_numbers || []).map(p => ({...p, type: "phone_numbers"})),
                    (a.actions.locations || []).map(loc => ({...loc, type: "locations"})),
                    (a.actions.follow_ups || []).map(f => ({...f, type: "follow_ups"}))
                );
            } else {
                email.actions = [];
            }
        });
    }
    render();
    if(statusEl)statusEl.textContent='';
}
async function reloadEmailsWithSummariesAndActions(){
    const qs=new URLSearchParams({limit:'10',filter:state.gfilter});
    if(state.gcat)qs.append('category',state.gcat);
    const data=await req('/api/emails?'+qs.toString());
    state.emails=Array.isArray(data)?data:[];
    state.emails.forEach(e=>{state.byId[e.id]=e});
    render();
}
async function summarizeOne(id){
    const sEl=document.getElementById('sum-'+id);
    if(sEl)sEl.textContent='Summarizing...';
    const body=JSON.stringify({email_id:id,force:true});
    const res=await req('/api/summarize',{method:'POST',headers:{'Content-Type':'application/json'},body});
    const out=(res&&res.summary_text)||'';
    if(sEl)sEl.innerHTML=formatSummary(out)||'(no summary)';
    const email = state.emails.find(e => e.id === id);
    if (email) email.summary = res;
    render();
}
async function extractOne(id){
    const sEl=document.getElementById('actions-'+id);
    if(sEl)sEl.textContent='Extracting actions...';
    const body=JSON.stringify({email_id:id,force:true});
    const res=await req('/api/extract_actions',{method:'POST',headers:{'Content-Type':'application/json'},body});
    if(sEl)sEl.innerHTML=formatActions(res && res.actions ? res.actions : []);
    const email = state.emails.find(e => e.id === id);
    if (email && res && typeof res.actions === "object" && res.actions !== null) {
        email.actions = [].concat(
            (res.actions.tasks || []).map(t => ({...t, type: "tasks"})),
            (res.actions.meetings || []).map(m => ({...m, type: "meetings"})),
            (res.actions.deadlines || []).map(d => ({...d, type: "deadlines"})),
            (res.actions.contacts || []).map(c => ({...c, type: "contacts"})),
            (res.actions.links || []).map(l => ({...l, type: "links"})),
            (res.actions.phone_numbers || []).map(p => ({...p, type: "phone_numbers"})),
            (res.actions.locations || []).map(loc => ({...loc, type: "locations"})),
            (res.actions.follow_ups || []).map(f => ({...f, type: "follow_ups"}))
        );
    } else {
        email.actions = [];
    }
    render();
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
            <div class="label">Summary</div>
            <div>${email.summary ? formatSummary(email.summary.summary_text) : "(no summary)"}</div>
            <div class="label">Action Items</div>
            <div>${email.actions ? formatGroupedActions(email.actions) : "(no actions)"}</div>
            <div><b>Received:</b> ${ftime(email.received_at) || ""}</div>
            <div><b>Gmail URL:</b> <a href="${email.gmail_url || "#"}" target="_blank">Open</a></div>
            <div style="margin-top:12px;display:flex;gap:8px;">
                <button id="modal-import" class="btn">Import Actions</button>
                <button id="modal-copy" class="btn">Copy Summary</button>
                <button id="modal-close" class="btn">Close</button>
            </div>
        `;
        modal.classList.remove("hidden");
        const importBtn = document.getElementById("modal-import");
        const copyBtn = document.getElementById("modal-copy");
        const closeBtn = document.getElementById("modal-close");
        if (importBtn) {
            importBtn.onclick = () => {
                alert("Import Actions: " + JSON.stringify(email.actions));
            };
        }
        if (copyBtn) {
            copyBtn.onclick = () => {
                const temp = document.createElement("textarea");
                temp.value = email.summary ? email.summary.summary_text : "";
                document.body.appendChild(temp);
                temp.select();
                document.execCommand("copy");
                document.body.removeChild(temp);
                alert("Summary copied to clipboard.");
            };
        }
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.add("hidden");
                modalEmailId = null;
            };
        }
    }
}
if (searchInput) {
    searchInput.addEventListener('input', function() {
        state.search = searchInput.value;
        render();
    });
}
if (logoutBtn) {
    logoutBtn.addEventListener('click', async function() {
        await req('/auth/logout', {method: 'POST'});
        window.location.reload();
    });
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
        await summarizeAll();
    });
}
if(extAll){
    extAll.addEventListener('click',async function(){
        await extractAll();
    });
}
if(refresh){
    refresh.addEventListener('click',async function(){
        await loadEmails();
        await summarizeAll();
        await extractAll();
    });
}
if(markAll){
    markAll.addEventListener('click',async function(){
        // await req('/api/mark_all_read',{method:'POST'});
        // await loadEmails();
    });
}
document.addEventListener('DOMContentLoaded',async ()=>{
    await loadMe();
    await loadEmails();
    await summarizeAll();
    await extractAll();
});
const filterTabs = document.querySelectorAll('.filters .tab');
filterTabs.forEach(tab => {
    tab.addEventListener('click', function() {
        filterTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.filterType = tab.getAttribute('data-filter');
        render();
    });
});
const gTabs = document.querySelectorAll('.gtab');
gTabs.forEach(tab => {
    tab.addEventListener('click', function() {
        gTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.gfilter = tab.getAttribute('data-gfilter');
        loadEmails();
        summarizeAll();
        extractAll();
    });
});
const cTabs = document.querySelectorAll('.ctab');
cTabs.forEach(tab => {
    tab.addEventListener('click', function() {
        cTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.gcat = tab.getAttribute('data-gcat');
        loadEmails();
        summarizeAll();
        extractAll();
    });
});
function formatGroupedActions(actions) {
    const types = ["tasks", "meetings", "deadlines", "contacts", "links", "phone_numbers", "locations", "follow_ups"];
    const grouped = {};
    actions.forEach(a => {
        if (!grouped[a.type]) grouped[a.type] = [];
        grouped[a.type].push(a);
    });
    return types.map(type => {
        if (!grouped[type] || !grouped[type].length) return '';
        const label = type.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        return `<div class="label">${label}</div>${formatActions(grouped[type])}`;
    }).join("");
}
