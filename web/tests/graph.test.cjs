const test=require('node:test'),assert=require('node:assert/strict');
const {ExplorerGraph,fitCamera,fitSphereCamera,zoomCamera,worldPoint,initialPositions,initialLayout,rotatePoint,projectSphere,surfaceDestination,degreeRadius,pickProjectedNode,normalizedOrientation,SPHERE,RANDOM_SEED}=require('../graph.js');
test('fit includes distant moved nodes and remains finite for empty and single rosters',()=>{
 const points=[{x:-3000,y:200},{x:5000,y:3000}],c=fitCamera(points,1200,700);
 for(const p of points){assert.ok(c.x+p.x*c.k>=0&&c.x+p.x*c.k<=1200);assert.ok(c.y+p.y*c.k>=0&&c.y+p.y*c.k<=700);}
 for(const set of [[],[{x:10,y:10}]])assert.ok(Object.values(fitCamera(set,375,500)).every(Number.isFinite));
});
test('zoom retains the world position beneath the pointer, including clamps',()=>{
 const before={x:40,y:-30,k:.8},anchor={x:300,y:250},world=worldPoint(before,anchor);
 for(const factor of [2,.4,100,.001]){const after=worldPoint(zoomCamera(before,factor,anchor),anchor);assert.ok(Math.abs(after.x-world.x)<1e-8);assert.ok(Math.abs(after.y-world.y)<1e-8);}
});
test('drag displacement remains in screen pixels under translated zoom',()=>{
 const camera={x:125,y:-80,k:2.5},a=worldPoint(camera,{x:300,y:210}),b=worldPoint(camera,{x:360,y:170});
 assert.equal((b.x-a.x)*camera.k,60);assert.equal((b.y-a.y)*camera.k,-40);
});
test('initial layouts are independent copies and handle coincident or missing positions',()=>{
 const nodes=[{actor_id:'a',layout:{x:4,y:4,id:'untrusted-id'}},{actor_id:'b',layout:{x:4,y:4}},{actor_id:'c'}],before=JSON.stringify(nodes),positions=initialPositions(nodes);
 assert.equal(positions.size,3);assert.ok([...positions.values()].every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));positions.get('a').x=2000;assert.equal(JSON.stringify(nodes),before);
});

const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
const fixture=[{actor_id:'a',name:'Alpha',degree:12,roleLabel:'Government',color:'#6ce8d7',layout:{x:-1,y:-1}},{actor_id:'b',name:'Beta',degree:6,roleLabel:'Media',color:'#f0c777',layout:{x:1,y:1}},{actor_id:'c',name:'Gamma',degree:0,roleLabel:'Not recorded',color:'#aab3cc',layout:{x:0,y:0}}];

test('new layouts are deterministic over the full roster and do not alter paper coordinates',()=>{
 const before=JSON.stringify(fixture);
 for(const kind of ['circle','random','sphere3d']){
  assert.deepEqual(initialLayout(fixture,kind),initialLayout([...fixture].reverse(),kind));
  assert.equal(initialLayout([],kind).size,0);
 }
 assert.deepEqual(initialLayout(fixture,'paper'),initialPositions(fixture));
 assert.deepEqual(initialPositions(fixture).get('a'),{x:85,y:65});
 for(const p of initialLayout(fixture,'sphere3d').values())near(Math.hypot(p.x,p.y,p.z),1);
 assert.deepEqual(initialLayout([fixture[0]],'sphere3d').get('a'),{x:0,y:0,z:1});
 assert.throws(()=>initialLayout(fixture,'unknown'),/Unsupported/);assert.equal(JSON.stringify(fixture),before);
});

test('orthographic sphere rotation is reversible and changes real depth',()=>{
 const point={x:.3,y:.4,z:Math.sqrt(.75)};
 for(const orientation of [{yaw:0,pitch:0},{yaw:75,pitch:35},{yaw:-180,pitch:-90}]){
  const rotated=rotatePoint(point,orientation),back=rotatePoint(rotated,orientation,true);
  near(Math.hypot(rotated.x,rotated.y,rotated.z),1);for(const key of ['x','y','z'])near(back[key],point[key]);
 }
 near(projectSphere({x:0,y:0,z:1},{yaw:90,pitch:0}).x,SPHERE.x+SPHERE.radius);
 near(projectSphere({x:0,y:0,z:1},{yaw:180,pitch:0}).z,-1);
 assert.deepEqual(normalizedOrientation(450,300),{yaw:90,pitch:90});assert.throws(()=>normalizedOrientation(NaN,0),/finite/);
});

