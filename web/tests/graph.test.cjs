const test=require('node:test'),assert=require('node:assert/strict');
const {fitCamera,zoomCamera,worldPoint,initialPositions}=require('../graph.js');
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
