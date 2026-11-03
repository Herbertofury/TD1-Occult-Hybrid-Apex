// Session-only preview history. Never represents a game or collection write.
export const CC_DEFAULTS=Object.freeze({yaw:0,pose:0,brightness:0,saturation:0,hue:0,opacity:16384});
const bounds={yaw:[-180,180],pose:[-90,90],brightness:[-8192,8192],saturation:[-8192,8192],hue:[-8192,8192],opacity:[3277,16384]};
function checked(value){
 if(!value||Object.keys(value).length!==6)throw Error('Complete preview parameters required');
 for(const [k,[min,max]] of Object.entries(bounds))if(!Number.isInteger(value[k])||value[k]<min||value[k]>max)throw Error(`Invalid preview ${k}`);
 return Object.freeze({...value});
}
const same=(a,b)=>Object.keys(bounds).every(k=>a[k]===b[k]);
export class PreviewHistory {
 constructor(initial,capacity=128,codec={checked,same}){
  this.checked=codec.checked;this.same=codec.same;
  if(!Number.isInteger(capacity)||capacity<2||capacity>1024)throw Error('Invalid history capacity');
  this.capacity=capacity;this.nodes=[{value:this.checked(initial),parent:null,children:[]}];this.current=0;this.staged=this.nodes[0].value;
 }
 exportState(){return {schema:1,capacity:this.capacity,current:this.current,nodes:this.nodes.map(n=>({value:{...n.value},parent:n.parent,children:[...n.children]}))};}
 restoreState(state){
  if(!state||Object.keys(state).length!==4||state.schema!==1||state.capacity!==this.capacity||!Array.isArray(state.nodes)||state.nodes.length<1||state.nodes.length>this.capacity||!Number.isInteger(state.current)||state.current<0||state.current>=state.nodes.length)throw Error('Invalid history checkpoint');
  const nodes=state.nodes.map((n,i)=>{if(!n||Object.keys(n).length!==3||!Array.isArray(n.children)||(i===0?n.parent!==null:!Number.isInteger(n.parent)||n.parent<0||n.parent>=i))throw Error('Invalid history graph');return {value:this.checked(n.value),parent:n.parent,children:[...n.children]};});
  const children=nodes.map(()=>[]);for(let i=1;i<nodes.length;i++)children[nodes[i].parent].push(i);
  for(let i=0;i<nodes.length;i++)if(nodes[i].children.length!==children[i].length||nodes[i].children.some((id,j)=>id!==children[i][j]))throw Error('Invalid history branches');
  this.nodes=nodes;this.current=state.current;this.staged=nodes[this.current].value;return this.value;
 }
 get value(){return {...this.staged};}
 get pending(){return !this.same(this.staged,this.nodes[this.current].value);}
 get canUndo(){return this.pending||this.nodes[this.current].parent!==null;}
 get branches(){return this.nodes[this.current].children.map(id=>({id,value:{...this.nodes[id].value}}));}
 stage(value){this.staged=this.checked(value);return this.value;}
 commit(){
  if(!this.pending)return false;
  if(this.nodes.length>=this.capacity){this.staged=this.nodes[this.current].value;throw Error('Preview history is full; existing history retained');}
  const id=this.nodes.length;this.nodes.push({value:this.staged,parent:this.current,children:[]});this.nodes[this.current].children.push(id);this.current=id;return true;
 }
 undo(){
  if(this.pending){this.staged=this.nodes[this.current].value;return this.value;}
  const parent=this.nodes[this.current].parent;if(parent!==null)this.current=parent;
  this.staged=this.nodes[this.current].value;return this.value;
 }
 redo(id){
  if(this.pending)throw Error('Finish or undo the current preview edit before redo');
  const children=this.nodes[this.current].children;
  if(id===undefined)id=children.at(-1);
  if(id===undefined)return this.value;
  if(!children.includes(id))throw Error('Redo branch is not a child of the current preview');
  this.current=id;this.staged=this.nodes[id].value;return this.value;
 }
}

export class CcHistory extends PreviewHistory {
 constructor(initial=CC_DEFAULTS,capacity=128){super(initial,capacity,{checked,same});}
}
