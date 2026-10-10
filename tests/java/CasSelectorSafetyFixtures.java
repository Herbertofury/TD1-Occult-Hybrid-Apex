// Static synthetic/locally extracted bytecode only: no game or profile access.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasSelectorSafetyFixtures {
    static ABC abc() { return new ABC((com.jpexs.decompiler.flash.tags.ABCContainerTag)null); }
    static byte[] op(int code,int... args) { return CasSelectorBytecodePatch.instruction(code,args); }
    static byte[] bytes(byte[]... rows) { return CasSelectorBytecodePatch.join(rows); }
    static MethodBody body(ABC abc,byte[] raw) {
        var result=new MethodBody(abc,new Traits(),raw,new ABCException[0]);
        result.max_stack=8; result.max_regs=8; result.init_scope_depth=3; result.max_scope_depth=5;
        return result;
    }
    static int qname(ABC abc,String name) { return qname(abc,name,Namespace.KIND_PACKAGE,""); }
    static int qname(ABC abc,String name,int kind,String nsName) {
        var nameInfo=new Multiname(); nameInfo.kind=Multiname.QNAME;
        nameInfo.name_index=abc.constants.getStringId(name,true);
        nameInfo.namespace_index=abc.constants.getNamespaceId(kind,nsName,0,true);
        return abc.constants.getMultinameId(nameInfo,true);
    }
    static byte[] call(ABC abc,String name,int count) { return bytes(op(0xd0),op(0x4f,qname(abc,name),count)); }
    static MethodBody registrations(ABC abc,String event,String callback,int count,boolean duplicate) {
        byte[] service=bytes(op(0xd0),op(0x2c,abc.constants.getStringId("ApexReadOwnerPairFeed",true)),
            op(0xd0),op(0x66,qname(abc,"ApexSelectorReadOwnerFeed")),op(0x4f,qname(abc,"RegisterServiceHandler"),2));
        byte[] reset=bytes(op(0xd0),op(0x2c,abc.constants.getStringId(event,true)),op(0xd0),
            op(0x66,qname(abc,callback)),op(0x4f,qname(abc,"AddMessageListener"),count));
        return body(abc,bytes(op(0xd0),op(0x30),service,reset,duplicate ? reset : new byte[0],op(0x47)));
    }
    static InstanceInfo owned(ABC abc) {
        var instance=new InstanceInfo(new Traits());
        String privateName="widgets.CAS.SimSelector:CASSimSelectorMain";
        for(var entry:CasSelectorBytecodePatch.FIELDS.entrySet()) {
            var field=new TraitSlotConst(); field.kindType=Trait.TRAIT_SLOT;
            field.name_index=qname(abc,entry.getKey(),Namespace.KIND_PRIVATE,privateName);
            field.type_index=qname(abc,entry.getValue()); instance.instance_traits.traits.add(field);
        }
        for(String key:CasSelectorBytecodePatch.METHODS) {
            boolean init=key.equals("ApexSelectorInitialize"), optional=key.equals("ApexSelectorClearFeed") || key.equals("ApexSelectorReadOwnerFeed");
            boolean returnsObject=key.equals("ApexSelectorCopyRow") || key.equals("ApexSelectorReadOwnerFeed");
            var info=new MethodInfo(init ? new int[0] : new int[]{qname(abc,"Object")},qname(abc,returnsObject ? "Object" : "void"),
                0,optional ? MethodInfo.FLAG_HAS_OPTIONAL : 0,optional ? new ValueKind[]{new ValueKind(ValueKind.CONSTANT_Null,ValueKind.CONSTANT_Null)} : new ValueKind[0],new int[0]);
            var trait=new TraitMethodGetterSetter(); trait.kindType=Trait.TRAIT_METHOD;
            trait.name_index=qname(abc,key,Namespace.KIND_PRIVATE,privateName); trait.method_info=abc.method_info.size(); abc.method_info.add(info);
            var method=init ? registrations(abc,"CASClearSimsForReset","ApexSelectorClearFeed",2,false)
                : body(abc,bytes(op(0x24,32),op(0x29),key.equals("ApexSelectorCaptureFeed") || key.equals("ApexSelectorReadOwnerFeed") ?
                    call(abc,"ApexSelectorCopyRow",1) : new byte[0],key.equals("ApexSelectorReadOwnerFeed") ? call(abc,"RequestItemAt",1) : new byte[0],op(0x47)));
            method.method_info=trait.method_info; abc.bodies.add(method); instance.instance_traits.traits.add(trait);
        }
        return instance;
    }
    interface Operation { void run() throws Exception; }
    static void refuses(Operation action,String reason) throws Exception {
        try { action.run(); } catch(IllegalArgumentException expected) {
            if(!expected.getMessage().contains(reason)) throw new AssertionError("Wrong refusal: "+expected.getMessage());
            return;
        }
        throw new AssertionError("Unsafe synthetic bytecode accepted: "+reason);
    }
    static void test(String key) throws Exception {
        ABC abc=abc();
        byte[] original=bytes(op(0xd0),op(0x30),op(0x26),op(0x12,2),op(0x24,1),op(0x47));
        var nativeBody=body(abc,original);
        if(key.equals("entry-preserves-branch")) {
            CasSelectorBytecodePatch.splice(nativeBody,16384,true);
            CasSelectorBytecodePatch.verifySplice(nativeBody,original,16384,true);
            if(nativeBody.getCode().code.get(3).definition.instructionCode != 0xd1) throw new AssertionError("Payload was not local1");
        } else if(key.equals("tail-preserves-return-branch")) {
            CasSelectorBytecodePatch.splice(nativeBody,16384,false);
            CasSelectorBytecodePatch.verifySplice(nativeBody,original,16384,false);
            var branch=nativeBody.getCode().code.get(3);
            if(branch.getTargetAddress() != original.length-1) throw new AssertionError("Tail branch skipped hook");
        } else if(key.equals("unknown-native-exception")) {
            nativeBody.exceptions=new ABCException[]{new ABCException()};
            refuses(()->CasSelectorBytecodePatch.splice(nativeBody,2,true),"unreviewed exception");
        } else if(key.equals("scope-prologue")) {
            nativeBody.setCodeBytes(bytes(op(0xd0),op(0x29),op(0x47)));
            refuses(()->CasSelectorBytecodePatch.splice(nativeBody,2,true),"scope prologue");
        } else if(key.equals("multiple-return")) {
            nativeBody.setCodeBytes(bytes(op(0xd0),op(0x30),op(0x47),op(0x47)));
            refuses(()->CasSelectorBytecodePatch.splice(nativeBody,2,true),"one final return");
        } else if(key.equals("branch-to-prologue")) {
            nativeBody.setCodeBytes(bytes(op(0xd0),op(0x30),op(0x10,-6),op(0x47)));
            refuses(()->CasSelectorBytecodePatch.splice(nativeBody,2,true),"branch leaves");
        } else if(key.equals("native-suffix-tamper") || key.equals("hook-qname-tamper") || key.equals("hook-argument-tamper")) {
            CasSelectorBytecodePatch.splice(nativeBody,2,true);
            byte[] changed=nativeBody.getCodeBytes().clone();
            changed[key.equals("native-suffix-tamper") ? changed.length-2 : key.equals("hook-qname-tamper") ? 5 : 6] ^= 1;
            nativeBody.setCodeBytes(changed);
            refuses(()->CasSelectorBytecodePatch.verifySplice(nativeBody,original,2,true),"outside the owned hook");
        } else if(key.equals("callback-copy-only")) {
            CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCaptureFeed",body(abc,bytes(call(abc,"ApexSelectorCopyRow",1),call(abc,"push",1),op(0x47))));
        } else if(key.equals("callback-native-getter") || key.equals("service-native-getter")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,key.startsWith("service") ? "ApexSelectorReadOwnerFeed" : "ApexSelectorCaptureFeed",
                body(abc,bytes(call(abc,"CallGameService",1),op(0x47)))),"unreviewed service/member");
        } else if(key.equals("callback-native-class")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCopyRow",body(abc,bytes(op(0x60,qname(abc,"CommunicationManager")),op(0x47)))),"native/transport");
        } else if(key.equals("callback-retained-getter")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCaptureFeed",body(abc,bytes(op(0xd0),op(0x66,qname(abc,"mDataFeed")),op(0x47)))),"outside its read service");
        } else if(key.equals("service-native-write")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorReadOwnerFeed",body(abc,bytes(op(0xd0),op(0x20),op(0x61,qname(abc,"mDataFeed")),op(0x47)))),"mutates retained/native");
        } else if(key.equals("service-observation-write")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorReadOwnerFeed",body(abc,bytes(op(0xd0),op(0x20),op(0x61,qname(abc,"apexSelectorFeed")),op(0x47)))),"changes owned observation");
        } else if(key.equals("initialize-clears-feed")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorInitialize",body(abc,bytes(op(0xd0),op(0x20),op(0x61,qname(abc,"apexSelectorFeed")),op(0x47)))),"already captured feed");
        } else if(key.equals("callback-closure") || key.equals("callback-direct-call") || key.equals("callback-outer-scope")) {
            int opcode=key.equals("callback-closure") ? 0x40 : key.equals("callback-direct-call") ? 0x41 : 0x67;
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCaptureFeed",body(abc,bytes(op(opcode,0),op(0x47)))),"unreviewed direct call");
        } else if(key.equals("local-scope-overflow")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCopyRow",body(abc,bytes(op(0x65,2),op(0x47)))),"scope index is out of range");
        } else if(key.equals("arbitrary-constructor")) {
            refuses(()->CasSelectorBytecodePatch.verifySafeBody(abc,"ApexSelectorCopyRow",body(abc,bytes(op(0x60,qname(abc,"Socket")),op(0x42,0),op(0x47)))),"native/transport");
        } else if(key.startsWith("inventory-")) {
            var instance=owned(abc); String reason="";
            if(key.equals("inventory-extra")) {
                var trait=instance.instance_traits.traits.get(0).clone(); trait.name_index=qname(abc,"apexUnreviewed",Namespace.KIND_PRIVATE,"widgets.CAS.SimSelector:CASSimSelectorMain");
                instance.instance_traits.traits.add(trait); reason="Unreviewed owned";
            } else if(key.equals("inventory-duplicate")) { instance.instance_traits.traits.add(instance.instance_traits.traits.get(0).clone()); reason="Duplicate owned";
            } else if(key.equals("inventory-private-namespace")) {
                instance.instance_traits.traits.get(0).name_index=qname(abc,CasSelectorBytecodePatch.name(abc,instance.instance_traits.traits.get(0)),Namespace.KIND_PRIVATE,"another-class"); reason="not class-private";
            } else if(key.equals("inventory-slot-collision")) { ((TraitSlotConst)instance.instance_traits.traits.get(0)).slot_id=1; reason="automatic slot";
            } else if(key.equals("inventory-optional-signature")) {
                var method=CasSelectorBytecodePatch.body(abc,instance,"ApexSelectorClearFeed"); abc.method_info.get(method.method_info).optional[0].value_kind=ValueKind.CONSTANT_False; reason="signature differs";
            } else if(key.equals("inventory-missing-bound")) {
                CasSelectorBytecodePatch.body(abc,instance,"ApexSelectorReadOwnerFeed").setCodeBytes(bytes(call(abc,"ApexSelectorCopyRow",1),call(abc,"RequestItemAt",1),op(0x47))); reason="32-row bound";
            } else if(key.equals("inventory-read-argument")) {
                CasSelectorBytecodePatch.body(abc,instance,"ApexSelectorReadOwnerFeed").setCodeBytes(bytes(op(0x24,32),op(0x29),call(abc,"ApexSelectorCopyRow",1),call(abc,"RequestItemAt",2),op(0x47))); reason="read argument";
            } else if(!key.equals("inventory-exact")) throw new AssertionError("Unknown inventory fixture");
            if(key.equals("inventory-exact")) CasSelectorBytecodePatch.ownedTraits(abc,instance);
            else { final String expected=reason; refuses(()->CasSelectorBytecodePatch.ownedTraits(abc,instance),expected); }
        } else if(key.startsWith("registration-")) {
            String event=key.equals("registration-event") ? "CASRefreshSimIcons" : "CASClearSimsForReset";
            String callback=key.equals("registration-callback") ? "ApexSelectorCaptureFeed" : "ApexSelectorClearFeed";
            MethodBody registration=registrations(abc,event,callback,key.equals("registration-arity") ? 3 : 2,key.equals("registration-duplicate"));
            if(key.equals("registration-exact")) CasSelectorBytecodePatch.verifyRegistration(abc,registration);
            else refuses(()->CasSelectorBytecodePatch.verifyRegistration(abc,registration),
                key.equals("registration-event") || key.equals("registration-callback") ? "event/callback linkage" : "two-argument widget wrapper");
        } else throw new AssertionError("Unknown fixture: "+key);
    }
    static ABC serialized(ABC abc,com.jpexs.decompiler.flash.SWF swf) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(); abc.saveToStream(bytes);
        return new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),swf,null);
    }
    static AVM2Instruction property(ABC abc,MethodBody body,String key,int opcode,int occurrence) {
        for(var instruction:body.getCode().code) if(CasBytecodePatch.property(abc,instruction,opcode,key) && occurrence-- == 0)
            return instruction;
        throw new AssertionError("Actual selector fixture member absent: "+key);
    }
    static AVM2Instruction literal(ABC abc,MethodBody body,String key) {
        for(var instruction:body.getCode().code) if(CasSelectorBytecodePatch.opcode(instruction,0x2c) &&
                key.equals(abc.constants.getString(instruction.operands[0]))) return instruction;
        throw new AssertionError("Actual selector fixture literal absent: "+key);
    }
    static void actual(String key,String sourcePath,String compiledPath) throws Exception {
        ABC reference=CasBytecodePatch.load(sourcePath), source=CasBytecodePatch.load(sourcePath);
        ABC compiled=CasBytecodePatch.load(compiledPath);
        byte[] patched=CasSelectorBytecodePatch.patch(source,compiled);
        ABC candidate=new ABC(new ABCInputStream(new MemoryInputStream(patched)),compiled.getSwf(),null);
        CasSelectorBytecodePatch.verifyIndependentDefault(reference,candidate);
        var copy=candidate.instance_info.get(candidate.findClassByName(CasSelectorBytecodePatch.COPY_TARGET));
        MethodBody update=CasSelectorBytecodePatch.body(candidate,copy,"UpdateSimInfo");
        MethodBody mode=CasSelectorBytecodePatch.body(candidate,copy,"SetCopyMode");
        MethodBody sync=CasSelectorBytecodePatch.body(candidate,copy,"SendLinkUpdate");
        MethodBody link=CasSelectorBytecodePatch.body(candidate,copy,"OnLink");
        MethodBody explicitCopy=CasSelectorBytecodePatch.body(candidate,copy,"OnCopy");
        switch(key) {
            case "actual-default-exact": break;
            case "actual-default-reverted": {
                var code=update.getCode(); code.markOffsets();
                for(int i=0;i<code.code.size();i++) if(code.code.get(i).getAddress() == 144)
                    code.code.set(i,new AVM2Instruction(0,0x27,new int[0]));
                break;
            }
            case "actual-remembered-guard": {
                var code=update.getCode().code;
                int at=code.indexOf(property(candidate,update,"hasOwnProperty",0x46,0));
                var branch=code.get(at+1);
                code.set(at+1,new AVM2Instruction(0,0x12,branch.operands.clone())); break;
            }
            case "actual-default-owner-key":
                property(candidate,update,"mCurrentBaseSimId",0x66,1).operands[0]=property(candidate,update,"mCopyFilters",0x66,0).operands[0]; break;
            case "actual-remembered-choice-read":
                property(candidate,update,"mCopyModeData",0x66,2).operands[0]=property(candidate,update,"mCopyFilters",0x66,0).operands[0]; break;
            case "actual-link-inversion": {
                var code=mode.getCode().code;
                for(int i=0;i<code.size();i++) if(CasSelectorBytecodePatch.opcode(code.get(i),0x96)) {
                    code.set(i,new AVM2Instruction(0,0x76,new int[0])); break;
                }
                break;
            }
            case "actual-explicit-link-memory":
                property(candidate,link,"mCurrentBaseSimId",0x66,0).operands[0]=property(candidate,link,"btnLink",0x66,0).operands[0]; break;
            case "actual-sync-zero": {
                var code=sync.getCode().code;
                if(!CasSelectorBytecodePatch.opcode(code.get(2),0x24)) throw new AssertionError("Expected zero initialization");
                code.get(2).operands[0]=1; break;
            }
            case "actual-sync-service":
                literal(candidate,sync,"CasEnableAutoSyncOccultForm").operands[0]=candidate.constants.getStringId("CasSyncSimOccultForm",true); break;
            case "actual-sync-payload":
                literal(candidate,sync,"syncFlags").operands[0]=candidate.constants.getStringId("copyFlag",true); break;
            case "actual-copy-handler":
                literal(candidate,explicitCopy,"copyFlag").operands[0]=candidate.constants.getStringId("syncFlags",true); break;
            case "actual-copy-exception": update.exceptions=new ABCException[]{new ABCException()}; break;
            case "actual-copy-trait": copy.instance_traits.traits.get(0).kindFlags ^= Trait.ATTR_Final; break;
            case "actual-native-already-patched": {
                ABC changed=CasBytecodePatch.load(sourcePath);
                var instance=changed.instance_info.get(changed.findClassByName(CasSelectorBytecodePatch.COPY_TARGET));
                CasSelectorBytecodePatch.patchIndependentDefault(changed,instance);
                ABC saved=serialized(changed,reference.getSwf());
                refuses(()->CasSelectorBytecodePatch.patchIndependentDefault(saved,
                    saved.instance_info.get(saved.findClassByName(CasSelectorBytecodePatch.COPY_TARGET))),"inspected default contract");
                return;
            }
            default: throw new AssertionError("Unknown actual selector fixture: "+key);
        }
        for(MethodBody body:List.of(update,mode,sync,link,explicitCopy)) body.setModified();
        ABC saved=serialized(candidate,reference.getSwf());
        if(key.equals("actual-default-exact")) CasSelectorBytecodePatch.verifyIndependentDefault(reference,saved);
        else refuses(()->CasSelectorBytecodePatch.verifyIndependentDefault(reference,saved),"Native");
    }
    public static void main(String[] args) throws Exception {
        if(args[0].startsWith("actual-")) actual(args[0],args[1],args[2]); else test(args[0]);
        System.out.println("PASS "+args[0]);
    }
}
