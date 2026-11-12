/* Original explorer code: MIT. Data rights are stated in each bundle. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PKOC=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const compare=(a,b)=>String(a)<String(b)?-1:String(a)>String(b)?1:0;
const key=(workflow,id)=>workflow+':'+id;
const unique=values=>[...new Set(values)].sort(compare);
function assert(condition,message){if(!condition)throw new Error(message);}
function list(value){return Array.isArray(value)?value:value==null?[]:[value];}
const ARRAYS=['reports','nodes','occurrences','claims','attributes','paragraphs','sentences','interventions','correspondence','reference_units','networks','codebook'];
function strings(value,label){assert(Array.isArray(value)&&value.every(v=>typeof v==='string'&&v.length>0),label+' must be an array of nonempty strings.');assert(new Set(value).size===value.length,label+' contains duplicates.');return value;}
function rowsBy(rows,fields,label){assert(Array.isArray(rows),label+' must be an array.');const out=new Map();for(const row of rows){assert(row&&typeof row==='object'&&!Array.isArray(row),label+' rows must be objects.');const parts=fields.map(f=>row[f]);assert(parts.every(v=>typeof v==='string'&&v.length>0),'Missing '+label+' identifier.');const id=JSON.stringify(parts);assert(!out.has(id),'Duplicate '+label+' identity.');out.set(id,row);}return out;}
function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort(compare).map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';return JSON.stringify(value);}
function publicFields(value){
 const forbidden=new Set(['text','paragraph_text','source_text','raw_text','raw_request','raw_response','request_body','response_body','journal','api_key','authorization','model_path','snapshot_path','reason','note']);
 const privateMarker=/(?:(?<![A-Za-z0-9])[A-Za-z]:[\\\/]|\/(?:Users|home)\/|\\\\[^\\]+\\|-----BEGIN .*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})/;
 function check(v){if(Array.isArray(v)){for(const item of v)check(item);}else if(v&&typeof v==='object'){for(const [k,item]of Object.entries(v)){assert(!forbidden.has(k.toLowerCase()),'Private or full-text field is not permitted in an explorer bundle: '+k);check(item);}}else if(typeof v==='string')assert(!privateMarker.test(v),'A private path or credential marker is not permitted in an explorer bundle.');else if(typeof v==='number')assert(Number.isFinite(v),'Nonfinite number in explorer bundle.');}check(value);
}
function matchesTrustedStudy(bundle,trusted){
 return !!(trusted&&trusted.schema==='pkoc-explorer-v1'&&trusted.dataset?.kind==='frozen-study'&&trusted.dataset?.id==='unmil-revision-04'&&bundle.dataset?.id===trusted.dataset.id&&canonical(bundle)===canonical(trusted));
}
function baselineSelection(bundle,{workflow,scale,reportIds,trustedStudy=false}={}){
 if(!trustedStudy||bundle.dataset.kind!=='frozen-study'||bundle.dataset.id!=='unmil-revision-04'||!['L','A'].includes(workflow))return false;
 const all=bundle.reports.map(r=>r.report_id).sort(compare),selected=(reportIds===undefined?all:[...reportIds]).sort(compare);
 if(canonical(all)!==canonical(selected))return false;
 return bundle.networks.some(n=>n.workflow===workflow&&n.scale===scale&&!n.reference_only&&canonical([...n.report_ids].sort(compare))===canonical(all));
}
function validateBundle(b){
 assert(b&&typeof b==='object'&&!Array.isArray(b),'The bundle must be a JSON object.');
 assert(b.schema==='pkoc-explorer-v1','Unsupported bundle version. Expected pkoc-explorer-v1.');
 assert(Object.keys(b).every(k=>['schema','dataset','provenance',...ARRAYS].includes(k)),'Unknown bundle root field.');
 assert(b.dataset&&typeof b.dataset.id==='string'&&b.dataset.id.length>0&&typeof b.dataset.title==='string','Dataset identity is missing.');
 assert(b.provenance&&typeof b.provenance==='object'&&!Array.isArray(b.provenance),'Provenance must be an object.');
 for(const field of ARRAYS)assert(Array.isArray(b[field]),'Expected an array: '+field);
 const rosters=strings(b.dataset.rosters,'dataset.rosters');assert(rosters.length>0&&rosters.every(w=>['L','A','R'].includes(w)),'Unsupported declared workflow.');
 assert(['frozen-study','model-only'].includes(b.dataset.kind),'Dataset kind must distinguish frozen-study from model-only output.');
 assert(b.dataset.kind!=='model-only'||canonical(rosters)==='["L"]','Automated model-only cases can expose only the L branch.');
 assert(b.reports.length<=10000&&b.nodes.length<=10000&&b.occurrences.length<=1000000,'Bundle exceeds the supported browser size.');
 const reports=new Map(),actors=new Map(),paragraphs=new Map(),sentences=new Map();
 rowsBy(b.reports,['report_id'],'report');for(const r of b.reports){
  reports.set(r.report_id,r);assert(r.year==null||(Number.isInteger(r.year)&&r.year>=1000&&r.year<=9999),'Invalid report year.');
  if(r.report_date!=null){assert(typeof r.report_date==='string'&&/^\d{4}(?:-\d{2}(?:-\d{2})?)?$/.test(r.report_date),'Date must preserve available ISO precision.');const [year,month=1,day=1]=r.report_date.split('-').map(Number);const days=[31,year%4===0&&(year%100!==0||year%400===0)?29:28,31,30,31,30,31,31,30,31,30,31];assert(year>0&&month>=1&&month<=12&&day>=1&&day<=days[month-1],'Invalid report date.');assert(r.year==null||r.year===year,'Report year/date mismatch.');}
  assert(!r.official_url||safeSourceUrl(r.official_url),'Official source URL must be HTTPS without embedded credentials.');
 }
 rowsBy(b.nodes,['workflow','actor_id'],'actor');for(const n of b.nodes){assert(rosters.includes(n.workflow)&&typeof n.name==='string','Actor has undeclared workflow or invalid name.');actors.set(key(n.workflow,n.actor_id),n);for(const f of ['aliases','cameo_codes','primary_cameo_codes'])strings(n[f]||[],'actor.'+f);if(n.layout!=null)assert(n.layout&&Number.isFinite(n.layout.x)&&Number.isFinite(n.layout.y),'Actor layout requires finite x/y.');}
 rowsBy(b.paragraphs,['paragraph_id'],'paragraph');for(const p of b.paragraphs){assert(reports.has(p.report_id),'Invalid paragraph report reference.');assert(!Object.hasOwn(p,'text'),'Full source text must be loaded separately, not embedded in a public bundle.');assert(typeof p.text_sha256==='string'&&/^[a-f0-9]{64}$/.test(p.text_sha256),'Paragraph hash is missing or malformed.');paragraphs.set(p.paragraph_id,p);}
 rowsBy(b.sentences,['sentence_id'],'sentence');for(const s of b.sentences){assert(paragraphs.has(s.paragraph_id)&&reports.has(s.report_id),'Invalid sentence reference.');assert(Number.isInteger(s.start)&&Number.isInteger(s.end)&&s.start>=0&&s.end>s.start,'Invalid sentence coordinates.');assert(paragraphs.get(s.paragraph_id).report_id===s.report_id,'Sentence crosses report boundaries.');sentences.set(s.sentence_id,s);}
 rowsBy(b.occurrences,['workflow','occurrence_id'],'occurrence');for(const o of b.occurrences){
  assert(rosters.includes(o.workflow),'Occurrence has an undeclared workflow.');
  assert(reports.has(o.report_id)&&paragraphs.has(o.paragraph_id),'Occurrence source is absent.');
  assert(paragraphs.get(o.paragraph_id).report_id===o.report_id,'Occurrence crosses report boundaries.');
  assert(o.actor_id==null||actors.has(key(o.workflow,o.actor_id)),'Occurrence actor is absent.');
  assert(o.sentence_id==null||sentences.has(o.sentence_id),'Occurrence sentence is absent.');
  assert((o.start==null&&o.end==null)||(Number.isInteger(o.start)&&Number.isInteger(o.end)&&o.start>=0&&o.end>o.start),'Invalid occurrence coordinates.');
  assert(typeof o.surface==='string'&&typeof o.grounding_status==='string'&&o.grounding_status.length>0,'Occurrence requires surface and grounding status strings.');
  if(o.start!=null&&o.grounding_status==='grounded')assert(Array.from(o.surface).length===o.end-o.start,'Grounded surface length disagrees with codepoint offsets.');
  if(o.sentence_id!=null){const sentence=sentences.get(o.sentence_id);assert(sentence.paragraph_id===o.paragraph_id,'Occurrence sentence belongs to a different paragraph.');if(o.start!=null)assert(sentence.start<=o.start&&o.end<=sentence.end,'Occurrence extends beyond its sentence.');}
 }
 for(const [array,keys]of [['attributes',['workflow','actor_id','report_id']],['claims',['workflow','actor_id','claim_key']]]){rowsBy(b[array],keys,array);for(const a of b[array]){assert(actors.has(key(a.workflow,a.actor_id)),'Invalid '+array+' actor reference.');if(array==='attributes')assert(reports.has(a.report_id),'Invalid attribute report reference.');for(const f of ['role_codes','specialty_codes','cameo_codes',...(array==='attributes'?['primary_cameo_codes']:[])])strings(a[f]||[],array+'.'+f);}}
 strings(b.reference_units,'reference_units');assert(b.reference_units.every(id=>paragraphs.has(id)),'Reference paragraph is unavailable.');
 for(const graph of b.networks){
  assert(rosters.includes(graph.workflow)&&['sentence','paragraph','report'].includes(graph.scale),'Invalid embedded network workflow/scale.');strings(graph.report_ids,'network.report_ids');assert(graph.report_ids.every(id=>reports.has(id)),'Embedded network selects an unknown report.');assert(typeof graph.reference_only==='boolean','Embedded network reference_only must be boolean.');
  rowsBy(graph.nodes,['actor_id'],'network actor');assert(Array.isArray(graph.edges),'Embedded network edges must be an array.');
  for(const edge of graph.edges){strings(edge.unit_ids,'edge.unit_ids');assert(Number.isInteger(edge.weight)&&edge.weight>=1&&edge.weight===edge.unit_ids.length,'Edge weight must count distinct units.');}
  const expected=project(b,{workflow:graph.workflow,scale:graph.scale,reportIds:graph.report_ids,referenceOnly:graph.reference_only});
  for(const field of ['edges','incidences','summary','exclusions'])assert(canonical(graph[field])===canonical(expected[field]),'Embedded network '+field+' disagrees with projection.');
  const measured=expected.nodes.map(n=>[n.actor_id,n.degree,n.strength]).sort((a,b)=>compare(a[0],b[0])),supplied=graph.nodes.map(n=>[n.actor_id,n.degree,n.strength]).sort((a,b)=>compare(a[0],b[0]));assert(canonical(measured)===canonical(supplied),'Embedded network drops isolates or changes degree/strength.');
 }
 publicFields(b);return b;
}
function indexBundle(bundle){
 validateBundle(bundle);
 const reports=new Map(bundle.reports.map(r=>[r.report_id,r])),nodes=new Map(bundle.nodes.map(n=>[key(n.workflow,n.actor_id),n]));
 const paragraphs=new Map(bundle.paragraphs.map(p=>[p.paragraph_id,p])),sentences=new Map(bundle.sentences.map(s=>[s.sentence_id,s]));
 const occurrences=new Map(),attributes=new Map(),claims=new Map();
 for(const o of bundle.occurrences){const k=key(o.workflow,o.actor_id);if(!occurrences.has(k))occurrences.set(k,[]);occurrences.get(k).push(o);}
 for(const a of bundle.attributes){const k=key(a.workflow,a.actor_id);if(!attributes.has(k))attributes.set(k,[]);attributes.get(k).push(a);}
 for(const c of bundle.claims){const k=key(c.workflow,c.actor_id);if(!claims.has(k))claims.set(k,[]);claims.get(k).push(c);}
 return {bundle,reports,nodes,paragraphs,sentences,occurrences,attributes,claims};
}
function project(bundle,{workflow='A',scale='paragraph',reportIds,referenceOnly=false}={}){
 assert(['sentence','paragraph','report'].includes(scale),'Unsupported network scale.');
 assert(bundle.dataset.rosters.includes(workflow),'Unknown workflow.');
 const requested=reportIds===undefined?bundle.reports.map(r=>r.report_id):strings(reportIds,'reportIds');
 const available=new Set(bundle.reports.map(r=>r.report_id));assert(requested.every(id=>available.has(id)),'Unknown selected report.');
 const selected=new Set(requested);referenceOnly=Boolean(referenceOnly||workflow==='R');
 const roster=bundle.nodes.filter(n=>n.workflow===workflow).sort((a,b)=>compare(a.actor_id,b.actor_id));
 const actorIds=new Set(roster.map(n=>n.actor_id)),reference=new Set(bundle.reference_units||[]),units=new Map();
 const exclusions={unassigned_identity:0,missing_unit:0,outside_selection:0};
 for(const o of bundle.occurrences){
  if(o.workflow!==workflow)continue;
  if(!selected.has(o.report_id)||(referenceOnly&&!reference.has(o.paragraph_id))){exclusions.outside_selection++;continue;}
  if(o.actor_id==null||!actorIds.has(o.actor_id)){exclusions.unassigned_identity++;continue;}
  const unit=scale==='sentence'?o.sentence_id:scale==='paragraph'?o.paragraph_id:o.report_id;
  if(!unit){exclusions.missing_unit++;continue;}
  if(!units.has(unit))units.set(unit,{unit_id:unit,report_id:o.report_id,actor_ids:new Set()});
  units.get(unit).actor_ids.add(o.actor_id);
 }
 const incidences=[...units.values()].sort((a,b)=>compare(a.unit_id,b.unit_id)).map(u=>({...u,actor_ids:[...u.actor_ids].sort(compare)}));
 const edgeMap=new Map();
 for(const u of incidences)for(let i=0;i<u.actor_ids.length;i++)for(let j=i+1;j<u.actor_ids.length;j++){
  const source=u.actor_ids[i],target=u.actor_ids[j],id=JSON.stringify([source,target]);
  if(!edgeMap.has(id))edgeMap.set(id,{source,target,weight:0,unit_ids:[]});
  const edge=edgeMap.get(id);edge.weight++;edge.unit_ids.push(u.unit_id);
 }
 const edges=[...edgeMap.values()].sort((a,b)=>compare(a.source,b.source)||compare(a.target,b.target));
 const nodes=roster.map(n=>({actor_id:n.actor_id,name:n.name,degree:0,strength:0,layout:n.layout}));
 const nodeMap=new Map(nodes.map(n=>[n.actor_id,n]));
 for(const e of edges)for(const id of [e.source,e.target]){nodeMap.get(id).degree++;nodeMap.get(id).strength+=e.weight;}
 return {workflow,scale,report_ids:[...selected].sort(compare),reference_only:referenceOnly,nodes,edges,incidences,
  summary:{nodes:nodes.length,edges:edges.length,isolates:nodes.filter(n=>n.degree===0).length,total_weight:edges.reduce((v,e)=>v+e.weight,0),observed_units:incidences.length},exclusions};
}
const ROLE_LABELS={AGR:'Agriculture',BUS:'Business',COP:'Police',CRM:'Criminal activity',CVL:'Civilian',DEV:'Development',EDU:'Education',ELI:'Elite / former official',ENV:'Environment',GOV:'Government',HLH:'Health',HRI:'Human rights',IGO:'Intergovernmental',INS:'Insurgent',INT:'International',JUD:'Judiciary',LAB:'Labor',LEG:'Legislature',MED:'Media',MIL:'Military',OPP:'Opposition',PTY:'Political party',REB:'Rebel',REF:'Refugee / migration',SEP:'Separatist',SPY:'Intelligence',UAF:'Unspecified armed force',UIS:'Unidentified state'};
const ROLE_COLORS={GOV:'#6ce8d7',IGO:'#80b3ff',ELI:'#c2a1ff',PTY:'#f7a2d3',LEG:'#f3c578',MIL:'#ff9b87',COP:'#9cd3ff',JUD:'#e6c89a',REB:'#edaf74',OPP:'#b9d48b',INS:'#ee8a9a',SEP:'#db9ab9',CVL:'#b7cadb',MED:'#b7d799',BUS:'#afd5c7',EDU:'#c5bcf5',HRI:'#e9b8de',DEV:'#8ed3cf',SPY:'#c6a5a0',CRM:'#cfafa5'};
function rolePresentation(roles){const code=roles.length>1?'__multiple__':roles[0]||'__none__';return {code,label:code==='__multiple__'?'Multiple roles':code==='__none__'?'Not recorded':ROLE_LABELS[code]||code,color:code==='__multiple__'?'#f0e8ff':code==='__none__'?'#8a9cb5':ROLE_COLORS[code]||'#c1cddd'};}
function actorCoding(index,{workflow,actorId,reportIds}={}){
 const selected=reportIds===undefined?null:new Set(reportIds),rows=(index.attributes.get(key(workflow,actorId))||[]).filter(a=>selected===null||selected.has(a.report_id));
 return {roles:unique(rows.flatMap(a=>list(a.role_codes))),specialties:unique(rows.flatMap(a=>list(a.specialty_codes))),union:unique(rows.flatMap(a=>list(a.cameo_codes))),primarySupport:unique(rows.flatMap(a=>list(a.primary_cameo_codes))),reports:unique(rows.map(a=>a.report_id))};
}
function yearRows(index,{workflow='A',search='',metric='mentions',order='total'}={}){
 const reports=[...index.reports.values()],years=unique(reports.map(r=>r.year==null?'Unknown':String(r.year)));
 const query=search.trim().toLocaleLowerCase(),rows=[];
 for(const node of index.bundle.nodes.filter(n=>n.workflow===workflow)){
  if(query&&![node.name,node.actor_id,...(node.aliases||[])].some(v=>String(v).toLocaleLowerCase().includes(query)))continue;
  const occ=index.occurrences.get(key(workflow,node.actor_id))||[],attrs=index.attributes.get(key(workflow,node.actor_id))||[];
  const cells=years.map(year=>{
   const entries=occ.filter(o=>String(index.reports.get(o.report_id)?.year??'Unknown')===year),reportIds=unique(entries.map(o=>o.report_id));
   const present=attrs.filter(a=>reportIds.includes(a.report_id));
   return {year,mentions:entries.length,reports:reportIds.length,report_ids:reportIds,occurrences:entries,
    codes:unique(present.flatMap(a=>list(a.cameo_codes))),role_codes:unique(present.flatMap(a=>list(a.role_codes))),specialty_codes:unique(present.flatMap(a=>list(a.specialty_codes))),
    coded_reports:unique(present.filter(a=>list(a.cameo_codes).length).map(a=>a.report_id)).length,
    primary_coded_reports:unique(present.filter(a=>list(a.primary_cameo_codes).length).map(a=>a.report_id)).length};
  });
  rows.push({node,cells,total:cells.reduce((sum,c)=>sum+c[metric],0)});
 }
 rows.sort((a,b)=>order==='name'?a.node.name.localeCompare(b.node.name)||compare(a.node.actor_id,b.node.actor_id):b.total-a.total||a.node.name.localeCompare(b.node.name)||compare(a.node.actor_id,b.node.actor_id));
 return {years,rows,coverage:years.map(y=>reports.filter(r=>String(r.year??'Unknown')===y).length)};
}
function csv(rows,columns){
 const fields=columns||unique(rows.flatMap(r=>Object.keys(r)));
 const cell=value=>{let v=value==null?'':typeof value==='object'?JSON.stringify(value):String(value);if(typeof value==='string'&&(/^\s*[=+@-]/.test(v)||/^[\t\r]/.test(v)))v="'"+v;return /[",\r\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;};
 return [fields.map(cell).join(','),...rows.map(r=>fields.map(f=>cell(r[f])).join(','))].join('\r\n')+'\r\n';
}
function xml(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));}
function graphml(network){
 const keys=[['name','node','string'],['degree','node','int'],['strength','node','int'],['role_codes','node','string'],['specialty_codes','node','string'],['weight','edge','int']];
 let out='<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n';
 for(const [name,target,type]of keys)out+='<key id="'+name+'" for="'+target+'" attr.name="'+name+'" attr.type="'+type+'"/>\n';
 out+='<graph id="cooccurrence" edgedefault="undirected">\n';
 for(const n of network.nodes){out+='<node id="'+xml(n.actor_id)+'">';for(const field of ['name','degree','strength','role_codes','specialty_codes'])out+='<data key="'+field+'">'+xml(field.endsWith('_codes')?JSON.stringify(n[field]||[]):n[field])+'</data>';out+='</node>\n';}
 network.edges.forEach((e,i)=>{out+='<edge id="e'+i+'" source="'+xml(e.source)+'" target="'+xml(e.target)+'"><data key="weight">'+e.weight+'</data></edge>\n';});
 return out+'</graph></graphml>\n';
}
function highlightParts(text,start,end){
 const chars=Array.from(text);
 assert(Number.isInteger(start)&&Number.isInteger(end)&&start>=0&&end>start&&end<=chars.length,'Span is outside the loaded paragraph.');
 return {before:chars.slice(0,start).join(''),marked:chars.slice(start,end).join(''),after:chars.slice(end).join('')};
}
function safeSourceUrl(value){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;}catch{return null;}}
async function verifySourceText(bundle,records,digest){
 const expected=new Map(bundle.paragraphs.map(p=>[p.paragraph_id,p])),loaded=new Map();
 for(const row of records){
  const id=row.paragraph_id||row.id;if(!expected.has(id))throw new Error('Source paragraph is not part of this dataset: '+id);
  assert(typeof row.text==='string'&&!loaded.has(id),'Invalid or duplicate source paragraph.');
  const actual=await digest(row.text);assert(actual.toLowerCase()===expected.get(id).text_sha256.toLowerCase(),'Source hash mismatch: '+id);
  loaded.set(id,row.text);
 }
 assert(loaded.size>0,'No canonical paragraphs were supplied.');
 return loaded;
}
return {compare,key,unique,list,canonical,matchesTrustedStudy,baselineSelection,validateBundle,indexBundle,project,actorCoding,rolePresentation,ROLE_LABELS,yearRows,csv,graphml,highlightParts,safeSourceUrl,verifySourceText};
});
