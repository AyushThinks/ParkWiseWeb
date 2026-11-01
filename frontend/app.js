const API = "/api";

let currentPage = "dashboard";
let slotsCache = [];
let sessionsCache = [];

const $ = (s) => document.querySelector(s);
const money = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits:2});

function extractErrorMessage(data, fallback = "Something went wrong.") {
  if (!data) return fallback;
  if (typeof data === "string") return data;
  if (data.detail) {
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(item => {
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join(" ") : "";
        const msg = item.msg || item.message || JSON.stringify(item);
        return field ? `${field}: ${msg}` : msg;
      }).join("; ");
    }
    if (typeof data.detail === "object") return JSON.stringify(data.detail);
  }
  if (data.message) return data.message;
  if (data.error) return data.error;
  return fallback;
}

async function request(path, options={}) {
  const token = localStorage.getItem("access_token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

  const res = await fetch(API + path, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/login.html";
    return null;
  }

  if (res.status === 403) {
    // If forbidden, user may be a customer trying to access admin
    window.location.href = "/customer";
    return null;
  }

  if (!res.ok) {
    let msg = "Something went wrong.";
    try {
      const d = await res.json();
      msg = extractErrorMessage(d, msg);
    } catch {
      try {
        const txt = await res.text();
        if (txt && txt.length < 200) msg = txt;
      } catch {}
    }
    throw new Error(msg);
  }

  if (res.status === 204) return null;
  return res.json();
}
function toast(message){const t=$("#toast");t.textContent=message;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2800)}
function setPage(page){
  currentPage=page;
  document.querySelectorAll(".nav-item[data-page]").forEach(b=>b.classList.toggle("active",b.dataset.page===page));
  const labels={dashboard:"Dashboard",vehicles:"Vehicles",slots:"Parking Slots",sessions:"Entry / Exit",bookings:"Bookings",reports:"Reports"};
  $("#crumbName").textContent=labels[page]; $("#pageTitle").innerHTML=page==="dashboard"?"Welcome to ParkWise <span>✦</span>":labels[page];
  $("#pageSubtitle").textContent=({dashboard:"Here's your parking facility at a glance.",vehicles:"Manage registered vehicles and customer details.",slots:"View availability and manage your parking inventory.",sessions:"Monitor vehicle arrivals, departures and parking fees.",bookings:"Manage upcoming parking reservations.",reports:"A clear picture of your parking facility performance."})[page];
  $("#primaryAction").style.display=["dashboard","vehicles","slots","bookings"].includes(page)?"inline-block":"none";
  $("#primaryAction").textContent=({dashboard:"＋ Add vehicle",vehicles:"＋ Add vehicle",slots:"＋ Add slot",bookings:"＋ New booking"})[page]||"＋ Add";
  renderPage();
}
async function renderPage(){
  const root=$("#pageContent"); root.innerHTML='<div class="loading">Loading…</div>';
  try{
    if(currentPage==="dashboard") await renderDashboard(root);
    if(currentPage==="vehicles") await renderVehicles(root);
    if(currentPage==="slots") await renderSlots(root);
    if(currentPage==="sessions") await renderSessions(root);
    if(currentPage==="bookings") await renderBookings(root);
    if(currentPage==="reports") await renderReports(root);
  }catch(e){root.innerHTML=`<div class="panel empty">Could not load data: ${escapeHtml(e.message)}<br><br><button class="primary-btn" onclick="renderPage()">Try again</button></div>`}
}
function escapeHtml(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function renderDashboard(root){
 const [d,slots,sessions]=await Promise.all([request("/dashboard"),request("/slots"),request("/sessions")]); slotsCache=slots;sessionsCache=sessions;
 const pct=d.total_slots?d.occupancy_percent:0;
 root.innerHTML=`
 <div class="stats">
  ${stat("▣",d.total_vehicles,"Registered vehicles","Across all vehicle types","#e9f3ff","#2688e8")}
  ${stat("P",d.occupied_slots,"Occupied slots",`${pct}% facility occupancy`,"#e7f9ef","#1db477")}
  ${stat("▤",d.available_slots,"Available slots","Ready for incoming vehicles","#f0eaff","#8055e8")}
  ${stat("₹",money(d.today_revenue),"Today's revenue","Completed parking sessions","#fff2e5","#e89a32")}
 </div>
 <div class="content-grid">
  <section class="panel"><div class="panel-head"><h3>Parking occupancy</h3><span class="muted">Live overview</span></div>
   <div class="occupancy"><div class="donut" style="--percent:${pct}%"><div class="donut-inner"><b>${pct}%</b><small>Occupied</small></div></div><div class="legend">
    <div class="legend-row"><span class="legend-label"><i class="dot" style="background:#6855e8"></i>Occupied</span><b>${d.occupied_slots}</b></div>
    <div class="legend-row"><span class="legend-label"><i class="dot" style="background:#e9e9f4"></i>Available</span><b>${d.available_slots}</b></div><hr style="border:0;border-top:1px solid var(--line);width:100%"><div class="legend-row"><span class="legend-label">Total capacity</span><b>${d.total_slots}</b></div>
   </div></div>
  </section>
  <section class="panel"><div class="panel-head"><h3>Recent entry / exit</h3><button class="link-btn" onclick="setPage('sessions')">View all →</button></div><div class="entry-list">
  ${sessions.slice(0,5).map(s=>`<div class="entry"><div class="entry-icon ${s.status==="completed"?"out":""}">${s.status==="active"?"➜":"↗"}</div><div class="entry-info"><b>${escapeHtml(s.vehicle)}</b><small>${s.status==="active"?"Entry":"Exit"} · ${new Date(s.entry_time).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}</small></div><span class="pill ${s.status==="active"?"green":"red"}">${s.status==="active"?"IN":"OUT"}</span></div>`).join("")||'<div class="empty">No vehicle activity yet.</div>'}
  </div></section>
  <section class="panel"><div class="panel-head"><h3>Quick actions</h3><span class="muted">Shortcuts</span></div><div class="quick-grid">
   <button class="quick-btn" onclick="openCheckIn()"><span>↘</span>Check in vehicle</button><button class="quick-btn" onclick="setPage('sessions')"><span>↗</span>Check out vehicle</button>
   <button class="quick-btn" onclick="openSlotModal()"><span>▤</span>Add parking slot</button><button class="quick-btn" onclick="openBookingModal()"><span>▦</span>New booking</button>
  </div></section>
 </div>
 <div class="lower-grid">
  <section class="panel"><div class="panel-head"><h3>Parking lot · Block A</h3><div class="slot-legend"><span><i style="background:#20b978"></i>Available</span><span><i style="background:#8065ed"></i>Occupied</span><span><i style="background:#e8b04b"></i>Reserved</span></div></div><div class="slot-grid">
   ${slots.slice(0,20).map(s=>`<button class="slot ${s.status}" title="${s.zone} · ${s.status}" onclick="setPage('slots')">${escapeHtml(s.code)}</button>`).join("")||'<div class="empty">No slots added yet.</div>'}
  </div></section>
  <section class="panel"><div class="panel-head"><h3>Recent activity</h3><span class="muted">Latest records</span></div><div class="activity">
   ${sessions.slice(0,4).map(s=>`<div class="activity-row"><div class="activity-symbol">${s.status==="active"?"▣":"₹"}</div><b>${s.status==="active"?"Vehicle parked":"Parking completed"} · ${escapeHtml(s.vehicle)}</b><small>${new Date(s.entry_time).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}</small></div>`).join("")||'<div class="empty">Activity will appear here.</div>'}
  </div></section>
 </div>`;
}
function stat(icon,value,label,foot,tint,accent){return `<div class="stat-card" style="--tint:${tint};--accent:${accent}"><div class="stat-top"><div class="stat-icon">${icon}</div><span class="muted" style="font-size:10px">PARKWISE</span></div><div class="stat-value">${value}</div><div class="stat-label">${label}</div><div class="stat-foot">${foot}</div></div>`}
async function renderVehicles(root){
 const rows=await request("/vehicles");
 root.innerHTML=`<section class="panel"><div class="toolbar"><input class="search-input" id="vehicleSearch" placeholder="Search registration or owner…"><span class="muted">${rows.length} registered vehicles</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>REGISTRATION</th><th>OWNER</th><th>PHONE</th><th>TYPE</th><th>ACTION</th></tr></thead><tbody id="vehicleRows">${vehicleRows(rows)}</tbody></table></div></section>`;
 $("#vehicleSearch").addEventListener("input",async e=>{const filtered=await request("/vehicles?search="+encodeURIComponent(e.target.value));$("#vehicleRows").innerHTML=vehicleRows(filtered)});
}
function vehicleRows(rows){return rows.map(v=>`<tr><td><b>${escapeHtml(v.registration_number)}</b></td><td>${escapeHtml(v.owner_name)}</td><td>${escapeHtml(v.phone||"—")}</td><td>${escapeHtml(v.vehicle_type)}</td><td class="table-actions"><button onclick="editVehicle(${v.id})">Edit</button> <button onclick="removeVehicle(${v.id})">Delete</button></td></tr>`).join("")||'<tr><td colspan="5" class="empty">No vehicles found.</td></tr>'}
async function renderSlots(root){
 const rows=await request("/slots");slotsCache=rows;
 root.innerHTML=`<section class="panel"><div class="toolbar"><div><b>${rows.length} parking slots</b><div class="muted" style="font-size:11px;margin-top:4px">Select a slot to see its current status.</div></div><select class="search-input" id="slotFilter"><option value="">All statuses</option><option>available</option><option>occupied</option></select></div><div class="slot-grid" id="slotGrid">${slotButtons(rows)}</div></section>`;
 $("#slotFilter").addEventListener("change",e=>$("#slotGrid").innerHTML=slotButtons(rows.filter(s=>!e.target.value||s.status===e.target.value)));
}
function slotButtons(rows){return rows.map(s=>`<button class="slot ${s.status}" onclick="slotInfo(${s.id})" title="${s.zone} · ${s.slot_type}">${escapeHtml(s.code)}<br><small>${s.status}</small></button>`).join("")||'<div class="empty">No slots. Add your first parking slot.</div>'}
async function renderSessions(root){
 const rows=await request("/sessions");sessionsCache=rows;
 root.innerHTML=`<section class="panel"><div class="panel-head"><h3>Parking sessions</h3><button class="primary-btn" onclick="openCheckIn()">＋ Check in vehicle</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>VEHICLE</th><th>OWNER</th><th>SLOT</th><th>ENTRY TIME</th><th>STATUS</th><th>ACTION</th></tr></thead><tbody>
 ${rows.map(s=>`<tr><td><b>${escapeHtml(s.vehicle)}</b></td><td>${escapeHtml(s.owner)}</td><td>${escapeHtml(s.slot)}</td><td>${new Date(s.entry_time).toLocaleString()}</td><td><span class="pill ${s.status==="active"?"green":"red"}">${s.status}</span></td><td class="table-actions">${s.status==="active"?`<button onclick="checkout(${s.id})">Check out</button>`:`${money(s.amount)}`}</td></tr>`).join("")||'<tr><td colspan="6" class="empty">No parking sessions yet.</td></tr>'}
 </tbody></table></div></section>`;
}
async function renderBookings(root){
 const [rows,slots]=await Promise.all([request("/bookings"),request("/slots")]);
 root.innerHTML=`<section class="panel"><div class="panel-head"><h3>Reservations</h3><button class="primary-btn" onclick="openBookingModal()">＋ New booking</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>BOOKING</th><th>CUSTOMER</th><th>VEHICLE</th><th>SLOT</th><th>START</th><th>STATUS</th></tr></thead><tbody>${rows.map(b=>`<tr><td>#BK-${b.id}</td><td>${escapeHtml(b.customer_name)}</td><td>${escapeHtml(b.vehicle_number)}</td><td>${slots.find(s=>s.id===b.slot_id)?.code||"—"}</td><td>${new Date(b.start_time).toLocaleString()}</td><td><span class="pill green">${b.status}</span></td></tr>`).join("")||'<tr><td colspan="6" class="empty">No bookings created yet.</td></tr>'}</tbody></table></div></section>`;
}
async function renderReports(root){
 const [d,s]=await Promise.all([request("/dashboard"),request("/sessions")]);
 const completed=s.filter(x=>x.status==="completed");
 root.innerHTML=`<div class="stats">${stat("▣",d.total_vehicles,"Registered vehicles","All vehicle records","#e9f3ff","#2688e8")}${stat("P",d.total_slots,"Total capacity","Parking spaces","#f0eaff","#8055e8")}${stat("✓",completed.length,"Completed sessions","Vehicle checkouts","#e7f9ef","#1db477")}${stat("₹",money(completed.reduce((a,x)=>a+Number(x.amount||0),0)),"Recorded revenue","All completed sessions","#fff2e5","#e89a32")}</div><section class="panel"><div class="panel-head"><h3>Session report</h3><button class="secondary-btn" onclick="downloadCSV()">Export CSV</button></div><p class="muted">A simple operational report of recorded parking sessions. Export this data for further TQM analysis.</p><div class="table-wrap"><table class="data-table"><thead><tr><th>VEHICLE</th><th>SLOT</th><th>ENTRY</th><th>EXIT</th><th>AMOUNT</th><th>STATUS</th></tr></thead><tbody>${s.map(x=>`<tr><td>${escapeHtml(x.vehicle)}</td><td>${escapeHtml(x.slot)}</td><td>${new Date(x.entry_time).toLocaleString()}</td><td>${x.exit_time?new Date(x.exit_time).toLocaleString():"—"}</td><td>${money(x.amount)}</td><td>${x.status}</td></tr>`).join("")||'<tr><td colspan="6" class="empty">No data available.</td></tr>'}</tbody></table></div></section>`;
}
function openModal(title,fields,onSave){$("#modalTitle").textContent=title;$("#modalFields").innerHTML=fields.map(f=>`<div class="field ${f.full?"full":""}"><label>${f.label}</label>${f.options?`<select name="${f.name}" ${f.required===false?"":"required"}>${f.options.map(o=>`<option value="${o.value}">${o.label}</option>`).join("")}</select>`:`<input name="${f.name}" type="${f.type||"text"}" placeholder="${f.placeholder||""}" ${f.required===false?"":"required"} ${f.pattern?`pattern="${f.pattern}"`:""} ${f.minlength?`minlength="${f.minlength}"`:""} ${f.maxlength?`maxlength="${f.maxlength}"`:""} ${f.title?`title="${f.title}"`:""} ${f.inputmode?`inputmode="${f.inputmode}"`:""} ${f.value!==undefined?`value="${escapeHtml(f.value)}"`:""}>`}</div>`).join("");$("#modal").classList.add("show");$("#modalForm").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target).entries());try{await onSave(data);$("#modal").classList.remove("show");toast("Saved successfully.");renderPage()}catch(err){toast(err.message)}}}
function openVehicleModal(v=null){openModal(v?"Edit vehicle":"Add vehicle",[
 {name:"registration_number",label:"Registration number",value:v?.registration_number,placeholder:"e.g. DL10AB1234",pattern:"(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9 -]{6,20}",minlength:6,maxlength:20,title:"Use 6–20 letters and digits, including at least one letter and one number."},
 {name:"owner_name",label:"Owner name",value:v?.owner_name,pattern:"[A-Za-z][A-Za-z .'-]{1,99}",minlength:2,maxlength:100,title:"Enter a valid name using letters and spaces."},
 {name:"phone",label:"Phone number",value:v?.phone,required:false,placeholder:"10-digit mobile number",pattern:"[6-9][0-9]{9}",minlength:10,maxlength:10,inputmode:"numeric",title:"Enter a valid 10-digit Indian mobile number."},
 {name:"vehicle_type",label:"Vehicle type",options:["car","bike","suv","other"].map(x=>({value:x,label:x.toUpperCase()}))}
],d=>request(v?`/vehicles/${v.id}`:"/vehicles",{method:v?"PATCH":"POST",body:JSON.stringify(d)}))}
async function editVehicle(id){const v=(await request("/vehicles")).find(x=>x.id===id);openVehicleModal(v)}
async function removeVehicle(id){if(!confirm("Delete this vehicle record?"))return;try{await request("/vehicles/"+id,{method:"DELETE"});toast("Vehicle deleted.");renderPage()}catch(e){toast(e.message)}}
function openSlotModal(){openModal("Add parking slot",[{name:"code",label:"Slot code",placeholder:"e.g. A21"},{name:"zone",label:"Parking zone",value:"Block A"},{name:"slot_type",label:"Slot type",options:["car","bike","suv"].map(x=>({value:x,label:x.toUpperCase()}))}],d=>request("/slots",{method:"POST",body:JSON.stringify(d)}))}
function slotInfo(id){const s=slotsCache.find(x=>x.id===id);if(!s)return;const msg=`${s.code} · ${s.zone}\nStatus: ${s.status}\nType: ${s.slot_type}`;if(s.status==="available"&&confirm(msg+"\n\nDelete this slot?"))request("/slots/"+id,{method:"DELETE"}).then(()=>{toast("Slot deleted.");renderPage()}).catch(e=>toast(e.message));else toast(msg.replace(/\n/g," · "))}
function openCheckIn(){openModal("Check in vehicle",[{name:"vehicle_number",label:"Vehicle registration",placeholder:"DL10AB1234"},{name:"slot_code",label:"Available slot",options:slotsCache.filter(s=>s.status==="available").map(s=>({value:s.code,label:s.code+" · "+s.zone}))}],d=>request("/check-in?"+new URLSearchParams(d),{method:"POST"}))}
async function checkout(id){if(!confirm("Confirm vehicle checkout?"))return;try{const r=await request("/check-out/"+id,{method:"POST"});toast(`Checkout complete · ${money(r.amount)}`);renderPage()}catch(e){toast(e.message)}}
async function openBookingModal(){const slots=await request("/slots");openModal("Create parking booking",[{name:"vehicle_number",label:"Vehicle number"},{name:"customer_name",label:"Customer name"},{name:"slot_id",label:"Parking slot",options:slots.map(s=>({value:s.id,label:s.code+" ("+s.status+")"}))},{name:"start_time",label:"Start time",type:"datetime-local"},{name:"end_time",label:"End time",type:"datetime-local"}],d=>request("/bookings",{method:"POST",body:JSON.stringify({...d,slot_id:Number(d.slot_id),start_time:new Date(d.start_time).toISOString(),end_time:new Date(d.end_time).toISOString()})}))}
function downloadCSV(){request("/sessions").then(rows=>{const cols=["vehicle","owner","slot","entry_time","exit_time","amount","status"];const csv=[cols.join(","),...rows.map(r=>cols.map(k=>JSON.stringify(r[k]??"")).join(","))].join("\n");const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"}));a.download="parkwise-sessions.csv";a.click();URL.revokeObjectURL(a.href)})}
$("#primaryAction").onclick=()=>({dashboard:()=>openVehicleModal(),vehicles:()=>openVehicleModal(),slots:()=>openSlotModal(),bookings:()=>openBookingModal()})[currentPage]?.();
$("#closeModal").onclick=$("#cancelModal").onclick=()=>$("#modal").classList.remove("show");
$("#themeToggle").onclick=()=>{document.body.classList.toggle("dark");localStorage.setItem("parkwise-theme",document.body.classList.contains("dark")?"dark":"light")};
if(localStorage.getItem("parkwise-theme")==="dark")document.body.classList.add("dark");

const logoutBtn = $("#logoutBtn");
if (logoutBtn) {
  logoutBtn.onclick = async () => {
    try {
      await fetch(API + "/auth/logout", { method: "POST" });
    } catch {}
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    window.location.href = "/login.html";
  };
}

document.querySelectorAll(".nav-item[data-page]").forEach(b=>b.addEventListener("click",()=>setPage(b.dataset.page)));

async function init(){
  const token = localStorage.getItem("access_token");
  if (!token) {
    window.location.href = "/login.html";
    return;
  }

  try{
    const me = await request("/auth/me");
    if (!me) return;

    if (me.role !== "ADMIN") {
      // Normal customers must never access admin panel
      window.location.href = "/customer";
      return;
    }

    const nameEl = $("#adminName");
    const avatarEl = $("#adminAvatar");
    if (nameEl && me.full_name) nameEl.textContent = me.full_name;
    if (avatarEl && me.full_name) avatarEl.textContent = me.full_name.charAt(0).toUpperCase();

    setPage("dashboard");
  }catch(e){
    if (e.message && e.message.includes("401")) {
      window.location.href = "/login.html";
      return;
    }
    const root=$("#pageContent");
    root.innerHTML=`<div class="panel empty">Could not connect to the ParkWise API: ${escapeHtml(e.message)}<br><br>Check that the FastAPI server is running, then refresh this page.</div>`;
    toast("API connection failed.");
  }
}
init();
