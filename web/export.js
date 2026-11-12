/* Self-contained, local graph images. Original code: MIT. */
(function(root,factory){
 'use strict';
 const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PKOCExport=api;
})(typeof window!=='undefined'?window:this,function(){
 'use strict';
 const NS='http://www.w3.org/2000/svg';
 const TAGS=new Set(['svg','g','circle','ellipse','line','path','polyline','polygon','rect','text','tspan','title','desc']);
 const ATTRS=new Set(['x','y','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height','d','points','transform','viewBox','preserveAspectRatio','dx','dy','textLength','lengthAdjust','rotate','vector-effect']);
 // Restrict copied styles to visual values. Never copy URLs, event handlers,
 // interaction state, page stylesheets, or optional evidence in the inspector.
 const STYLES=['fill','fill-opacity','fill-rule','stroke','stroke-width','stroke-opacity','stroke-linecap','stroke-linejoin','stroke-miterlimit','stroke-dasharray','stroke-dashoffset','opacity','display','visibility','font-family','font-size','font-weight','font-style','font-variant','letter-spacing','word-spacing','text-anchor','dominant-baseline','paint-order','vector-effect'];
 function escapeXml(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));}
 function safeColor(value,fallback='#a9bbd1'){
  const color=String(value||'').trim();
  return /^(?:#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})|(?:rgb|rgba|hsl|hsla)\([\d\s.,%+/-]+\)|transparent|black|white)$/i.test(color)?color:fallback;
 }
 function fileName(value,format){
  const base=String(value||'pkoc-network').replace(/\.(?:svg|png)$/i,'').replace(/[\x00-\x1f\x7f<>:"/\\|?*]/g,'-').replace(/[. ]+$/g,'').trim().slice(0,150)||'pkoc-network';
  return base+'.'+format;
 }
 function dimensions(width,height){
  const w=Math.ceil(Number(width)),h=Math.ceil(Number(height));
  if(!Number.isFinite(w)||!Number.isFinite(h)||w<1||h<1||w>8192||h>8192)throw new Error('The graph must be visible and at most 8,192 pixels in each dimension to export.');
  return {width:w,height:h};
 }
 function wrapText(value,maxCharacters){
  const limit=Math.max(8,Math.floor(maxCharacters));
  const paragraphs=String(value||'').replace(/\r/g,'').split('\n'),lines=[];
  for(const paragraph of paragraphs){
   let line='';
   for(const word of paragraph.split(/\s+/).filter(Boolean)){
    const chars=Array.from(word);
    if(chars.length>limit){
     if(line){lines.push(line);line='';}
     while(chars.length>limit)lines.push(chars.splice(0,limit).join(''));
     line=chars.join('');
    }else if(!line)line=word;
    else if(Array.from(line).length+1+chars.length<=limit)line+=' '+word;
    else{lines.push(line);line=word;}
   }
   if(line)lines.push(line);else if(!paragraph.trim())lines.push('');
  }
  return lines;
 }
 function footerSvg(width,options={}){
  const pad=20,usable=Math.max(40,width-pad*2),limit=Math.max(8,Math.floor(usable/8));
  let y=29;const parts=[];
  const text=(value,x,baseline,size=13,color='#a9bbd1',weight=400)=>'<text x="'+x+'" y="'+baseline+'" fill="'+safeColor(color)+'" font-family="system-ui, sans-serif" font-size="'+size+'" font-weight="'+weight+'">'+escapeXml(value)+'</text>';
  for(const line of wrapText(options.caption||'PKOC UNMIL Network Explorer · Current view',limit)){parts.push(text(line,pad,y,13,'#eaf1fc'));y+=20;}
  const legend=Array.isArray(options.legend)?options.legend:[];
  if(legend.length){
   y+=8;parts.push(text('CAMEO roles',pad,y,12,'#a9bbd1',600));y+=22;
   let x=pad;
   for(const item of legend){
    const lines=wrapText(item.label,Math.max(8,Math.floor((usable-26)/7.2))),itemWidth=Math.min(usable,28+Math.max(...lines.map(s=>Array.from(s).length))*7.2);
    if(x>pad&&x+itemWidth>width-pad){x=pad;y+=27;}
    parts.push('<circle cx="'+(x+5)+'" cy="'+(y-4)+'" r="4" fill="'+safeColor(item.color)+'"/>');
    lines.forEach((line,i)=>parts.push(text(line,x+16,y+i*19,12)));
    if(lines.length>1){y+=(lines.length-1)*19;x=pad;y+=27;}else x+=itemWidth;
   }
   y+=25;
  }
  const sizeKey=(Array.isArray(options.sizeKey)?options.sizeKey:[]).filter(p=>Number.isFinite(p.degree)&&p.degree>=0&&Number.isFinite(p.radius)&&p.radius>0&&p.radius<=30);
  if(sizeKey.length){
   y+=6;for(const line of wrapText('Node size: distinct connected actors (degree)',limit)){parts.push(text(line,pad,y,12,'#a9bbd1',600));y+=18;}y+=14;
   let x=pad;
   for(const item of sizeKey){
    const label=String(item.degree),itemWidth=item.radius*2+18+Array.from(label).length*8+24;
    if(x>pad&&x+itemWidth>width-pad){x=pad;y+=48;}
    parts.push('<circle cx="'+(x+item.radius)+'" cy="'+y+'" r="'+item.radius+'" fill="#83a3c7" stroke="#eaf1fc" stroke-width="1"/>');
    parts.push(text(label,x+item.radius*2+10,y+4,12));x+=itemWidth;
   }
   y+=28;
  }
  for(const line of wrapText('Undirected co-occurrence, not interactions or alliances. Layout and visibility are presentation choices.',limit)){parts.push(text(line,pad,y+10,12));y+=19;}
  return {source:parts.join(''),height:y+22};
 }
 function cloneVisual(source,doc,view){
  if(source.nodeType===3)return doc.createTextNode(source.nodeValue||'');
  if(source.nodeType!==1||source.namespaceURI!==NS||!TAGS.has(source.localName))return null;
  const clone=doc.createElementNS(NS,source.localName);
  for(const attribute of source.attributes){if(ATTRS.has(attribute.name)&&!/(?:url\s*\(|javascript:)/i.test(attribute.value))clone.setAttribute(attribute.name,attribute.value);}
  const style=view.getComputedStyle(source);
  for(const property of STYLES){
   const value=style.getPropertyValue(property);
   if(value&&!/(?:url\s*\(|var\s*\(|javascript:)/i.test(value))clone.style.setProperty(property,value);
  }
  for(const child of source.childNodes){const copy=cloneVisual(child,doc,view);if(copy)clone.append(copy);}
  return clone;
 }
 function serializeGraph(svg,options={}){
  if(!svg||svg.namespaceURI!==NS||svg.localName!=='svg'||!svg.ownerDocument?.defaultView)throw new Error('Select a visible network graph before exporting.');
  const doc=svg.ownerDocument,view=doc.defaultView,rect=svg.getBoundingClientRect(),size=dimensions(rect.width,rect.height);
  const clone=cloneVisual(svg,doc,view),footer=footerSvg(size.width,options),height=size.height+footer.height;
  if(height>8192)throw new Error('The export caption and legend are too large. Reduce their length before exporting.');
  clone.setAttribute('x','0');clone.setAttribute('y','0');clone.setAttribute('width',String(size.width));clone.setAttribute('height',String(size.height));
  clone.setAttribute('viewBox',svg.getAttribute('viewBox')||'0 0 '+size.width+' '+size.height);
  clone.style.setProperty('overflow','hidden');
  const content=new view.XMLSerializer().serializeToString(clone);
  const title=options.title||'PKOC UNMIL Network Explorer';
  const source='<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="'+NS+'" width="'+size.width+'" height="'+height+'" viewBox="0 0 '+size.width+' '+height+'" role="img"><title>'+escapeXml(title)+'</title><desc>'+escapeXml(options.caption||'Current network view')+'</desc><rect width="100%" height="100%" fill="'+safeColor(options.background,'#080f1b')+'"/>'+content+'<g transform="translate(0 '+size.height+')"><path d="M20 0H'+Math.max(20,size.width-20)+'" stroke="#2b405b"/>'+footer.source+'</g></svg>';
  return {source,width:size.width,height};
 }
 function downloadBlob(doc,blob,name){
  const view=doc.defaultView,url=view.URL.createObjectURL(blob),anchor=doc.createElement('a');
  anchor.href=url;anchor.download=name;doc.body.append(anchor);anchor.click();anchor.remove();
  view.setTimeout(()=>view.URL.revokeObjectURL(url),30000);
 }
 async function exportGraph(svg,options={}){
  const format=options.format||'svg';if(!['svg','png'].includes(format))throw new Error('Choose SVG or PNG for the graph image.');
  const snapshot=serializeGraph(svg,options),doc=svg.ownerDocument,view=doc.defaultView,name=fileName(options.filename,format);
  const vector=new view.Blob([snapshot.source],{type:'image/svg+xml;charset=utf-8'});
  if(format==='svg')downloadBlob(doc,vector,name);
  else{
   if(snapshot.width*snapshot.height*4>67108864)throw new Error('This image is too large for a 2× PNG. Reduce the graph viewport or use SVG.');
   const url=view.URL.createObjectURL(vector);
   try{
    const image=await new Promise((resolve,reject)=>{const img=new view.Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('The browser could not render this SVG. Download SVG or try a smaller graph view.'));img.src=url;});
    const canvas=doc.createElement('canvas');canvas.width=snapshot.width*2;canvas.height=snapshot.height*2;
    const context=canvas.getContext('2d');if(!context)throw new Error('This browser could not create the PNG image. Download SVG instead.');
    context.drawImage(image,0,0,canvas.width,canvas.height);
    const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('PNG encoding failed. Download SVG instead.')),'image/png'));
    downloadBlob(doc,blob,name);
   }finally{view.URL.revokeObjectURL(url);}
  }
  return {filename:name,width:snapshot.width*(format==='png'?2:1),height:snapshot.height*(format==='png'?2:1),format};
 }
 return {exportGraph,serializeGraph,escapeXml,safeColor,fileName,dimensions,wrapText,footerSvg};
});
