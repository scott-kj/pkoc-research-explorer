/* Interactive presentation layer. Original code: MIT.
 * Positions and camera are private view state; scientific nodes are never mutated.
 */
(function(root,factory){
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PKOCGraph=api;
})(typeof window!=='undefined'?window:this,function(){
 'use strict';
 function fitCamera(points,width,height){
  if(!points.length)return {x:width/2,y:height/2,k:1};
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  const left=Math.min(...xs),right=Math.max(...xs),top=Math.min(...ys),bottom=Math.max(...ys);
  const k=Math.max(.05,Math.min(2,Math.max(40,width-160)/Math.max(80,right-left),Math.max(40,height-120)/Math.max(80,bottom-top)));
  return {x:width/2-(left+right)/2*k,y:height/2-(top+bottom)/2*k,k};
 }
 function zoomCamera(camera,factor,point){
  const k=Math.max(.05,Math.min(6,camera.k*factor)),ratio=k/camera.k;
  return {x:point.x-(point.x-camera.x)*ratio,y:point.y-(point.y-camera.y)*ratio,k};
 }
 function worldPoint(camera,point){return {x:(point.x-camera.x)/camera.k,y:(point.y-camera.y)/camera.k};}
 function initialPositions(roster){
  const raw=roster.map((n,i)=>({id:n.actor_id,...(n.layout&&Number.isFinite(n.layout.x)&&Number.isFinite(n.layout.y)?{x:n.layout.x,y:n.layout.y}:{x:Math.cos(2*Math.PI*i/Math.max(1,roster.length)),y:Math.sin(2*Math.PI*i/Math.max(1,roster.length))})}));
  const xs=raw.map(p=>p.x),ys=raw.map(p=>p.y),left=Math.min(...xs),top=Math.min(...ys),dx=Math.max(...xs)-left,dy=Math.max(...ys)-top;
  return new Map(raw.map(p=>[p.id,{x:85+730*(p.x-left)/(dx||1),y:65+510*(p.y-top)/(dy||1)}]));
 }
 function svgElement(tag,attrs={},text){
  const n=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [key,value]of Object.entries(attrs))n.setAttribute(key,String(value));
  if(text!=null)n.textContent=text;return n;
 }
 class ExplorerGraph{
  constructor(svg,{onNode,onEdge}){
   this.svg=svg;this.onNode=onNode;this.onEdge=onEdge;this.contexts=new Map();this.mode='smart';this.camera={x:0,y:0,k:1};this.nodes=[];this.edges=[];this.width=900;this.height=640;
   this.nodeElements=new Map();this.lines=[];this.selected=null;this.hover=null;this.drag=null;
   svg.addEventListener('pointerdown',e=>this.pointerDown(e));
   svg.addEventListener('pointermove',e=>this.pointerMove(e));
   for(const type of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(type,e=>this.pointerEnd(e));
   svg.addEventListener('click',e=>{if(this.suppressClick){e.stopImmediatePropagation();this.suppressClick=false;}},true);
   svg.addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();this.camera=zoomCamera(this.camera,Math.exp(-e.deltaY*.002),this.screenPoint(e));this.draw();},{passive:false});
   this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(svg);
  }
  resize(){
   const rect=this.svg.getBoundingClientRect();if(rect.width<1||rect.height<1)return;
   this.measured=true;
   this.camera.x+=(rect.width-this.width)/2;this.camera.y+=(rect.height-this.height)/2;
   this.width=rect.width;this.height=rect.height;this.svg.setAttribute('viewBox','0 0 '+this.width+' '+this.height);
   this.fit();
  }
  clear(){this.contexts.clear();this.context=null;this.selected=null;this.hover=null;}
  setData(nodes,edges,roster,context){
   if(this.drag){const id=this.drag.pointerId;this.drag=null;if(this.svg.hasPointerCapture(id))this.svg.releasePointerCapture(id);this.svg.classList.remove('dragging');}
   const changed=context!==this.context;this.context=context;
   if(!this.contexts.has(context))this.contexts.set(context,initialPositions(roster));
   this.positions=this.contexts.get(context);this.nodes=nodes;this.edges=edges;this.roster=roster;this.hover=null;
   this.svg.replaceChildren(svgElement('title',{},'Interactive co-occurrence network'),svgElement('desc',{},'Drag a node to move it; drag the background to pan. Focus a node and use arrow keys to move, Enter to inspect. Positions have no analytical meaning.'));
   this.group=svgElement('g',{id:'graph-content'});this.svg.append(this.group);
   this.lines=[];this.nodeElements=new Map();
   for(const edge of edges){
    const line=svgElement('line',{class:'graph-edge','vector-effect':'non-scaling-stroke','stroke-width':Math.min(4,1+Math.log1p(edge.weight)*.6)});
    line.append(svgElement('title',{},edge.label));line.addEventListener('click',()=>this.onEdge(edge));
    this.group.append(line);this.lines.push({line,edge});
   }
   for(const node of nodes){
    const g=svgElement('g',{class:'graph-node'+(!node.degree?' isolate':''),tabindex:0,role:'button','data-actor-id':node.actor_id,'aria-label':node.name+', '+node.roleLabel+', degree '+node.degree+'. Enter to inspect; arrow keys to move.'});
    g.style.setProperty('--node-color',node.color);
    const hit=svgElement('circle',{class:'node-hit'}),dot=svgElement('circle',{class:'node-dot','vector-effect':'non-scaling-stroke'});
    const label=svgElement('text',{'aria-hidden':'true',class:'actor-label'},node.name);
    g.append(hit,dot,svgElement('title',{},node.name+' · '+node.roleLabel));
    g.addEventListener('click',()=>{this.select(node.actor_id);this.onNode(node);});
    g.addEventListener('pointerenter',()=>{this.hover=node.actor_id;this.draw();});
    g.addEventListener('pointerleave',()=>{this.hover=null;this.draw();});
    g.addEventListener('focus',()=>{this.hover=node.actor_id;this.draw();});
    g.addEventListener('blur',()=>{this.hover=null;this.draw();});
    g.addEventListener('keydown',e=>{
     if(['Enter',' '].includes(e.key)){e.preventDefault();this.select(node.actor_id);this.onNode(node);}
     const moves={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
     if(moves[e.key]){e.preventDefault();this.select(node.actor_id);this.move(...moves[e.key],e.shiftKey?40:12);this.onNode(node);}
    });
    this.nodeElements.set(node.actor_id,{g,hit,dot,label,node});this.group.append(g);
   }
   const labels=svgElement('g',{class:'actor-label-layer','pointer-events':'none'});
   for(const row of this.nodeElements.values())labels.append(row.label);this.group.append(labels);
   if(!nodes.length)this.svg.append(svgElement('text',{x:'50%',y:'50%','text-anchor':'middle',fill:'#a9bbd1'},'No actors match these filters.'));
   if(changed)this.fit();else this.draw();
  }
  screenPoint(e){
   const matrix=this.svg.getScreenCTM();return new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());
  }
  pointerDown(e){
   if(e.button!==0||this.drag||!this.group)return;
   const p=this.screenPoint(e),world=worldPoint(this.camera,p);
   // Overlapping touch targets select the nearest visible node center.
   let id=null,distance=23;
   for(const node of this.nodes){const q=this.positions.get(node.actor_id),d=Math.hypot((q.x-world.x)*this.camera.k,(q.y-world.y)*this.camera.k);if(d<distance){id=node.actor_id;distance=d;}}
   this.drag={pointerId:e.pointerId,id,edge:this.lines.find(row=>row.line===e.target)?.edge,start:p,world,position:id?{...this.positions.get(id)}:null,camera:{...this.camera},moved:false};
   this.suppressClick=false;this.svg.setPointerCapture(e.pointerId);
  }
  pointerMove(e){
   const d=this.drag;if(!d||e.pointerId!==d.pointerId)return;
   const p=this.screenPoint(e),dx=p.x-d.start.x,dy=p.y-d.start.y;
   if(Math.hypot(dx,dy)>4)d.moved=true;if(!d.moved)return;
   if(d.id){this.positions.set(d.id,{x:d.position.x+dx/d.camera.k,y:d.position.y+dy/d.camera.k});this.selected=d.id;}
   else this.camera={...d.camera,x:d.camera.x+dx,y:d.camera.y+dy};
   this.svg.classList.add('dragging');this.draw();
  }
  pointerEnd(e){
   const d=this.drag;if(!d||d.pointerId!==e.pointerId)return;
   this.drag=null;this.svg.classList.remove('dragging');this.suppressClick=d.moved||!!d.id||!!d.edge;
   if(this.svg.hasPointerCapture(e.pointerId))this.svg.releasePointerCapture(e.pointerId);
   if(d.id&&e.type==='pointerup'){this.select(d.id);this.onNode(this.nodes.find(n=>n.actor_id===d.id));}
   else if(d.edge&&!d.moved&&e.type==='pointerup')this.onEdge(d.edge);
  }
  select(id){this.selected=id;this.draw();}
  move(dx,dy,pixels=24){
   const p=this.positions?.get(this.selected);if(!p)return;
   this.positions.set(this.selected,{x:p.x+dx*pixels/this.camera.k,y:p.y+dy*pixels/this.camera.k});this.draw();
  }
  fit(){this.camera=fitCamera(this.nodes.map(n=>this.positions.get(n.actor_id)),this.width,this.height);this.draw();}
  zoom(factor){this.camera=zoomCamera(this.camera,factor,{x:this.width/2,y:this.height/2});this.draw();}
  reset(){this.contexts.delete(this.context);const key=this.context;this.context=null;this.setData(this.nodes,this.edges,this.roster,key);}
  snapshot(){return {positions:Object.fromEntries(this.positions||[]),camera:{...this.camera},labels:this.mode,presentation_only:true};}
  draw(){
   if(!this.group)return;const {x,y,k}=this.camera;this.group.setAttribute('transform','translate('+x+' '+y+') scale('+k+')');
   const active=this.hover||this.selected;
   for(const {line,edge} of this.lines){
    const p=this.positions.get(edge.source),q=this.positions.get(edge.target);
    for(const [key,value]of Object.entries({x1:p.x,y1:p.y,x2:q.x,y2:q.y}))line.setAttribute(key,value);
    line.classList.toggle('connected',edge.source===active||edge.target===active);
   }
   const ranked=[...this.nodeElements.values()].sort((a,b)=>Number(b.node.actor_id===active)-Number(a.node.actor_id===active)||b.node.degree-a.node.degree||a.node.actor_id.localeCompare(b.node.actor_id));
   const occupied=[];let count=0;
   for(const {node,g,hit,dot,label} of ranked){
    const p=this.positions.get(node.actor_id),selected=node.actor_id===active;
    g.setAttribute('transform','translate('+p.x+' '+p.y+')');g.classList.toggle('selected',node.actor_id===this.selected);
    hit.setAttribute('r',22/k);dot.setAttribute('r',(5+Math.min(5,Math.sqrt(node.degree)*.55))/k);
    label.setAttribute('transform','translate('+p.x+' '+p.y+')');label.style.fontSize=(selected?15:14)/k+'px';label.style.strokeWidth=5/k+'px';
    const sx=x+p.x*k,sy=y+p.y*k,w=node.name.length*7.8+10;
    const right=sx+w+15<this.width;label.setAttribute('x',(right?12:-12)/k);label.setAttribute('y',-12/k);label.setAttribute('text-anchor',right?'start':'end');
    const box={l:right?sx+10:sx-w-12,r:right?sx+w+12:sx-10,t:sy-30,b:sy-9};
    const fits=box.l>=2&&box.r<=this.width-2&&box.t>=2&&box.b<=this.height-2&&!occupied.some(b=>box.l<b.r+7&&box.r>b.l-7&&box.t<b.b+5&&box.b>b.t-5);
    const show=selected||this.mode==='all'||(this.mode==='smart'&&fits&&count<Math.max(14,Math.floor(this.width*this.height/15000)));
    label.style.display=show?'':'none';if(show){occupied.push(box);count++;}
   }
   // Raise only the decorative label, preserving node keyboard order.
   const activeLabel=this.nodeElements.get(active)?.label;if(activeLabel)activeLabel.parentElement.append(activeLabel);
   for(const {g,node}of this.nodeElements.values())g.classList.toggle('active',node.actor_id===active);
  }
 }
 return {ExplorerGraph,fitCamera,zoomCamera,worldPoint,initialPositions};
});
