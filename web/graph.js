/* Original code: MIT. Layouts, sphere orientation and camera are presentation only. */
(function(root,factory){
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PKOCGraph=api;
})(typeof window!=='undefined'?window:this,function(){
 'use strict';
 const LAYOUTS=['paper','circle','random','sphere3d'],SPHERE={x:450,y:320,radius:255},RANDOM_SEED='pkoc-random-v1';
 const compare=(a,b)=>a<b?-1:a>b?1:0,clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
 function fitCamera(points,width,height){
  if(!points.length)return {x:width/2,y:height/2,k:1};
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y),left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);
  const k=Math.max(.000001,Math.min(2,Math.max(40,width-160)/Math.max(80,right-left),Math.max(40,height-120)/Math.max(80,bottom-top)));
  return {x:width/2-(left+right)/2*k,y:height/2-(top+bottom)/2*k,k};
 }
 function zoomCamera(camera,factor,point){
  const k=clamp(camera.k*factor,.000001,6),ratio=k/camera.k;
  return {x:point.x-(point.x-camera.x)*ratio,y:point.y-(point.y-camera.y)*ratio,k};
 }
 function fitSphereCamera(width,height){
  const k=Math.max(.000001,Math.min(2,Math.max(40,width-80)/(2*SPHERE.radius),Math.max(40,height-56)/(2*SPHERE.radius)));
  return {x:width/2-SPHERE.x*k,y:height/2-SPHERE.y*k,k};
 }
 function worldPoint(camera,point){return {x:(point.x-camera.x)/camera.k,y:(point.y-camera.y)/camera.k};}
 function initialPositions(roster){
  // Preserve the original paper coordinate normalization and roster order.
  const raw=roster.map((n,i)=>({id:n.actor_id,...(n.layout&&Number.isFinite(n.layout.x)&&Number.isFinite(n.layout.y)?{x:n.layout.x,y:n.layout.y}:{x:Math.cos(2*Math.PI*i/Math.max(1,roster.length)),y:Math.sin(2*Math.PI*i/Math.max(1,roster.length))})}));
  const xs=raw.map(p=>p.x),ys=raw.map(p=>p.y),left=Math.min(...xs),top=Math.min(...ys),dx=Math.max(...xs)-left,dy=Math.max(...ys)-top;
  return new Map(raw.map(p=>[p.id,{x:85+730*(p.x-left)/(dx||1),y:65+510*(p.y-top)/(dy||1)}]));
 }
 function hashUnit(value){let h=2166136261;for(const c of value){h^=c.codePointAt(0);h=Math.imul(h,16777619);}h^=h>>>16;h=Math.imul(h,0x85ebca6b);h^=h>>>13;h=Math.imul(h,0xc2b2ae35);h^=h>>>16;return (h>>>0)/4294967296;}
 function initialLayout(roster,kind){
  if(!LAYOUTS.includes(kind))throw new Error('Unsupported graph layout: '+kind);
  if(kind==='paper')return initialPositions(roster);
  const ids=roster.map(n=>n.actor_id).sort(compare),count=ids.length;
  return new Map(ids.map((id,i)=>{
   if(kind==='sphere3d'){
    if(count===1)return [id,{x:0,y:0,z:1}];
    const y=1-2*(i+.5)/count,r=Math.sqrt(Math.max(0,1-y*y)),angle=i*Math.PI*(3-Math.sqrt(5));
    return [id,{x:r*Math.cos(angle),y,z:r*Math.sin(angle)}];
   }
   if(count===1)return [id,{x:450,y:320}];
   if(kind==='circle'){const a=2*Math.PI*i/count-Math.PI/2;return [id,{x:450+255*Math.cos(a),y:320+255*Math.sin(a)}];}
   return [id,{x:85+730*hashUnit(RANDOM_SEED+':x:'+id),y:65+510*hashUnit(RANDOM_SEED+':y:'+id)}];
  }));
 }
 function normalizedOrientation(yaw,pitch){
  if(!Number.isFinite(yaw)||!Number.isFinite(pitch))throw new Error('Rotation must use finite degrees.');
  return {yaw:((yaw+180)%360+360)%360-180,pitch:clamp(pitch,-90,90)};
 }
 function rotatePoint(p,orientation,inverse=false){
  const yaw=orientation.yaw*Math.PI/180,pitch=orientation.pitch*Math.PI/180,cy=Math.cos(yaw),sy=Math.sin(yaw),cx=Math.cos(pitch),sx=Math.sin(pitch);
  if(inverse){const y=p.y*cx+p.z*sx,z=-p.y*sx+p.z*cx;return {x:p.x*cy-z*sy,y,z:p.x*sy+z*cy};}
  const x=p.x*cy+p.z*sy,z=-p.x*sy+p.z*cy;return {x,y:p.y*cx-z*sx,z:p.y*sx+z*cx};
 }
 function projectSphere(p,orientation){const q=rotatePoint(p,orientation);return {x:SPHERE.x+q.x*SPHERE.radius,y:SPHERE.y-q.y*SPHERE.radius,z:q.z};}
 function surfaceDestination(point,orientation,hemisphere=1,clampToRim=true){
  let x=(point.x-SPHERE.x)/SPHERE.radius,y=-(point.y-SPHERE.y)/SPHERE.radius;const distance=Math.hypot(x,y);
  if(distance>1){if(!clampToRim)return null;x/=distance;y/=distance;}
  const z=distance>=1?0:(hemisphere<0?-1:1)*Math.sqrt(Math.max(0,1-x*x-y*y));return rotatePoint({x,y,z},orientation,true);
 }
 function degreeRadius(degree,maxDegree){return Math.sqrt(25+299*(maxDegree>0?clamp(degree/maxDegree,0,1):0));}
 function pickProjectedNode(candidates,point,sphere=false){
  const hits=candidates.map(n=>({...n,distance:Math.hypot(point.x-n.x,point.y-n.y)})).filter(n=>n.distance<=Math.max(22,n.radius));
  const physical=hits.filter(n=>n.distance<=n.radius),pool=physical.length?physical:hits;
  pool.sort((a,b)=>(sphere&&physical.length?b.z-a.z:0)||a.distance-b.distance||(sphere?b.z-a.z:0)||compare(a.id,b.id));return pool[0]?.id||null;
 }
 function svgElement(tag,attrs={},text){
  const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value]of Object.entries(attrs))n.setAttribute(key,String(value));if(text!=null)n.textContent=text;return n;
 }
 class ExplorerGraph{
  constructor(svg,{onNode=()=>{},onEdge=()=>{},onStatus=()=>{},onOrientation=()=>{}}={}){
   Object.assign(this,{svg,onNode,onEdge,onStatus,onOrientation,contexts:new Map(),mode:'smart',layoutType:'paper',orientation:{yaw:0,pitch:0},camera:{x:0,y:0,k:1},nodes:[],edges:[],roster:[],width:900,height:640,nodeElements:new Map(),lines:[],selected:null,hover:null,drag:null,repositioning:false});
   svg.addEventListener('pointerdown',e=>this.pointerDown(e));svg.addEventListener('pointermove',e=>this.pointerMove(e));
   for(const type of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(type,e=>this.pointerEnd(e));
   svg.addEventListener('click',e=>{if(this.suppressClick){e.stopImmediatePropagation();this.suppressClick=false;}},true);
   svg.addEventListener('wheel',e=>{if((!e.ctrlKey&&!e.metaKey)||this.drag)return;e.preventDefault();this.camera=zoomCamera(this.camera,Math.exp(-e.deltaY*.002),this.screenPoint(e));this.draw();},{passive:false});
   this.escapeHandler=e=>{if(e.key==='Escape'&&this.repositioning){e.preventDefault();e.stopImmediatePropagation();this.cancelReposition();}};
   document.addEventListener('keydown',this.escapeHandler,true);
   this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(svg);
  }
  resize(){const rect=this.svg.getBoundingClientRect();if(rect.width<1||rect.height<1)return;this.width=rect.width;this.height=rect.height;this.svg.setAttribute('viewBox','0 0 '+this.width+' '+this.height);this.fit();}
  stopDrag(){if(!this.drag)return;const id=this.drag.pointerId;this.drag=null;if(this.svg.hasPointerCapture(id))this.svg.releasePointerCapture(id);this.svg.classList.remove('dragging');this.suppressClick=true;}
  clear(){this.stopDrag();this.cancelReposition(false);this.contexts.clear();this.context=null;this.activeKey=null;this.layoutType='paper';this.orientation={yaw:0,pitch:0};this.selected=null;this.hover=null;this.onOrientation({...this.orientation});}
  storeCamera(){const record=this.contexts.get(this.activeKey);if(record){record.camera={...this.camera};record.orientation={...this.orientation};}}
  activateContext(context){
   const key=JSON.stringify([context,this.layoutType]);if(key===this.activeKey)return false;
   this.storeCamera();this.activeKey=key;this.context=context;
   if(!this.contexts.has(key))this.contexts.set(key,{positions:initialLayout(this.roster,this.layoutType),orientation:{yaw:0,pitch:0},camera:null});
   const record=this.contexts.get(key);this.positions=record.positions;this.orientation={...record.orientation};if(record.camera)this.camera={...record.camera};
   this.onOrientation({...this.orientation});return !record.camera;
  }
  setLayout(kind){
   if(!LAYOUTS.includes(kind))throw new Error('Unsupported graph layout: '+kind);if(kind===this.layoutType)return;
   this.stopDrag();this.cancelReposition(false);this.storeCamera();this.layoutType=kind;
   if(this.context!=null)this.setData(this.nodes,this.edges,this.roster,this.context);
  }
  setOrientation(yaw,pitch){
   this.stopDrag();this.cancelReposition(false);this.orientation=normalizedOrientation(Number(yaw),Number(pitch));this.storeCamera();this.onOrientation({...this.orientation});this.draw();
  }
  setData(nodes,edges,roster,context){
   this.stopDrag();this.cancelReposition(false);this.nodes=nodes;this.edges=edges;this.roster=roster;this.hover=null;
   const fresh=this.activateContext(context);this.maxDegree=Math.max(0,...roster.map(n=>Number(n.degree)||0));
   if(!nodes.some(n=>n.actor_id===this.selected))this.selected=null;
   this.svg.dataset.layout=this.layoutType;
   this.svg.replaceChildren(svgElement('title',{},'Interactive co-occurrence network'),svgElement('desc',{},this.layoutType==='sphere3d'?'Three-dimensional sphere with orthographic projection. Drag background to rotate; drag actors along the surface. Focus an actor and use arrows to move, Enter to inspect. Positions are presentation only.':'Drag actors to move them; drag background to pan. Focus an actor and use arrows to move, Enter to inspect. Positions are presentation only.'));
   this.group=svgElement('g',{id:'graph-content'});this.svg.append(this.group);
   this.edgeLayer=svgElement('g',{class:'graph-edges'});this.visualLayer=svgElement('g',{class:'graph-visuals','aria-hidden':'true','pointer-events':'none'});this.controlLayer=svgElement('g',{class:'graph-controls'});this.labelLayer=svgElement('g',{class:'actor-label-layer','pointer-events':'none','aria-hidden':'true'});
   if(this.layoutType==='sphere3d'){
    const guide=svgElement('circle',{cx:SPHERE.x,cy:SPHERE.y,r:SPHERE.radius,fill:'none',stroke:'#64839a','stroke-opacity':'.35','stroke-width':'1','vector-effect':'non-scaling-stroke','pointer-events':'none','aria-hidden':'true'});this.group.append(guide);
   }
   this.group.append(this.edgeLayer,this.visualLayer,this.controlLayer,this.labelLayer);this.lines=[];this.nodeElements=new Map();
   for(const edge of edges){const line=svgElement('line',{class:'graph-edge','vector-effect':'non-scaling-stroke','stroke-width':Math.min(4,1+Math.log1p(edge.weight)*.6)});line.append(svgElement('title',{},edge.label));line.addEventListener('click',()=>this.onEdge(edge));this.edgeLayer.append(line);this.lines.push({line,edge});}
   for(const node of nodes){
    const g=svgElement('g',{class:'node-control',tabindex:0,role:'button','data-actor-id':node.actor_id,'aria-label':node.name+', '+node.roleLabel+', degree '+node.degree+'. Enter to inspect; arrow keys to move.'});
    const visual=svgElement('g',{class:'graph-node'+(!node.degree?' isolate':''),'data-actor-id':node.actor_id}),hit=svgElement('circle',{class:'node-hit',fill:'transparent'}),dot=svgElement('circle',{class:'node-dot','vector-effect':'non-scaling-stroke'}),label=svgElement('text',{'aria-hidden':'true',class:'actor-label'},node.name);
    visual.style.setProperty('--node-color',node.color||'#83a3c7');visual.append(dot);g.append(hit,svgElement('title',{},node.name+' · '+node.roleLabel));
    g.addEventListener('click',()=>{this.select(node.actor_id);this.onNode(node);});
    g.addEventListener('pointerenter',()=>{this.hover=node.actor_id;this.draw();});g.addEventListener('pointerleave',()=>{this.hover=null;this.draw();});
    g.addEventListener('focus',()=>{this.hover=node.actor_id;this.draw();});g.addEventListener('blur',()=>{this.hover=null;this.draw();});
    g.addEventListener('keydown',e=>{
     if(['Enter',' '].includes(e.key)){e.preventDefault();this.select(node.actor_id);this.onNode(node);}
     const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
     if(moves[e.key]){e.preventDefault();this.select(node.actor_id);this.move(...moves[e.key],e.shiftKey?40:12);this.onNode(node);}
    });
    this.nodeElements.set(node.actor_id,{g,visual,hit,dot,label,node});this.visualLayer.append(visual);this.controlLayer.append(g);this.labelLayer.append(label);
   }
   if(!nodes.length)this.svg.append(svgElement('text',{x:'50%',y:'50%','text-anchor':'middle',fill:'#a9bbd1'},'No actors match these filters.'));
   if(fresh)this.fit();else this.draw();
  }
  projectedPositions(){return new Map([...(this.positions||[])].map(([id,p])=>[id,this.layoutType==='sphere3d'?projectSphere(p,this.orientation):{x:p.x,y:p.y,z:0}]));}
  screenPoint(e){const matrix=this.svg.getScreenCTM();return matrix?new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse()):{x:0,y:0};}
  pick(point){const positions=this.projectedPositions();return pickProjectedNode(this.nodes.map(n=>{const p=positions.get(n.actor_id);return {id:n.actor_id,x:this.camera.x+p.x*this.camera.k,y:this.camera.y+p.y*this.camera.k,z:p.z,radius:degreeRadius(n.degree,this.maxDegree)};}),point,this.layoutType==='sphere3d');}
  pointerDown(e){
   if(e.button!==0||this.drag||!this.group)return;
   const p=this.screenPoint(e),world=worldPoint(this.camera,p),id=this.repositioning?this.selected:this.pick(p),position=id?this.projectedPositions().get(id):null;
   this.drag={pointerId:e.pointerId,id,edge:this.lines.find(row=>row.line===e.target)?.edge,start:p,world,position:position?{...position}:null,camera:{...this.camera},orientation:{...this.orientation},hemisphere:position?.z<0?-1:1,moved:false,reposition:this.repositioning};
   this.suppressClick=false;this.svg.setPointerCapture(e.pointerId);
  }
  pointerMove(e){
   const d=this.drag;if(!d){if(this.group&&e.pointerType!=='touch'&&!this.repositioning){const id=this.pick(this.screenPoint(e));if(id!==this.hover){this.hover=id;this.draw();}}return;}if(e.pointerId!==d.pointerId)return;const p=this.screenPoint(e),dx=p.x-d.start.x,dy=p.y-d.start.y;
   if(Math.hypot(dx,dy)>4)d.moved=true;if(!d.moved||d.reposition)return;
   if(d.id){
    const target={x:d.position.x+dx/d.camera.k,y:d.position.y+dy/d.camera.k};
    this.positions.set(d.id,this.layoutType==='sphere3d'?surfaceDestination(target,d.orientation,d.hemisphere):target);this.selected=d.id;
   }else if(this.layoutType==='sphere3d'){
    this.orientation=normalizedOrientation(d.orientation.yaw+dx*.35,d.orientation.pitch+dy*.35);this.onOrientation({...this.orientation});
   }else this.camera={...d.camera,x:d.camera.x+dx,y:d.camera.y+dy};
   this.svg.classList.add('dragging');this.draw();
  }
  pointerEnd(e){
   const d=this.drag;if(!d||d.pointerId!==e.pointerId)return;this.drag=null;this.svg.classList.remove('dragging');this.suppressClick=d.moved||!!d.id||!!d.edge||d.reposition;
   if(this.svg.hasPointerCapture(e.pointerId))this.svg.releasePointerCapture(e.pointerId);
   if(e.type!=='pointerup')return;
   if(d.reposition){if(!d.moved)this.repositionAt(this.screenPoint(e));return;}
   if(d.id){const node=this.nodes.find(n=>n.actor_id===d.id);if(node){this.select(d.id);this.onNode(node);}}
   else if(d.edge&&!d.moved)this.onEdge(d.edge);
  }
  select(id){if(this.repositioning&&id!==this.selected)this.cancelReposition(false);this.selected=id;this.draw();}
  move(dx,dy,pixels=24){
   const p=this.projectedPositions().get(this.selected);if(!p)return;const target={x:p.x+dx*pixels/this.camera.k,y:p.y+dy*pixels/this.camera.k};
   this.positions.set(this.selected,this.layoutType==='sphere3d'?surfaceDestination(target,this.orientation,p.z<0?-1:1):target);this.draw();
  }
  armReposition(){
   if(!this.selected||!this.nodeElements.has(this.selected)){this.onStatus('Select an actor first.');return false;}
   this.stopDrag();this.repositioning=true;const p=this.projectedPositions().get(this.selected);this.repositionHemisphere=p.z<0?-1:1;this.svg.classList.add('repositioning');
   this.onStatus(this.layoutType==='sphere3d'?'Click inside the sphere to reposition the selected actor. Escape cancels.':'Click in the graph to reposition the selected actor. Escape cancels.');return true;
  }
  cancelReposition(announce=true){const was=this.repositioning;this.repositioning=false;this.svg.classList.remove('repositioning');if(was&&announce)this.onStatus('Actor repositioning cancelled.');}
  repositionAt(point){
   if(!this.repositioning||!this.positions.has(this.selected))return false;const target=worldPoint(this.camera,point),position=this.layoutType==='sphere3d'?surfaceDestination(target,this.orientation,this.repositionHemisphere,false):target;
   if(!position){this.onStatus('Choose a destination inside the sphere, or press Escape to cancel.');return false;}
   this.positions.set(this.selected,position);this.cancelReposition(false);this.draw();this.onStatus('Actor repositioned. Only the view changed.');return true;
  }
  fit(){
   const p=this.projectedPositions();this.camera=this.layoutType==='sphere3d'?fitSphereCamera(this.width,this.height):fitCamera(this.nodes.map(n=>p.get(n.actor_id)),this.width,this.height);this.draw();
  }
  zoom(factor){this.camera=zoomCamera(this.camera,factor,{x:this.width/2,y:this.height/2});this.draw();}
  reset(){this.stopDrag();this.cancelReposition(false);this.contexts.delete(this.activeKey);this.activeKey=null;this.setData(this.nodes,this.edges,this.roster,this.context);}
  snapshot(){return {positions:Object.fromEntries([...this.projectedPositions()].map(([id,p])=>[id,{x:p.x,y:p.y}])),camera:{...this.camera},labels:this.mode,presentation_only:true,layout:this.layoutType,orientation:{...this.orientation},projection:this.layoutType==='sphere3d'?'orthographic-3d':'2d',random_seed:this.layoutType==='random'?RANDOM_SEED:null,sphere_positions:this.layoutType==='sphere3d'?Object.fromEntries([...(this.positions||[])].map(([id,p])=>[id,{...p}])):null,degree_size:{encoding:'area-linear',minimum_radius_px:5,maximum_radius_px:18,roster_max_degree:this.maxDegree||0}};}
  draw(){
   if(!this.group||!this.positions)return;const {x,y,k}=this.camera,positions=this.projectedPositions(),sphere=this.layoutType==='sphere3d',active=this.hover||this.selected;
   this.group.setAttribute('transform','translate('+x+' '+y+') scale('+k+')');
   const depthEdges=[...this.lines].sort((a,b)=>sphere?(positions.get(a.edge.source).z+positions.get(a.edge.target).z)-(positions.get(b.edge.source).z+positions.get(b.edge.target).z):0);
   for(const {line,edge} of depthEdges){
    const p=positions.get(edge.source),q=positions.get(edge.target);for(const [key,value]of Object.entries({x1:p.x,y1:p.y,x2:q.x,y2:q.y}))line.setAttribute(key,value);
    line.classList.toggle('connected',edge.source===active||edge.target===active);line.style.opacity=sphere?String(.35+.65*((p.z+q.z)/4+.5)):'1';if(sphere)this.edgeLayer.append(line);
   }
   const ordered=[...this.nodeElements.values()].sort((a,b)=>sphere?positions.get(a.node.actor_id).z-positions.get(b.node.actor_id).z||compare(a.node.actor_id,b.node.actor_id):0);
   for(const {visual,node}of ordered){if(sphere)this.visualLayer.append(visual);visual.style.opacity=sphere?String(.6+.4*(positions.get(node.actor_id).z+1)/2):'1';}
   const ranked=[...this.nodeElements.values()].sort((a,b)=>Number(b.node.actor_id===active)-Number(a.node.actor_id===active)||b.node.degree-a.node.degree||compare(a.node.actor_id,b.node.actor_id)),occupied=[];let count=0;
   for(const {node,g,visual,hit,dot,label}of ranked){
    const p=positions.get(node.actor_id),selected=node.actor_id===active,transform='translate('+p.x+' '+p.y+')';g.setAttribute('transform',transform);visual.setAttribute('transform',transform);
    visual.classList.toggle('selected',node.actor_id===this.selected);visual.classList.toggle('active',selected);if(selected)visual.style.opacity='1';
    hit.setAttribute('r',22/k);dot.setAttribute('r',degreeRadius(node.degree,this.maxDegree)/k);
    label.setAttribute('transform',transform);label.style.fontSize=(selected?15:14)/k+'px';label.style.strokeWidth=5/k+'px';
    const sx=x+p.x*k,sy=y+p.y*k,w=node.name.length*7.8+10,right=sx+w+22<this.width,offset=degreeRadius(node.degree,this.maxDegree)+7;
    label.setAttribute('x',(right?offset:-offset)/k);label.setAttribute('y',-offset/k);label.setAttribute('text-anchor',right?'start':'end');
    const box={l:right?sx+offset:sx-w-offset,r:right?sx+w+offset:sx-offset,t:sy-offset-18,b:sy-offset+3};
    const fits=box.l>=2&&box.r<=this.width-2&&box.t>=2&&box.b<=this.height-2&&!occupied.some(b=>box.l<b.r+7&&box.r>b.l-7&&box.t<b.b+5&&box.b>b.t-5);
    const show=selected||this.mode==='all'||(this.mode==='smart'&&fits&&count<Math.max(14,Math.floor(this.width*this.height/15000)));
    label.style.display=show?'':'none';if(show){occupied.push(box);count++;}
   }
   const activeLabel=this.nodeElements.get(active)?.label;if(activeLabel)this.labelLayer.append(activeLabel);this.storeCamera();
  }
 }
 return {ExplorerGraph,fitCamera,fitSphereCamera,zoomCamera,worldPoint,initialPositions,initialLayout,normalizedOrientation,rotatePoint,projectSphere,surfaceDestination,degreeRadius,pickProjectedNode,LAYOUTS,SPHERE,RANDOM_SEED};
});
