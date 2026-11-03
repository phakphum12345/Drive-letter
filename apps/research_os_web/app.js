const API_BASE_URL=(window.RESEARCH_OS_API_BASE_URL||'https://research-os-api-phakphoum-v0wf.onrender.com').replace(/\/$/,'');
const state={sessionId:null,sending:false,messages:[],deepMode:true,account:null,chatWide:false};
const stages=['define','plan','gather','verify','synthesize','remember'];
const $=id=>document.getElementById(id);
function addMessage(role,text){const node=document.createElement('div');node.className=`message ${role}`;node.textContent=text;$('messages').appendChild(node);node.scrollIntoView({behavior:'smooth',block:'end'});state.messages.push({role,content:text});return node;}
function setStage(stage){const index=stages.indexOf(stage);document.querySelectorAll('.flow-item[data-stage]').forEach((node,i)=>{node.classList.toggle('active',i===index);node.classList.toggle('complete',i<index);const icon=node.querySelector('i');if(icon)icon.textContent=i<index?'✓':i===index?'●':'○';});}
async function request(path,options={},timeoutMs=65000){const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);try{const response=await fetch(`${API_BASE_URL}${path}`,{headers:{'Content-Type':'application/json'},credentials:'include',signal:controller.signal,...options});let data;try{data=await response.json()}catch(_){throw new Error(`API returned invalid JSON (HTTP ${response.status})`)}if(!response.ok)throw new Error(data.detail||data.error||`HTTP ${response.status}`);return data}catch(error){if(error.name==='AbortError')throw new Error('Research request timed out after 65 seconds');throw error}finally{clearTimeout(timer)}}
function setChatWide(enabled){
  state.chatWide=Boolean(enabled);
  document.body.classList.toggle('chat-wide-mode',state.chatWide);
  const button=$('chatLayoutToggle');
  if(button){
    button.setAttribute('aria-pressed',String(state.chatWide));
    button.textContent=state.chatWide?'↙ กลับหน้าปกติ':'↗ แชทกว้าง';
    button.setAttribute('aria-label',state.chatWide?'Switch to normal chat':'Switch to wide chat');
  }
  try{localStorage.setItem('research-os-chat-layout',state.chatWide?'wide':'normal')}catch(_){}
}
function restoreChatLayout(){
  let wide=false;
  try{wide=localStorage.getItem('research-os-chat-layout')==='wide'}catch(_){}
  setChatWide(wide);
}
function setRunning(value){state.sending=value;const button=$('runButton');button.disabled=value;button.innerHTML=value?'กำลังค้นคว้า… <b>◌</b>':'Send <b>↑</b>';$('prompt').disabled=value;if(value)$('researchState').textContent='RUNNING'}
function roleRank(role){return ({USER:10,PRO:20,OWNER:30})[String(role||'USER').toUpperCase()]||0}
function renderAccount(){const account=state.account||{};const role=String(account.role||'USER').toUpperCase();const email=account.email||'Not signed in';$('accountEmail').textContent=email;$('accountRole').textContent=role;$('accountRole').className=`role-badge role-${role.toLowerCase()}`;$('authButton').textContent=account.email?'Sign out':'Sign in';$('ownerTools').hidden=role!=='OWNER';document.querySelectorAll('[data-min-role]').forEach(node=>{node.hidden=roleRank(role)<roleRank(node.dataset.minRole)});document.querySelectorAll('[data-admin-only]').forEach(node=>{node.hidden=role!=='OWNER'});if(role!=='OWNER'&&!$('adminView').hidden)setPlatformView('home');}
async function refreshAuth(){try{const result=await request('/v1/auth/google/status');state.account=result.account&&result.connected?result.account:null;renderAccount();await refreshControlCenter();return result}catch(error){state.account=null;renderAccount();showControlCenterSignIn();throw error}}
function providerLabel(provider){return provider==='google'?'Google':provider==='microsoft'?'Microsoft':'GitHub'}
function addEmailOtpControls(panel){
const heading=document.createElement('p');heading.textContent='Or sign in with Email OTP';panel.appendChild(heading);
const email=document.createElement('input');email.type='email';email.autocomplete='email';email.placeholder='Email address';email.setAttribute('aria-label','Email address');panel.appendChild(email);
const send=document.createElement('button');send.type='button';send.className='tool-chip';send.textContent='Send Email OTP';panel.appendChild(send);
const code=document.createElement('input');code.type='text';code.inputMode='numeric';code.autocomplete='one-time-code';code.maxLength=6;code.placeholder='6-digit code';code.setAttribute('aria-label','Email verification code');code.hidden=true;panel.appendChild(code);
const verify=document.createElement('button');verify.type='button';verify.className='tool-chip';verify.textContent='Verify code';verify.hidden=true;panel.appendChild(verify);
const message=document.createElement('small');message.setAttribute('role','status');panel.appendChild(message);
send.addEventListener('click',async()=>{send.disabled=true;message.textContent='Sending…';try{await request('/v1/auth/email-otp/start',{method:'POST',body:JSON.stringify({email:email.value.trim()})});code.hidden=false;verify.hidden=false;message.textContent='If SMTP is configured, a code has been sent. It expires in 5 minutes.'}catch(error){message.textContent=error.message}finally{send.disabled=false}});
verify.addEventListener('click',async()=>{verify.disabled=true;message.textContent='Verifying…';try{const result=await request('/v1/auth/email-otp/verify',{method:'POST',body:JSON.stringify({email:email.value.trim(),code:code.value.trim()})});state.account=result.account||null;renderAccount();panel.hidden=true;addMessage('system','Email OTP sign-in complete.');refreshControlCenter()}catch(error){message.textContent=error.message}finally{verify.disabled=false}});
}
async function showLoginOptions(){const panel=$('loginOptions');if(!panel.hidden){panel.hidden=true;return}panel.hidden=false;panel.textContent='Loading login providers…';try{const result=await request('/v1/auth/providers');panel.innerHTML='';for(const provider of result.providers||[]){const button=document.createElement('button');button.type='button';button.className='tool-chip';button.textContent=`Continue with ${providerLabel(provider.id)}${provider.available?'':' (not configured)'}`;button.disabled=!provider.available;button.addEventListener('click',()=>handleProviderLogin(provider.id));panel.appendChild(button)}addEmailOtpControls(panel)}catch(error){panel.textContent=`Login providers unavailable: ${error.message}`}}
async function handleProviderLogin(provider){if(state.sending)return;try{const result=await request('/v1/auth/providers/login',{method:'POST',body:JSON.stringify({provider})});if(!result.authorization_url)throw new Error('Authorization URL was not returned');window.location.assign(result.authorization_url)}catch(error){addMessage('system',`${providerLabel(provider)} sign-in unavailable: ${error.message}`)}}
async function handleAuth(){if(state.sending)return;if(state.account&&state.account.email){try{await request('/v1/auth/google/signout',{method:'POST'});state.account=null;renderAccount();setPlatformView('home');showControlCenterSignIn();addMessage('system','Signed out successfully.')}catch(error){addMessage('system',`Sign out failed: ${error.message}`)}return}await showLoginOptions()}
async function startResearch(prompt){if(state.sending||!prompt)return;if(!state.sessionId)state.sessionId=crypto.randomUUID();if(state.messages.length===0)$('researchTitle').textContent=prompt.length>72?`${prompt.slice(0,72)}…`:prompt;addMessage('user',prompt);setRunning(true);setStage('define');const pending=addMessage('assistant','DEFINE — locking the research question, scope, and goal…');try{const health=await request('/health');$('health').textContent=health.version||'ONLINE';await new Promise(r=>setTimeout(r,180));setStage('plan');pending.textContent='PLAN — coordinating the investigation through Unified Master…';await new Promise(r=>setTimeout(r,180));setStage('gather');pending.textContent=state.deepMode?'GATHER — running the deep research path through the existing API contract…':'GATHER — requesting research output through the existing API contract…';const result=await request('/v1/ai/generate',{method:'POST',body:JSON.stringify({prompt,session_id:state.sessionId,mode:state.deepMode?'deep':'standard'})});setStage('verify');pending.textContent='VERIFY — validating the returned response and checking the research contract…';await new Promise(r=>setTimeout(r,180));setStage('synthesize');pending.textContent='SYNTHESIZE — preparing the answer and unresolved questions…';await new Promise(r=>setTimeout(r,180));const answer=(result.text||result.answer||'Research completed without a text response.').toString().trim();pending.remove();state.messages.pop();addMessage('assistant',answer||'Research completed without a text response.');setStage('remember');$('researchState').textContent='COMPLETE'}catch(error){pending.remove();state.messages.pop();addMessage('assistant',`Research could not start: ${error.message}`);$('researchState').textContent='ERROR'}finally{setRunning(false)}}
$('researchForm').addEventListener('submit',event=>{event.preventDefault();startResearch($('prompt').value.trim())});
$('newResearch').addEventListener('click',()=>{setPlatformView('chat');state.sessionId=crypto.randomUUID();state.messages=[];$('messages').innerHTML='<div class="empty-state"><div class="empty-icon">✦</div><b>Your research workspace is ready.</b><span>Research output, claims, and verification notes will appear here.</span></div>';$('researchTitle').textContent='Ready for your investigation';$('researchState').textContent='IDLE';$('prompt').value='';setStage('define');window.scrollTo({top:0,behavior:'smooth'})});
$('startWork').addEventListener('click',()=>{$('prompt').focus();$('prompt').scrollIntoView({behavior:'smooth',block:'center'})});
$('deepMode').addEventListener('click',event=>{state.deepMode=!state.deepMode;const on=event.currentTarget.querySelector('span');on.textContent=state.deepMode?'ON':'OFF';event.currentTarget.classList.toggle('enabled',state.deepMode);event.currentTarget.setAttribute('aria-pressed',String(state.deepMode))});
$('authButton').addEventListener('click',handleAuth);
$('loginOptionsButton').addEventListener('click',showLoginOptions);
refreshAuth().catch(()=>{});


