// Transplant two explicitly edited catalog handlers, preserving all others.
// Input SWFs and decompiled sources stay private; no process/game-file writes.
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasCatalogBytecodePatch {
    static final String PIN="2f09c674e42b87a09d21a7ef76c194967520c9ab93174d460df9f0c7b57ca52c";
    static final Map<String,Set<String>> TARGETS=Map.of(
        "widgets.CAS.controls.CASContextMenu",Set.of("UpdateMenu","HandleItemSelection"));
    static void require(boolean b,String s){CasBytecodePatch.require(b,s);}
    static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    static MethodBody body(ABC a,InstanceInfo i,String n){return CasBytecodePatch.ownedBody(a,i,n);}
    public static void main(String[] args)throws Exception {
        require(args.length==3 || (args.length==4 && args[3].equals("plan")),"Use original catalog SWF, compiled catalog SWF and output ABC, optionally plan.");
        boolean plan=args.length==4;
        String pin=plan?"060ced2b95e5cc25aaba4b30f0b850d2b0ce992139c68311dc4110f510200f35":PIN;
        Map<String,Set<String>> targets=plan?Map.of("widgets.CAS.PlanOutfit.CASPlanOutfitMain",
            Set.of("BindPanelToSim","HandleSetPlanOutfitVisible")):TARGETS;
        require(sha(Files.readAllBytes(Path.of(args[0]))).equals(pin),"Installed CAS catalog differs from inspected build.");
        ABC a=CasBytecodePatch.load(args[0]),c=CasBytecodePatch.load(args[1]);CasBytecodePatch.prefix(a,c);
        Map<Integer,byte[]> before=new HashMap<>();for(var b:a.bodies)before.put(b.method_info,b.getCodeBytes().clone());
        Map<Integer,MethodBody> edits=new HashMap<>();Map<String,String> hashes=new TreeMap<>();
        for(var entry:targets.entrySet()) {
            int ai=a.findClassByName(entry.getKey()),ci=c.findClassByName(entry.getKey());
            require(ai>=0 && ai==ci,"Catalog class inventory/order differs.");
            var ia=a.instance_info.get(ai);var ic=c.instance_info.get(ci);
            for(String n:entry.getValue()) {
                var old=body(a,ia,n);var made=body(c,ic,n);var b=made.clone();
                require(old.exceptions.length==0 && made.exceptions.length==0,"Catalog handler has unreviewed exception regions.");
                require(old.traits.traits.isEmpty() && made.traits.traits.isEmpty(),"Catalog handler has unreviewed activation traits.");
                int delta=old.init_scope_depth-made.init_scope_depth;
                require(delta>=0 && delta<=16,"Catalog lexical scope differs from the inspected compiler contract.");
                for(var op:b.getCode().code) {
                    require(op.definition.instructionCode!=0x40 && op.definition.instructionCode!=0x44 && op.definition.instructionCode!=0x67,
                        "Catalog handler contains an unreviewed nested/outer function dependency.");
                    if(op.definition.instructionCode==0x65) require(op.operands[0]<made.max_scope_depth-made.init_scope_depth,
                        "Catalog local scope index is invalid.");
                }
                b.method_info=old.method_info;b.init_scope_depth+=delta;b.max_scope_depth+=delta;
                require(edits.put(old.method_info,b)==null,"Catalog handler is duplicated.");
                hashes.put(entry.getKey()+"."+n,sha(b.getCodeBytes()));
            }
        }
        // Only the compiler's extended constant pool is consumed. All native
        // classes, scripts, signatures and unselected method bodies are kept.
        a.constants=c.constants;
        for(int i=0;i<a.bodies.size();i++) if(edits.containsKey(a.bodies.get(i).method_info)) a.bodies.set(i,edits.get(a.bodies.get(i).method_info));
        ByteArrayOutputStream out=new ByteArrayOutputStream();a.saveToStream(out);
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(out.toByteArray())),a.getSwf(),null);
        require(saved.bodies.size()==before.size(),"Catalog method inventory changed.");
        for(var b:saved.bodies) require(Arrays.equals(b.getCodeBytes(),edits.containsKey(b.method_info)?edits.get(b.method_info).getCodeBytes():before.get(b.method_info)),
            "Catalog serialized handler differs or another native handler changed.");
        Files.write(Path.of(args[2]),out.toByteArray());
        System.out.println("{\"ok\":true,\"unrelated_native_methods_preserved\":true,\"native_lexical_scope_preserved\":true,\"edited_method_count\":"+edits.size()+",\"base_resource_sha256\":\""+pin+"\"}");
    }
}
