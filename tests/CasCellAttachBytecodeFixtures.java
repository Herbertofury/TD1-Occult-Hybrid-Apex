import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;

public class CasCellAttachBytecodeFixtures {
 static void check(boolean b,String s){CasStructuralRolesPatch.check(b,s);}
 public static void main(String[]args)throws Exception{
  var donor=CasStructuralRolesPatch.load(args[0]);var base=CasStructuralRolesPatch.load(args[1]);var valid=CasStructuralRolesPatch.load(args[2]);var plan=CasCellAttachPatch.rewrite(base);CasCellAttachPatch.verify(donor,base,valid,plan);System.out.println("PASS serialized-valid");
  int start=CasCellAttachPatch.deadWrite(base);check(CasCellAttachPatch.body(base).getCode().code.size()-CasCellAttachPatch.body(valid).getCode().code.size()==5,"Exactly five instructions must be removed");
  // Execute the actual unchanged native scale-write region for arbitrary user
  // scales, proving retained final X/Y values rather than comparing text only.
  for(double value:new double[]{0.01,0.2,0.4813084112149533,0.5,1,1.6,3.25}){
   var original=run(base,start,start+13,value);var changed=run(valid,start,start+8,value);check(Arrays.equals(original,changed)&&original[0]==value&&original[1]==value,"Final arbitrary scale differs");
  }System.out.println("PASS arbitrary-final-xy-execution");
  for(String mode:List.of("final-scale-x","final-scale-y","final-authority-slot","right-click","favorite-listener","other-native-draw","constructor","trait","pool","exception","baseline-halfvalue","baseline-intervening-call","branch-into-removed")){
   var a=CasStructuralRolesPatch.reparse(valid);var before=CasStructuralRolesPatch.reparse(base);MethodBody b=null;
   if(mode.equals("final-scale-x")||mode.equals("final-scale-y")||mode.equals("final-authority-slot")){
    b=CasCellAttachPatch.body(a);var code=b.getCode().code;if(mode.equals("final-scale-x"))code.get(start+3).operands[0]=a.constants.getPublicQnameId("alpha",true);
    else if(mode.equals("final-scale-y"))code.get(start+7).operands[0]=a.constants.getPublicQnameId("scaleX",true);else code.get(start+2).operands[0]=a.constants.getPublicQnameId("otherScale",true);
   }
   if(mode.equals("right-click")||mode.equals("favorite-listener")){
    b=CasCellAttachPatch.body(a);for(var i:b.getCode().code)if(i.operands!=null&&i.operands.length>0&&((mode.equals("right-click")&&i.definition.instructionCode==0x61&&"RightMouseButtonEnabled".equals(CasStructuralRolesPatch.name(a,i.operands[0])))||(mode.equals("favorite-listener")&&i.definition.instructionCode==0x66&&"HandleDCCFavoriteItemClick".equals(CasStructuralRolesPatch.name(a,i.operands[0]))))){i.operands[0]=a.constants.getPublicQnameId("wrongMember",true);break;}
   }
   if(mode.equals("other-native-draw"))b=CasStructuralRolesPatch.body(a,CasCellAttachPatch.CELL,"Draw",false);
   if(mode.equals("constructor"))b=a.findBody(a.instance_info.get(a.findClassByName(CasCellAttachPatch.CELL)).iinit_index);
   if(mode.equals("other-native-draw")||mode.equals("constructor"))b.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));
   if(mode.equals("trait"))a.instance_info.get(a.findClassByName(CasCellAttachPatch.CELL)).instance_traits.traits.get(0).kindFlags^=1;
   if(mode.equals("pool"))a.constants.getStringId("unexpected append",true);
   if(mode.equals("exception"))CasCellAttachPatch.body(a).exceptions=new ABCException[]{new ABCException()};
   if(b!=null){b.setCode(b.getCode());b.setModified();}
   boolean refused=false;
   if(mode.startsWith("baseline-")||mode.equals("branch-into-removed")){
    var original=CasCellAttachPatch.body(before);var code=original.getCode().code;
    if(mode.equals("baseline-halfvalue"))code.get(start+2).operands[0]=3;
    if(mode.equals("baseline-intervening-call"))code.set(start+5,CasStructuralRolesPatch.ins(0x4f,before.constants.getPublicQnameId("foreignCallback",true),0));
    if(mode.equals("branch-into-removed")){var branch=CasStructuralRolesPatch.ins(0x10,0);code.add(start-1,branch);CasStructuralRolesPatch.set(original,new ArrayList<>(code));var target=code.get(start+2);branch.operands[0]=(int)(target.getAddress()-branch.getAddress()-branch.getBytesLength());}
    original.setCode(original.getCode());original.setModified();try{CasCellAttachPatch.rewrite(before);}catch(Exception expected){refused=true;}
   }else try{CasCellAttachPatch.verify(donor,base,a,plan);}catch(Exception expected){refused=true;}
   check(refused,"Corruption accepted: "+mode);System.out.println("PASS "+mode);
  }
 }
 static double[] run(ABC a,int from,int to,double value){
  var stack=new ArrayList<Object>();var cell=new HashMap<String,Double>();var owner=Map.of("modded_thumbnail_scale",value);var code=CasCellAttachPatch.body(a).getCode().code;
  for(int k=from;k<to;k++){var i=code.get(k);int op=i.definition.instructionCode;
   if(op==0xd0)stack.add(cell);else if(op==0x24)stack.add((double)i.operands[0]);else if(op==0xa3){double right=(Double)stack.remove(stack.size()-1),left=(Double)stack.remove(stack.size()-1);stack.add(left/right);}
   else if(op==0x60){check("CASCustomizerMain".equals(CasStructuralRolesPatch.name(a,i.operands[0])),"Unexpected scale owner");stack.add(owner);}
   else if(op==0x66){var object=(Map<?,?>)stack.remove(stack.size()-1);stack.add(object.get(CasStructuralRolesPatch.name(a,i.operands[0])));}
   else if(op==0x61){double v=(Double)stack.remove(stack.size()-1);var object=(Map<String,Double>)stack.remove(stack.size()-1);object.put(CasStructuralRolesPatch.name(a,i.operands[0]),v);}
   else throw new IllegalArgumentException("Unexpected scale instruction "+op);
  }check(stack.isEmpty(),"Scale stack differs");return new double[]{cell.get("scaleX"),cell.get("scaleY")};
 }
}
