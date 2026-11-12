const test=require('node:test');
const assert=require('node:assert/strict');
const E=require('../export.js');

test('image captions escape XML while preserving Unicode names',()=>{
 const value='José & Aïcha <actor> "役割" 🕊';
 assert.equal(E.escapeXml(value),'José &amp; Aïcha &lt;actor&gt; &quot;役割&quot; 🕊');
 const footer=E.footerSvg(600,{caption:value,legend:[{label:'<script>alert(1)</script>',color:'url(https://example.org/private.svg)'}]});
 assert.ok(!footer.source.includes('<script>'));
 assert.ok(!footer.source.includes('https://'));
 assert.match(footer.source,/&lt;script&gt;/);
 assert.match(footer.source,/José/);
 assert.ok(footer.height>0);
});
test('word wrapping does not split Unicode codepoints or lose words',()=>{
 const long='😀'.repeat(19);
 assert.deepEqual(E.wrapText(long,8),['😀'.repeat(8),'😀'.repeat(8),'😀'.repeat(3)]);
 assert.deepEqual(E.wrapText('one two three four',8),['one two','three','four']);
 const chars=E.wrapText('a'.repeat(25)+' last',8).join('');
 assert.equal(chars,'a'.repeat(25)+' last');
});
test('image filenames cannot become paths or retain invalid extensions',()=>{
 assert.equal(E.fileName('../../unsafe:<name>.svg','png'),'..-..-unsafe--name-.png');
 assert.equal(E.fileName('UNMIL José.svg','svg'),'UNMIL José.svg');
 assert.equal(E.fileName('','svg'),'pkoc-network.svg');
});
test('export dimensions reject invisible or excessive viewports',()=>{
 assert.deepEqual(E.dimensions(950.25,540),{width:951,height:540});
 for(const dimensions of [[0,2],[-1,400],[NaN,12],[Infinity,12],[12000,400]])assert.throws(()=>E.dimensions(...dimensions));
});
test('CAMEO legend and degree key are independently included only when supplied',()=>{
 const plain=E.footerSvg(600,{caption:'Model-only · Paragraph'});
 assert.ok(!plain.source.includes('CAMEO roles'));
 assert.ok(!plain.source.includes('Node size:'));
 const annotated=E.footerSvg(600,{caption:'Model-only · Paragraph',legend:[{label:'Government',color:'#c284f5'}],sizeKey:[{degree:0,radius:5},{degree:20,radius:18}]});
 assert.match(annotated.source,/CAMEO roles/);
 assert.match(annotated.source,/Government/);
 assert.match(annotated.source,/Node size:/);
 assert.match(annotated.source,/r="18"/);
 assert.ok(annotated.height>plain.height);
});
test('narrow exports wrap long legend labels and reject nonfinite size keys',()=>{
 const label='A long role label that needs to fit within a small mobile export';
 const wide=E.footerSvg(1200,{legend:[{label,color:'#abc'}]});
 const narrow=E.footerSvg(320,{legend:[{label,color:'#abc'}],sizeKey:[{degree:Infinity,radius:12},{degree:3,radius:NaN}]});
 assert.ok(narrow.height>wide.height);
 assert.ok(!narrow.source.includes('Infinity'));
 assert.ok(!narrow.source.includes('NaN'));
 assert.equal(E.safeColor('red; fill:url(x)'),'#a9bbd1');
 assert.equal(E.safeColor('rgb(255, 10, 0)'),'rgb(255, 10, 0)');
});
