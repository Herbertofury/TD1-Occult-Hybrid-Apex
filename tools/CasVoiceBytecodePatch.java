// Prevent a programmatic voice range refresh from emitting a snapped edit.
// Reads build inputs only. Native interaction handlers remain byte-identical.
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasVoiceBytecodePatch {
    static final String TARGET="widgets.CAS.AgeGender.AgeGenderPane";
    static final String METHOD="RefreshVoicePitchRange";
    static final String PIN="d0f81a01e1ef4039dc8fb4b5d39dac680ea45e512a8102e243e59a99d3362764";
    static String sha(byte[] bytes)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    static void require(boolean value,String message){CasBytecodePatch.require(value,message);}
    static MethodBody body(ABC abc,String type,String name){
        int index=abc.findClassByName(type);require(index>=0,"Voice widget/slider class absent.");
        return CasBytecodePatch.ownedBody(abc,abc.instance_info.get(index),name);
    }
    static int refreshCall(ABC abc,MethodBody body,int argc){
        int found=-1;var code=body.getCode().code;
        for(int i=0;i<code.size();i++) if(CasBytecodePatch.property(abc,code.get(i),0x4f,"SetCurrentValue")){
            require(found<0 && code.get(i).operands[1]==argc,"Voice refresh setter inventory/arguments changed.");found=i;
        }
        require(found>=0,"Voice refresh has no slider setter.");return found;
    }
    static void verifySlider(ABC library){
        MethodBody slider=body(library,"olympus.gui.sliders.Slider","SetCurrentValue");
        MethodInfo info=library.method_info.get(slider.method_info);
        require(info.param_types.length==4 && info.optional.length==3 && info.flagHas_optional(),
            "Slider requires the inspected four-argument value/smooth/absolute/notify contract.");
        require(library.constants.getString(library.constants.getMultiname(info.param_types[0]).name_index).equals("Number"),
            "Slider value type differs.");
        for(int i=1;i<4;i++) require(library.constants.getString(library.constants.getMultiname(info.param_types[i]).name_index).equals("Boolean") &&
            info.optional[i-1].value_kind==ValueKind.CONSTANT_True,"Slider notification option differs.");
        require(CasBytecodePatch.propertyCalls(library,slider).contains("dispatchEvent"),"Slider event path missing.");
    }
    static byte[] patch(ABC abc)throws Exception{
        var target=body(abc,TARGET,METHOD);require(target.exceptions.length==0,"Voice refresh exception layout changed.");
        int at=refreshCall(abc,target,1);var code=target.getCode();code.markOffsets();
        long offset=code.code.get(at).getAddress();byte[] before=target.getCodeBytes().clone();
        for(var op:code.code)for(long to:op.getOffsets())
            require(!(op.getAddress()<offset && to>offset) && !(to<offset && op.getAddress()>offset),
                "Voice refresh crosses the insertion with an unreviewed branch.");
        byte[] call=code.code.get(at).getBytes();require(call[call.length-1]==1,"Voice setter argc encoding differs.");
        byte[] replacement=call.clone();replacement[replacement.length-1]=4;
        ByteArrayOutputStream expected=new ByteArrayOutputStream();expected.write(before,0,(int)offset);
        expected.write(new byte[]{0x26,0x26,0x27});expected.write(replacement);
        expected.write(before,(int)offset+call.length,before.length-(int)offset-call.length);
        code.code.get(at).operands[1]=4;
        target.insertAll(at,List.of(new AVM2Instruction(0,0x26,new int[0]),new AVM2Instruction(0,0x26,new int[0]),new AVM2Instruction(0,0x27,new int[0])));
        target.max_stack=Math.max(target.max_stack,5);target.setModified();
        require(Arrays.equals(target.getCodeBytes(),expected.toByteArray()),"Voice patch changed bytes outside its exact silent refresh call.");
        return before;
    }
    public static void main(String[] args)throws Exception{
        require(args.length==3,"Use original age/gender SWF, pinned UI library and output ABC.");
        require(sha(Files.readAllBytes(Path.of(args[0]))).equals(PIN),"Voice widget differs from inspected game version.");
        ABC library=CasBytecodePatch.load(args[1]);verifySlider(library);ABC abc=CasBytecodePatch.load(args[0]);
        Map<Integer,byte[]> originals=new HashMap<>();for(var b:abc.bodies)originals.put(b.method_info,b.getCodeBytes().clone());
        MethodBody target=body(abc,TARGET,METHOD);byte[] old=patch(abc);byte[] patched=target.getCodeBytes().clone();
        ByteArrayOutputStream stream=new ByteArrayOutputStream();abc.saveToStream(stream);
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(stream.toByteArray())),abc.getSwf(),null);
        require(saved.bodies.size()==originals.size(),"Voice patch changed native method inventory.");
        for(var b:saved.bodies)require(Arrays.equals(b.getCodeBytes(),b.method_info==target.method_info?patched:originals.get(b.method_info)),
            "Voice patch changed another native handler or failed serialized readback.");
        require(refreshCall(saved,body(saved,TARGET,METHOD),4)>=0,"Silent voice setter failed serialization.");
        Files.write(Path.of(args[2]),stream.toByteArray());
        System.out.println("{\"ok\":true,\"unrelated_native_methods_preserved\":true,\"user_voice_handler_preserved\":true,\"base_method_sha256\":\""+sha(old)+"\",\"patched_method_sha256\":\""+sha(patched)+"\"}");
    }
}
