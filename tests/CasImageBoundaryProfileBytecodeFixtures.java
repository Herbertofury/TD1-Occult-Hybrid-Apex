import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;

public class CasImageBoundaryProfileBytecodeFixtures {
 static MethodBody body(ABC a,String type,String n){return CasImageBoundaryProfilePatch.body(a,type,n);}
 static int op(com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction i){return i.definition.instructionCode;}
 static boolean truth(Object o){return o!=null&&(!(o instanceof Boolean)||((Boolean)o));}
 static String gate(ABC a,CasImageBoundaryProfilePatch.Wrapped w,Object receiver)throws Exception{
  var code=w.body().getCode().code;var addresses=CasStructuralRolesPatch.addresses(w.body());var stack=new ArrayList<Object>();int pc=0;
  while(pc<code.size()){
   if(pc==w.disabled().boundaries.get(2)){if(!stack.isEmpty())throw new IllegalArgumentException("Disabled gate leaked operand stack");return "disabled";}
   if(pc==w.enabled().boundaries.get(2)){if(!stack.isEmpty())throw new IllegalArgumentException("Enabled gate leaked operand stack");return "enabled";}
   var i=code.get(pc++);int opcode=op(i);
   if(opcode==0xd0)stack.add(receiver);
   else if(opcode==0x30||opcode==0x29)stack.remove(stack.size()-1);
   else if(opcode==0x2a)stack.add(stack.get(stack.size()-1));
   else if(opcode==0x2b){int n=stack.size();var x=stack.get(n-1);stack.set(n-1,stack.get(n-2));stack.set(n-2,x);}
   else if(opcode==0x2c)stack.add(a.constants.getString(i.operands[0]));
   else if(opcode==0x26)stack.add(true);
   else if(opcode==0x66){var obj=(Map<?,?>)stack.remove(stack.size()-1);stack.add(obj.get(CasStructuralRolesPatch.name(a,i.operands[0])));}
   else if(opcode==0xb4){var obj=(Map<?,?>)stack.remove(stack.size()-1);var key=stack.remove(stack.size()-1);stack.add(obj.containsKey(key));}
   else if(opcode==0x11||opcode==0x12){boolean value=truth(stack.remove(stack.size()-1));if(value==(opcode==0x11))pc=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));}
   else throw new IllegalArgumentException("Unexpected gate opcode "+opcode);
  }throw new IllegalArgumentException("Gate failed to enter retained native flow");
 }
 static Map<Integer,CasImageBoundaryProfilePatch.Wrapped> wraps(ABC base,ABC a)throws Exception{
  var result=new HashMap<Integer,CasImageBoundaryProfilePatch.Wrapped>();
  for(String[] t:new String[][]{{CasImageBoundaryProfilePatch.RESOURCE,"OnAddedToStage"},{CasImageBoundaryProfilePatch.LOADER,"OnContainerAddedToStage"},{CasImageBoundaryProfilePatch.LOADER,"LoadImage"}}){var b=body(base,t[0],t[1]);result.put(b.method_info,CasImageBoundaryProfilePatch.wrap(a,b,t[0],t[1]));}return result;
 }
 public static void main(String[]args)throws Exception{
  var base=CasStructuralRolesPatch.load(args[0]);var valid=CasStructuralRolesPatch.load(args[1]);var plans=wraps(base,valid);CasImageBoundaryProfilePatch.verify(base,valid,plans);System.out.println("PASS serialized-valid");
  var resource=plans.get(body(base,CasImageBoundaryProfilePatch.RESOURCE,"OnAddedToStage").method_info);
  var nil=new HashMap<String,Object>();nil.put("mLoader",null);if(!gate(valid,resource,nil).equals("disabled"))throw new IllegalArgumentException("Null Loader not retained");
  for(var loader:List.of(Map.of(),Map.of(CasImageBoundaryProfilePatch.ACTIVE,false,CasImageBoundaryProfilePatch.STAMP,true),Map.of(CasImageBoundaryProfilePatch.ACTIVE,true)))if(!gate(valid,resource,Map.of("mLoader",loader)).equals("disabled"))throw new IllegalArgumentException("Unsupported/disabled Loader changed native path");
  if(!gate(valid,resource,Map.of("mLoader",Map.of(CasImageBoundaryProfilePatch.ACTIVE,true,CasImageBoundaryProfilePatch.STAMP,true))).equals("enabled"))throw new IllegalArgumentException("Enabled actual Loader not profiled");
  for(String n:new String[]{"LoadImage","OnContainerAddedToStage"}){var plan=plans.get(body(base,CasImageBoundaryProfilePatch.LOADER,n).method_info);if(!gate(valid,plan,Map.of(CasImageBoundaryProfilePatch.ACTIVE,false)).equals("disabled")||!gate(valid,plan,Map.of(CasImageBoundaryProfilePatch.ACTIVE,true)).equals("enabled"))throw new IllegalArgumentException("Loader native gate differs");}
  System.out.println("PASS actual-loader-gate-paths");
  for(String mode:List.of("disabled-native-call","enabled-native-call","gate-branch","marker-phase","marker-arguments","marker-target","active-getter","budget-bound","fault-field","field-privacy","mode-oracle","native-constructor","native-initialize","native-cinit","native-exception")){
   var a=CasStructuralRolesPatch.reparse(valid);MethodBody changed=null;
   if(mode.equals("disabled-native-call")||mode.equals("enabled-native-call")){
    var plan=plans.get(body(base,CasImageBoundaryProfilePatch.RESOURCE,"OnAddedToStage").method_info);var origins=mode.startsWith("disabled")?plan.disabled().origins:plan.enabled().origins;changed=a.findBody(plan.body().method_info);
    for(int j=0;j<origins.size();j++)if(origins.get(j)>=0&&op(changed.getCode().code.get(j))==0x46&&"getRect".equals(CasStructuralRolesPatch.name(a,changed.getCode().code.get(j).operands[0]))){changed.getCode().code.get(j).operands[0]=a.constants.getPublicQnameId("getBounds",true);break;}
   }
   if(mode.equals("gate-branch")){changed=body(a,CasImageBoundaryProfilePatch.LOADER,"LoadImage");changed.getCode().code.get(4).definition=CasStructuralRolesPatch.ins(0x12,0).definition;}
   if(mode.equals("marker-phase")||mode.equals("marker-arguments")){
    changed=body(a,CasImageBoundaryProfilePatch.LOADER,"LoadImage");var code=changed.getCode().code;
    for(int j=0;j<code.size();j++)if(op(code.get(j))==0x4f&&CasImageBoundaryProfilePatch.STAMP.equals(CasStructuralRolesPatch.name(a,code.get(j).operands[0]))){if(mode.equals("marker-phase"))code.get(j-2).operands[0]=99;else code.get(j).operands[1]=1;break;}
   }
   if(mode.equals("marker-target")){changed=body(a,CasImageBoundaryProfilePatch.RESOURCE,"OnAddedToStage");for(var i:changed.getCode().code)if(op(i)==0x66&&"mLoader".equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=a.constants.getPublicQnameId("mLoader",true);break;}}
   if(mode.equals("active-getter")){changed=body(a,CasImageBoundaryProfilePatch.LOADER,CasImageBoundaryProfilePatch.ACTIVE);changed.getCode().code.get(2).definition=CasStructuralRolesPatch.ins(0x26).definition;changed.getCode().code.get(2).operands=new int[0];}
   if(mode.equals("budget-bound")){changed=body(a,CasImageBoundaryProfilePatch.LOADER,"ApexImageTraceEnable");for(var i:changed.getCode().code)if(i.operands!=null&&i.operands.length==1&&i.operands[0]==4096){i.operands[0]=4097;break;}}
   if(mode.equals("fault-field")){changed=body(a,CasImageBoundaryProfilePatch.LOADER,CasImageBoundaryProfilePatch.STAMP);var code=changed.getCode().code;code.get(code.size()-2).operands[0]=CasImageBoundaryProfilePatch.field(a,CasImageBoundaryProfilePatch.LOADER,"apexImageTraceRequested",true);}
   if(mode.equals("field-privacy")){for(var t:a.class_info.get(a.findClassByName(CasImageBoundaryProfilePatch.LOADER)).static_traits.traits)if("apexImageTraceState".equals(CasStructuralRolesPatch.name(a,t.name_index))){t.name_index=a.constants.getPublicQnameId("apexImageTraceState",true);break;}}
   if(mode.equals("mode-oracle")){changed=body(a,CasImageBoundaryProfilePatch.BUTTON,"ApexCommButtonIndexStats");for(var i:changed.getCode().code)if(op(i)==0x66&&"UsingMouseKeyboard".equals(CasStructuralRolesPatch.name(a,i.operands[0]))){i.operands[0]=a.constants.getPublicQnameId("UsingController",true);break;}}
   if(mode.equals("native-constructor")){changed=a.findBody(a.instance_info.get(a.findClassByName(CasImageBoundaryProfilePatch.LOADER)).iinit_index);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
   if(mode.equals("native-initialize")){changed=body(a,CasImageBoundaryProfilePatch.LOADER,"Initialize");changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
   if(mode.equals("native-cinit")){changed=a.findBody(a.class_info.get(a.findClassByName(CasImageBoundaryProfilePatch.LOADER)).cinit_index);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
   if(mode.equals("native-exception"))body(a,CasImageBoundaryProfilePatch.LOADER,"LoadImage").exceptions=new ABCException[]{new ABCException()};
   if(changed!=null){changed.setCode(changed.getCode());changed.setModified();}boolean refused=false;try{CasImageBoundaryProfilePatch.verify(base,a,plans);}catch(Exception expected){refused=true;}
   if(!refused)throw new IllegalArgumentException("Corruption accepted: "+mode);System.out.println("PASS "+mode);
  }
 }
}
