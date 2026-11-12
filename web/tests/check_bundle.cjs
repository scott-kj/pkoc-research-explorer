'use strict';
const fs=require('node:fs'),assert=require('node:assert/strict'),C=require('../core.js');
const file=process.argv[2];if(!file){console.error('Usage: node web/tests/check_bundle.cjs path/to/bundle.json');process.exit(2);}
const bundle=C.validateBundle(JSON.parse(fs.readFileSync(file,'utf8')));
const expected={L_sentence:116,A_sentence:128,L_paragraph:186,A_paragraph:196,L_report:929,A_report:887};
let count=0;
for(const baseline of bundle.networks||[]){
 const n=C.project(bundle,{workflow:baseline.workflow,scale:baseline.scale,reportIds:baseline.report_ids});
 const id=n.workflow+'_'+n.scale;
 assert.deepEqual(n.edges,baseline.edges,id+' exact weighted edges and unit evidence');
 assert.deepEqual(n.incidences,baseline.incidences,id+' exact binary incidence');
 assert.deepEqual(n.nodes.map(({actor_id,degree,strength})=>({actor_id,degree,strength})),baseline.nodes.map(({actor_id,degree,strength})=>({actor_id,degree,strength})),id+' native roster, degrees, strengths and isolates');
 assert.deepEqual(n.summary,baseline.summary,id+' summary');
 if(bundle.dataset.id==='unmil-revision-04')assert.equal(n.edges.length,expected[id],id+' published edge count');
 console.log(id+': '+n.nodes.length+' nodes, '+n.edges.length+' edges; exact parity');count++;
}
if(bundle.dataset.id==='unmil-revision-04')assert.equal(count,6,'All six UNMIL baselines must be checked');else assert.ok(count>0,'No baseline network was supplied');
console.log('Verified '+count+' networks with the independent JavaScript projector.');
