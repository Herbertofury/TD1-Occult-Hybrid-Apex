// Append suppression/origin reads and an explicit aggregate Reset profiler.
// No native method, class initializer, trait, constant or script is recompiled.
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.ABCOutputStream;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasGridBytecodePatch {
    static final String TARGET="olympus.layout.RecyclingGridLayout";
    static final String PROPERTY="SuppressUpdates";
    static final String ORIGIN="ApexGridProviderIdentity";
    static final String PROFILE="ApexProfileResetAndPositionCells";
    static final String DONOR_TGI="62ECC59A:00000000:89D13757C58C2E05";
    record Provider(String tgi,int methods) {}
    static final Map<String,Provider> PINS=Map.of(
        "6ddb983fee2bd284a2b7efec155e1544bfe99d27f16d4d28097bada25e1864f0",new Provider(DONOR_TGI,8479),
        "5f475a80a4f9c77f9a0439e133221a31f766cb929318f74191b4b9bad98e8cae",new Provider("62ECC59A:00000000:12272E1AC0C1F8E2",9194));
    static void require(boolean value,String message) { if(!value)throw new IllegalArgumentException(message); }
    static String sha(byte[] data)throws Exception {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));}
    static byte[] serialize(ABC abc)throws IOException {var out=new ByteArrayOutputStream();abc.saveToStream(out);return out.toByteArray();}
    static ABC reparse(ABC abc)throws IOException {
        return new ABC(new ABCInputStream(new MemoryInputStream(serialize(abc))),abc.parentTag==null?null:abc.getSwf(),abc.parentTag);
    }
    static ABC load(String path)throws Exception {
        var swf=new SWF(new FileInputStream(path),false);
        require(swf.getAbcList().size()==1,"Grid provider must contain exactly one native ABC.");
        return swf.getAbcList().get(0).getABC();
    }
    static String name(ABC abc,int multiname) {return abc.constants.getString(abc.constants.getMultiname(multiname).name_index);}
    static TraitMethodGetterSetter accessor(ABC abc,int kind) {
        int target=abc.findClassByName(TARGET);require(target>=0,"Native recycling grid is absent.");
        TraitMethodGetterSetter result=null;
        for(var trait:abc.instance_info.get(target).instance_traits.traits)
            if(name(abc,trait.name_index).equals(PROPERTY) && trait.kindType==kind) {
                require(result==null && trait instanceof TraitMethodGetterSetter,"Ambiguous grid accessor.");
                result=(TraitMethodGetterSetter)trait;
            }
        return result;
    }
    static int setterField(ABC abc) {
        var setter=accessor(abc,Trait.TRAIT_SETTER);require(setter!=null,"Native grid setter is absent.");
        var publicName=abc.constants.getMultiname(setter.name_index);
        require(publicName.kind==Multiname.QNAME && setter.kindFlags==0 && setter.disp_id==0,
            "Native grid setter trait differs from its public auto-dispatch contract.");
        var namespace=abc.constants.getNamespace(publicName.namespace_index);
        require(namespace.kind==Namespace.KIND_PACKAGE && abc.constants.getString(namespace.name_index).isEmpty(),
            "Native grid setter is not public.");
        var info=abc.method_info.get(setter.method_info);var body=abc.findBody(setter.method_info);
        require(info.param_types.length==1 && name(abc,info.param_types[0]).equals("Boolean") &&
            name(abc,info.ret_type).equals("void") && body!=null && body.exceptions.length==0 && body.traits.traits.isEmpty(),
            "Native grid setter signature or exception contract differs.");
        var ops=body.getCode().code;
        require(ops.size()==6 && ops.get(0).definition.instructionCode==0xd0 && ops.get(1).definition.instructionCode==0x30 &&
            ops.get(2).definition.instructionCode==0xd0 && ops.get(3).definition.instructionCode==0xd1 &&
            ops.get(4).definition.instructionCode==0x68 && ops.get(5).definition.instructionCode==0x47 &&
            body.max_stack==2 && body.max_regs==2 && body.max_scope_depth==body.init_scope_depth+1,
            "Native grid setter is not the inspected single-field write.");
        int field=ops.get(4).operands[0];var fieldName=abc.constants.getMultiname(field);
        require(name(abc,field).equals("mbSuppressUpdates") && fieldName.kind==Multiname.QNAME &&
            abc.constants.getNamespace(fieldName.namespace_index).kind==Namespace.KIND_PROTECTED,
            "Native grid setter no longer targets its protected suppression field.");
        boolean slot=false;
        for(var trait:abc.instance_info.get(abc.findClassByName(TARGET)).instance_traits.traits)
            if(trait.name_index==field && trait instanceof TraitSlotConst)
                slot=name(abc,((TraitSlotConst)trait).type_index).equals("Boolean");
        require(slot,"Native suppression field is not the setter's exact Boolean slot.");
        return field;
    }
    static byte[] getterCode(int field) throws IOException {
        var bytes=new ByteArrayOutputStream();bytes.write(new byte[]{(byte)0xd0,0x30,(byte)0xd0,0x66});
        new ABCOutputStream(bytes).writeU30(field);bytes.write(0x48);return bytes.toByteArray();
    }
    static byte[] originCode(int identity) throws IOException {
        var bytes=new ByteArrayOutputStream();bytes.write(new byte[]{(byte)0xd0,0x30,0x2c});
        new ABCOutputStream(bytes).writeU30(identity);bytes.write(0x48);return bytes.toByteArray();
    }
    static TraitMethodGetterSetter method(ABC abc,String name) {
        TraitMethodGetterSetter result=null;
        for(var trait:abc.instance_info.get(abc.findClassByName(TARGET)).instance_traits.traits)
            if(name(abc,trait.name_index).equals(name) && trait.kindType==Trait.TRAIT_METHOD) {
                require(result==null && trait instanceof TraitMethodGetterSetter,"Ambiguous grid method: "+name);
                result=(TraitMethodGetterSetter)trait;
            }
        return result;
    }
    static MethodBody resetBody(ABC abc) {
        var reset=method(abc,"ResetAndPositionCells");require(reset!=null,"Native Reset is absent.");
        var body=abc.findBody(reset.method_info);var info=abc.method_info.get(reset.method_info);
        require(info.param_types.length==0 && name(abc,info.ret_type).equals("void") && info.flags==0 &&
            body!=null && body.max_stack==5 && body.max_regs==1 && body.init_scope_depth==5 && body.max_scope_depth==6 &&
            body.exceptions.length==0 && body.traits.traits.isEmpty(),"Native Reset header differs.");
        var ops=body.getCode().code;
        int[] shape={0xd0,0x30,0xd0,0x66,0x12,0x47,0xd0,0x66,0x12,0xd0,0x66,0x24,0x61,0xd0,0x4f,
            0x60,0x66,0x24,0x0e,0xd0,0x26,0x4f,0xd0,0x26,0x4f,0x60,0x5d,0x60,0x66,0x20,0x5d,0x4a,0x4a,0x4f,0x47};
        require(ops.size()==shape.length,"Native Reset instruction inventory differs.");
        for(int n=0;n<shape.length;n++)require(ops.get(n).definition.instructionCode==shape[n],"Native Reset flow differs.");
        require(ops.get(4).getTargetAddress()==ops.get(6).getAddress() && ops.get(8).getTargetAddress()==ops.get(13).getAddress() &&
            ops.get(18).getTargetAddress()==ops.get(25).getAddress(),"Native Reset branch targets differ.");
        int[] at={3,7,10,12,14,15,16,21,24,25,26,27,28,30,31,32,33};
        String[] names={"mbSuppressUpdates","mPrevRectangleUpdate","mPrevRectangleUpdate","y","SetupCells","mCells","length",
            "PositionCellsInternal","InitializeCellData","mGridView","GridEvent","GridEvent","RESIZE","Array","Array","GridEvent","dispatchEvent"};
        for(int n=0;n<at.length;n++)require(name(abc,ops.get(at[n]).operands[0]).equals(names[n]),"Native Reset property/call differs.");
        require(ops.get(3).operands[0]==setterField(abc) && ops.get(7).operands[0]==ops.get(10).operands[0] &&
            ops.get(11).operands[0]==0 && ops.get(17).operands[0]==0 && ops.get(14).operands[1]==0 &&
            ops.get(21).operands[1]==1 && ops.get(24).operands[1]==1 && ops.get(31).operands[1]==0 &&
            ops.get(32).operands[1]==3 && ops.get(33).operands[1]==1,"Native Reset arguments differ.");
        return body;
    }
    static AVM2Instruction op(int code,int... operands) {return new AVM2Instruction(0,code,operands);}
    static void local(List<AVM2Instruction> out,int register) {out.add(op(0x62,register));}
    static void timer(List<AVM2Instruction> out,int getTimer) {out.add(op(0x5d,getTimer));out.add(op(0x46,getTimer,0));}
    static void start(List<AVM2Instruction> out,int getTimer,int register) {timer(out,getTimer);out.add(op(0x63,register));}
    static void elapsed(List<AVM2Instruction> out,int getTimer,int destination) {
        timer(out,getTimer);local(out,3);out.add(op(0xa1));out.add(op(0x73));out.add(op(0x63,destination));
    }
    static void count(List<AVM2Instruction> out,int cells,int length) {out.add(op(0x60,cells));out.add(op(0x66,length));out.add(op(0x73));}
    static void report(List<AVM2Instruction> out,ABC abc,boolean suppressed,int getTimer,int cells,int length) {
        String[] keys={"suppressed","before_count","after_count","setup_ms","position_ms","bind_ms","resize_ms","total_ms"};
        for(int n=0;n<keys.length;n++) {
            out.add(op(0x2c,abc.constants.getStringId(keys[n],true)));
            if(n==0)out.add(op(suppressed?0x26:0x27));
            else if(suppressed)out.add(op(0x24,n<=2?-1:0));
            else if(n==1)local(out,2);
            else if(n==2)count(out,cells,length);
            else if(n<7)local(out,n+1);
            else {timer(out,getTimer);local(out,1);out.add(op(0xa1));out.add(op(0x73));}
        }
        out.add(op(0x55,keys.length));out.add(op(0x48));
    }
    static byte[] profileCode(ABC abc)throws Exception {
        var nativeBody=resetBody(abc);var nativeOps=nativeBody.getCode().code;
        int getTimer=abc.constants.getQnameId("getTimer",Namespace.KIND_PACKAGE,"flash.utils",true);
        int cells=nativeOps.get(15).operands[0],length=nativeOps.get(16).operands[0];
        var out=new ArrayList<AVM2Instruction>();var positions=new HashMap<Long,Integer>();
        var branches=new ArrayList<AVM2Instruction>();var destinations=new ArrayList<Long>();
        for(int n=0;n<nativeOps.size();n++) {
            var original=nativeOps.get(n);positions.put(original.getAddress(),out.size());
            if(n==6) { // Only after the original suppression guard.
                start(out,getTimer,1);count(out,cells,length);out.add(op(0x63,2));
                for(int r=4;r<=7;r++) {out.add(op(0x24,0));out.add(op(0x63,r));}
            }
            if(n==13 || n==19 || n==22 || n==25)start(out,getTimer,3);
            if(n==5 || n==34)report(out,abc,n==5,getTimer,cells,length);
            else {
                var copy=original.clone();out.add(copy);
                if(n==4 || n==8 || n==18) {branches.add(copy);destinations.add(original.getTargetAddress());}
            }
            if(n==14)elapsed(out,getTimer,4);
            if(n==21)elapsed(out,getTimer,5);
            if(n==24)elapsed(out,getTimer,6);
            if(n==33)elapsed(out,getTimer,7);
        }
        long address=0;
        for(var instruction:out) {instruction.setAddress(address);address+=instruction.getBytesLength();}
        for(int n=0;n<branches.size();n++) {
            var branch=branches.get(n);var target=out.get(positions.get(destinations.get(n)));
            branch.operands[0]=(int)(target.getAddress()-branch.getAddress()-branch.getBytesLength());
        }
        var bytes=new ByteArrayOutputStream();for(var instruction:out)bytes.write(instruction.getBytes());return bytes.toByteArray();
    }
    static void appendProfile(ABC abc)throws Exception {
        require(method(abc,PROFILE)==null,"Grid Reset profiler already exists.");
        var nativeBody=resetBody(abc);var nativeReset=method(abc,"ResetAndPositionCells");
        var profile=nativeReset.clone();profile.kindFlags=0;profile.disp_id=0;profile.method_info=abc.method_info.size();
        var name=new Multiname();name.kind=Multiname.QNAME;
        name.namespace_index=abc.constants.getMultiname(accessor(abc,Trait.TRAIT_SETTER).name_index).namespace_index;
        name.name_index=abc.constants.getStringId(PROFILE,true);profile.name_index=abc.constants.getMultinameId(name,true);
        int objectType=abc.constants.getPublicQnameId("Object",false);require(objectType>0,"Native Object type is absent.");
        byte[] code=profileCode(abc);
        abc.method_info.add(new MethodInfo(new int[0],objectType,name.name_index,0,new ValueKind[0],new int[0]));
        var body=new MethodBody(abc,new Traits(),code,new ABCException[0]);body.method_info=profile.method_info;
        body.max_stack=18;body.max_regs=8;body.init_scope_depth=nativeBody.init_scope_depth;body.max_scope_depth=nativeBody.max_scope_depth;
        abc.bodies.add(body);abc.instance_info.get(abc.findClassByName(TARGET)).instance_traits.traits.add(profile);
    }
    static void append(ABC abc)throws Exception {append(abc,DONOR_TGI);}
    static void append(ABC abc,String provider)throws Exception {
        int field=setterField(abc);require(accessor(abc,Trait.TRAIT_GETTER)==null,"Grid getter is already present.");
        var setter=accessor(abc,Trait.TRAIT_SETTER);var setterInfo=abc.method_info.get(setter.method_info);
        var setterBody=abc.findBody(setter.method_info);
        var getter=setter.clone();getter.kindType=Trait.TRAIT_GETTER;getter.method_info=abc.method_info.size();
        var info=new MethodInfo(new int[0],setterInfo.param_types[0],setterInfo.name_index,0,new ValueKind[0],new int[0]);
        var body=new MethodBody(abc,new Traits(),getterCode(field),new ABCException[0]);
        body.method_info=getter.method_info;body.max_stack=1;body.max_regs=1;
        body.init_scope_depth=setterBody.init_scope_depth;body.max_scope_depth=setterBody.max_scope_depth;
        abc.method_info.add(info);abc.bodies.add(body);
        var traits=abc.instance_info.get(abc.findClassByName(TARGET)).instance_traits.traits;
        traits.add(getter);
        for(var trait:traits)require(!name(abc,trait.name_index).equals(ORIGIN),"Grid provider identity already exists.");
        // Append pool entries only. Reuse the native public namespace and String
        // type, and retain every existing pool index used by native methods.
        int stringType=abc.constants.getPublicQnameId("String",false);
        require(stringType>0,"Native String return type is absent.");
        var originName=new Multiname();originName.kind=Multiname.QNAME;
        originName.namespace_index=abc.constants.getMultiname(setter.name_index).namespace_index;
        originName.name_index=abc.constants.getStringId(ORIGIN,true);
        var origin=new TraitMethodGetterSetter();origin.kindType=Trait.TRAIT_METHOD;
        origin.name_index=abc.constants.getMultinameId(originName,true);origin.method_info=abc.method_info.size();
        int identity=abc.constants.getStringId(provider,true);
        var originInfo=new MethodInfo(new int[0],stringType,originName.name_index,0,new ValueKind[0],new int[0]);
        var originBody=new MethodBody(abc,new Traits(),originCode(identity),new ABCException[0]);
        originBody.method_info=origin.method_info;originBody.max_stack=1;originBody.max_regs=1;
        originBody.init_scope_depth=setterBody.init_scope_depth;originBody.max_scope_depth=setterBody.max_scope_depth;
        abc.method_info.add(originInfo);abc.bodies.add(originBody);traits.add(origin);
        appendProfile(abc);
        abc.resetMethodIndexing();
    }
    static void verify(ABC original,ABC candidate)throws Exception {verify(original,candidate,DONOR_TGI);}
    static void verify(ABC original,ABC candidate,String provider)throws Exception {
        int field=setterField(original);var setter=accessor(original,Trait.TRAIT_SETTER);
        require(accessor(original,Trait.TRAIT_GETTER)==null,"Native reference already has a grid getter.");
        int target=original.findClassByName(TARGET);require(candidate.findClassByName(TARGET)==target,"Native grid class moved.");
        var traits=candidate.instance_info.get(target).instance_traits.traits;
        int nativeTraits=original.instance_info.get(target).instance_traits.traits.size();
        require(candidate.method_info.size()==original.method_info.size()+3 && candidate.bodies.size()==original.bodies.size()+3 &&
            traits.size()==nativeTraits+3,"Grid patch must append exactly one getter, origin method and Reset profiler.");
        var getter=accessor(candidate,Trait.TRAIT_GETTER);
        require(getter!=null && traits.get(nativeTraits)==getter && getter.name_index==setter.name_index &&
            getter.kindFlags==setter.kindFlags && getter.disp_id==setter.disp_id && getter.method_info==original.method_info.size(),
            "Appended grid getter namespace, dispatch or method index differs from the native setter.");
        var expectedTrait=setter.clone();expectedTrait.kindType=Trait.TRAIT_GETTER;expectedTrait.method_info=getter.method_info;
        var expectedBytes=new ByteArrayOutputStream();var actualBytes=new ByteArrayOutputStream();
        new ABCOutputStream(expectedBytes).writeTrait(expectedTrait);new ABCOutputStream(actualBytes).writeTrait(getter);
        require(Arrays.equals(expectedBytes.toByteArray(),actualBytes.toByteArray()),"Grid getter acquired unreviewed trait metadata.");
        var info=candidate.method_info.get(getter.method_info);var setterInfo=original.method_info.get(setter.method_info);
        var body=candidate.findBody(getter.method_info);var setterBody=original.findBody(setter.method_info);
        require(info.param_types.length==0 && info.ret_type==setterInfo.param_types[0] && info.name_index==setterInfo.name_index &&
            info.flags==0 && info.optional.length==0 && info.paramNames.length==0,
            "Grid getter must be a parameterless Boolean read using the native setter's exact type.");
        require(body!=null && body==candidate.bodies.get(original.bodies.size()) && body.max_stack==1 && body.max_regs==1 &&
            body.init_scope_depth==setterBody.init_scope_depth && body.max_scope_depth==setterBody.max_scope_depth &&
            body.exceptions.length==0 && body.traits.traits.isEmpty() && Arrays.equals(body.getCodeBytes(),getterCode(field)),
            "Grid getter must only read the native protected field in the setter's exact lexical scope.");
        // Compare the complete deterministic append, including both method
        // signatures/bodies/scopes, Reset flow and appended pool entries.
        // Any native-prefix or unreviewed suffix change is refused.
        ABC expected=reparse(original);append(expected,provider);
        require(Arrays.equals(serialize(expected),serialize(candidate)),"Grid provider differs from the exact three-method append.");
        // Remove only the verified final appends and their pool suffix. Full
        // equality above proves that restoring the original pool removes only
        // entries appended by getStringId/getMultinameId, preserving its prefix.
        ABC retained=reparse(candidate);
        for(int n=0;n<3;n++) {
            retained.method_info.remove(original.method_info.size());retained.bodies.remove(original.bodies.size());
            retained.instance_info.get(target).instance_traits.traits.remove(nativeTraits);
        }
        retained.constants=original.constants.clone();
        require(Arrays.equals(serialize(original),serialize(retained)),"Grid adaptation changed retained native ABC bytes.");
    }
    public static void main(String[] args)throws Exception {
        require(args.length==2,"Use an authenticated grid-provider SWF and output ABC.");
        byte[] source=Files.readAllBytes(Path.of(args[0]));Provider provider=PINS.get(sha(source));
        require(provider!=null,"Grid provider differs from the two reviewed native resources.");
        ABC original=load(args[0]);require(original.method_info.size()==provider.methods(),"Grid provider method inventory differs.");
        ABC candidate=reparse(original);append(candidate,provider.tgi());candidate=reparse(candidate);verify(original,candidate,provider.tgi());
        byte[] patched=serialize(candidate);Files.write(Path.of(args[1]),patched);
        System.out.println("{\"ok\":true,\"native_method_count\":"+original.method_info.size()+
            ",\"unchanged_native_methods\":"+original.method_info.size()+",\"appended_native_getters\":1,"+
            "\"appended_provider_identity_methods\":1,\"provider_identity_verified\":true,\"provider_resource_tgi\":\""+provider.tgi()+"\","+
            "\"appended_reset_profile_methods\":1,\"reset_profile_native_flow_verified\":true,\"reset_profile_scope_verified\":true,\"reset_profile_report_verified\":true,"+
            "\"retained_native_abc_sha256\":\""+sha(serialize(original))+"\",\"getter_field_namespace_verified\":true,"+
            "\"getter_scope_verified\":true,\"getter_read_only_verified\":true,\"native_abc_retention_verified\":true}");
    }
}