test('surface repositioning preserves hemisphere, radius and exact projected destination',()=>{
 const orientation={yaw:61,pitch:-32},destination={x:490,y:350};
 for(const side of [-1,1]){
  const point=surfaceDestination(destination,orientation,side),projected=projectSphere(point,orientation);
  near(Math.hypot(point.x,point.y,point.z),1);near(projected.x,destination.x);near(projected.y,destination.y);assert.equal(Math.sign(projected.z),side);
 }
 assert.equal(surfaceDestination({x:10000,y:10000},orientation,1,false),null);
 const rim=surfaceDestination({x:10000,y:10000},orientation,-1,true);near(Math.hypot(rim.x,rim.y,rim.z),1);near(projectSphere(rim,orientation).z,0);
});

test('degree maps linearly to area with retained minimum size and roster-wide maximum',()=>{
 assert.equal(degreeRadius(0,12),5);assert.equal(degreeRadius(12,12),18);assert.equal(degreeRadius(0,0),5);
 near(degreeRadius(6,12)**2,(5**2+18**2)/2);assert.ok(degreeRadius(6,12)<degreeRadius(6,6));
});

test('sphere fit uses compact margins without changing the original paper fitter',()=>{
 const width=900,height=281,c=fitSphereCamera(width,height);near(c.k*SPHERE.radius*2,height-56);
 near(c.x+SPHERE.x*c.k,width/2);near(c.y+SPHERE.y*c.k,height/2);
 const mobile=fitSphereCamera(375,560);near(mobile.k*SPHERE.radius*2,375-80);
 assert.ok(c.k>fitCamera([{x:195,y:65},{x:705,y:575}],width,height).k);
});

test('sphere picking chooses the frontmost overlapping visible disc and keeps touch targets',()=>{
 const points=[{id:'back',x:100,y:100,z:-.8,radius:8},{id:'front',x:105,y:100,z:.8,radius:18}];
 assert.equal(pickProjectedNode(points,{x:100,y:100},true),'front');
 assert.equal(pickProjectedNode(points,{x:100,y:100},false),'back');
 assert.equal(pickProjectedNode([points[0]],{x:120,y:100},true),'back');assert.equal(pickProjectedNode(points,{x:900,y:900},true),null);
});

// A small DOM fixture tests controller state and event transitions. Real browser
// checks separately cover pointer capture, focus and the rendered/exported SVG.
function withGraph(run){
 class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.attrs={};this.dataset={};this.handlers={};this.style={setProperty(k,v){this[k]=v;}};this.classes=new Set();this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),toggle:(x,on)=>on?this.classes.add(x):this.classes.delete(x)};this.capture=new Set();}
  setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k];}
  append(...nodes){for(const node of nodes){if(node.parentElement)node.parentElement.children=node.parentElement.children.filter(n=>n!==node);node.parentElement=this;this.children.push(node);}}
  replaceChildren(...nodes){for(const child of this.children)child.parentElement=null;this.children=[];this.append(...nodes);}
  addEventListener(type,handler){(this.handlers[type]??=[]).push(handler);}
  getBoundingClientRect(){return {width:900,height:640};}getScreenCTM(){return {inverse:()=>({})};}
  setPointerCapture(id){this.capture.add(id);}hasPointerCapture(id){return this.capture.has(id);}releasePointerCapture(id){this.capture.delete(id);}
 }
 const saved={document:global.document,ResizeObserver:global.ResizeObserver,DOMPoint:global.DOMPoint},documentHandlers={};
 global.document={createElementNS:(_,tag)=>new Element(tag),addEventListener:(name,fn)=>{documentHandlers[name]=fn;}};
 global.ResizeObserver=class{observe(){}};global.DOMPoint=class{constructor(x,y){this.x=x;this.y=y;}matrixTransform(){return {x:this.x,y:this.y};}};
 try{
  const svg=new Element('svg'),status=[],selected=[],graph=new ExplorerGraph(svg,{onStatus:m=>status.push(m),onNode:n=>selected.push(n.actor_id)}),nodes=structuredClone(fixture),edges=[{source:'a',target:'b',weight:2,label:'Alpha and Beta'}];
  graph.setData(nodes,edges,nodes,'A:paragraph');run({graph,svg,nodes,edges,status,selected,documentHandlers});
 }finally{for(const [key,value]of Object.entries(saved)){if(value===undefined)delete global[key];else global[key]=value;}}
}

