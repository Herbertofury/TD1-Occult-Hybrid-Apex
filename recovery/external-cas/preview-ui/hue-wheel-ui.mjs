import {beginHueGesture,advanceHueGesture,huePosition,quantizeHue} from './hue-wheel-model.mjs';

// Routes through the existing range input and its history owner; never recolors pixels here.
export function bindHueWheel({wheel,input,output,announcement,enabled=()=>!input.disabled,coarseStep=256}) {
  if(input.step!=='1'||!Number.isInteger(coarseStep)||coarseStep<1||coarseStep>16384)throw Error('Exact Q14 input step and bounded coarse step required');
  let pointer=null,keyboard=null;
  const marker=wheel.querySelector('.hue-wheel-marker');
  const values=()=>{const v={value:Number(input.value),min:Number(input.min),max:Number(input.max)};if(!Number.isInteger(v.value)||quantizeHue(v.value/16384,v.min,v.max)!==v.value)throw Error('Invalid hue input bounds/value');return v;};
  const description=value=>`${(value*360/16384).toFixed(2)} degrees hue shift; ${value} Q14`;
  function sync(){
    const active=enabled();if(!active&&(pointer||keyboard)){cancel();return;}
    const {value,min,max}=values(),p=huePosition(value);
    marker.style.left=`${50+42*p.x}%`;marker.style.top=`${50+42*p.y}%`;
    wheel.setAttribute('aria-valuemin',String(min));wheel.setAttribute('aria-valuemax',String(max));
    wheel.setAttribute('aria-valuenow',String(value));wheel.setAttribute('aria-valuetext',description(value));
    wheel.setAttribute('aria-disabled',String(!active));wheel.tabIndex=active?0:-1;
    output.textContent=`${(value*360/16384).toFixed(2)}° · ${value}/16384`;
  }
  function set(value){
    if(Number(input.value)!==value){input.value=String(value);input.dispatchEvent(new Event('input',{bubbles:true}));}
    sync();
  }
  function commit(){input.dispatchEvent(new Event('change',{bubbles:true}));sync();announcement.textContent=description(Number(input.value));}
  function stop(){
    const id=pointer?.id;pointer=null;keyboard=null;
    if(id!==undefined&&wheel.hasPointerCapture(id))wheel.releasePointerCapture(id);
  }
  function cancel(){const original=pointer?.state.original??keyboard?.original;stop();if(original!==undefined)set(original);sync();}
  function point(event){const r=wheel.getBoundingClientRect();return {dx:event.clientX-r.left-r.width/2,dy:event.clientY-r.top-r.height/2,radius:Math.min(r.width,r.height)/2};}
  wheel.addEventListener('pointerdown',event=>{
    if(!enabled()||event.button!==0||event.isPrimary===false||pointer||keyboard)return;
    const p=point(event);if(p.radius<=0||Math.hypot(p.dx,p.dy)<p.radius*.6||Math.hypot(p.dx,p.dy)>p.radius*1.05)return;
    const state=beginHueGesture(values(),p.dx,p.dy);if(!state)return;
    event.preventDefault();wheel.focus();wheel.setPointerCapture(event.pointerId);
    pointer={id:event.pointerId,state};set(state.value);
  });
  function move(event){
    if(!pointer||pointer.id!==event.pointerId)return;
    if(!enabled()){cancel();return;}
    const p=point(event);if(Math.hypot(p.dx,p.dy)<p.radius*.6)return;
    pointer.state=advanceHueGesture(pointer.state,p.dx,p.dy);set(pointer.state.value);
  }
  wheel.addEventListener('pointermove',move);
  wheel.addEventListener('pointerup',event=>{if(pointer?.id!==event.pointerId)return;move(event);if(!pointer)return;if(!enabled()){cancel();return;}stop();commit();});
  wheel.addEventListener('pointercancel',event=>{if(pointer?.id===event.pointerId)cancel();});
  wheel.addEventListener('lostpointercapture',event=>{if(pointer?.id===event.pointerId)cancel();});
  const keys=new Set(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','PageUp','PageDown','Home','End']);
  wheel.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&(pointer||keyboard)){event.preventDefault();cancel();return;}
    if(!enabled()||pointer||event.ctrlKey||event.metaKey||event.altKey||!keys.has(event.key))return;
    event.preventDefault();const {value,min,max}=values();keyboard??={original:value,held:new Set()};keyboard.held.add(event.key);
    const step=event.shiftKey?1:coarseStep,amount=step*(event.key.startsWith('Page')?8:1);
    if(!Number.isInteger(step)||step<1)throw Error('Integer hue input step required');
    const target=event.key==='Home'?min:event.key==='End'?max:value+(['ArrowLeft','ArrowDown','PageDown'].includes(event.key)?-amount:amount);
    set(Math.max(min,Math.min(max,target)));
  });
  wheel.addEventListener('keyup',event=>{if(keyboard&&keys.has(event.key)){keyboard.held.delete(event.key);if(!keyboard.held.size){if(!enabled())cancel();else{stop();commit();}}}});
  wheel.addEventListener('blur',()=>{if(pointer)cancel();else if(keyboard){if(!enabled())cancel();else{stop();commit();}}});
  input.addEventListener('input',sync);input.addEventListener('change',sync);sync();
  return {sync,stop,cancel};
}
