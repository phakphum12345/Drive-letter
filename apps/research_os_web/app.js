const API_BASE_URL=(window.RESEARCH_OS_API_BASE_URL||'https://research-os-api-phakphoum-v0wf.onrender.com').replace(/\/$/,'');
const state={sessionId:null,sending:false,messages:[],deepMode:true,account:null,chatWide:false,chatSessions:[]};
const stages=['define','plan','gather','verify','synthesize','remember'];
const $=id=>document.getElementById(id);
function appendMessageNode(message){
  const node=document.createElement('div');
  node.className=`message ${message.role||'assistant'}`;
  node.textContent=message.content||'';
  $('messages').appendChild(node);
  if(message.meta){
    const meta=document.createElement('small');
    meta.className='chat-response-meta';
    meta.textContent=[message.meta.route,message.meta.provider,message.meta.model].filter(Boolean).join(' · ');
    if(meta.textContent)node.appendChild(meta);
  }
  return node;
}
function chatStorageKey(){
  const account=state.account||{};
  const identity=String(account.user_id||account.email||'').trim().toLowerCase();
  return identity?'research-os-chat-history:'+encodeURIComponent(identity):null;
}
function renderChatHistoryOptions(){
  const select=$('chatHistory');
  if(!select)return;
  select.textContent='';
  const placeholder=document.createElement('option');
  placeholder.value='';
  placeholder.textContent='History on this device';
  select.appendChild(placeholder);
  state.chatSessions.forEach(session=>{
    const option=document.createElement('option');
    option.value=session.id;
    option.textContent=session.title||'New conversation';
    select.appendChild(option);
  });
  select.value=state.sessionId||'';
}
function persistChatHistory(){
  const key=chatStorageKey();
  if(!key||!state.sessionId)return;
  const firstUser=state.messages.find(message=>message.role==='user');
  const title=(firstUser?.content||'New conversation').replace(/\s+/g,' ').slice(0,72);
  const session={id:state.sessionId,title,updated_at:Date.now(),messages:state.messages.slice(-100)};
  state.chatSessions=state.chatSessions.filter(item=>item.id!==session.id);
  state.chatSessions.unshift(session);
  state.chatSessions.sort((a,b)=>Number(b.updated_at||0)-Number(a.updated_at||0));
  state.chatSessions=state.chatSessions.slice(0,50);
  try{
    localStorage.setItem(key,JSON.stringify(state.chatSessions));
    $('chatHistoryStatus').textContent='Saved locally on this device';
  }catch(error){
    $('chatHistoryStatus').textContent='Local save unavailable';
  }
  renderChatHistoryOptions();
}
function renderChatSession(session){
  state.sessionId=session.id;
  state.messages=Array.isArray(session.messages)?session.messages.slice(-100):[];
  $('messages').textContent='';
  if(state.messages.length){
    state.messages.forEach(appendMessageNode);
    const last=$('messages').lastElementChild;
    last?.scrollIntoView({block:'end'});
  }else{
    $('messages').innerHTML='<div class="empty-state"><div class="empty-icon">✦</div><b>Your research workspace is ready.</b><span>Start a new investigation when you are ready.</span></div>';
  }
  $('researchTitle').textContent=session.title||'เริ่มต้นการวิจัย';
  $('researchState').textContent='HISTORY';
  $('chatHistoryStatus').textContent='Local history · '+new Date(Number(session.updated_at||Date.now())).toLocaleString();
  renderChatHistoryOptions();
}
function clearChatStateForSignedOut(statusText='Sign in to view local conversation history.'){
  state.chatSessions=[];
  state.messages=[];
  state.sessionId=null;
  $('messages').textContent='';
  $('researchTitle').textContent='เริ่มต้นการวิจัย';
  $('researchState').textContent='READY';
  $('chatHistoryStatus').textContent=statusText;
  renderChatHistoryOptions();
}
function restoreLocalChatHistory(){
  const key=chatStorageKey();
  state.chatSessions=[];
  state.messages=[];
  state.sessionId=null;
  $('messages').textContent='';
  $('researchTitle').textContent='เริ่มต้นการวิจัย';
  $('researchState').textContent='READY';
  if(!key){
    $('chatHistoryStatus').textContent='Sign in to view local conversation history.';
    renderChatHistoryOptions();
    return;
  }
  try{
    const raw=localStorage.getItem(key);
    const sessions=raw?JSON.parse(raw):[];
    state.chatSessions=Array.isArray(sessions)?sessions.filter(item=>item&&typeof item.id==='string'&&Array.isArray(item.messages)).slice(0,50):[];
    state.chatSessions.sort((a,b)=>Number(b.updated_at||0)-Number(a.updated_at||0));
    if(state.chatSessions.length)renderChatSession(state.chatSessions[0]);
    else{
      state.sessionId=crypto.randomUUID();
      state.messages=[];
      $('messages').innerHTML='<div class="empty-state"><div class="empty-icon">✦</div><b>Your research workspace is ready.</b><span>Start a new investigation when you are ready.</span></div>';
      $('researchTitle').textContent='Ready for your investigation';
      renderChatHistoryOptions();
      $('chatHistoryStatus').textContent='Local history ready · this device only';
    }
  }catch(error){
    clearChatStateForSignedOut('Could not read local history');
  }
}
function startNewChatSession(){
  if(state.sending)return;
  state.sessionId=crypto.randomUUID();
  state.messages=[];
  $('messages').innerHTML='<div class="empty-state"><div class="empty-icon">✦</div><b>Your research workspace is ready.</b><span>Research output, claims, and verification notes will appear here.</span></div>';
  $('researchTitle').textContent='Ready for your investigation';
  $('researchState').textContent='IDLE';
  $('prompt').value='';
  setStage('define');
  persistChatHistory();
}
function addMessage(role,text,meta=null){
  const message={role,content:text,...(meta?{meta}: {})};
  const node=appendMessageNode(message);
  node.scrollIntoView({behavior:'smooth',block:'end'});
  state.messages.push(message);
  persistChatHistory();
  return node;
}
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
async function refreshAuth(){try{const result=await request('/v1/auth/google/status');state.account=result.account&&result.connected?result.account:null;renderAccount();if(state.account)restoreLocalChatHistory();else clearChatStateForSignedOut();await refreshControlCenter();return result}catch(error){state.account=null;clearChatStateForSignedOut();renderAccount();showControlCenterSignIn();throw error}}
function providerLabel(provider){return provider==='google'?'Google':provider==='microsoft'?'Microsoft':'GitHub'}
function addEmailOtpControls(panel){
const heading=document.createElement('p');heading.textContent='Or sign in with Email OTP';panel.appendChild(heading);
const email=document.createElement('input');email.type='email';email.autocomplete='email';email.placeholder='Email address';email.setAttribute('aria-label','Email address');panel.appendChild(email);
const send=document.createElement('button');send.type='button';send.className='tool-chip';send.textContent='Send Email OTP';panel.appendChild(send);
const code=document.createElement('input');code.type='text';code.inputMode='numeric';code.autocomplete='one-time-code';code.maxLength=6;code.placeholder='6-digit code';code.setAttribute('aria-label','Email verification code');code.hidden=true;panel.appendChild(code);
const verify=document.createElement('button');verify.type='button';verify.className='tool-chip';verify.textContent='Verify code';verify.hidden=true;panel.appendChild(verify);
const message=document.createElement('small');message.setAttribute('role','status');panel.appendChild(message);
send.addEventListener('click',async()=>{send.disabled=true;message.textContent='Sending…';try{await request('/v1/auth/email-otp/start',{method:'POST',body:JSON.stringify({email:email.value.trim()})});code.hidden=false;verify.hidden=false;message.textContent='If email delivery is configured, a code has been sent. It expires in 5 minutes.'}catch(error){message.textContent=error.message}finally{send.disabled=false}});
verify.addEventListener('click',async()=>{verify.disabled=true;message.textContent='Verifying…';try{const result=await request('/v1/auth/email-otp/verify',{method:'POST',body:JSON.stringify({email:email.value.trim(),code:code.value.trim()})});state.account=result.account||null;renderAccount();if(state.account)restoreLocalChatHistory();panel.hidden=true;addMessage('system','Email OTP sign-in complete.');refreshControlCenter()}catch(error){message.textContent=error.message}finally{verify.disabled=false}});
}
async function showLoginOptions(){const panel=$('loginOptions');if(!panel.hidden){panel.hidden=true;return}panel.hidden=false;panel.textContent='Loading login providers…';try{const result=await request('/v1/auth/providers');panel.innerHTML='';for(const provider of result.providers||[]){const button=document.createElement('button');button.type='button';button.className='tool-chip';button.textContent=`Continue with ${providerLabel(provider.id)}${provider.available?'':' (not configured)'}`;button.disabled=!provider.available;button.addEventListener('click',()=>handleProviderLogin(provider.id));panel.appendChild(button)}addEmailOtpControls(panel)}catch(error){panel.textContent=`Login providers unavailable: ${error.message}`}}
async function handleProviderLogin(provider){if(state.sending)return;try{const result=await request('/v1/auth/providers/login',{method:'POST',body:JSON.stringify({provider})});if(!result.authorization_url)throw new Error('Authorization URL was not returned');window.location.assign(result.authorization_url)}catch(error){addMessage('system',`${providerLabel(provider)} sign-in unavailable: ${error.message}`)}}
async function handleAuth(){if(state.sending)return;if(state.account&&state.account.email){try{await request('/v1/auth/google/signout',{method:'POST'});state.account=null;clearChatStateForSignedOut();renderAccount();setPlatformView('home');showControlCenterSignIn();addMessage('system','Signed out successfully.')}catch(error){addMessage('system',`Sign out failed: ${error.message}`)}return}await showLoginOptions()}
async function startResearch(prompt){if(state.sending||!prompt)return;if(!state.sessionId)state.sessionId=crypto.randomUUID();if(state.messages.length===0)$('researchTitle').textContent=prompt.length>72?`${prompt.slice(0,72)}…`:prompt;addMessage('user',prompt);setRunning(true);setStage('define');const pending=addMessage('assistant','DEFINE — locking the research question, scope, and goal…');try{const health=await request('/health');$('health').textContent=health.version||'ONLINE';await new Promise(r=>setTimeout(r,180));setStage('plan');pending.textContent='PLAN — coordinating the investigation through Unified Master…';await new Promise(r=>setTimeout(r,180));setStage('gather');pending.textContent=state.deepMode?'GATHER — running the deep research path through the existing API contract…':'GATHER — requesting research output through the existing API contract…';const result=await request('/v1/ai/generate',{method:'POST',body:JSON.stringify({prompt,session_id:state.sessionId,mode:state.deepMode?'deep':'standard'})});setStage('verify');pending.textContent='VERIFY — validating the returned response and checking the research contract…';await new Promise(r=>setTimeout(r,180));setStage('synthesize');pending.textContent='SYNTHESIZE — preparing the answer and unresolved questions…';await new Promise(r=>setTimeout(r,180));const answer=(result.text||result.answer||'Research completed without a text response.').toString().trim();pending.remove();state.messages.pop();persistChatHistory();addMessage('assistant',answer||'Research completed without a text response.',{route:result.route,provider:result.provider,model:result.model});setStage('remember');$('researchState').textContent='COMPLETE'}catch(error){pending.remove();state.messages.pop();addMessage('assistant',`Research could not start: ${error.message}`);$('researchState').textContent='ERROR'}finally{setRunning(false)}}
$('researchForm').addEventListener('submit',event=>{event.preventDefault();startResearch($('prompt').value.trim())});
$('newResearch').addEventListener('click',()=>{setPlatformView('chat');startNewChatSession();window.scrollTo({top:0,behavior:'smooth'})});
$('newChatSession').addEventListener('click',startNewChatSession);
$('chatHistory').addEventListener('change',event=>{
  const session=state.chatSessions.find(item=>item.id===event.target.value);
  if(session&&!state.sending)renderChatSession(session);
});
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
  item.append(heading,detail);container.appendChild(item);return item;
}
const adminCreateFields={
  organizations:[['organization_id','Organization ID'],['name','Name']],
  projects:[['project_id','Project ID'],['organization_id','Organization ID'],['name','Name']],
  applications:[['application_id','Application ID'],['project_id','Project ID'],['name','Name']],
  apis:[['api_id','API ID'],['project_id','Project ID'],['name','Name']]
};
function renderAdminCreateFields(){
  const type=$('adminResourceType').value;
  $('adminCreateFields').textContent='';
  (adminCreateFields[type]||[]).forEach(([name,label])=>{
    const field=document.createElement('label');
    field.className='admin-create-field';
    field.textContent=label;
    const input=document.createElement('input');
    input.name=name;
    input.required=true;
    input.maxLength=160;
    input.autocomplete='off';
    input.placeholder=label;
    field.appendChild(input);
    $('adminCreateFields').appendChild(field);
  });
}
async function createAdminResource(event){
  event.preventDefault();
  if(String(state.account?.role||'').toUpperCase()!=='OWNER'){
    $('adminStatus').textContent='OWNER role required.';
    return;
  }
  const type=$('adminResourceType').value;
  if(!window.confirm('Create this '+type+' resource in the Owner management registry? This action is persisted and audited.'))return;
  const payload={};
  $('adminCreateFields').querySelectorAll('input[name]').forEach(input=>payload[input.name]=input.value.trim());
  if(Object.values(payload).some(value=>!value)){
    $('adminStatus').textContent='กรอกข้อมูลให้ครบทุกช่องก่อนสร้าง Resource';
    return;
  }
  $('adminCreateSubmit').disabled=true;
  $('adminStatus').textContent='กำลังสร้าง '+type+' ผ่าน Management API…';
  try{
    await request('/platform/v1/'+type,{method:'POST',body:JSON.stringify(payload)});
    $('adminCreateForm').reset();
    renderAdminCreateFields();
    $('adminStatus').textContent='สร้าง '+type+' สำเร็จและบันทึก Management Audit แล้ว';
    await refreshAdminConsole();
  }catch(error){
    $('adminStatus').textContent='สร้าง Resource ไม่สำเร็จ: '+String(error.message||error);
  }finally{$('adminCreateSubmit').disabled=false}
}
async function runAdminApiLifecycle(apiId,action){
  if(String(state.account?.role||'').toUpperCase()!=='OWNER')return;
  if(!['publish','disable'].includes(action))return;
  const verb=action==='publish'?'publish':'disable';
  if(!window.confirm('Confirm '+verb+' API '+apiId+'? This changes its persisted management lifecycle and records an audit event.'))return;
  const button=$('adminApis').querySelector('[data-admin-id="'+CSS.escape(apiId)+'"]');
  if(button)button.disabled=true;
  try{
    await request('/platform/v1/apis/'+encodeURIComponent(apiId)+'/'+action,{method:'POST',body:JSON.stringify({})});
    $('adminStatus').textContent='API '+apiId+' lifecycle changed: '+action+' · Management Audit recorded';
    await refreshAdminConsole();
  }catch(error){
    $('adminStatus').textContent='API lifecycle action failed: '+String(error.message||error);
    if(button)button.disabled=false;
  }
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
        const rendered=adminItem($(group.id),name,identifier+' · '+stateLabel);
        if(group.id==='adminApis'&&identifier){
          const action=String(item.lifecycle||'active').toLowerCase()==='active'?'disable':'publish';
          const button=document.createElement('button');
          button.type='button';
          button.className='subtle-button admin-lifecycle-action';
          button.textContent=action==='disable'?'Disable':'Publish';
          button.dataset.adminId=identifier;
          button.addEventListener('click',()=>runAdminApiLifecycle(identifier,action));
          rendered.appendChild(button);
        }
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


function pluginRecord(container,title,detail,status){
  const item=document.createElement('div');
  item.className='plugin-record';
  const copy=document.createElement('div');
  copy.className='plugin-record-copy';
  const heading=document.createElement('strong');
  heading.textContent=title||'Unnamed integration';
  const description=document.createElement('small');
  description.textContent=detail||'';
  copy.append(heading,description);
  item.appendChild(copy);
  if(status){
    const state=document.createElement('span');
    state.className='home-status-tag status-'+String(status).toLowerCase().replace(/[^a-z0-9_-]/g,'');
    state.textContent=status;
    item.appendChild(state);
  }
  container.appendChild(item);
}
async function refreshPluginCenter(){
  if(!$('pluginView')||$('pluginView').hidden)return;
  if(String(state.account?.role||'').toUpperCase()!=='OWNER'){
    $('pluginStatus').textContent='OWNER role required. Integration credentials and service scopes are shared backend resources.';
    return;
  }
  $('pluginStatus').textContent='กำลังอ่าน Integration Catalog และสถานะจาก API จริง…';
  $('pluginRefresh').disabled=true;
  try{
    const results=await Promise.allSettled([
      request('/v1/google-workspace/dashboard'),
      request('/v1/google-workspace/oauth/status'),
      request('/v1/ai/connections'),
      request('/v1/auth/providers'),
      request('/v1/providers')
    ]);
    const dashboard=results[0].status==='fulfilled'?results[0].value:null;
    const oauth=results[1].status==='fulfilled'?results[1].value:null;
    if(!dashboard||!oauth){
      $('pluginGoogleState').textContent='UNAVAILABLE';
      $('pluginGoogleDetail').textContent='Google Workspace API unavailable: '+String(results[0].reason||results[1].reason);
      $('pluginGoogleConnect').disabled=true;
      $('pluginGoogleDisconnect').disabled=true;
      $('pluginGoogleServices').textContent='No service data available.';
    }else{
      const connected=oauth.connected===true;
      $('pluginGoogleState').textContent=connected?'CONNECTED':dashboard.oauth_configured?'READY FOR OAUTH':'NOT CONFIGURED';
      $('pluginGoogleDetail').textContent='Account: '+String(oauth.account?.email||'Not connected')+' · token storage: backend only · OAuth configured: '+String(Boolean(dashboard.oauth_configured));
      $('pluginGoogleConnect').disabled=connected||!dashboard.oauth_configured;
      $('pluginGoogleDisconnect').disabled=!connected;
      $('pluginGoogleServices').textContent='';
      (dashboard.services||[]).forEach(service=>{
        const label=document.createElement('label');
        label.className='plugin-service';
        const input=document.createElement('input');
        input.type='checkbox';
        input.checked=service.enabled===true;
        input.dataset.service=service.service;
        const copy=document.createElement('span');
        copy.textContent=service.service+' · '+String(service.state||'UNKNOWN')+' · '+(Array.isArray(service.scopes)?service.scopes.join(', '):'scopes unavailable');
        label.append(input,copy);
        $('pluginGoogleServices').appendChild(label);
      });
      if(!(dashboard.services||[]).length)$('pluginGoogleServices').textContent='No Workspace services returned.';
    }
    $('pluginAIProviders').textContent='';
    if(results[2].status==='fulfilled'){
      const providers=Array.isArray(results[2].value.providers)?results[2].value.providers:[];
      providers.forEach(provider=>pluginRecord(
        $('pluginAIProviders'),
        provider.label||provider.provider,
        'credential configured: '+String(Boolean(provider.credential_configured))+' · endpoint configured: '+String(Boolean(provider.endpoint_configured))+' · model configured: '+String(Boolean(provider.model_configured)),
        provider.state||'UNKNOWN'
      ));
      if(!providers.length)pluginRecord($('pluginAIProviders'),'No AI providers returned','Configure supported providers on the backend','UNKNOWN');
    }else pluginRecord($('pluginAIProviders'),'AI provider status unavailable',String(results[2].reason),'UNAVAILABLE');
    $('pluginIdentityProviders').textContent='';
    if(results[3].status==='fulfilled'){
      const providers=Array.isArray(results[3].value.providers)?results[3].value.providers:[];
      providers.forEach(provider=>pluginRecord(
        $('pluginIdentityProviders'),
        provider.name||provider.id,
        'enabled: '+String(Boolean(provider.enabled))+' · configured: '+String(Boolean(provider.configured))+' · scopes: '+(Array.isArray(provider.scopes)?provider.scopes.join(', '):'not reported'),
        provider.available?'AVAILABLE':provider.enabled?'NOT CONFIGURED':'DISABLED'
      ));
      if(!providers.length)pluginRecord($('pluginIdentityProviders'),'No identity providers returned','No provider catalog entries','UNKNOWN');
    }else pluginRecord($('pluginIdentityProviders'),'Identity catalog unavailable',String(results[3].reason),'UNAVAILABLE');
    if(results[4].status==='fulfilled'){
      const value=results[4].value;
      pluginRecord($('pluginAIProviders'),'Active AI route provider',String(value.active||'UNKNOWN')+' · available adapters: '+(Array.isArray(value.providers)?value.providers.join(', '):'not reported'),'OBSERVED');
    }
    $('pluginStatus').textContent='แสดงสถานะจริงจาก Backend · Google Workspace lifecycle ใช้ OAuth และการตั้งค่า service ที่มีอยู่ · AI credentials ไม่ถูกส่งมายัง Browser';
    $('pluginUpdated').textContent='Updated '+new Date().toLocaleTimeString();
  }catch(error){
    $('pluginStatus').textContent='โหลด Plugin Center ไม่สำเร็จ: '+String(error.message||error);
  }finally{
    $('pluginRefresh').disabled=false;
  }
}
async function connectGoogleWorkspace(){
  if(String(state.account?.role||'').toUpperCase()!=='OWNER')return;
  $('pluginStatus').textContent='กำลังเริ่ม Google OAuth จาก Backend…';
  try{
    const result=await request('/v1/google-workspace/oauth/start',{method:'POST',body:JSON.stringify({})});
    if(!result.authorization_url)throw new Error('Backend did not return an OAuth authorization URL');
    window.location.assign(result.authorization_url);
  }catch(error){$('pluginStatus').textContent='เริ่ม OAuth ไม่สำเร็จ: '+String(error.message||error)}
}
async function disconnectGoogleWorkspace(){
  if(String(state.account?.role||'').toUpperCase()!=='OWNER')return;
  if(!window.confirm('Disconnect Google Workspace? This removes the backend OAuth token.'))return;
  $('pluginGoogleDisconnect').disabled=true;
  try{
    await request('/v1/google-workspace/oauth/disconnect',{method:'POST',body:JSON.stringify({})});
    await refreshPluginCenter();
  }catch(error){$('pluginStatus').textContent='Disconnect ไม่สำเร็จ: '+String(error.message||error);$('pluginGoogleDisconnect').disabled=false}
}
async function saveGoogleWorkspaceServices(){
  if(String(state.account?.role||'').toUpperCase()!=='OWNER')return;
  const enabled=[...$('pluginGoogleServices').querySelectorAll('input[data-service]:checked')].map(input=>input.dataset.service);
  $('pluginGoogleSave').disabled=true;
  try{
    await request('/v1/google-workspace/services',{method:'POST',body:JSON.stringify({enabled_services:enabled})});
    await refreshPluginCenter();
  }catch(error){$('pluginStatus').textContent='บันทึก Service settings ไม่สำเร็จ: '+String(error.message||error)}
  finally{$('pluginGoogleSave').disabled=false}
}

function workspaceRecord(title, detail, status) {
  const card=document.createElement('article');
  card.className='workspace-record';
  const heading=document.createElement('strong');
  heading.textContent=title||'Unnamed item';
  const description=document.createElement('small');
  description.textContent=detail||'';
  card.append(heading,description);
  if(status){
    const badge=document.createElement('span');
    badge.className='home-status-tag status-'+String(status).toLowerCase().replace(/[^a-z0-9_-]/g,'');
    badge.textContent=status;
    card.appendChild(badge);
  }
  $('workspaceContent').appendChild(card);
}
function workspaceEmpty(message){
  const empty=document.createElement('div');
  empty.className='home-empty';
  empty.textContent=message;
  $('workspaceContent').appendChild(empty);
}
async function refreshWorkspaceView(moduleName){
  if(!$('workspaceView')||$('workspaceView').hidden)return;
  $('workspaceTitle').textContent=moduleName||'Workspace';
  $('workspaceStatus').textContent='กำลังอ่านข้อมูลจาก Research OS API…';
  $('workspaceContent').textContent='';
  $('workspaceRefresh').disabled=true;
  try{
    if(!state.account||!state.account.email){
      $('workspaceStatus').textContent='ต้องลงชื่อเข้าใช้ก่อนจึงจะอ่านข้อมูลบัญชีได้';
      workspaceEmpty('Sign in required. ไม่มีการแสดงข้อมูลตัวอย่าง');
      return;
    }
    if(moduleName==='Projects & Files'){
      $('workspaceDescription').textContent='ProjectRegistry และ Workspace Index ที่มีอยู่จริง · โหมดอ่านข้อมูล';
      const results=await Promise.allSettled([request('/v1/projects'),request('/v2/workspaces')]);
      const projectResult=results[0];
      const workspaceResult=results[1];
      if(projectResult.status==='fulfilled'){
        const snapshot=projectResult.value;
        const projects=Array.isArray(snapshot.projects)?snapshot.projects:[];
        workspaceRecord('ProjectRegistry',String(snapshot.configured_count??projects.length)+' configured · '+String(snapshot.supported_project_contexts??'—')+' supported contexts · release authority '+String(snapshot.release_authority??'UNKNOWN'),'LIVE');
        if(!projects.length)workspaceEmpty('ProjectRegistry ยังไม่มี project ที่ตั้งค่าไว้');
        projects.forEach(project=>workspaceRecord(
          project.display_name||project.project_id,
          String(project.project_id||'unknown')+' · v'+String(project.version??'unknown')+' · '+(Array.isArray(project.capabilities)?project.capabilities.join(', '):'capabilities not reported'),
          project.status||'REGISTERED'
        ));
      }else{
        workspaceRecord('ProjectRegistry unavailable',String(projectResult.reason),'UNAVAILABLE');
      }
      if(workspaceResult.status==='fulfilled'){
        const workspaces=Array.isArray(workspaceResult.value.workspaces)?workspaceResult.value.workspaces:[];
        workspaceRecord('Workspace Index',String(workspaces.length)+' workspace(s) returned by /v2/workspaces','LIVE');
        workspaces.forEach(workspace=>workspaceRecord(
          workspace.name||workspace.workspace_id||workspace.id,
          String(workspace.workspace_id||workspace.id||'unknown')+' · '+String(workspace.description||workspace.kind||'Workspace record'),
          workspace.status||'REGISTERED'
        ));
      }else{
        workspaceRecord('Workspace Index unavailable',String(workspaceResult.reason),'UNAVAILABLE');
      }
      $('workspaceStatus').textContent='แสดงเฉพาะข้อมูลจริงจาก ProjectRegistry และ Workspace Index · หน้านี้ยังไม่สร้าง/แก้ไข/ลบ project หรือไฟล์';
    }else if(moduleName==='History & Activity'){
      $('workspaceDescription').textContent='งานและ Workflow ที่อ่านได้จาก API จริง พร้อมสถานะและเวลา · read-only';
      const results=await Promise.allSettled([
        request('/api/v1/jobs?limit=50'),
        request('/v1/agents/orchestrations?limit=50')
      ]);
      let total=0;
      if(results[0].status==='fulfilled'){
        const jobs=Array.isArray(results[0].value.jobs)?results[0].value.jobs:[];
        workspaceRecord('Execution Jobs',jobs.length+' job(s) returned by /api/v1/jobs','LIVE');
        total+=jobs.length;
        if(!jobs.length)workspaceEmpty('ยังไม่มี execution jobs');
        jobs.forEach(job=>workspaceRecord(
          job.task_type||job.job_id,
          String(job.job_id||'unknown')+' · '+formatHomeTime(job.updated_at||job.created_at),
          job.status||'UNKNOWN'
        ));
      }else workspaceRecord('Execution Jobs unavailable',String(results[0].reason),'UNAVAILABLE');
      if(results[1].status==='fulfilled'){
        const runs=Array.isArray(results[1].value.runs)?results[1].value.runs:(Array.isArray(results[1].value.orchestrations)?results[1].value.orchestrations:[]);
        workspaceRecord('Workflow Runs',runs.length+' run(s) returned by orchestration API','LIVE');
        total+=runs.length;
        if(!runs.length)workspaceEmpty('ยังไม่มี workflow runs');
        runs.forEach(run=>workspaceRecord(
          run.objective||run.run_id,
          String(run.run_id||'unknown')+' · '+formatHomeTime(run.updated_at||run.created_at),
          run.status||'UNKNOWN'
        ));
      }else workspaceRecord('Workflow Runs unavailable',String(results[1].reason),'UNAVAILABLE');
      $('workspaceStatus').textContent='โหลด '+total+' รายการจาก Jobs และ Workflow API · รายละเอียดหลักฐานจะแสดงเมื่อ API ต้นทางส่งกลับ';
    }else if(moduleName==='Settings & Account'){
      $('workspaceDescription').textContent='ข้อมูลบัญชี ผู้ให้บริการ และสถานะการเชื่อมต่อ · ไม่มีการเปิดเผย Secret';
      const results=await Promise.allSettled([
        request('/v1/auth/status'),
        request('/v1/auth/providers'),
        request('/v1/providers'),
        request('/v1/ai/connections')
      ]);
      const labels=['Authenticated Account','Login Providers','AI Providers','AI Provider Connections'];
      results.forEach((result,index)=>{
        if(result.status!=='fulfilled'){
          workspaceRecord(labels[index]+' unavailable',String(result.reason),'UNAVAILABLE');
          return;
        }
        const value=result.value;
        if(index===0){
          const account=value.account||value.user||value;
          workspaceRecord(labels[index],String(account.email||account.user_id||'Session active')+' · role '+String(account.role||value.role||'UNKNOWN'),value.authenticated===false?'UNKNOWN':'AVAILABLE');
        }else if(index===1){
          const providers=Array.isArray(value.providers)?value.providers:[];
          workspaceRecord(labels[index],providers.map(item=>String(item.label||item.id||item.name)+' '+(item.available?'available':'not configured')).join(' · ')||'No providers returned','LIVE');
        }else if(index===2){
          workspaceRecord(labels[index],'Active provider: '+String(value.active||'UNKNOWN')+' · available: '+(Array.isArray(value.providers)?value.providers.join(', '):'not reported'),'LIVE');
        }else{
          const providers=Array.isArray(value.providers)?value.providers:[];
          workspaceRecord(labels[index],providers.map(item=>String(item.label||item.provider)+' · '+String(item.state||'UNKNOWN')+' · credential configured: '+String(Boolean(item.credential_configured))+' · model configured: '+String(Boolean(item.model_configured))).join(' | ')||'No connection status returned',value.safe===false?'WARNING':'LIVE');
        }
      });
      $('workspaceStatus').textContent='ข้อมูลการตั้งค่าเป็น read-only; ไม่แสดงค่า Secret และยังไม่เปิดปุ่มเปลี่ยนค่าที่ไม่มี API รองรับ';
    }else{
      $('workspaceStatus').textContent='โมดูลนี้ยังเป็น Architecture Directory';
      workspaceEmpty('ยังไม่มี API binding สำหรับโมดูลนี้ จึงไม่แสดงสถานะ Connected หรือข้อมูลจำลอง');
    }
    $('workspaceUpdated').textContent='Updated '+new Date().toLocaleTimeString();
  }catch(error){
    $('workspaceStatus').textContent='โหลดข้อมูลไม่สำเร็จ: '+String(error.message||error);
    workspaceEmpty('API ไม่พร้อมใช้งาน · ไม่มีการใช้ข้อมูลจำลองแทน');
  }finally{
    $('workspaceRefresh').disabled=false;
  }
}

// Platform workspace navigation and responsive controls.
function setPlatformView(view,moduleName){
  let selected=view||'home';
  if(selected==='admin'&&String(state.account?.role||'').toUpperCase()!=='OWNER')selected='home';
  $('homeView').hidden=selected!=='home';
  $('chatView').hidden=selected!=='chat';
  $('registryView').hidden=selected!=='registry';
  if(selected==='plugins'&&String(state.account?.role||'').toUpperCase()!=='OWNER')selected='home';
  $('workspaceView').hidden=selected!=='workspace';
  $('pluginView').hidden=selected!=='plugins';
  $('adminView').hidden=selected!=='admin';
  document.querySelectorAll('.nav-link').forEach(button=>button.classList.toggle('active',button.dataset.view===selected&&(!['registry','workspace'].includes(selected)||button.dataset.module===moduleName)));
  $('pageTitle').textContent=selected==='home'?'Control Center':selected==='chat'?'Research Chat':selected==='admin'?'Admin Console':selected==='plugins'?'Plugin Center':selected==='workspace'?(moduleName||'Workspace'):(moduleName||'Platform Directory');
  if(selected==='registry')$('registryTitle').textContent=moduleName||'Platform domains';
  document.body.classList.remove('focus-mode');
  if(selected==='chat')setChatWide(state.chatWide);else document.body.classList.remove('chat-wide-mode');
  $('sidebar').classList.remove('open');
  $('sidebarScrim').classList.remove('open');
  if(selected==='home')refreshControlCenter();
  if(selected==='workspace')refreshWorkspaceView(moduleName);
  if(selected==='plugins')refreshPluginCenter();
  if(selected==='admin')refreshAdminConsole();
}
document.querySelectorAll('.nav-link').forEach(button=>button.addEventListener('click',()=>{
  setPlatformView(button.dataset.view,button.dataset.module);
}));
$('returnChat').addEventListener('click',()=>setPlatformView('chat'));
$('refreshAdminConsole').addEventListener('click',refreshAdminConsole);
$('adminResourceType').addEventListener('change',renderAdminCreateFields);
$('adminCreateForm').addEventListener('submit',createAdminResource);
renderAdminCreateFields();

$('refreshControlCenter').addEventListener('click',refreshControlCenter);
$('workspaceRefresh').addEventListener('click',()=>refreshWorkspaceView($('workspaceTitle').textContent));
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
  persistChatHistory();
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
