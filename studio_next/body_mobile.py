"""Phone-sized production BODY console. Unprivileged static files only.

The service still binds only to loopback. A separately configured, authenticated
HTTPS access layer is required for any remote/mobile browser access.
"""
from __future__ import annotations

PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZX7 Studio | Production</title><link rel="stylesheet" href="/studio.css"></head>
<body><main><header><h1>ZX7 <span>STUDIO</span></h1><p>Original media · real tools · recoverable projects</p></header>
<section id="diagnostics-panel" aria-label="System evidence">
<h2>System diagnostics</h2><p>Evidence, not a fabricated AI power score. Requires a private host connection.</p>
<div class="diagnostic-grid" id="diagnostic-grid" aria-live="polite"><div>Connect to inspect real capabilities and blockers.</div></div>
<button id="diagnostics-button" disabled>Refresh diagnostic evidence</button>
<details><summary>Observed limitations and next checks</summary><div id="diagnostic-issues">Not measured</div></details>
</section>
<section><h2>Connect</h2><p>Host token is kept only in this browser tab, never saved.</p>
<label for="token">Studio host token</label><input id="token" type="password" autocomplete="off" placeholder="Host token (32+ characters)">
<button id="connect">Connect</button><output id="status" aria-live="polite"></output></section>
<section><h2>Production capabilities</h2><button id="tools-button" disabled>Discover actual tools</button><div id="tools"></div></section>
<section><h2>Actual host capacity</h2><p>Live measurements only. Detected GPU does not mean an installed cinematic model.</p>
<button id="resources-button" disabled>Measure resources</button><pre id="resources"></pre></section>
<section><h2>Original media import</h2><p>Rights evidence is mandatory.</p>
<label for="asset-space">Workspace ID</label><input id="asset-space" placeholder="my_film">
<label for="source">Original source ID</label><input id="source">
<label for="rights">Rights evidence</label><textarea id="rights"></textarea>
<label for="asset">Media file</label><input id="asset" type="file">
<button id="upload" disabled>Import verified media</button><output id="upload-status"></output></section>
<section><h2>Create from a brief</h2><p id="creative-runtime">Connect to check the local creative model.</p>
<label for="creative-workspace">Workspace ID</label><input id="creative-workspace" placeholder="my_film">
<label for="creative-brief">What should the studio create?</label><textarea id="creative-brief" placeholder="Describe your goal, audience and creative needs. You can use your phone keyboard's dictation."></textarea>
<label for="creative-facts">Known facts (optional, one per line)</label><textarea id="creative-facts"></textarea>
<button id="creative-submit" disabled>Create</button><button id="creative-refresh" disabled>Refresh creative progress</button>
<button id="creative-stop" disabled>Stop creative session</button>
<output id="creative-status" aria-live="polite"></output></section>
<section><h2>Submit authored film</h2><p>The BODY accepts original Film IR. It does not write or change the screenplay.</p>
<label for="workspace">Workspace ID</label><input id="workspace">
<label for="film">Original Film IR JSON</label><input id="film" type="file" accept=".json,application/json">
<button id="submit" disabled>Submit film</button><output id="submit-status"></output></section>
<section><h2>Non-destructive edit impact</h2><p>Compare two original Film IR revisions. This checks graph changes; real cached media must still be verified before reuse.</p>
<label for="before-film">Earlier approved Film IR</label><input id="before-film" type="file" accept=".json,application/json">
<label for="after-film">Revised Film IR</label><input id="after-film" type="file" accept=".json,application/json">
<button id="impact-button" disabled>Preview affected operations</button>
<pre id="impact"></pre></section>
<section><h2>Durable jobs</h2><button id="jobs-button" disabled>Refresh jobs</button><div id="jobs"></div></section>
<footer>Local studio control · output quality depends on the installed model and tools.</footer></main>
<script defer src="/studio.js"></script></body></html>"""

STYLE = """*{box-sizing:border-box}body{margin:0;background:#0d131a;color:#f5f7fb;font:16px system-ui,sans-serif}main{max-width:720px;margin:0 auto;padding:18px 15px 70px}
h1{letter-spacing:.08em}h1 span{color:#eac572}header p,p,footer{font-size:14px;color:#b0bcc9;line-height:1.5}
section{background:#19232e;border:1px solid #344454;padding:19px;border-radius:15px;margin:16px 0}
h2{font-size:19px}label{display:block;font-size:13px;margin:14px 0 6px}input,textarea{width:100%;padding:12px;background:#0f1922;color:#fff;border:1px solid #637488;border-radius:8px;font:inherit}
button{margin:12px 7px 5px 0;border:0;border-radius:9px;padding:12px 14px;min-height:44px;font:700 14px system-ui;background:#eac572;color:#10141a}
button:disabled{opacity:.4}button:focus,input:focus,textarea:focus{outline:2px solid #eac572}
output{display:block;overflow-wrap:anywhere;white-space:pre-wrap}.entry{border-top:1px solid #394958;padding:12px 0;overflow-wrap:anywhere}
pre{white-space:pre-wrap;font-size:12px}footer{text-align:center;padding:20px}
.diagnostic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(125px,1fr));gap:10px;margin:12px 0}
.diagnostic-card{background:#101d28;border:1px solid #415669;border-radius:10px;padding:12px;min-width:0}
.diagnostic-card strong{display:block;font-size:19px;margin-top:4px;overflow-wrap:anywhere}
.diagnostic-card span{font-size:12px;color:#b0bcc9}
#diagnostic-issues .entry{font-size:13px}details{margin-top:8px}summary{cursor:pointer}
"""

SCRIPT = r"""(()=>{
'use strict';
let secret=null,creativeSession=null,creativeReady=false,creativeTimer=null;
const e=id=>document.getElementById(id);
const print=(id,msg)=>{e(id).textContent=String(msg)};
const node=(tag,msg)=>{const n=document.createElement(tag);n.textContent=String(msg);return n};
const valid=x=>typeof x==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(x);
async function api(path,options={}){
 if(!secret)throw Error('Connect first');
 const headers={'Authorization':'Bearer '+secret,...options.headers};
 const r=await fetch(path,{...options,headers,cache:'no-store',credentials:'omit'});
 if(!r.ok){let s='HTTP '+r.status;try{s=(await r.json()).error||s}catch(_){}throw Error(s)}
 return r.json();
}
function enabled(v){if(!v&&creativeTimer){clearTimeout(creativeTimer);creativeTimer=null}for(const id of ['diagnostics-button','tools-button','resources-button','impact-button','jobs-button','upload','submit','creative-refresh','creative-stop'])e(id).disabled=!v}
function diagnosticCard(label,value){
 const n=document.createElement('div');n.className='diagnostic-card';
 const heading=node('span',label),data=node('strong',value);
 n.append(heading,data);return n;
}
async function diagnostics(){
 const view=await api('/v1/diagnostics'),body=view.body||{},brain=view.model||{},
       jobs=view.jobs||{},host=view.host||{},pairs=view.controlled_comparisons||{};
 const root=e('diagnostic-grid');root.replaceChildren();
 root.append(diagnosticCard('Installed operations',body.installed_operations??'Unknown'),
   diagnosticCard('Capability families',body.capability_families??'Unknown'),
   diagnosticCard('Local model',brain.configured?
       'Configured · '+(brain.capability_assessment||'unmeasured'):'Not configured'),
   diagnosticCard('Durable failures',Number(jobs.by_state?.blocked||0)+Number(jobs.by_state?.failed||0)),
   diagnosticCard('Controlled model/BODY comparisons',pairs.observed_pairs??0),
   diagnosticCard('Creative quality',brain.independent_creativity||'unmeasured'));
 const issues=e('diagnostic-issues');issues.replaceChildren();
 for(const issue of (view.diagnostics||[]).slice(0,12)){
   const block=node('div',(issue.layer||'Unknown')+' / '+(issue.code||'unmeasured')
     +' — '+(issue.next_check||'Review actual source evidence'));
   block.className='entry';issues.append(block);
 }
 if(!(view.diagnostics||[]).length)issues.append(node('div','No recorded blockers; unmeasured areas are not certified.'));
 const families=(body.capabilities||[]).filter(x=>x.needs_setup_operations);
 for(const family of families.slice(0,8)){
    const item=node('div',family.name+': '+family.needs_setup_operations
       +' operations need setup — '+(family.operations_needing_setup||[]).join(', '));
    item.className='entry';issues.append(item);
 }
}
async function tools(){
 const root=e('tools');root.replaceChildren();
 for(const t of (await api('/v1/tools')).tools||[]){const n=node('div',t.tool_id+' — '+t.capability+' ('+t.access+')');n.className='entry';root.append(n)}
}
async function resources(){
 const report=await api('/v1/resources');
 const disk=report.workspace_disk||{},gpu=report.nvidia_gpu_driver||{};
 print('resources','CPU: '+report.cpu_logical_processors+' logical threads\n'
  +'Free host disk: '+disk.free_bytes+' bytes\n'
  +'Host RAM available: '+report.memory?.available_bytes+' bytes\n'
  +'GPU driver: '+gpu.driver_query_status+' ('+(gpu.devices||[]).length+' reported devices)\n'
  +'GPU hardware is NOT evidence of an installed original-film generation model');
}
async function jobs(){
 const root=e('jobs');root.replaceChildren();
 const payload=await api('/v1/jobs'),rows=Array.isArray(payload)?payload:(payload.jobs||[]);
 for(const item of rows){const id=item.id||item.job_id;if(!valid(id))continue;
   const div=node('div',id+' — '+item.status);div.className='entry';root.append(div);
   const info=document.createElement('pre');div.append(info);
   for(const action of ['status','artifacts','pause','resume','retry','cancel']){
     const b=node('button',action);div.append(b);
     b.onclick=async()=>{try{
       if(action==='status')info.textContent=JSON.stringify(await api('/v1/jobs/'+id),null,2);
       else if(action==='artifacts'){
         const listing=await api('/v1/jobs/'+id+'/artifacts');
         info.replaceChildren();
         for(const media of listing.assets||[]){
           const line=document.createElement('div');line.className='entry';info.append(line);
           line.append(node('span',media.path+' — '+media.bytes+' bytes '));
           const download=node('button','Authorize download');line.append(download);
           download.onclick=async()=>{try{
             const encoded=media.path.split('/').map(encodeURIComponent).join('/');
             const receipt=await api('/v1/jobs/'+id+'/artifacts/'+encoded+'/download-ticket',
               {method:'POST',body:new Uint8Array(0)});
             const link=node('a','Download now (single use, expires in '+receipt.expires_in_seconds+'s)');
             link.href=receipt.url;link.download=media.path.split('/').pop();
             link.rel='noreferrer';line.append(document.createElement('br'),link);
           }catch(err){print('status',err.message)}};
         }
       }
       else{
         if(['cancel','retry'].includes(action)&&!confirm(action+' original project?'))return;
         await api('/v1/jobs/'+id+'/'+action,{method:'POST',body:new Uint8Array(0)});await jobs();
       }
     }catch(err){print('status',err.message)}};
   }
 }
}
e('connect').onclick=async()=>{
 const key=e('token').value;if(key.length<32){print('status','Token must contain at least 32 characters');return}
 secret=key;e('token').value='';
 try{const health=await api('/v1/health');creativeReady=health.creative_model_configured===true;enabled(true);e('creative-submit').disabled=!creativeReady;print('creative-runtime',creativeReady?'A local creative model is configured. Describe your idea to begin.':'Local creative model is not configured on this host.');print('status','Connected, token stays in tab memory');await Promise.all([tools(),jobs(),resources(),diagnostics()])}
 catch(err){secret=null;enabled(false);e('creative-submit').disabled=true;print('status',err.message)}
};
async function creativeProgress(){
 if(creativeTimer){clearTimeout(creativeTimer);creativeTimer=null}
 if(!creativeSession)throw Error('Create a brief first');
 const state=await api('/v1/creative-sessions/'+encodeURIComponent(creativeSession));
 const last=state.events?.at(-1);
 print('creative-status',state.status+' · '+(state.events||[]).length+' decisions\n'+(state.summary||state.question||state.error||last?.decision?.reason||'Working')+'\n'+(last?.result?.error||'')+'\nJobs: '+(state.jobs||[]).join(', '));
 if(['queued','running'].includes(state.status))creativeTimer=setTimeout(()=>creativeProgress().catch(err=>print('creative-status',err.message)),1500);
}
e('creative-submit').onclick=async()=>{try{
 const workspace=e('creative-workspace').value.trim(),brief=e('creative-brief').value.trim();
 if(!valid(workspace)||!brief)throw Error('Enter workspace ID and your creative brief');
 const facts={};e('creative-facts').value.split('\n').map(x=>x.trim()).filter(Boolean).forEach((line,i)=>facts['fact_'+(i+1)]=line);
 const session=await api('/v1/creative-sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:workspace,brief,facts})});
 creativeSession=session.session_id;await creativeProgress();
}catch(err){print('creative-status',err.message)}};
e('creative-stop').onclick=async()=>{try{if(!creativeSession)throw Error('No active creative session');await api('/v1/creative-sessions/'+encodeURIComponent(creativeSession)+'/stop',{method:'POST'});print('creative-status','Stop requested. Use job controls to stop an existing render.')}catch(err){print('creative-status',err.message)}};
e('creative-refresh').onclick=()=>creativeProgress().catch(err=>print('creative-status',err.message));
e('diagnostics-button').onclick=()=>diagnostics().catch(err=>print('status',err.message));
e('tools-button').onclick=()=>tools().catch(err=>print('status',err.message));
e('resources-button').onclick=()=>resources().catch(err=>print('status',err.message));
e('jobs-button').onclick=()=>jobs().catch(err=>print('status',err.message));
e('impact-button').onclick=async()=>{
 try{
  const old=e('before-film').files[0],updated=e('after-film').files[0];
  if(!old||!updated||old.size>1800000||updated.size>1800000)
    throw Error('Two original Film IR files below 1.8 MB each are required');
  const payload={before:JSON.parse(await old.text()),after:JSON.parse(await updated.text())};
  const report=await api('/v1/revisions/impact',{method:'POST',
       headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  print('impact','Candidate unaffected stages: '+report.original_unchanged_candidates.join(', ')
    +'\nStages requiring new execution: '+report.new_or_changed_operations.join(', ')
    +'\nDeleted original stages: '+report.deleted_original_operations.join(', ')
    +'\nOriginal source bytes and rights must be reverified at runtime');
 }catch(err){print('impact',err.message)}
};
e('submit').onclick=async()=>{try{
 const space=e('workspace').value.trim(),file=e('film').files[0];
 if(!valid(space)||!file||!file.size||file.size>4000000)throw Error('Workspace and JSON under 4 MB required');
 const ir=JSON.parse(await file.text());
 const receipt=await api('/v1/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:space,film_ir:ir})});
 print('submit-status',JSON.stringify(receipt));await jobs()
}catch(err){print('submit-status',err.message)}};
e('upload').onclick=async()=>{try{
 const space=e('asset-space').value.trim(),source=e('source').value.trim(),rights=e('rights').value.trim(),file=e('asset').files[0];
 if(!valid(space)||!source||!rights||!file||!file.size||file.size>1073741824)throw Error('Workspace, source, rights and file <=1 GB required');
 if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,179}$/.test(file.name))throw Error('Unsafe filename');
 const b64=s=>{let raw='';for(const v of new TextEncoder().encode(s))raw+=String.fromCharCode(v);return btoa(raw)};
 const receipt=await api('/v1/workspaces/'+space+'/assets/'+encodeURIComponent(file.name),{method:'POST',body:file,
 headers:{'Content-Type':file.type||'application/octet-stream','X-Source-Id-B64':b64(source),'X-Rights-Evidence-B64':b64(rights)}});
 print('upload-status',JSON.stringify(receipt))
}catch(err){print('upload-status',err.message)}};
})();"""

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
ASSETS = {
    "/studio": ("text/html; charset=utf-8", PAGE.encode("utf-8")),
    "/studio.css": ("text/css; charset=utf-8", STYLE.encode("utf-8")),
    "/studio.js": ("text/javascript; charset=utf-8", SCRIPT.encode("utf-8")),
}
