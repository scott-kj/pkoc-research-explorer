'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const C=require('../core.js');
const hash=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
test('CAMEO roles remain distinct from specialties and follow selected reports',()=>{
 const b=fixture();b.attributes.push({workflow:'A',actor_id:'a',report_id:'r2',role_codes:['MIL'],specialty_codes:['GOV'],cameo_codes:['GOV','MIL'],primary_cameo_codes:['MIL']});const index=C.indexBundle(b);
 assert.deepEqual(C.actorCoding(index,{workflow:'A',actorId:'a',reportIds:['r1']}).roles,['GOV']);
 assert.deepEqual(C.actorCoding(index,{workflow:'A',actorId:'a',reportIds:['r2']}).roles,['MIL']);
 assert.deepEqual(C.actorCoding(index,{workflow:'A',actorId:'a',reportIds:['r2']}).specialties,['GOV']);
 assert.deepEqual(C.actorCoding(index,{workflow:'A',actorId:'a',reportIds:[]}).roles,[]);
 assert.equal(C.rolePresentation(C.actorCoding(index,{workflow:'A',actorId:'a'}).roles).code,'__multiple__');
 assert.equal(C.rolePresentation(C.actorCoding(index,{workflow:'L',actorId:'a'}).roles).code,'__none__');
});
test('role presentation does not invent a primary role or change the projection',()=>{
 const b=fixture(),before=C.project(b,{workflow:'A'}),index=C.indexBundle(b);const coding=C.actorCoding(index,{workflow:'A',actorId:'a'});
 assert.equal(C.rolePresentation(coding.roles).label,'Government');assert.equal(C.rolePresentation(['GOV','MIL']).label,'Multiple roles');
 assert.deepEqual(C.project(b,{workflow:'A'}),before);assert.deepEqual(b.attributes[0].role_codes,['GOV']);
});
test('GraphML can carry report-scoped roles and specialties without changing edges',()=>{
 const graph=C.project(fixture(),{workflow:'A'});graph.nodes[0].role_codes=['GOV'];graph.nodes[0].specialty_codes=['MIL'];
 const value=C.graphml(graph);assert.ok(value.includes('key="role_codes">[&quot;GOV&quot;]'));assert.ok(value.includes('key="specialty_codes">[&quot;MIL&quot;]'));assert.ok(value.includes('<data key="weight">2</data>'));
});
function fixture(){
 const b={schema:'pkoc-explorer-v1',dataset:{id:'fixture',title:'Domain fixture',kind:'frozen-study',rosters:['L','A']},
 reports:[{report_id:'r1',document_symbol:'S/2020/1',report_date:'2020-01-01',year:2020,official_url:'https://example.org/1'},{report_id:'r2',document_symbol:'S/2021/2',report_date:null,year:null,official_url:'https://example.org/2'}],
 nodes:[{workflow:'A',actor_id:'a',name:'Alpha',aliases:['A. Name'],cameo_codes:['GOV','MIL']},{workflow:'A',actor_id:'b',name:'Beta',aliases:[]},{workflow:'A',actor_id:'c',name:'Isolate',aliases:[]},{workflow:'L',actor_id:'a',name:'Different native identity',aliases:[]}],
 paragraphs:[{paragraph_id:'p1',report_id:'r1',text_sha256:hash('x😀Alpha Beta')},{paragraph_id:'p2',report_id:'r2',text_sha256:hash('Alpha Beta')}],
 sentences:[{sentence_id:'s1',paragraph_id:'p1',report_id:'r1',start:0,end:12},{sentence_id:'s2',paragraph_id:'p2',report_id:'r2',start:0,end:10}],
 occurrences:[],attributes:[{workflow:'A',actor_id:'a',report_id:'r1',role_codes:['GOV'],specialty_codes:['MIL'],cameo_codes:['GOV','MIL'],primary_cameo_codes:['GOV'],uncertainty:[]}],claims:[],reference_units:['p1']};
 const add=(workflow,id,actor,report,paragraph,sentence,start,end,surface)=>b.occurrences.push({workflow,occurrence_id:id,actor_id:actor,report_id:report,paragraph_id:paragraph,sentence_id:sentence,start,end,surface,grounding_status:'grounded'});
 add('A','o1','a','r1','p1','s1',2,7,'Alpha');add('A','o2','a','r1','p1','s1',2,7,'Alpha');add('A','o3','b','r1','p1','s1',8,12,'Beta');
 add('A','o4','a','r2','p2','s2',0,5,'Alpha');add('A','o5','b','r2','p2',null,6,10,'Beta');add('A','o6',null,'r2','p2',null,null,null,'unresolved');
 add('L','o1','a','r1','p1','s1',2,7,'Alpha');Object.assign(b,{interventions:[],correspondence:[],networks:[],codebook:[],provenance:{}});return b;
}
test('bundle relationships are validated without requiring invented dates',()=>{const b=fixture();assert.equal(C.validateBundle(b),b);assert.equal(C.indexBundle(b).reports.get('r2').year,null);});
test('binary projection deduplicates repeated mentions, counts units, and retains native isolates',()=>{
 const b=fixture(),n=C.project(b,{workflow:'A',scale:'paragraph'});assert.deepEqual(n.edges,[{source:'a',target:'b',weight:2,unit_ids:['p1','p2']}]);assert.deepEqual(n.nodes.map(n=>[n.actor_id,n.degree,n.strength]),[['a',1,2],['b',1,2],['c',0,0]]);assert.equal(n.summary.observed_units,2);assert.equal(n.exclusions.unassigned_identity,1);
});
test('sentence missing-unit exclusions and report projection are distinct',()=>{const b=fixture(),n=C.project(b,{workflow:'A',scale:'sentence'});assert.equal(n.edges[0].weight,1);assert.equal(n.exclusions.missing_unit,1);assert.equal(n.exclusions.unassigned_identity,1);assert.equal(C.project(b,{workflow:'A',scale:'report'}).edges[0].weight,2);});
test('report and reference selection preserve roster, including an explicit empty selection',()=>{const b=fixture();assert.equal(C.project(b,{workflow:'A',reportIds:['r1']}).edges[0].weight,1);const empty=C.project(b,{workflow:'A',reportIds:[]});assert.equal(empty.nodes.length,3);assert.equal(empty.edges.length,0);assert.equal(empty.summary.isolates,3);assert.equal(C.project(b,{workflow:'A',referenceOnly:true}).edges[0].weight,1);});
test('workflow identity namespaces do not merge duplicate native actor IDs',()=>{const b=fixture();const n=C.project(b,{workflow:'L'});assert.equal(n.nodes.length,1);assert.equal(n.nodes[0].name,'Different native identity');assert.equal(n.edges.length,0);assert.equal(C.indexBundle(b).occurrences.get('L:a').length,1);});
test('actor-year cells distinguish mentions/reports and retain role, specialty, and primary support',()=>{const b=fixture(),r=C.yearRows(C.indexBundle(b),{workflow:'A',search:'A. Name'});assert.equal(r.rows.length,1);assert.deepEqual(r.years,['2020','Unknown']);assert.deepEqual(r.coverage,[1,1]);const c=r.rows[0].cells[0];assert.equal(c.mentions,2);assert.equal(c.reports,1);assert.deepEqual(c.role_codes,['GOV']);assert.deepEqual(c.specialty_codes,['MIL']);assert.deepEqual(c.codes,['GOV','MIL']);assert.equal(c.primary_coded_reports,1);assert.equal(C.yearRows(C.indexBundle(b),{workflow:'A',metric:'reports'}).rows.find(r=>r.node.actor_id==='a').total,2);});
test('highlighting uses Unicode codepoints, not UTF-16 positions',()=>{assert.deepEqual(C.highlightParts('x😀Alpha Beta',2,7),{before:'x😀',marked:'Alpha',after:' Beta'});assert.throws(()=>C.highlightParts('😀',1,2),/outside/);assert.throws(()=>C.highlightParts('abc',2,1),/outside/);});
test('malformed identifiers, relationships, spans and embedded prose fail validation',()=>{
 for(const mutate of [b=>b.nodes.push({...b.nodes[0]}),b=>b.occurrences.push({...b.occurrences[0]}),b=>b.occurrences[0].actor_id='absent',b=>b.occurrences[0].report_id='r2',b=>b.occurrences[0].sentence_id='s2',b=>b.occurrences[0].end=-1,b=>b.paragraphs[0].text='private paragraph',b=>b.paragraphs[0].text_sha256='bad',b=>b.schema='future-version']){const b=fixture();mutate(b);assert.throws(()=>C.validateBundle(b));}
});
test('GraphML and source links safely handle untrusted strings',()=>{const b=fixture();b.nodes[0].name='<img src=x onerror=alert(1)>&"';C.validateBundle(b);const xml=C.graphml(C.project(b,{workflow:'A'}));assert.ok(xml.includes('&lt;img'));assert.ok(!xml.includes('<img'));assert.equal(C.safeSourceUrl('javascript:alert(1)'),null);assert.equal(C.safeSourceUrl('https://user:secret@example.org'),null);assert.equal(C.safeSourceUrl('file:///C:/private'),null);assert.equal(C.safeSourceUrl('https://docs.un.org/S/2020/1'),'https://docs.un.org/S/2020/1');});
test('CSV quotes structured fields and makes formula-like imported strings inert',()=>{const rows=[{name:'=1+1',value:-1,quoted:'a,"b"',array:['x','y']},{name:'  @SUM(A1)',value:3,quoted:'line\nbreak',array:[]}];const s=C.csv(rows,['name','value','quoted','array']);assert.ok(s.includes("'=1+1,-1"));assert.ok(s.includes("'  @SUM(A1)"));assert.ok(s.includes('"a,""b"""'));assert.ok(s.includes('"[""x"",""y""]"'));assert.equal(rows[0].name,'=1+1');});
test('local source verification accepts only canonical, hash-matching records atomically',async()=>{const b=fixture(),digest=async s=>hash(s);const m=await C.verifySourceText(b,[{paragraph_id:'p1',text:'x😀Alpha Beta'}],digest);assert.equal(m.get('p1'),'x😀Alpha Beta');await assert.rejects(C.verifySourceText(b,[{paragraph_id:'p1',text:'changed'}],digest),/hash mismatch/);await assert.rejects(C.verifySourceText(b,[{paragraph_id:'p1',text:'x😀Alpha Beta'},{paragraph_id:'p1',text:'x😀Alpha Beta'}],digest),/duplicate/);await assert.rejects(C.verifySourceText(b,[{paragraph_id:'unknown',text:'x'}],digest),/not part/);});

