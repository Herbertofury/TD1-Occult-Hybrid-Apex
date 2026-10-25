import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

/** Execute the serialized native-read prefixes, then reject corrupt continuations. */
public class CasGridPoolBytecodeFixtures {
    static void check(boolean value,String why){CasGridPoolPatch.check(value,why);}
    static int op(AVM2Instruction i){return CasGridPoolPatch.op(i);}
    static MethodBody body(ABC a,String type,String method){return CasGridPoolPatch.body(a,type,method);}
    static Map<Integer,CasStructuralRolesPatch.Rewrite> reads(ABC base,ABC a)throws Exception{
        var result=new HashMap<Integer,CasStructuralRolesPatch.Rewrite>();
        for(var r:CasGridPoolPatch.READS){var b=body(base,r.owner(),r.method());result.put(b.method_info,CasGridPoolPatch.prefix(a,b,r));}
        return result;
    }
    static Map<Integer,String> hashes(ABC a)throws Exception{
        var result=new HashMap<Integer,String>();
        for(String n:CasGridPoolPatch.owned()){var b=body(a,CasGridPoolPatch.REC,n);result.put(b.method_info,CasGridPoolPatch.hash(b.getCodeBytes()));}
        for(var r:CasGridPoolPatch.READS){var b=body(a,r.owner(),r.method());result.put(b.method_info,CasGridPoolPatch.hash(b.getCodeBytes()));}
        return result;
    }
    static Object pop(List<Object> values){check(!values.isEmpty(),"Prefix stack underflow");return values.remove(values.size()-1);}
    static void execute(ABC a,MethodBody b,CasStructuralRolesPatch.Rewrite plan,CasGridPoolPatch.Read r,
                        boolean recycling,boolean owned)throws Exception{
        var code=b.getCode().code;var addresses=CasStructuralRolesPatch.addresses(b);var stack=new ArrayList<Object>();
        Object self=new Object(),cell=new Object(),returned=new Object();int pc=0,ownsCalls=0,helperCalls=0;
        int nativeEntry=plan.boundaries.get(2);
        for(int steps=0;steps<40;steps++){
            if(pc==nativeEntry){check(!recycling||!owned,"Armed native read bypassed pool");check(stack.isEmpty(),"Native entry stack changed");check(ownsCalls==(recycling?1:0)&&helperCalls==0,"Unarmed read invokes helper");return;}
            var i=code.get(pc++);
            switch(op(i)){
                case 0xd0 -> stack.add(self);
                case 0xd1 -> stack.add(r.mode()==3?Integer.valueOf(17):cell);
                case 0x30 -> check(pop(stack)==self,"Native scope receiver differs");
                case 0xb2 -> {check(pop(stack)==self&&CasGridPoolPatch.name(a,i.operands[0]).equals("RecyclingGridLayout"),"Wrong pool class gate");stack.add(recycling);}
                case 0x12 -> {if(!CasStructuralRolesPatch.truth(pop(stack)))pc=CasStructuralRolesPatch.index(addresses,CasStructuralRolesPatch.target(i,0));}
                case 0x20 -> stack.add(null);
                case 0x24 -> stack.add(i.operands[0]);
                case 0x46 -> {
                    var args=new ArrayList<Object>();for(int n=0;n<i.operands[1];n++)args.add(0,pop(stack));
                    check(pop(stack)==self,"Read helper receiver differs");String name=CasGridPoolPatch.name(a,i.operands[0]);
                    if(name.equals("ApexGridPoolOwns")){check(args.isEmpty(),"Owns has arguments");ownsCalls++;stack.add(owned);}
                    else {
                        check(name.equals(r.helper())&&recycling&&owned,"Armed helper route differs");helperCalls++;
                        if(Math.abs(r.mode())==1)check(args.size()==2&&args.get(0)==null&&args.get(1).equals(r.mode()),"First/last direction differs");
                        else if(Math.abs(r.mode())==2)check(args.size()==2&&args.get(0)==cell&&args.get(1).equals(r.mode()>0?1:-1),"Next/previous direction differs");
                        else if(r.mode()==3)check(args.equals(List.of(17)),"Mapping input index differs");
                        else check(args.isEmpty(),"Enumeration acquired arguments");
                        stack.add(returned);
                    }
                }
                case 0x80 -> check(i.operands[0]==a.method_info.get(b.method_info).ret_type,"Read coercion changed native result type");
                case 0x48 -> {check(pop(stack)==returned&&stack.isEmpty()&&helperCalls==1&&ownsCalls==1,"Read result/stack differs");return;}
                default -> throw new IllegalArgumentException("Unreviewed pool read gate opcode "+op(i));
            }
        }
        throw new IllegalArgumentException("Read prefix did not terminate");
    }
    public static void main(String[]args)throws Exception{
        var base=CasStructuralRolesPatch.load(args[0]);var valid=CasStructuralRolesPatch.load(args[1]);
        var plans=reads(base,valid);var expected=hashes(valid);CasGridPoolPatch.verify(base,valid,plans,expected);
        System.out.println("PASS complete-serialized-proof");
        for(var r:CasGridPoolPatch.READS){
            var b=body(valid,r.owner(),r.method());var plan=plans.get(b.method_info);
            for(boolean recycling:new boolean[]{false,true})for(boolean owned:new boolean[]{false,true})execute(valid,b,plan,r,recycling,owned);
            System.out.println("PASS read-route-"+r.method());
        }
        for(String mode:List.of("native-class-gate","pool-ownership-branch","helper-target","helper-direction","native-read-tail",
            "read-exception","park-body","coherence-body","helper-stack","helper-public-visibility","helper-private-visibility",
            "helper-trait-kind","native-constructor","native-cinit","native-other-method","native-signature","new-field")){
            var a=CasStructuralRolesPatch.reparse(valid);MethodBody changed=null;
            if(mode.equals("native-class-gate")){changed=body(a,CasGridPoolPatch.GRID,"FirstCell");changed.getCode().code.get(3).definition=CasStructuralRolesPatch.ins(0x12,0).definition;}
            if(mode.equals("pool-ownership-branch")){changed=body(a,CasGridPoolPatch.GRID,"FirstCell");changed.getCode().code.get(7).definition=CasStructuralRolesPatch.ins(0x11,0).definition;}
            if(mode.equals("helper-target")){changed=body(a,CasGridPoolPatch.GRID,"FirstCell");for(var i:changed.getCode().code)if(op(i)==0x46&&CasGridPoolPatch.name(a,i.operands[0]).equals("ApexGridPoolNeighbor")){i.operands[0]=CasGridPoolPatch.method(a,CasGridPoolPatch.REC,"ApexGridPoolMap").name_index;break;}}
            if(mode.equals("helper-direction")){changed=body(a,CasGridPoolPatch.GRID,"FirstCell");for(var i:changed.getCode().code)if(op(i)==0x24){i.operands[0]=-1;break;}}
            if(mode.equals("native-read-tail")){changed=body(a,CasGridPoolPatch.GRID,"GetAllCells");var plan=plans.get(changed.method_info);changed.getCode().code.get(plan.boundaries.get(2)).definition=CasStructuralRolesPatch.ins(0x02).definition;changed.getCode().code.get(plan.boundaries.get(2)).operands=new int[0];}
            if(mode.equals("read-exception"))body(a,CasGridPoolPatch.GRID,"GetAllCells").exceptions=new ABCException[]{new ABCException()};
            if(mode.equals("park-body")){changed=body(a,CasGridPoolPatch.REC,"ApexGridPoolPark");changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("coherence-body")){changed=body(a,CasGridPoolPatch.REC,"ApexGridPoolCoherent");changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("helper-stack"))body(a,CasGridPoolPatch.REC,"ApexGridPoolSlot").max_stack++;
            if(mode.equals("helper-public-visibility")){var t=CasGridPoolPatch.method(a,CasGridPoolPatch.REC,"ApexGridPoolViews");t.name_index=CasGridPoolPatch.method(a,CasGridPoolPatch.REC,"ApexGridPoolCoherent").name_index;}
            if(mode.equals("helper-private-visibility")){var t=CasGridPoolPatch.method(a,CasGridPoolPatch.REC,"ApexGridPoolPark");t.name_index=a.constants.getPublicQnameId("ApexGridPoolPark",true);}
            if(mode.equals("helper-trait-kind"))CasGridPoolPatch.method(a,CasGridPoolPatch.REC,"ApexGridPoolMap").kindType=Trait.TRAIT_GETTER;
            if(mode.equals("native-constructor")){changed=a.findBody(a.instance_info.get(a.findClassByName(CasGridPoolPatch.REC)).iinit_index);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-cinit")){changed=a.findBody(a.class_info.get(a.findClassByName(CasGridPoolPatch.GRID)).cinit_index);changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-other-method")){changed=body(a,CasGridPoolPatch.GRID,"GetNumItems");changed.getCode().code.add(0,CasStructuralRolesPatch.ins(0x02));}
            if(mode.equals("native-signature"))a.method_info.get(body(a,CasGridPoolPatch.GRID,"FirstCell").method_info).flags^=1;
            if(mode.equals("new-field")){var traits=a.instance_info.get(a.findClassByName(CasGridPoolPatch.REC)).instance_traits.traits;var t=traits.stream().filter(x->x instanceof TraitSlotConst).findFirst().orElseThrow().clone();traits.add(t);}
            if(changed!=null){changed.setCode(changed.getCode());changed.setModified();}
            boolean refused=false;try{CasGridPoolPatch.verify(base,a,plans,expected);}catch(Exception expectedFailure){refused=true;}
            check(refused,"Corrupt pool continuation accepted: "+mode);System.out.println("PASS refuse-"+mode);
        }
    }
}
