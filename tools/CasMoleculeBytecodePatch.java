// Transplant four explicitly edited molecule handlers, preserving all others.
// Input SWFs and decompiled sources stay private; no process/game-file writes.
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasMoleculeBytecodePatch {
    static final String PIN="3124ed12ea50140da6f072d16ab0703e6154e448974edb1c3f6f7d05f7c24524";
    static final Map<String,Set<String>> TARGETS=Map.of(
        "widgets.TraitsMolecule.OccultSelectionButton",Set.of("UpdateIconDisplay"),
        "widgets.CAS.Molecule.EquippedTraitsAsp",Set.of("SetSimInfo","OnOccultClick","OnOccultSelected"));
    static void require(boolean b,String s){CasBytecodePatch.require(b,s);}
    static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    static MethodBody body(ABC a,InstanceInfo i,String n){return CasBytecodePatch.ownedBody(a,i,n);}
    public static void main(String[] args)throws Exception {
        require(args.length==3,"Use original molecule SWF, compiled molecule SWF and output ABC.");
        require(sha(Files.readAllBytes(Path.of(args[0]))).equals(PIN),"Installed CAS molecule differs from inspected build.");
        ABC a=CasBytecodePatch.load(args[0]),c=CasBytecodePatch.load(args[1]);CasBytecodePatch.prefix(a,c);
        Map<Integer,byte[]> before=new HashMap<>();for(var b:a.bodies)before.put(b.method_info,b.getCodeBytes().clone());
        Map<Integer,MethodBody> edits=new HashMap<>();Map<String,String> hashes=new TreeMap<>();
        for(var entry:TARGETS.entrySet()) {
            int ai=a.findClassByName(entry.getKey()),ci=c.findClassByName(entry.getKey());
            require(ai>=0 && ai==ci,"Molecule class inventory/order differs.");
            var ia=a.instance_info.get(ai);var ic=c.instance_info.get(ci);
            for(String n:entry.getValue()) {
                var old=body(a,ia,n);var made=body(c,ic,n);var b=made.clone();
                require(old.exceptions.length==0 && made.exceptions.length==0,"Molecule handler has unreviewed exception regions.");
                require(old.traits.traits.isEmpty() && made.traits.traits.isEmpty(),"Molecule handler has unreviewed activation traits.");
                int delta=old.init_scope_depth-made.init_scope_depth;
                require(delta>=0 && delta<=16,"Molecule lexical scope differs from the inspected compiler contract.");
                for(var op:b.getCode().code) {
                    require(op.definition.instructionCode!=0x40 && op.definition.instructionCode!=0x44 && op.definition.instructionCode!=0x67,
                        "Molecule handler contains an unreviewed nested/outer function dependency.");
                    if(op.definition.instructionCode==0x65) require(op.operands[0]<made.max_scope_depth-made.init_scope_depth,
                        "Molecule local scope index is invalid.");
                }
                b.method_info=old.method_info;b.init_scope_depth+=delta;b.max_scope_depth+=delta;
                require(edits.put(old.method_info,b)==null,"Molecule handler is duplicated.");
                hashes.put(entry.getKey()+"."+n,sha(b.getCodeBytes()));
            }
        }
        // Only the compiler's extended constant pool is consumed. All native
        // classes, scripts, signatures and unselected method bodies are kept.
        a.constants=c.constants;
        for(int i=0;i<a.bodies.size();i++) if(edits.containsKey(a.bodies.get(i).method_info)) a.bodies.set(i,edits.get(a.bodies.get(i).method_info));
        ByteArrayOutputStream out=new ByteArrayOutputStream();a.saveToStream(out);
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(out.toByteArray())),a.getSwf(),null);
        require(saved.bodies.size()==before.size(),"Molecule method inventory changed.");
        for(var b:saved.bodies) require(Arrays.equals(b.getCodeBytes(),edits.containsKey(b.method_info)?edits.get(b.method_info).getCodeBytes():before.get(b.method_info)),
            "Molecule serialized handler differs or another native handler changed.");
        Files.write(Path.of(args[2]),out.toByteArray());
        System.out.println("{\"ok\":true,\"unrelated_native_methods_preserved\":true,\"native_lexical_scope_preserved\":true,\"edited_method_count\":4,\"base_resource_sha256\":\""+PIN+"\"}");
    }
}