test('declared rosters are enforced and automated cases cannot fabricate A/R branches',()=>{
 for(const mutate of [b=>b.dataset.rosters=['L','A','A'],b=>b.dataset.rosters=['L'],b=>b.nodes[0].workflow='R',b=>b.occurrences[5].workflow='R',b=>b.dataset.kind='model-only']){const b=fixture();mutate(b);assert.throws(()=>C.validateBundle(b));}
 const b=fixture();b.dataset.kind='model-only';b.dataset.rosters=['L'];b.nodes=b.nodes.filter(n=>n.workflow==='L');b.occurrences=b.occurrences.filter(o=>o.workflow==='L');b.attributes=[];b.reference_units=[];assert.equal(C.validateBundle(b),b);
});
test('grounded spans count Unicode codepoints and must fit their saved sentence',()=>{
 const b=fixture();b.occurrences[0].surface='😀';b.occurrences[0].start=1;b.occurrences[0].end=2;assert.equal(C.validateBundle(b),b);
 b.occurrences[0].end=3;assert.throws(()=>C.validateBundle(b),/surface length/);
 const outside=fixture();outside.occurrences[0].start=9;outside.occurrences[0].end=14;assert.throws(()=>C.validateBundle(outside),/beyond its sentence/);
});
test('embedded networks must exactly reproject, including isolates and incidence evidence',()=>{
 const original=fixture();original.networks=[C.project(original,{workflow:'A',scale:'paragraph'})];assert.equal(C.validateBundle(original),original);
 for(const mutate of [g=>g.edges[0].weight++,g=>g.edges[0].unit_ids[1]='p1',g=>g.incidences[0].actor_ids.pop(),g=>g.nodes.pop(),g=>g.nodes[0].degree++,g=>g.summary.isolates++,g=>g.exclusions.unassigned_identity++,g=>g.report_ids.push('unknown')]){
  const b=structuredClone(original);mutate(b.networks[0]);assert.throws(()=>C.validateBundle(b));
 }
});
test('report metadata cannot invent incompatible dates or undeclared reports',()=>{
 for(const mutate of [b=>b.reports[0].report_date='2020-02-30',b=>b.reports[0].report_date='2021',b=>b.reports[0].official_url='javascript:alert(1)',b=>b.reports[0].year=20,b=>b.provenance={api_key:'secret'}]){const b=fixture();mutate(b);assert.throws(()=>C.validateBundle(b));}
 assert.throws(()=>C.project(fixture(),{workflow:'A',reportIds:['missing']}),/Unknown selected report/);
 assert.throws(()=>C.project(fixture(),{workflow:'A',reportIds:['r1','r1']}),/duplicates/);
});
function trustedFixture(){const b=fixture();b.dataset.id='unmil-revision-04';for(const workflow of ['L','A'])for(const scale of ['sentence','paragraph','report'])b.networks.push(C.project(b,{workflow,scale}));b.networks[0].nodes[0].published_metrics={community:2};return b;}
test('local study trust requires full structural equality to the trusted embedded UNMIL bundle',()=>{
 const trusted=trustedFixture(),copy=structuredClone(trusted);assert.equal(C.matchesTrustedStudy(copy,trusted),true);
 const reorder=v=>Array.isArray(v)?v.map(reorder):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).reverse().map(([k,x])=>[k,reorder(x)])):v;
 assert.equal(C.matchesTrustedStudy(reorder(copy),trusted),true);
 for(const mutate of [b=>b.nodes[0].name='Different',b=>b.networks[0].nodes[0].published_metrics.community=99,b=>b.dataset.id='other-study',b=>b.provenance.claim='different']){
  const changed=structuredClone(copy);mutate(changed);assert.equal(C.matchesTrustedStudy(changed,trusted),false);
 }
 assert.equal(C.matchesTrustedStudy(copy,null),false);
});
test('baseline scope follows trusted construction, independently of display-only filters',()=>{
 const b=trustedFixture(),scope={workflow:'A',scale:'paragraph',reportIds:['r1','r2'],trustedStudy:true};
 assert.equal(C.baselineSelection(b,scope),true);
 assert.equal(C.baselineSelection(b,{...scope,search:'Alpha',code:'GOV',weight:500,hideIsolates:true}),true);
 assert.equal(C.baselineSelection(b,{...scope,reportIds:['r1']}),false);
 assert.equal(C.baselineSelection(b,{...scope,trustedStudy:false}),false);
 assert.equal(C.baselineSelection(b,{...scope,workflow:'R'}),false);
 assert.equal(C.baselineSelection(b,{...scope,scale:'custom'}),false);
});
