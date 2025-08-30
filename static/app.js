const state = { filter: "all", emails: [], byId: {}, acts: {}, me: { connected: false } };
const list = document.getElementById("list");
const refresh = document.getElementById("refresh");
const connect = document.getElementById("connect");
const userEl = document.getElementById("user");
function ftime(s) { try { return new Date(s).toLocaleString() } catch (e) { return "" } }
function card(e) { const sid = "s-" + e.id; const chips = '<div class="chips" id="' + sid + '"></div>'; const link = '<a class="btn" href="' + (e.gmail_url || "#") + '" target="_blank">Open</a>'; return '<div class="card"><div class="row"><div><div class="subject">' + (e.subject || "(no subject)") + '</div><div class="meta">' + (e.sender || "") + ' • ' + (ftime(e.received_at) || "") + '</div></div><div>' + link + '</div></div><div class="summary" id="sum-' + e.id + '"></div>' + chips + '<div class="actions"><button class="btn" data-act="done" data-id="' + e.id + '">Done</button><button class="btn" data-act="snooze" data-id="' + e.id + '">Snooze 1d</button></div></div>' }
function passFilter(e) { if (state.filter === "all") return true; const a = state.acts[e.id]; if (!a) return false; if (state.filter === "tasks") return (a.tasks || []).length > 0; if (state.filter === "meetings") return (a.meetings || []).length > 0; if (state.filter === "deadlines") return (a.deadlines || []).length > 0; return true }
function render() { const rows = state.emails.filter(passFilter).map(card).join(""); list.innerHTML = rows; state.emails.forEach(function (e) { loadSummary(e.id) }) }
function setMe() { if (state.me.connected) { if (connect) connect.style.display = 'none'; if (userEl) userEl.textContent = state.me.email ? ('Connected as ' + state.me.email) : 'Connected' } else { if (connect) connect.style.display = 'inline-block'; if (userEl) userEl.textContent = '' } }
async function req(url, opt) { const r = await fetch(url, opt); if (!r.ok) return null; return r.json() }
async function loadMe() { const me = await req('/api/me'); state.me = me || { connected: false }; setMe() }
async function loadEmails() { const data = await req('/api/emails?limit=50'); state.emails = Array.isArray(data) ? data : []; state.byId = {}; state.emails.forEach(function (e) { state.byId[e.id] = e }); render() }
async function loadSummary(id) {
    const res = await req('/api/summarize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email_id: id }) }); if (!res) return; const sEl = document.getElementById('sum-' + id); if (sEl) sEl.textContent = res.summary_text || ""; let acts = { tasks: [], meetings: [], deadlines: [] }; try { acts = JSON.parse(res.actions_json || "{}") } catch (e) { }
    state.acts[id] = acts; const chipsEl = document.getElementById('s-' + id); if (!chipsEl) return; const all = []; (acts.tasks || []).forEach(function (a) { all.push('task: ' + (a.title || "")) }); (acts.meetings || []).forEach(function (a) { all.push('meeting: ' + (a.title || "") + (a.when_text ? ' • ' + a.when_text : "")) }); (acts.deadlines || []).forEach(function (a) { all.push('deadline: ' + (a.title || "") + (a.when_text ? ' • ' + a.when_text : "")) }); chipsEl.innerHTML = all.map(function (x) { return '<span class="chip">' + x + '</span>' }).join("")
}
list.addEventListener('click', async function (ev) {
    const b = ev.target.closest('button.btn'); if (!b) return; const act = b.getAttribute('data-act'); const id = parseInt(b.getAttribute('data-id'), 10); if (act === 'done') { await req('/api/items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email_id: id, type: 'task', title: 'Done' }) }) }
    if (act === 'snooze') { const until = new Date(Date.now() + 86400000).toISOString(); const r = await req('/api/items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email_id: id, type: 'task', title: 'Snoozed' }) }); if (r && r.id) { await req('/api/items/' + r.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'snoozed', snooze_until: until }) }) } }
})
document.querySelectorAll('.tab').forEach(function (btn) { btn.addEventListener('click', function () { document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('active') }); btn.classList.add('active'); state.filter = btn.getAttribute('data-filter') || 'all'; render() }) })
refresh.addEventListener('click', function(){ loadEmails() })
loadMe().then(loadEmails)
