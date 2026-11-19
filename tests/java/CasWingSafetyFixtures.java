// Local compiled/serialized ABC mutation fixtures. No game or profile access.
import java.io.*;
import java.util.*;
import java.util.logging.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasWingSafetyFixtures {
    static ABC serialized(ABC abc) throws Exception {
        var bytes=new ByteArrayOutputStream(); abc.saveToStream(bytes);
        return new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),abc.getSwf(),null);
    }
    static int member(ABC abc,String name) {
        for(int i=1;i<abc.constants.getMultinameCount();i++) {
            var item=abc.constants.getMultiname(i);
            if(name.equals(abc.constants.getString(item.name_index))) return i;
        }
        throw new AssertionError("Missing mutation fixture member: "+name);
    }
    static void check(ABC abc) {
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        CasBytecodePatch.verifyWingSelection(abc,instance);
    }
    public static void main(String[] args) throws Exception {
        Logger.getLogger("com.jpexs.decompiler.flash.SWFInputStream").setLevel(Level.OFF);
        String key=args[0]; ABC abc=CasBytecodePatch.load(args[1]); check(abc);
        var instance=abc.instance_info.get(abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        var body=CasBytecodePatch.ownedBody(abc,instance,"ApexReadback");
        var rows=body.getCode().code;
        var observation=CasBytecodePatch.ownedBody(abc,instance,"ApexWingObservation");
        var probe=observation.getCode().code;
        int base=CasBytecodePatch.uniqueLiteral(abc,observation,"GetCatalogBaseItemSelected");
        int color=CasBytecodePatch.uniqueLiteral(abc,observation,"GetCatalogVariantItemSelected");
        int query=CasBytecodePatch.uniqueLiteral(abc,observation,"state");
        int guard=CasBytecodePatch.uniqueLiteral(abc,body,"Native wing base and color did not both read back exactly")-56;
        int publish=guard+59;
        switch(key) {
            case "wing-exact-serialized": break;
            case "wing-base-getter": probe.get(base).operands[0]=abc.constants.getStringId("GetCatalogItemsSelected",true); break;
            case "wing-color-getter": probe.get(color).operands[0]=abc.constants.getStringId("GetCatalogItem",true); break;
            case "wing-color-bodytype": probe.get(color+2).operands[0]=member(abc,"HAIR"); break;
            case "wing-panel-state": rows.get(guard-39).operands[0]=member(abc,"CLOTHING_HAIR"); break;
            case "wing-base-arity": probe.get(base+4).operands[1]=2; break;
            case "wing-base-native-flag": probe.set(base+3,new AVM2Instruction(0,0x27,new int[0])); break;
            case "wing-base-detachment": probe.get(base+5).operands[0]=member(abc,"ApexEncode"); break;
            case "wing-filter-detachment": probe.get(query+8).operands[0]=member(abc,"ApexEncode"); break;
            case "wing-color-arity": probe.get(color+3).operands[1]=3; break;
            case "wing-color-coerced-string": probe.set(color+5,new AVM2Instruction(0,0x85,new int[0])); break;
            case "wing-base-count": rows.get(guard+10).operands[0]=2; break;
            case "wing-base-type": rows.get(guard+20).operands[0]=member(abc,"Number"); break;
            case "wing-color-type": rows.get(guard+42).operands[0]=member(abc,"Number"); break;
            case "wing-base-intent": rows.get(guard+33).operands[0]=member(abc,"selection_variant_id"); break;
            case "wing-color-intent": rows.get(guard+51).operands[0]=rows.get(guard-13).operands[0]; break;
            case "wing-variant-source": {
                boolean changed=false;
                for(int i=guard-85;i<guard;i++) if(CasBytecodePatch.property(abc,rows.get(i),0x66,"selection_variant_id") &&
                        CasBytecodePatch.opcode(rows.get(i+1),0x70)) {
                    rows.get(i).operands[0]=member(abc,"selection_base_id"); changed=true; break;
                }
                if(!changed) throw new AssertionError("Missing native variant intent fixture."); break;
            }
            case "wing-refusal-bypass": {
                var branch=rows.get(guard+5);
                branch.operands[0]=(int)(rows.get(publish).getAddress()-branch.getAddress()-branch.getBytesLength()); break;
            }
            case "wing-refusal-throw": rows.set(guard+58,new AVM2Instruction(0,0x29,new int[0])); break;
            case "wing-color-ack": rows.get(publish+12).operands[0]=rows.get(guard-13).operands[0]; break;
            case "wing-native-write": {
                boolean changed=false;
                for(int i=0;i<base;i++) if(CasBytecodePatch.property(abc,probe.get(i),0x46,"GetCatalogFilter")) {
                    probe.get(i).operands[0]=member(abc,"CallGameService"); changed=true; break;
                }
                if(!changed) throw new AssertionError("Missing native filter fixture."); break;
            }
            case "wing-observation-color-detachment": probe.get(color+4).operands[0]=member(abc,"ApexEncode"); break;
            case "wing-observation-qualified": {
                int at=CasBytecodePatch.uniqueLiteral(abc,observation,"qualified_success");
                probe.set(at+1,new AVM2Instruction(0,0x26,new int[0])); break;
            }
            case "wing-observation-base-type": {
                int at=CasBytecodePatch.uniqueProperty(abc,observation,0x61,"base_return_type");
                probe.set(at-1,new AVM2Instruction(0,0x70,new int[0])); break;
            }
            case "wing-observation-raw-color": {
                int at=CasBytecodePatch.uniqueProperty(abc,observation,0x61,"selected_color_id");
                probe.get(at-1).operands[0]=probe.get(base+7).operands[0]; break;
            }
            case "wing-observation-bound": {
                boolean changed=false;
                for(int i=0;i+1<probe.size();i++) if(CasBytecodePatch.opcode(probe.get(i),0x24) && probe.get(i).operands[0]==32 &&
                        CasBytecodePatch.opcode(probe.get(i+1),0xaf)) { probe.get(i).operands[0]=33; changed=true; break; }
                if(!changed) throw new AssertionError("Missing observation bound fixture."); break;
            }
            case "wing-observation-panel":
                probe.get(CasBytecodePatch.uniqueProperty(abc,observation,0x66,"CLOTHING_BODY_WINGS")).operands[0]=member(abc,"CLOTHING_HAIR"); break;
            case "wing-observation-publication": {
                int at=CasBytecodePatch.uniqueProperty(abc,body,0x46,"ApexWingObservation");
                rows.get(at+1).operands[0]=member(abc,"wing_selection"); break;
            }
            case "wing-observation-native-property":
                probe.get(CasBytecodePatch.uniqueProperty(abc,observation,0x61,"selected_color_id")).operands[0]=member(abc,"mCurrState"); break;
            case "wing-observation-socket-caller": {
                var socket=CasBytecodePatch.ownedBody(abc,instance,"ApexSocketConnect");
                var op=socket.getCode().code.get(CasBytecodePatch.uniqueProperty(abc,socket,0x46,"split"));
                op.operands[0]=member(abc,"ApexWingObservation"); socket.setModified(); break;
            }
            default: throw new AssertionError("Unknown wing fixture: "+key);
        }
        body.setModified(); observation.setModified(); ABC saved=serialized(abc);
        if(key.equals("wing-exact-serialized")) check(saved);
        else {
            try { check(saved); }
            catch(IllegalArgumentException expected) {
                if(!expected.getMessage().startsWith("Wing ")) throw new AssertionError("Wrong refusal: "+expected.getMessage());
                System.out.println("PASS "+key); return;
            }
            throw new AssertionError("Unsafe serialized wing mutation was accepted: "+key);
        }
        System.out.println("PASS "+key);
    }
}
