// Synthetic test control against a real private fixture and headless Chromium.
// No game interaction or native fidelity claim.
const { chromium }=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const root=process.argv[2];assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(root||''));
 const bindings=await (await fetch(root+'/prepared-dresses')).json();
 const initial=await (await fetch(root+'/scene-catalog')).json();
 const current=initial.active;
 const chosen={};for(const r of bindings.items)if(r.transitions[current]===current)chosen[r.kind]=r.part_id;
 const alternate=(kind,from)=>bindings.items.find(r=>r.kind===kind&&r.part_id!==chosen[kind]&&r.transitions[from]);
 const top=alternate('top',current),topTarget=top.transitions[current];
 const bottom=alternate('bottom',topTarget),bottomTarget=bottom.transitions[topTarget];
 assert(top&&bottom);
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function select(kind,part,target){
  await page.goto(root+'/cc-library',{waitUntil:'domcontentloaded'});
  await page.locator('#query-fields').waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('#query-fields').disabled,null,{timeout:30000});
  await page.locator('[name="body_type"]').fill(kind==='top'?'6':'7');
  await page.locator('#filters button[type="submit"]').click();
  const card=page.locator('#results > [data-part-id="'+part+'"]');
  await card.waitFor({state:'visible',timeout:30000});
  const button=card.locator('[data-prepared-dress-action]');await button.waitFor({state:'visible',timeout:30000});
  assert.match(await button.innerText(),new RegExp(kind+' combo'));
  await Promise.all([page.waitForURL('**/cas-room',{timeout:90000}),button.click()]);
  const state=await (await fetch(root+'/scene-catalog')).json();assert.equal(state.active,target);
 }
 await select('top',top.part_id,topTarget);await select('bottom',bottom.part_id,bottomTarget);
 assert.deepEqual(errors,[]);console.log('PASS real Chromium UI: source-bound prepared top then bottom; navigation and active-scene tokens verified; no game writes');
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