function showControlCenterSignIn(message){
  $('homeStatus').textContent=message||'ลงชื่อเข้าใช้เพื่อดูงาน อุปกรณ์ และหลักฐานของคุณ';
  $('homeAgentCount').textContent='—';$('homeAgentDetail').textContent='Sign in required';
  $('homeJobCount').textContent='—';$('homeJobDetail').textContent='Sign in required';
  $('homeJobs').textContent='Sign in to view your jobs.';
  $('homeAgents').textContent='Sign in to view registered devices.';
  $('homeEvidence').textContent='Sign in to view evidence.';
  $('homeJobSummary').textContent='Not signed in';$('homeAgentSummary').textContent='Not signed in';
}
function homeItem(container,title,meta,status){
  const item=document.createElement('div');item.className='home-list-item';
  const copy=document.createElement('div');copy.className='home-list-copy';
  const heading=document.createElement('strong');heading.textContent=title||'Untitled';
  const detail=document.createElement('small');detail.textContent=meta||'';
  copy.append(heading,detail);item.appendChild(copy);
  if(status){const badge=document.createElement('span');badge.className='home-status-tag status-'+String(status).toLowerCase().replace(/[^a-z0-9_-]/g,'');badge.textContent=status;item.appendChild(badge)}
  container.appendChild(item);
}
function formatHomeTime(value){
  const date=value?new Date(value):null;
  return date&&!Number.isNaN(date.getTime())?date.toLocaleString():'Time unavailable';
}
async function refreshControlCenter(){
  if(!$('homeView')||$('homeView').hidden)return;
  if(!state.account||!state.account.email){showControlCenterSignIn();return}
  $('homeStatus').textContent='กำลังโหลดข้อมูลจริงจาก Research OS API…';
  $('refreshControlCenter').disabled=true;
  try{
    const health=await request('/health');
    updateConnection(true,health.version);
    $('homeApiStatus').textContent='Online';
    $('homeApiDetail').textContent=health.version||'Research OS API reachable';
    const results=await Promise.all([
      request('/api/v1/jobs?limit=20'),
      request('/api/v1/agents')
    ]);
    const jobs=Array.isArray(results[0].jobs)?results[0].jobs:[];
    const agents=Array.isArray(results[1].agents)?results[1].agents:[];
    const counts=jobs.reduce((acc,job)=>{const key=String(job.status||'UNKNOWN');acc[key]=(acc[key]||0)+1;return acc},{});
    const running=(counts.RUNNING||0)+(counts.ASSIGNED||0)+(counts.CHECKPOINTING||0);
    const waiting=(counts.WAITING_FOR_LOCAL_AGENT||0)+(counts.QUEUED||0)+(counts.RETRY_WAIT||0);
    const connected=agents.filter(agent=>{
      if(agent.lifecycle_state!=='ACTIVE')return false;
      const stamp=Date.parse(agent.last_heartbeat_at||agent.registered_at||'');
      return Number.isFinite(stamp)&&Date.now()-stamp<120000;
    });
    const stale=agents.filter(agent=>agent.lifecycle_state==='ACTIVE'&&!connected.includes(agent));
    $('homeAgentCount').textContent=String(connected.length);
    $('homeAgentDetail').textContent=agents.length+' registered · '+stale.length+' without recent heartbeat · '+agents.filter(a=>a.lifecycle_state==='REVOKED').length+' revoked';
    $('homeJobCount').textContent=String(jobs.length);
    $('homeJobDetail').textContent=running+' active · '+waiting+' queued/waiting · '+(counts.COMPLETED||0)+' completed';
    $('homeJobSummary').textContent=running+' active · '+waiting+' waiting';
    $('homeAgentSummary').textContent=connected.length+' connected · '+stale.length+' stale';
    $('homeJobs').textContent='';
    if(!jobs.length)$('homeJobs').textContent='ยังไม่มีงานในบัญชีนี้';
    jobs.slice(0,8).forEach(job=>homeItem($('homeJobs'),job.task_type||job.job_id,job.job_id+' · '+formatHomeTime(job.updated_at||job.created_at),job.status));
    $('homeAgents').textContent='';
    if(!agents.length)$('homeAgents').textContent='ยังไม่มี Local Agent ที่ลงทะเบียน';
    agents.slice(0,8).forEach(agent=>{
      const stamp=Date.parse(agent.last_heartbeat_at||agent.registered_at||'');
      const label=agent.lifecycle_state==='REVOKED'?'REVOKED':agent.lifecycle_state==='ACTIVE'&&Number.isFinite(stamp)&&Date.now()-stamp<120000?'CONNECTED':'NO RECENT HEARTBEAT';
      homeItem($('homeAgents'),agent.device_id||agent.agent_id,(agent.os_name||'Unknown OS')+' · '+formatHomeTime(agent.last_heartbeat_at),label);
    });
    $('homeEvidence').textContent='';
    const evidenceResults=await Promise.allSettled(jobs.slice(0,5).map(job=>request('/api/v1/jobs/'+encodeURIComponent(job.job_id)+'/evidence')));
    const evidence=evidenceResults.flatMap(result=>result.status==='fulfilled'?(result.value.evidence||[]):[]).sort((a,b)=>Date.parse(b.occurred_at)-Date.parse(a.occurred_at)).slice(0,8);
    if(!evidence.length)$('homeEvidence').textContent='ยังไม่มี evidence ที่บันทึกไว้';
    evidence.forEach(item=>homeItem($('homeEvidence'),item.event_type,item.job_id+' · '+formatHomeTime(item.occurred_at),item.result));
    $('homeStatus').textContent='ข้อมูลโหลดจาก API จริงแล้ว · ตัวเลขแสดงเฉพาะงานและอุปกรณ์ที่ API ส่งกลับ';
    $('homeLastUpdated').textContent='Updated '+new Date().toLocaleTimeString();
    $('homeCloudStatus').textContent='Not deployed';
    $('homeCloudDetail').textContent='Cloud worker ยังไม่เปิดใช้งาน · งาน CLOUD/AUTO จะคงอยู่ในคิว';
  }catch(error){
    const message=String(error.message||error);
    if(message.includes('authentication_required')||message.includes('401')){
      showControlCenterSignIn('Session ไม่พร้อมใช้งาน กรุณา Sign in ใหม่เพื่อโหลดข้อมูล');
    }else if(message.includes('cloud_local_storage_not_configured')||message.includes('503')){
      $('homeStatus').textContent='Cloud + Local storage ยังไม่ถูกตั้งค่า PostgreSQL จึงยังไม่สามารถโหลดงานและอุปกรณ์ได้';
      $('homeJobs').textContent='Storage not configured — no demo data is shown.';
      $('homeAgents').textContent='Storage not configured — no demo data is shown.';
      $('homeEvidence').textContent='Storage not configured — no demo data is shown.';
      $('homeJobCount').textContent='Unavailable';$('homeAgentCount').textContent='Unavailable';
      $('homeJobDetail').textContent='Waiting for PostgreSQL configuration';
      $('homeAgentDetail').textContent='Waiting for PostgreSQL configuration';
    }else{
      $('homeStatus').textContent='โหลดข้อมูลไม่สำเร็จ: '+message;
    }
  }finally{$('refreshControlCenter').disabled=false}
}

