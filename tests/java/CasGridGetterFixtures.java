// Synthetic ABC serialize/reparse mutations. No game, profile or UI access.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCOutputStream;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;

public class CasGridGetterFixtures {
    static int qname(ABC abc,String name,int kind,String namespace) {
        var value=new Multiname();value.kind=Multiname.QNAME;value.name_index=abc.constants.getStringId(name,true);
        value.namespace_index=abc.constants.getNamespaceId(kind,namespace,0,true);return abc.constants.getMultinameId(value,true);
    }
    static int qname(ABC abc,String name) {return qname(abc,name,Namespace.KIND_PACKAGE,"");}
    static int method(ABC abc,int[] params,int returns,byte[] code,int stack,int regs) {
        int id=abc.method_info.size();abc.method_info.add(new MethodInfo(params,returns,0,0,new ValueKind[0],new int[0]));
        var body=new MethodBody(abc,new Traits(),code,new ABCException[0]);body.method_info=id;body.max_stack=stack;body.max_regs=regs;
        body.init_scope_depth=5;body.max_scope_depth=6;abc.bodies.add(body);return id;
    }
    static byte[] resetCode(ABC abc,int field)throws Exception {
        String scope="olympus.layout:RecyclingGridLayout",base="olympus.layout:GridLayout";
        int prev=qname(abc,"mPrevRectangleUpdate",Namespace.KIND_PROTECTED,scope),y=qname(abc,"y");
        int setup=qname(abc,"SetupCells",Namespace.KIND_PROTECTED,scope),cells=qname(abc,"mCells",Namespace.KIND_PROTECTED,base);
        int length=qname(abc,"length"),position=qname(abc,"PositionCellsInternal",Namespace.KIND_PROTECTED,scope);
        int initialize=qname(abc,"InitializeCellData",Namespace.KIND_PROTECTED,scope),grid=qname(abc,"mGridView",Namespace.KIND_PROTECTED,base);
        int event=qname(abc,"GridEvent",Namespace.KIND_PACKAGE,"olympus.events"),resize=qname(abc,"RESIZE"),array=qname(abc,"Array"),dispatch=qname(abc,"dispatchEvent");
        var a=new ArrayList<com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction>();
        int[][] args={{},{},{},{field},{0},{},{},{prev},{0},{},{prev},{0},{y},{},{setup,0},{cells},{length},{0},{0},{},{},{position,1},{},{},{initialize,1},{grid},{event},{event},{resize},{},{array},{array,0},{event,3},{dispatch,1},{}};
        int[] codes={0xd0,0x30,0xd0,0x66,0x12,0x47,0xd0,0x66,0x12,0xd0,0x66,0x24,0x61,0xd0,0x4f,0x60,0x66,0x24,0x0e,0xd0,0x26,0x4f,0xd0,0x26,0x4f,0x60,0x5d,0x60,0x66,0x20,0x5d,0x4a,0x4a,0x4f,0x47};
        long at=0;for(int n=0;n<codes.length;n++){var op=CasGridBytecodePatch.op(codes[n],args[n]);op.setAddress(at);at+=op.getBytesLength();a.add(op);}
        for(int[] branch:new int[][]{{4,6},{8,13},{18,25}})a.get(branch[0]).operands[0]=(int)(a.get(branch[1]).getAddress()-a.get(branch[0]).getAddress()-a.get(branch[0]).getBytesLength());
        var bytes=new ByteArrayOutputStream();for(var op:a)bytes.write(op.getBytes());return bytes.toByteArray();
    }
    static ABC original()throws Exception {
        var abc=new ABC((com.jpexs.decompiler.flash.tags.ABCContainerTag)null);
        int bool=qname(abc,"Boolean"),nothing=qname(abc,"void");qname(abc,"String");
        var instance=new InstanceInfo(new Traits());
        instance.name_index=qname(abc,"RecyclingGridLayout",Namespace.KIND_PACKAGE,"olympus.layout");
        instance.super_index=qname(abc,"Object");instance.interfaces=new int[0];
        instance.iinit_index=method(abc,new int[0],nothing,new byte[]{(byte)0xd0,0x30,0x47},1,1);
        var type=new ClassInfo(new Traits());type.cinit_index=method(abc,new int[0],nothing,new byte[]{(byte)0xd0,0x30,0x47},1,1);
        int field=qname(abc,"mbSuppressUpdates",Namespace.KIND_PROTECTED,"olympus.layout:RecyclingGridLayout");
        var slot=new TraitSlotConst();slot.kindType=Trait.TRAIT_SLOT;slot.name_index=field;slot.type_index=bool;slot.slot_id=1;
        instance.instance_traits.traits.add(slot);
        var bytes=new ByteArrayOutputStream();bytes.write(new byte[]{(byte)0xd0,0x30,(byte)0xd0,(byte)0xd1,0x68});
        new ABCOutputStream(bytes).writeU30(field);bytes.write(0x47);
        var setter=new TraitMethodGetterSetter();setter.kindType=Trait.TRAIT_SETTER;setter.name_index=qname(abc,"SuppressUpdates");
        setter.method_info=method(abc,new int[]{bool},nothing,bytes.toByteArray(),2,2);instance.instance_traits.traits.add(setter);
        var reset=new TraitMethodGetterSetter();reset.kindType=Trait.TRAIT_METHOD;reset.name_index=qname(abc,"ResetAndPositionCells");
        reset.method_info=method(abc,new int[0],nothing,resetCode(abc,field),5,1);instance.instance_traits.traits.add(reset);
        abc.instance_info.add(instance);abc.class_info.add(type);
        var script=new ScriptInfo(new Traits());script.init_index=method(abc,new int[0],nothing,new byte[]{(byte)0xd0,0x30,0x47},1,1);
        abc.script_info.add(script);return CasGridBytecodePatch.reparse(abc);
    }
    static void run(String mode)throws Exception {
        ABC original=original(),candidate=CasGridBytecodePatch.reparse(original);
        CasGridBytecodePatch.append(candidate);candidate=CasGridBytecodePatch.reparse(candidate);
        var getter=CasGridBytecodePatch.accessor(candidate,Trait.TRAIT_GETTER);var body=candidate.findBody(getter.method_info);
        var info=candidate.method_info.get(getter.method_info);
        var origin=CasGridBytecodePatch.method(candidate,CasGridBytecodePatch.ORIGIN);
        var originBody=candidate.findBody(origin.method_info);
        var profile=CasGridBytecodePatch.method(candidate,CasGridBytecodePatch.PROFILE);
        var profileBody=candidate.findBody(profile.method_info);
        switch(mode) {
            case "valid":break;
            case "write-in-getter": {
                byte[] bytes=body.getCodeBytes().clone();bytes[3]=0x68;body.setCodeBytes(bytes);break;
            }
            case "wrong-field":body.setCodeBytes(CasGridBytecodePatch.getterCode(qname(candidate,"mbOther",Namespace.KIND_PROTECTED,"olympus.layout:RecyclingGridLayout")));break;
            case "wrong-public-namespace":getter.name_index=qname(candidate,"SuppressUpdates",Namespace.KIND_PACKAGE_INTERNAL,"");break;
            case "wrong-scope":body.init_scope_depth++;body.max_scope_depth++;break;
            case "wrong-stack":body.max_stack++;break;
            case "wrong-return-type":info.ret_type=qname(candidate,"Object");break;
            case "unexpected-parameter":info.param_types=new int[]{info.ret_type};break;
            case "native-method-flag":info.flags=MethodInfo.FLAG_NATIVE;break;
            case "retained-setter":candidate.findBody(CasGridBytecodePatch.accessor(candidate,Trait.TRAIT_SETTER).method_info).setCodeBytes(new byte[]{0x47});break;
            case "retained-cinit":candidate.findBody(candidate.class_info.get(0).cinit_index).setCodeBytes(new byte[]{0x02,0x47});break;
            case "retained-slot":((TraitSlotConst)candidate.instance_info.get(0).instance_traits.traits.get(0)).slot_id++;break;
            case "retained-pool":candidate.constants.getStringId("Unreviewed constant",true);break;
            case "extra-method":method(candidate,new int[0],info.ret_type,new byte[]{0x26,0x48},1,1);break;
            case "duplicate-getter":candidate.instance_info.get(0).instance_traits.traits.add(getter.clone());break;
            case "body-order":Collections.swap(candidate.bodies,0,candidate.bodies.size()-1);candidate.resetMethodIndexing();break;
            case "origin-write":originBody.setCodeBytes(new byte[]{(byte)0xd0,0x30,(byte)0xd0,0x26,0x68,0x01,0x48});break;
            case "wrong-origin":originBody.setCodeBytes(CasGridBytecodePatch.originCode(candidate.constants.getStringId("62ECC59A:00000000:3FFE72432A703655",true)));break;
            case "origin-namespace":origin.name_index=qname(candidate,CasGridBytecodePatch.ORIGIN,Namespace.KIND_PACKAGE_INTERNAL,"");break;
            case "origin-signature":candidate.method_info.get(origin.method_info).ret_type=qname(candidate,"Object");break;
            case "origin-missing":candidate.instance_info.get(0).instance_traits.traits.remove(origin);break;
            case "pool-prefix":candidate.constants.setString(1,"changed native string");break;
            case "profile-return-type":candidate.method_info.get(profile.method_info).ret_type=qname(candidate,"Boolean");break;
            case "profile-scope":profileBody.init_scope_depth++;profileBody.max_scope_depth++;break;
            case "profile-flow": {
                byte[] code=profileBody.getCodeBytes().clone();code[6]++;profileBody.setCodeBytes(code);break;
            }
            case "profile-bind-argument": {
                var code=profileBody.getCode();
                for(int n=0;n<code.code.size();n++)if(code.code.get(n).definition.instructionCode==0x4f &&
                    CasGridBytecodePatch.name(candidate,code.code.get(n).operands[0]).equals("InitializeCellData"))
                    code.replaceInstruction(n-1,CasGridBytecodePatch.op(0x27),profileBody);
                profileBody.setCodeBytes(code.getBytes());
                break;
            }
            case "profile-report-key": {
                int key=candidate.constants.getStringId("bind_ms",false);candidate.constants.setString(key,"wrong_bind_ms");break;
            }
            case "profile-write":profileBody.setCodeBytes(new byte[]{(byte)0xd0,0x30,(byte)0xd0,0x26,0x68,0x01,0x48});break;
            case "retained-native-reset":candidate.findBody(CasGridBytecodePatch.method(candidate,"ResetAndPositionCells").method_info).setCodeBytes(new byte[]{0x47});break;
            case "already-patched": {
                boolean refused=false;try{CasGridBytecodePatch.append(candidate);}catch(IllegalArgumentException expected){refused=true;}
                CasGridBytecodePatch.require(refused,"A duplicate getter append was accepted.");System.out.println("PASS "+mode);return;
            }
            default:throw new IllegalArgumentException("Unknown fixture "+mode);
        }
        candidate=CasGridBytecodePatch.reparse(candidate);
        boolean refused=false;try{CasGridBytecodePatch.verify(original,candidate);}catch(IllegalArgumentException expected){refused=true;}
        CasGridBytecodePatch.require(refused!=mode.equals("valid"),"Getter mutation was accepted, or a valid serialized getter was refused: "+mode);
        System.out.println("PASS "+mode);
    }
    public static void main(String[] args)throws Exception {
        for(String mode:List.of("valid","write-in-getter","wrong-field","wrong-public-namespace","wrong-scope","wrong-stack",
            "wrong-return-type","unexpected-parameter","native-method-flag","retained-setter","retained-cinit","retained-slot",
            "retained-pool","extra-method","duplicate-getter","body-order","origin-write","wrong-origin","origin-namespace",
            "origin-signature","origin-missing","pool-prefix","profile-return-type","profile-scope","profile-flow",
            "profile-bind-argument","profile-report-key","profile-write","retained-native-reset","already-patched"))run(mode);
    }
}