test('each layout/context retains its own positions, filters preserve them, and sources stay unchanged',()=>withGraph(({graph,nodes,edges})=>{
 const before=JSON.stringify({nodes,edges}),paper=graph.snapshot();graph.select('a');graph.move(1,0,30);const movedPaper=graph.snapshot();
 graph.setLayout('random');assert.equal(graph.snapshot().random_seed,RANDOM_SEED);
 graph.setLayout('sphere3d');graph.setOrientation(54,-28);graph.select('b');graph.move(1,1,15);const sphere=graph.snapshot();
 graph.setData(nodes.slice(0,2),edges,nodes,'A:paragraph');assert.deepEqual(graph.snapshot().sphere_positions,sphere.sphere_positions);assert.equal(graph.maxDegree,12);
 graph.setData(nodes,edges,nodes,'L:paragraph');assert.deepEqual(graph.orientation,{yaw:0,pitch:0});
 graph.setData(nodes,edges,nodes,'A:paragraph');assert.deepEqual(graph.snapshot().sphere_positions,sphere.sphere_positions);assert.deepEqual(graph.orientation,sphere.orientation);
 graph.setLayout('paper');assert.deepEqual(graph.snapshot().positions,movedPaper.positions);graph.reset();assert.deepEqual(graph.snapshot().positions,paper.positions);
 graph.setLayout('sphere3d');graph.clear();graph.setData(nodes,edges,nodes,'A:paragraph');assert.equal(graph.layoutType,'paper');assert.equal(JSON.stringify({nodes,edges}),before);
}));

test('rotation sorts decorative depth without changing focus order or degree radii',()=>withGraph(({graph})=>{
 graph.setLayout('sphere3d');const controls=graph.controlLayer.children.map(n=>n.attrs['data-actor-id']);
 graph.setOrientation(120,45);assert.deepEqual(graph.controlLayer.children.map(n=>n.attrs['data-actor-id']),controls);
 const z=graph.visualLayer.children.map(n=>graph.projectedPositions().get(n.attrs['data-actor-id']).z);assert.deepEqual(z,[...z].sort((a,b)=>a-b));
 const radius=Number(graph.nodeElements.get('a').dot.attrs.r)*graph.camera.k;graph.zoom(1.8);near(Number(graph.nodeElements.get('a').dot.attrs.r)*graph.camera.k,radius);near(radius,18);
}));

test('node drag under zoom changes only its position and background drag orbits only the camera',()=>withGraph(({graph,svg,nodes,edges,selected})=>{
 const before=JSON.stringify({nodes,edges});graph.select('a');graph.zoom(1.7);const origin={...graph.positions.get('a')},start={x:graph.camera.x+origin.x*graph.camera.k,y:graph.camera.y+origin.y*graph.camera.k},scale=graph.camera.k;
 graph.pointerDown({button:0,pointerId:1,clientX:start.x,clientY:start.y,target:svg});graph.pointerMove({pointerId:1,clientX:start.x+50,clientY:start.y-20});graph.pointerEnd({type:'pointerup',pointerId:1});
 near((graph.positions.get('a').x-origin.x)*scale,50);near((graph.positions.get('a').y-origin.y)*scale,-20);assert.equal(selected.at(-1),'a');assert.equal(svg.capture.size,0);
 graph.setLayout('sphere3d');const vectors=graph.snapshot().sphere_positions;
 graph.pointerDown({button:0,pointerId:2,clientX:1,clientY:1,target:svg});graph.pointerMove({pointerId:2,clientX:81,clientY:41});graph.pointerEnd({type:'pointerup',pointerId:2});
 assert.notEqual(graph.orientation.yaw,0);assert.deepEqual(graph.snapshot().sphere_positions,vectors);assert.equal(JSON.stringify({nodes,edges}),before);
}));

test('single-click reposition validates sphere bounds, escape cancels, and stale drags are released',()=>withGraph(({graph,svg,nodes,edges,status,documentHandlers})=>{
 graph.setLayout('sphere3d');graph.select('b');assert.equal(graph.armReposition(),true);
 assert.equal(graph.repositionAt({x:-10000,y:-10000}),false);assert.equal(graph.repositioning,true);assert.match(status.at(-1),/inside the sphere/);
 const point={x:graph.camera.x+450*graph.camera.k,y:graph.camera.y+320*graph.camera.k};assert.equal(graph.repositionAt(point),true);near(graph.projectedPositions().get('b').x,450);assert.equal(graph.repositioning,false);
 graph.armReposition();let stopped=false;documentHandlers.keydown({key:'Escape',preventDefault(){},stopImmediatePropagation(){stopped=true;}});assert.equal(stopped,true);assert.equal(graph.repositioning,false);
 graph.pointerDown({button:0,pointerId:3,clientX:1,clientY:1,target:svg});assert.equal(svg.capture.size,1);graph.setData(nodes,edges,nodes,'A:paragraph');assert.equal(graph.drag,null);assert.equal(svg.capture.size,0);
 const snapshot=graph.snapshot();snapshot.sphere_positions.a.x=100;assert.notEqual(graph.positions.get('a').x,100);
}));