function adminItem(container,title,meta){
  const item=document.createElement('div');item.className='admin-list-item';
  const heading=document.createElement('strong');heading.textContent=title||'Unnamed resource';
  const detail=document.createElement('small');detail.textContent=meta||'';
  item.append(heading,detail);container.appendChild(item);
}
async function refreshAdminConsole(){
  if(!$('adminView')||$('adminView').hidden)return;
  if(String(state.account?.role||'').toUpperCase()!=='OWNER'){
    $('adminStatus').textContent='OWNER role required.';
    setPlatformView('home');return;
  }
  $('adminStatus').textContent='กำลังโหลด Management API inventory และ audit log…';
  $('refreshAdminConsole').disabled=true;
  try{
    const values=await Promise.all([
      request('/platform/v1/'),
      request('/platform/v1/organizations'),
      request('/platform/v1/projects'),
      request('/platform/v1/applications'),
      request('/platform/v1/apis'),
      request('/platform/v1/audit')
    ]);
    const groups=[
      {id:'adminOrganizations',count:'adminOrganizationsCount',items:values[1].items||[],key:'organization_id'},
      {id:'adminProjects',count:'adminProjectsCount',items:values[2].items||[],key:'project_id'},
      {id:'adminApplications',count:'adminApplicationsCount',items:values[3].items||[],key:'application_id'},
      {id:'adminApis',count:'adminApisCount',items:values[4].items||[],key:'api_id'}
    ];
    groups.forEach(group=>{
      $(group.count).textContent=String(group.items.length);
      $(group.id).textContent='';
      if(!group.items.length)$(group.id).textContent='No resources registered.';
      group.items.slice(0,20).forEach(item=>{
        const name=item.name||item.title||item[group.key]||item.id||'Unnamed resource';
        const identifier=item[group.key]||item.id||'';
        const stateLabel=item.lifecycle||item.status||'REGISTERED';
        adminItem($(group.id),name,identifier+' · '+stateLabel);
      });
    });
    const audit=values[5].items||[];
    $('adminAudit').textContent='';
    $('adminAuditCount').textContent=audit.length+' records';
    if(!audit.length)$('adminAudit').textContent='No management audit events recorded.';
    audit.slice(-20).reverse().forEach(item=>{
      adminItem($('adminAudit'),(item.action||'event')+' · '+(item.resource||'resource'),(item.actor||'unknown actor')+' · '+(item.outcome||'unknown outcome')+' · '+(item.created_at||item.timestamp||''));
    });
    $('adminStatus').textContent='Management API: '+(values[0].status||'ready')+' · inventory is read-only in this release';
    $('adminLastUpdated').textContent='Updated '+new Date().toLocaleTimeString();
  }catch(error){
    const message=String(error.message||error);
    $('adminStatus').textContent=message.includes('owner_required')?'สิทธิ์ OWNER เท่านั้นที่เข้าถึง Admin Console ได้':'โหลด Admin Console ไม่สำเร็จ: '+message;
  }finally{$('refreshAdminConsole').disabled=false}
}

