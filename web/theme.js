/* Local appearance preference. Original code: MIT. */
(function(){
 'use strict';
 const key='pkoc-explorer-theme',root=document.documentElement;
 function valid(value){return value==='light'?'light':'dark';}
 function saved(){try{return valid(localStorage.getItem(key));}catch{return 'dark';}}
 function syncControls(){
  const next=root.dataset.theme==='light'?'dark':'light';
  for(const button of document.querySelectorAll('[data-theme-toggle]')){
   button.setAttribute('aria-label','Switch to '+next+' mode');
   button.title='Current theme: '+root.dataset.theme+'. Switch to '+next+' mode.';
   button.querySelector('[data-theme-label]').textContent=next==='light'?'Light mode':'Dark mode';
  }
 }
 function apply(value,persist){
  const theme=valid(value);root.dataset.theme=theme;root.style.colorScheme=theme;
  document.querySelector('meta[name="color-scheme"]')?.setAttribute('content',theme);
  if(persist){try{localStorage.setItem(key,theme);}catch{/* The current page still switches when storage is unavailable. */}}
  syncControls();
 }
 // Run before stylesheets so a saved light preference does not flash dark.
 apply(saved(),false);
 document.addEventListener('DOMContentLoaded',syncControls,{once:true});
 document.addEventListener('click',event=>{if(event.target.closest?.('[data-theme-toggle]'))apply(root.dataset.theme==='light'?'dark':'light',true);});
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(event.newValue,false);});
 window.PKOCTheme=Object.freeze({get:()=>root.dataset.theme,set:value=>apply(value,true)});
})();
