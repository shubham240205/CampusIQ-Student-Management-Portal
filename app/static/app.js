let token = localStorage.getItem("campusiq_token");
let me = null, subjects = [], students = [], charts = {}, currentStudentPage = 1;
const $ = id => document.getElementById(id);
const api = async (path, options={}) => {
  const headers = {...(options.headers||{}), ...(token ? {Authorization:`Bearer ${token}`} : {})};
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"]="application/json";
  const res = await fetch(path,{...options,headers,cache:"no-store"});
  if(!res.ok){let msg=`Request failed (${res.status})`;try{msg=(await res.json()).detail||msg}catch{};throw new Error(msg)}
  return res.json();
};
const initials = name => (name||"?").split(" ").map(x=>x[0]).slice(0,2).join("").toUpperCase();
const statusClass = s => s==="At Risk"?"risk":s==="Needs Attention"?"warn":"good";
const pct = n => n===null || n===undefined ? "Not recorded" : `${Number(n).toFixed(1)}%`;
function toast(msg){const el=$("toast");if(!el)return;el.textContent=msg;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),3000)}
function showLogin(){ $("login-screen").classList.remove("hidden");$("app").classList.add("hidden"); }
function showLoadError(err){
  console.error("CampusIQ dashboard load failed:",err);
  const target=$("overview-table");
  if(target) target.innerHTML=`<div class="panel" style="padding:18px"><b>We couldn't load the dashboard data.</b><p class="muted">${String(err.message||err)}</p><button class="primary" onclick="location.reload()">Retry</button></div>`;
  toast(`Dashboard data error: ${err.message||err}`);
}
async function boot(){
  if(!token){showLogin();return}
  try{
    me=await api("/api/me");
    $("login-screen").classList.add("hidden");$("app").classList.remove("hidden");
    setupShell();
    try { await loadOverview(); } catch(err) { showLoadError(err); }
  } catch(err){
    token=null;localStorage.removeItem("campusiq_token");showLogin();
    if(err.message!=="Invalid or expired session") $("login-error").textContent=err.message;
  }
}
$("login-form").addEventListener("submit",async e=>{
  e.preventDefault();$("login-error").textContent="";
  try{
    const body=new URLSearchParams({username:$("email").value,password:$("password").value});
    const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body});
    const data=await r.json();if(!r.ok)throw new Error(data.detail||"Login failed");
    token=data.access_token;localStorage.setItem("campusiq_token",token);await boot();
  }catch(err){$("login-error").textContent=err.message}
});
$("logout").addEventListener("click",()=>{token=null;localStorage.removeItem("campusiq_token");showLogin()});
function setupShell(){
  $("user-name").textContent=me.name;$("user-role").textContent=me.role[0].toUpperCase()+me.role.slice(1);$("avatar").textContent=initials(me.name);
  $("today-date").textContent=new Date().toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"});
  document.querySelectorAll(".teacher-only").forEach(el=>el.classList.toggle("hidden",me.role==="student"));
  document.querySelectorAll(".nav-item[data-page]").forEach(btn=>btn.addEventListener("click",()=>navigate(btn.dataset.page)));
  document.querySelectorAll("[data-goto]").forEach(btn=>btn.addEventListener("click",()=>navigate(btn.dataset.goto)));
  if(me.role==="student"){
    $("welcome-title").textContent=`Welcome back, ${me.name.split(" ")[0]}`;
    $("welcome-subtitle").textContent="Your real assessment history and learning activity are shown below.";
    $("welcome-label").textContent="YOUR LEARNING OVERVIEW";
    $("table-title").textContent="Your recent assessment results";
    $("table-subtitle").textContent="Historical assessment scores from the Open University dataset";
    const insight=document.querySelector(".insight-panel");
    if(insight){const h=insight.querySelector("h3");const p=insight.querySelector("p");if(h)h.textContent="Learning engagement";if(p)p.textContent="Recorded activity in the online learning environment";}
  }
}
async function navigate(page){
  document.querySelectorAll(".page").forEach(x=>x.classList.add("hidden"));$(`page-${page}`).classList.remove("hidden");
  document.querySelectorAll(".nav-item[data-page]").forEach(x=>x.classList.toggle("active",x.dataset.page===page));
  $("crumb-page").textContent=page.replace("-"," ").replace(/\b\w/g,c=>c.toUpperCase());
  if(page==="students")await loadStudents(1);if(page==="classes")await loadClasses();if(page==="assignments")await loadAssignments();if(page==="records")await loadRecordOptions();
}
function metric(label,value,foot,icon){return `<div class="metric"><div class="metric-top"><span>${label}</span><span class="metric-icon">${icon}</span></div><div class="metric-value">${value}</div><div class="metric-foot">${foot}</div></div>`}
function drawTeacherCharts(overview){
  if(typeof Chart==="undefined")return;
  const perf=$("performance-chart");if(charts.perf)charts.perf.destroy();
  charts.perf=new Chart(perf,{type:"bar",data:{labels:(overview.subject_performance||[]).map(s=>s.code),datasets:[{label:"Actual average score",data:(overview.subject_performance||[]).map(s=>s.average),backgroundColor:"#72a887",borderRadius:5,maxBarThickness:34}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:100,grid:{color:"#eef2ee"}},x:{grid:{display:false}}}}});
  const counts=[overview.on_track||0,overview.needs_attention||0,overview.at_risk||0];
  if(charts.health)charts.health.destroy();charts.health=new Chart($("health-chart"),{type:"doughnut",data:{labels:["On track","Needs attention","At risk"],datasets:[{data:counts,backgroundColor:["#438b66","#e3b45e","#d87575"],borderWidth:0}]},options:{cutout:"76%",maintainAspectRatio:false,plugins:{legend:{display:false}}}});
  $("healthy-count").textContent=counts[0];
}
function drawStudentCharts(detail){
  if(typeof Chart==="undefined")return;
  if(charts.perf)charts.perf.destroy();
  const rows=detail.subject_performance||[];
  charts.perf=new Chart($("performance-chart"),{type:"bar",data:{labels:rows.map(s=>s.code),datasets:[{label:"Your average score",data:rows.map(s=>s.average),backgroundColor:"#72a887",borderRadius:5,maxBarThickness:34}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:100,grid:{color:"#eef2ee"}},x:{grid:{display:false}}}}});
  if(charts.health)charts.health.destroy();
  const clicks=Number(detail.engagement_clicks||0), days=Number(detail.active_days||0);
  charts.health=new Chart($("health-chart"),{type:"doughnut",data:{labels:["Recorded clicks","Remaining display scale"],datasets:[{data:[Math.max(clicks,0),Math.max(1,1000-clicks)],backgroundColor:["#438b66","#e9eee9"],borderWidth:0}]},options:{cutout:"76%",maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>`${ctx.label}: ${ctx.label==="Recorded clicks"?clicks.toLocaleString():"activity scale"}`}}}}});
  $("healthy-count").textContent=clicks.toLocaleString();
  const center=document.querySelector(".donut-center small");if(center)center.textContent=`${days.toLocaleString()} active days`;
}
async function loadOverview(){
  const [overview,subs]=await Promise.all([api("/api/overview"),api("/api/subjects")]);subjects=subs;
  if(me.role==="student"){
    const detail=await api(`/api/students/${me.id}`);
    const avg=detail.average_marks;
    $("metrics").innerHTML=metric("Overall average",avg===null?"No scores yet":pct(avg),`${detail.assessment_count} recorded assessments`,"◈")+
      metric("Attendance",pct(detail.attendance),detail.attendance===null?"No classroom roll-call recorded":detail.attendance<75?"Below the 75% target":"At or above the 75% target","◷")+
      metric("Subjects",detail.registered_subjects.length,"Registered course presentations","▤")+
      metric("VLE activity",Number(detail.engagement_clicks).toLocaleString(),`${detail.active_days} active course-days`,"✦");
    const marks=(detail.marks||[]).slice(-10).reverse();
    $("overview-table").innerHTML=marks.length?`<table class="data-table"><thead><tr><th>SUBJECT</th><th>ASSESSMENT</th><th>SCORE</th><th>WEIGHT</th></tr></thead><tbody>${marks.map(m=>`<tr><td>${m.subject} <small>${m.code}</small></td><td>${m.assessment}</td><td><b>${Number(m.score).toFixed(1)}/100</b></td><td>${Number(m.weight).toFixed(1)}%</td></tr>`).join("")}</tbody></table>`:`<div class="empty-state"><b>No assessment scores recorded for this student ID.</b><p>This account exists in OULAD, but the dataset may not contain a submitted assessment for this student. Check another student ID or the teacher's data diagnostics.</p></div>`;
    $("student-personal").classList.remove("hidden");
    const subjectsHtml=detail.subject_performance.length?detail.subject_performance.map(a=>`<p class="muted" style="font-size:12px">${a.code} · ${a.subject}<b style="float:right">${a.average}%</b></p><div class="progress" style="width:100%;height:7px;margin-bottom:12px"><i style="width:${a.average}%;background:${a.average<40?"#d87575":"#5b9c76"}"></i></div>`).join(""):`<p class="muted">No assessment performance is available for this account yet.</p>`;
    const attendanceHtml=detail.attendance_by_subject.length?detail.attendance_by_subject.map(a=>`<p class="muted" style="font-size:12px">${a.subject}<b style="float:right">${a.percentage}% (${a.present}/${a.total})</b></p>`).join(""):`<p class="muted">Classroom attendance has not been entered by a teacher. VLE clicks are not counted as physical attendance.</p>`;
    $("student-personal").innerHTML=`<div class="panel"><h3>Subject performance</h3>${subjectsHtml}<h3 style="margin-top:22px">Classroom attendance</h3>${attendanceHtml}</div><div class="panel"><h3>Your academic profile</h3><p class="muted">OULAD student ID: <b>${detail.oulad_student_id}</b></p><p class="muted">Department: <b>${detail.department}</b></p><p class="muted">Email: <b>${detail.email}</b></p><h3 style="margin-top:18px">Learning activity</h3><p class="muted">${Number(detail.engagement_clicks).toLocaleString()} VLE clicks across ${detail.active_days} active course-days.</p></div>`;
    drawStudentCharts(detail);
  }else{
    $("metrics").innerHTML=metric("Total students",overview.students.toLocaleString(),"Imported OULAD student accounts","♙")+
      metric("Average marks",overview.average_marks===null?"No scores":pct(overview.average_marks),"Average of student assessment averages","◈")+
      metric("Average attendance",pct(overview.attendance),"Teacher-entered classroom attendance only","◷")+
      metric("At-risk students",overview.at_risk.toLocaleString(),"Based on recorded marks and attendance","⚑");
    drawTeacherCharts(overview);
    $("overview-table").innerHTML=tableMarkup(overview.students_list||[]);
    $("student-count").textContent=overview.students.toLocaleString();
  }
}
function tableMarkup(rows){return `<table class="data-table"><thead><tr><th>STUDENT</th><th>AVERAGE MARKS</th><th>ATTENDANCE</th><th>STATUS</th><th></th></tr></thead><tbody>${rows.map(s=>`<tr><td><div class="person"><span class="mini-avatar">${initials(s.name)}</span><span><b>${s.name}</b><small>OULAD ID: ${s.oulad_student_id||s.roll_no}</small></span></div></td><td><b>${s.average_marks===null?"No scores":pct(s.average_marks)}</b></td><td>${pct(s.attendance)}</td><td><span class="status ${statusClass(s.status)}">${s.status}</span></td><td><button class="text-button" onclick="openStudent(${s.id})">Details ↗</button></td></tr>`).join("")||`<tr><td colspan="5">No students need attention based on the current recorded data.</td></tr>`}</tbody></table>`}
async function loadStudents(page=1){
  currentStudentPage=page;
  const q=$("student-search").value||"",status=$("status-filter").value||"All";
  const data=await api(`/api/students?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&page=${page}&limit=50`);
  students=data.items||[];
  $("directory-total").textContent=`${data.total.toLocaleString()} students · page ${data.page} of ${Math.max(data.pages,1)}`;
  $("students-table").innerHTML=tableMarkup(students)+`<div class="toolbar" style="justify-content:flex-end"><button class="secondary" ${page<=1?"disabled":""} id="prev-students">Previous</button><button class="secondary" ${page>=data.pages?"disabled":""} id="next-students">Next</button></div>`;
  $("prev-students")?.addEventListener("click",()=>loadStudents(page-1));$("next-students")?.addEventListener("click",()=>loadStudents(page+1));
}
function debounce(fn,delay=350){let timer;return (...args)=>{clearTimeout(timer);timer=setTimeout(()=>fn(...args),delay)}}
$("student-search").addEventListener("input",debounce(()=>loadStudents(1).catch(e=>toast(e.message))));
$("status-filter").addEventListener("change",()=>loadStudents(1).catch(e=>toast(e.message)));
async function openStudent(id){
  const d=await api(`/api/students/${id}`);
  $("detail-content").innerHTML=`<div class="eyebrow">STUDENT PROFILE</div><h2 style="font:700 22px Manrope">${d.name}</h2><p class="muted">OULAD ID ${d.oulad_student_id} · ${d.department}</p><div class="metric-grid" style="grid-template-columns:1fr 1fr;margin-top:18px"><div class="metric"><div class="metric-top">Average marks</div><div class="metric-value">${d.average_marks===null?"No scores":pct(d.average_marks)}</div></div><div class="metric"><div class="metric-top">Attendance</div><div class="metric-value">${pct(d.attendance)}</div></div></div><h3>Assessment history</h3><table class="data-table"><thead><tr><th>SUBJECT</th><th>ASSESSMENT</th><th>SCORE</th></tr></thead><tbody>${d.marks.map(m=>`<tr><td>${m.subject}</td><td>${m.assessment}</td><td>${Number(m.score).toFixed(1)}/100</td></tr>`).join("")||"<tr><td colspan='3'>No assessment results.</td></tr>"}</tbody></table><h3 style="margin-top:22px">Classroom attendance</h3>${d.attendance_by_subject.map(a=>`<p style="font-size:11px">${a.subject}<b style="float:right">${a.percentage}%</b></p>`).join("")||"<p class='muted'>Not recorded yet.</p>"}`;
  $("detail-modal").classList.remove("hidden");
}
$("modal-close").addEventListener("click",()=>$("detail-modal").classList.add("hidden"));
$("detail-modal").addEventListener("click",e=>{if(e.target.id==="detail-modal")$("detail-modal").classList.add("hidden")});
async function loadClasses(){
  const [sessions,subs]=await Promise.all([api("/api/classes"),api("/api/subjects")]);
  $("subject-metrics").innerHTML=subs.map(s=>`<div class="subject-card"><small>${s.code}</small><b>${s.name}</b><small>${s.teacher}</small></div>`).join("")||"<p class='muted'>No registered course presentations.</p>";
  $("timetable").innerHTML=sessions.length?sessions.map(c=>`<div class="class-card"><span class="class-day">${c.day.toUpperCase()}</span><b>${c.subject}</b><small>◷ ${c.start} – ${c.end}</small><small>⌂ Room ${c.room}</small></div>`).join(""):`<div class="class-card" style="grid-column:1/-1"><b>No classroom timetable has been configured</b><small>OULAD contains online course activity, not physical class schedules. A teacher/admin must add class sessions.</small></div>`;
}
async function loadAssignments(){
  const rows=await api("/api/assignments");
  $("assignment-list").innerHTML=rows.length?rows.map(a=>`<div class="assignment-card"><span class="tag">${a.subject}</span><h3>${a.title}</h3><p>${a.description||"Teacher-managed coursework"}</p><span class="due">◷ Due ${new Date(a.due_date).toLocaleDateString("en-IN")}</span></div>`).join(""):`<div class="panel"><h3>No live assignments configured</h3><p class="muted">OULAD assessment records are historical research data, not current assignment deadlines.</p></div>`;
}
async function loadRecordOptions(){
  const data=await api("/api/students?page=1&limit=200");students=data.items||[];
  if(!subjects.length)subjects=await api("/api/subjects");
  const studentOpts=students.map(s=>`<option value="${s.id}">${s.name} · ${s.oulad_student_id}</option>`).join("");
  const subjectOpts=subjects.map(s=>`<option value="${s.id}">${s.code} · ${s.name}</option>`).join("");
  $("mark-student").innerHTML=studentOpts;$("attendance-student").innerHTML=studentOpts;
  $("mark-subject").innerHTML=subjectOpts;$("attendance-subject").innerHTML=subjectOpts;
  $("class-date").value=new Date().toISOString().slice(0,10);
}
$("marks-form").addEventListener("submit",async e=>{
  e.preventDefault();try{await api("/api/marks",{method:"POST",body:JSON.stringify({student_id:$("mark-student").value,subject_id:$("mark-subject").value,assessment:$("assessment").value,score:$("score").value,max_score:$("max-score").value})});$("marks-message").textContent="Marks saved successfully.";toast("Assessment record saved.");await loadOverview()}catch(err){$("marks-message").textContent=err.message}
});
$("attendance-form").addEventListener("submit",async e=>{
  e.preventDefault();try{await api("/api/attendance",{method:"POST",body:JSON.stringify({student_id:$("attendance-student").value,subject_id:$("attendance-subject").value,class_date:$("class-date").value,present:document.querySelector('input[name="present"]:checked').value==="true"})});$("attendance-message").textContent="Attendance saved successfully.";toast("Attendance record saved.");await loadOverview()}catch(err){$("attendance-message").textContent=err.message}
});
boot().catch(showLoadError);