// Platform workspace navigation and responsive controls.
function setPlatformView(view,moduleName){
  let selected=view||'home';
  if(selected==='admin'&&String(state.account?.role||'').toUpperCase()!=='OWNER')selected='home';
  $('homeView').hidden=selected!=='home';
  $('chatView').hidden=selected!=='chat';
  $('registryView').hidden=selected!=='registry';
  $('adminView').hidden=selected!=='admin';
  document.querySelectorAll('.nav-link').forEach(button=>button.classList.toggle('active',button.dataset.view===selected&&(selected!=='registry'||button.dataset.module===moduleName)));
  $('pageTitle').textContent=selected==='home'?'Control Center':selected==='chat'?'Research Chat':selected==='admin'?'Admin Console':(moduleName||'Platform Directory');
  if(selected==='registry')$('registryTitle').textContent=moduleName||'Platform domains';
  document.body.classList.remove('focus-mode');
  if(selected==='chat')setChatWide(state.chatWide);else document.body.classList.remove('chat-wide-mode');
  $('sidebar').classList.remove('open');
  $('sidebarScrim').classList.remove('open');
  if(selected==='home')refreshControlCenter();
  if(selected==='admin')refreshAdminConsole();
}
document.querySelectorAll('.nav-link').forEach(button=>button.addEventListener('click',()=>{
  setPlatformView(button.dataset.view,button.dataset.module);
}));
$('returnChat').addEventListener('click',()=>setPlatformView('chat'));
$('refreshAdminConsole').addEventListener('click',refreshAdminConsole);
$('refreshControlCenter').addEventListener('click',refreshControlCenter);
$('homeStartResearch').addEventListener('click',()=>{setPlatformView('chat');$('prompt').focus()});
$('homeViewDirectory').addEventListener('click',()=>setPlatformView('registry'));
$('openSidebar').addEventListener('click',()=>{$('sidebar').classList.add('open');$('sidebarScrim').classList.add('open')});
$('closeSidebar').addEventListener('click',()=>{$('sidebar').classList.remove('open');$('sidebarScrim').classList.remove('open')});
$('sidebarScrim').addEventListener('click',()=>{$('sidebar').classList.remove('open');$('sidebarScrim').classList.remove('open')});
$('focusMode').addEventListener('click',()=>document.body.classList.toggle('focus-mode'));
$('chatLayoutToggle').addEventListener('click',()=>setChatWide(!state.chatWide));
restoreChatLayout();
$('clearConversation').addEventListener('click',()=>{
  if(state.sending)return;
  state.messages=[];
  $('messages').innerHTML='<div class="empty-state" id="welcomeState"><div class="welcome-mark">R</div><span class="eyebrow">YOUR RESEARCH DESK</span><h2>What are we solving today?</h2><p>เริ่มจากคำถามหรือปัญหาที่ต้องการค้นคว้า แล้วให้ Research OS ช่วยจัดโครงสร้างการตรวจสอบ</p></div>';
  $('researchTitle').textContent='เริ่มต้นการวิจัย';
  $('researchState').textContent='READY';
});
const promptInput=$('prompt');
promptInput.addEventListener('input',()=>{promptInput.style.height='auto';promptInput.style.height=Math.min(promptInput.scrollHeight,180)+'px'});
promptInput.addEventListener('keydown',event=>{
  if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('researchForm').requestSubmit()}
});
document.querySelectorAll('[data-prompt]').forEach(button=>button.addEventListener('click',()=>{
  promptInput.value=button.dataset.prompt;
  promptInput.focus();
  promptInput.dispatchEvent(new Event('input'));
}));
const healthIndicator=$('health');
function updateConnection(ok,version){
  if(healthIndicator)healthIndicator.textContent=ok?(version||'ONLINE'):'OFFLINE';
  if($('homeApiStatus'))$('homeApiStatus').textContent=ok?'Online':'Offline';
  if($('homeApiDetail'))$('homeApiDetail').textContent=ok?(version||'Research OS API reachable'):'API endpoint unavailable';
  $('apiLabel').textContent=ok?'API connected':'API unavailable';
  $('apiDetail').textContent=ok?(version||'Research OS service online'):'Check API endpoint or network';
  $('apiDot').style.background=ok?'var(--good)':'var(--danger)';
  $('connectionText').textContent=ok?'API connected':'API offline';
  $('connectionDot').style.background=ok?'var(--good)':'var(--danger)';
}
request('/health').then(data=>updateConnection(true,data.version)).catch(()=>updateConnection(false));
setPlatformView('home');
