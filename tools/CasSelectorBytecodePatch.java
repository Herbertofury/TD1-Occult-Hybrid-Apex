// Build-time selector observer transplant. No game/process/profile access.
// Compile with CasBytecodePatch.java and FFDec's public ABC library.
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasSelectorBytecodePatch {
    static final String TARGET = "widgets.CAS.SimSelector.CASSimSelectorMain";
    static final String COPY_TARGET = "widgets.CAS.SimSelector.CASSimSelectorCopyOptionPanel";
    static final String COPY_UPDATE_PIN = "fba1b85704b12cf1d8d9a15964b1639d52a2dbf3e086db498b5499792ab182f4";
    static final String PIN = "420eb0f8417bfc6935ffb4126086f19b72f2cae98a853d34abf6d59a94d454f1";
    static final String CLEANUP_PIN = "e79b3b65c8b6234c54d4a76f4c7a671f46ece7ddb9f6940bc5db312850fdef91";
    static final Map<String,String> FIELDS = Map.of("apexSelectorFeed", "Object",
        "apexSelectorSequence", "int", "apexSelectorRegistered", "Boolean", "apexSelectorResetRegistered", "Boolean");
    static final Set<String> METHODS = Set.of("ApexSelectorInitialize", "ApexSelectorCaptureFeed",
        "ApexSelectorClearFeed", "ApexSelectorCopyRow", "ApexSelectorReadOwnerFeed");
    static void require(boolean value, String message) { CasBytecodePatch.require(value, message); }
    static String name(ABC abc, Trait trait) { return CasBytecodePatch.name(abc, trait); }
    static String member(ABC abc, int id) {
        String value=abc.constants.getString(abc.constants.getMultiname(id).name_index);
        return value == null ? "" : value;
    }
    static MethodBody body(ABC abc, InstanceInfo instance, String key) {
        MethodBody result = null;
        for (Trait trait : instance.instance_traits.traits) if (name(abc, trait).equals(key)) {
            require(result == null && trait instanceof TraitMethodGetterSetter, "Ambiguous selector method: " + key);
            result = abc.findBody(((TraitMethodGetterSetter)trait).method_info);
        }
        require(result != null, "Missing selector method: " + key);
        return result;
    }
    static int traitName(ABC abc, InstanceInfo instance, String key) {
        for (Trait trait : instance.instance_traits.traits) if (name(abc, trait).equals(key)) return trait.name_index;
        throw new IllegalArgumentException("Missing selector trait: " + key);
    }
    static boolean opcode(AVM2Instruction op, int value) { return op.definition.instructionCode == value; }
    static byte[] instruction(int opcode, int... operands) { return new AVM2Instruction(0, opcode, operands).getBytes(); }
    static byte[] join(byte[]... rows) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (byte[] row : rows) out.writeBytes(row);
        return out.toByteArray();
    }
    static void verifyBranches(MethodBody body, int minimumTarget) {
        var code = body.getCode();
        code.markOffsets();
        Set<Long> boundaries = new HashSet<>();
        for (var op : code.code) boundaries.add(op.getAddress());
        for (var op : code.code) for (long target : op.getOffsets())
            require(target >= minimumTarget && boundaries.contains(target), "Native selector branch leaves its reviewed body.");
        code.checkValidOffsets(body);
    }
    static void nativeHookContract(MethodBody body, boolean entry) {
        var code = body.getCode().code;
        require(body.exceptions.length == 0, "Native selector has unreviewed exception regions.");
        require(code.size() >= 3 && opcode(code.get(0), 0xd0) && opcode(code.get(1), 0x30),
            "Native selector scope prologue differs.");
        int returns = 0;
        for (var op : code) if (opcode(op, 0x47)) returns++;
        require(returns == 1 && opcode(code.get(code.size()-1), 0x47), "Native selector needs one final return.");
        require(body.getCodeBytes()[0] == (byte)0xd0 && body.getCodeBytes()[1] == (byte)0x30,
            "Native selector scope prologue serialization differs.");
        verifyBranches(body, entry ? 2 : 0);
    }
    static byte[] hook(int methodName, boolean entry) {
        require(methodName > 0, "Owned selector hook QName is absent.");
        return entry ? join(instruction(0xd0), instruction(0xd1), instruction(0x4f, methodName, 1))
            : join(instruction(0xd0), instruction(0x4f, methodName, 0));
    }
    static void splice(MethodBody body, int methodName, boolean entry) {
        nativeHookContract(body, entry);
        byte[] nativeBytes = body.getCodeBytes().clone(), owned = hook(methodName, entry);
        int at = entry ? 2 : nativeBytes.length-1;
        // Raw insertion preserves every original branch operand. Entry branches
        // remain within the uniformly shifted native suffix. A tail branch to
        // the old return now targets the owned call, then the same native return.
        body.setCodeBytes(join(Arrays.copyOfRange(nativeBytes, 0, at), owned,
            Arrays.copyOfRange(nativeBytes, at, nativeBytes.length)));
        body.max_stack = Math.max(body.max_stack, entry ? 2 : 1);
        verifySplice(body, nativeBytes, methodName, entry);
    }
    static void verifySplice(MethodBody body, byte[] nativeBytes, int methodName, boolean entry) {
        byte[] actual = body.getCodeBytes(), owned = hook(methodName, entry);
        int at = entry ? 2 : nativeBytes.length-1;
        require(actual.length == nativeBytes.length + owned.length &&
            Arrays.equals(Arrays.copyOfRange(actual, at, at+owned.length), owned) &&
            Arrays.equals(join(Arrays.copyOfRange(actual, 0, at), Arrays.copyOfRange(actual, at+owned.length, actual.length)), nativeBytes),
            "Native selector bytes changed outside the owned hook.");
        require(body.exceptions.length == 0, "Serialized selector hook gained an exception region.");
        verifyBranches(body, 0);
    }
    static boolean namedOperand(AVM2Instruction op) {
        return Set.of(0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5d,0x5e,0x5f,
            0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2).contains(op.definition.instructionCode);
    }
    static void verifySafeBody(ABC abc, String key, MethodBody body) {
        Set<String> calls = key.equals("ApexSelectorInitialize") ? Set.of("RegisterServiceHandler", "AddMessageListener")
            : key.equals("ApexSelectorCopyRow") ? Set.of("test", "String", "int", "Boolean")
            : key.equals("ApexSelectorReadOwnerFeed") ? Set.of("RequestItemAt", "ApexSelectorCopyRow", "push", "String", "int", "Boolean")
            : key.equals("ApexSelectorCaptureFeed") ? Set.of("ApexSelectorCopyRow", "push", "String", "int", "Boolean") : Set.of();
        var instructions=body.getCode().code;
        for (int index=0;index<instructions.size();index++) {
            var op=instructions.get(index);
            int code = op.definition.instructionCode;
            require(!Set.of(0x40,0x41,0x43,0x44,0x45,0x4e,0x53,0x58,0x67).contains(code),
                "Owned selector uses unreviewed direct call, closure, class or outer scope: " + key);
            if (code == 0x65) require(op.operands[0] >= 0 && op.operands[0] < body.max_scope_depth-body.init_scope_depth,
                "Owned selector local scope index is out of range.");
            if (code == 0x46 || code == 0x4c || code == 0x4f)
                require(calls.contains(member(abc, op.operands[0])), "Owned selector calls an unreviewed service/member: " + key);
            if (code == 0x4a) require(Set.of("Error", "RegExp").contains(member(abc, op.operands[0])),
                "Owned selector constructs an unreviewed property.");
            if (code == 0x42) require(key.equals("ApexSelectorCopyRow") && index >= 2 && op.operands[0] == 1 &&
                opcode(instructions.get(index-2),0x60) && member(abc,instructions.get(index-2).operands[0]).equals("RegExp") &&
                opcode(instructions.get(index-1),0x2c) && abc.constants.getString(instructions.get(index-1).operands[0]).equals("^(0|[1-9][0-9]{0,19})$"),
                "Owned selector constructs an unreviewed dynamic receiver.");
            if (namedOperand(op)) {
                String property = member(abc, op.operands[0]);
                require(!Set.of("CommunicationManager", "CallGameService", "CallUIService", "SendUIMessage", "SendMessage",
                    "Socket", "Timer", "connect", "writeUTFBytes", "flush", "SelectSim", "CasSelectSim", "CasSelectOccultForm").contains(property),
                    "Owned selector accesses native/transport work: " + key);
                if (!key.equals("ApexSelectorReadOwnerFeed"))
                    require(!Set.of("mDataFeed", "mSelectedSimIndex", "mSelectedSimLayerIndex", "mCurrSimId", "RequestItemAt").contains(property),
                        "Selector callback reads retained/native state outside its read service.");
                if (code == 0x61 || code == 0x68 || code == 0x6a)
                    require(!Set.of("mDataFeed", "mSelectedSimIndex", "mSelectedSimLayerIndex", "mCurrSimId", "sim_layers").contains(property),
                        "Owned selector mutates retained/native state.");
                if (key.equals("ApexSelectorReadOwnerFeed") && (code == 0x61 || code == 0x68))
                    require(!FIELDS.containsKey(property), "Selector read service changes owned observation state.");
                if (key.equals("ApexSelectorInitialize") && (code == 0x61 || code == 0x68))
                    require(!Set.of("apexSelectorFeed", "apexSelectorSequence").contains(property),
                        "Selector initialization clears an already captured feed.");
            }
        }
    }
    static String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    static String verifyExternalCleanup(ABC library) throws Exception {
        int widget=library.findClassByName("olympus.core.widget.WidgetBase"), manager=library.findClassByName("olympus.io.CommunicationManager");
        require(widget >= 0 && manager >= 0,"Pinned cleanup library lacks native widget/communication classes.");
        MethodBody unload=body(library,library.instance_info.get(widget),"Unload");
        int calls=0; var code=unload.getCode().code;
        for(int i=3;i<code.size();i++) if(opcode(code.get(i),0x4f) && member(library,code.get(i).operands[0]).equals("RemoveWidgetFunctions")) {
            require(code.get(i).operands[1] == 1 && opcode(code.get(i-3),0x60) &&
                member(library,code.get(i-3).operands[0]).equals("CommunicationManager") && opcode(code.get(i-2),0xd0) &&
                opcode(code.get(i-1),0x66) && member(library,code.get(i-1).operands[0]).equals("mName"),
                "Widget cleanup is not bound to its native communication class/widget name.");
            var receiver=library.constants.getMultiname(code.get(i-3).operands[0]);
            require(receiver.kind == Multiname.QNAME && library.constants.getString(
                library.constants.getNamespace(receiver.namespace_index).name_index).equals("olympus.io"),
                "Widget cleanup communication receiver namespace differs.");
            calls++;
        }
        require(calls == 1,"Widget cleanup removal inventory differs.");
        MethodBody remove=body(library,library.instance_info.get(manager),"RemoveWidgetFunctions"), bridge=null;
        for(Trait trait:library.class_info.get(manager).static_traits.traits)
            if(name(library,trait).equals("RemoveWidgetFunctions") && trait instanceof TraitMethodGetterSetter)
                bridge=library.findBody(((TraitMethodGetterSetter)trait).method_info);
        require(bridge != null && CasBytecodePatch.propertyCalls(library,bridge).equals(Set.of("RemoveWidgetFunctions")),
            "Native static widget cleanup delegation differs.");
        Set<String> reads=new HashSet<>();
        for(var op:remove.getCode().code) if(namedOperand(op)) reads.add(member(library,op.operands[0]));
        require(reads.containsAll(Set.of("mMessageListeners","mServiceHandlers","RemoveWidgetsFunctions","HasWidget")) &&
            CasBytecodePatch.propertyCalls(library,remove).containsAll(Set.of("RemoveWidgetsFunctions","HasWidget")),
            "Native cleanup no longer removes listener functions and service handlers.");
        return "\"cleanup_library_sha256\":\""+CLEANUP_PIN+"\",\"widget_unload_code_sha256\":\""+sha(unload.getCodeBytes())+
            "\",\"cleanup_static_bridge_code_sha256\":\""+sha(bridge.getCodeBytes())+"\",\"cleanup_instance_code_sha256\":\""+sha(remove.getCodeBytes())+"\"";
    }
    static void verifyRegistration(ABC abc, MethodBody body) {
        var code = body.getCode().code;
        Map<String,String> expected = Map.of("RegisterServiceHandler", "ApexReadOwnerPairFeed", "AddMessageListener", "CASClearSimsForReset");
        Map<String,String> callbacks = Map.of("RegisterServiceHandler", "ApexSelectorReadOwnerFeed", "AddMessageListener", "ApexSelectorClearFeed");
        Set<String> seen = new HashSet<>();
        for (int index=0; index<code.size(); index++) {
            var op = code.get(index);
            if (!(opcode(op,0x46) || opcode(op,0x4c) || opcode(op,0x4f))) continue;
            String operation = member(abc, op.operands[0]);
            require(expected.containsKey(operation) && seen.add(operation) && op.operands[1] == 2,
                "Selector registration is not an exact two-argument widget wrapper.");
            String event=null, callback=null;
            for (int prior=Math.max(0,index-5); prior<index; prior++) {
                var arg = code.get(prior);
                if (opcode(arg,0x2c)) event=abc.constants.getString(arg.operands[0]);
                if (opcode(arg,0x60) || opcode(arg,0x66)) {
                    String candidate=member(abc,arg.operands[0]);
                    if (METHODS.contains(candidate)) callback=candidate;
                }
            }
            require(expected.get(operation).equals(event) && callbacks.get(operation).equals(callback),
                "Selector registration event/callback linkage differs.");
        }
        require(seen.equals(expected.keySet()), "Selector registration inventory differs.");
    }
    static List<Trait> ownedTraits(ABC abc, InstanceInfo instance) {
        List<Trait> added=new ArrayList<>(); Set<String> seen=new HashSet<>(); Set<Integer> methods=new HashSet<>();
        int privateNamespace=-1;
        for (Trait trait : instance.instance_traits.traits) {
            String key=name(abc,trait);
            if (!key.startsWith("Apex") && !key.startsWith("apex")) continue;
            require(seen.add(key), "Duplicate owned selector trait.");
            Multiname qname=abc.constants.getMultiname(trait.name_index);
            require(qname.kind == Multiname.QNAME && qname.namespace_index > 0 &&
                abc.constants.getNamespace(qname.namespace_index).kind == Namespace.KIND_PRIVATE &&
                abc.constants.getString(abc.constants.getNamespace(qname.namespace_index).name_index).equals("widgets.CAS.SimSelector:CASSimSelectorMain"),
                "Owned selector trait is not class-private.");
            if (privateNamespace < 0) privateNamespace=qname.namespace_index;
            require(privateNamespace == qname.namespace_index, "Owned selector private namespaces differ.");
            if (FIELDS.containsKey(key)) {
                require(trait instanceof TraitSlotConst && trait.kindType == Trait.TRAIT_SLOT && trait.kindFlags == 0,
                    "Owned selector field kind differs.");
                var slot=(TraitSlotConst)trait;
                require(FIELDS.get(key).equals(member(abc,slot.type_index)) && slot.slot_id == 0,
                    "Owned selector field type/automatic slot contract differs.");
                require(slot.value_index == 0 || (key.equals("apexSelectorSequence") &&
                    slot.value_kind == ValueKind.CONSTANT_Int && abc.constants.getInt(slot.value_index) == 0) ||
                    (FIELDS.get(key).equals("Boolean") && slot.value_kind == ValueKind.CONSTANT_False &&
                    slot.value_index == ValueKind.CONSTANT_False),
                    "Owned selector field default differs.");
            } else {
                require(METHODS.contains(key) && trait instanceof TraitMethodGetterSetter && trait.kindType == Trait.TRAIT_METHOD && trait.kindFlags == 0,
                    "Unreviewed owned selector method/trait.");
                int index=((TraitMethodGetterSetter)trait).method_info;
                require(methods.add(index), "Owned selector methods alias the same body.");
                MethodInfo method=abc.method_info.get(index);
                boolean initialize=key.equals("ApexSelectorInitialize"), returnsObject=key.equals("ApexSelectorCopyRow") || key.equals("ApexSelectorReadOwnerFeed");
                boolean optional=key.equals("ApexSelectorClearFeed") || key.equals("ApexSelectorReadOwnerFeed");
                require(method.param_types.length == (initialize ? 0 : 1) &&
                    (initialize || member(abc,method.param_types[0]).equals("Object")) &&
                    member(abc,method.ret_type).equals(returnsObject ? "Object" : "void") &&
                    !method.flagNative() && !method.flagNeed_arguments() && !method.flagNeed_rest() && !method.flagSetsdxns() &&
                    method.flagHas_optional() == optional && (!optional || method.optional.length == 1 &&
                    method.optional[0].value_kind == ValueKind.CONSTANT_Null && method.optional[0].value_index == ValueKind.CONSTANT_Null),
                    "Owned selector method signature differs: " + key);
                verifySafeBody(abc,key,body(abc,instance,key));
            }
            added.add(trait.clone());
        }
        Set<String> expected=new HashSet<>(METHODS); expected.addAll(FIELDS.keySet());
        require(seen.equals(expected), "Owned selector trait inventory differs.");
        verifyRegistration(abc,body(abc,instance,"ApexSelectorInitialize"));
        for(String key:List.of("ApexSelectorCaptureFeed","ApexSelectorReadOwnerFeed")) {
            MethodBody copy=body(abc,instance,key); Set<String> calls=CasBytecodePatch.propertyCalls(abc,copy);
            require(calls.contains("ApexSelectorCopyRow") && (!key.equals("ApexSelectorReadOwnerFeed") || calls.contains("RequestItemAt")),
                "Selector observer omits its primitive copier/retained read linkage.");
            boolean cap=false;
            for(var op:copy.getCode().code) {
                if((opcode(op,0x24) || opcode(op,0x25)) && op.operands[0] == 32) cap=true;
                if((opcode(op,0x46) || opcode(op,0x4c) || opcode(op,0x4f)) && member(abc,op.operands[0]).equals("RequestItemAt"))
                    require(op.operands[1] == 1,"Selector retained read argument inventory differs.");
            }
            require(cap,"Selector observer has no reviewed 32-row bound.");
        }
        return added;
    }
    // Canonical encoding of native structure, excluding only appended traits.
    static byte[] nativeStructure(ABC abc, int nativeMethodCount, int target, int nativeTraitCount) throws IOException {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(); ABCOutputStream out=new ABCOutputStream(bytes);
        for (int i=0;i<nativeMethodCount;i++) out.writeMethodInfo(abc.method_info.get(i));
        for (int i=0;i<abc.instance_info.size();i++) {
            var instance=abc.instance_info.get(i); var saved=instance.instance_traits.traits;
            if (i == target) instance.instance_traits.traits=new ArrayList<>(saved.subList(0,nativeTraitCount));
            try { out.writeInstanceInfo(instance); } finally { instance.instance_traits.traits=saved; }
        }
        for (var info:abc.class_info) { out.writeU30(info.cinit_index); out.writeTraits(info.static_traits); }
        for (var info:abc.script_info) { out.writeU30(info.init_index); out.writeTraits(info.traits); }
        for (var info:abc.metadata_info) { out.writeU30(info.name_index); out.writeU30(info.keys.length);
            for(int key:info.keys) out.writeU30(key); for(int value:info.values) out.writeU30(value); }
        return bytes.toByteArray();
    }
    static byte[] bodyStructure(MethodBody body, boolean hooked) throws IOException {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(); ABCOutputStream out=new ABCOutputStream(bytes);
        out.writeU30(body.method_info); if(!hooked) out.writeU30(body.max_stack);
        out.writeU30(body.max_regs); out.writeU30(body.init_scope_depth); out.writeU30(body.max_scope_depth);
        out.writeU30(body.exceptions.length);
        for(var ex:body.exceptions) { out.writeU30(ex.start); out.writeU30(ex.end); out.writeU30(ex.target);
            out.writeU30(ex.type_index); out.writeU30(ex.name_index); }
        out.writeTraits(body.traits);
        return bytes.toByteArray();
    }
    // Change only the original unseen-owner default. All native link/copy
    // handlers stay intact; this widget's remembered choices are not saved.
    static int independentDefaultOffset(ABC abc, MethodBody update) throws Exception {
        require(sha(update.getCodeBytes()).equals(COPY_UPDATE_PIN),
            "Native copy-panel UpdateSimInfo differs from the inspected default contract.");
        nativeHookContract(update,false);
        var code=update.getCode(); code.markOffsets(); var ops=code.code;
        int found=-1;
        for(int i=10;i+9<ops.size();i++) {
            if(!opcode(ops.get(i),0x27) || !opcode(ops.get(i+1),0x61) ||
                    abc.constants.getMultiname(ops.get(i+1).operands[0]).kind != Multiname.MULTINAMEL) continue;
            if(!opcode(ops.get(i-4),0xd0) || !CasBytecodePatch.property(abc,ops.get(i-3),0x66,"mCopyModeData") ||
                    !opcode(ops.get(i-2),0xd0) || !CasBytecodePatch.property(abc,ops.get(i-1),0x66,"mCurrentBaseSimId")) continue;
            require(opcode(ops.get(i-10),0xd0) && CasBytecodePatch.property(abc,ops.get(i-9),0x66,"mCopyModeData") &&
                opcode(ops.get(i-8),0xd0) && CasBytecodePatch.property(abc,ops.get(i-7),0x66,"mCurrentBaseSimId") &&
                CasBytecodePatch.property(abc,ops.get(i-6),0x46,"hasOwnProperty") && ops.get(i-6).operands[1] == 1 &&
                opcode(ops.get(i-5),0x11) && ops.get(i-5).getTargetAddress() == ops.get(i+2).getAddress(),
                "Native unseen-owner guard no longer skips the default write for remembered choices.");
            require(opcode(ops.get(i+2),0xd0) && opcode(ops.get(i+3),0xd0) &&
                CasBytecodePatch.property(abc,ops.get(i+4),0x66,"mCopyModeData") && opcode(ops.get(i+5),0xd0) &&
                CasBytecodePatch.property(abc,ops.get(i+6),0x66,"mCurrentBaseSimId") && opcode(ops.get(i+7),0x66) &&
                abc.constants.getMultiname(ops.get(i+7).operands[0]).kind == Multiname.MULTINAMEL &&
                CasBytecodePatch.property(abc,ops.get(i+8),0x4f,"SetCopyMode") && ops.get(i+8).operands[1] == 1,
                "Native SetCopyMode no longer receives the remembered current owner's Boolean.");
            require(found < 0,"Native copy-panel has multiple unseen-owner default writes.");
            found=(int)ops.get(i).getAddress();
        }
        require(found == 144,"Native copy-panel reviewed default instruction is absent.");
        return found;
    }
    static void verifyIndependentDefaultBytes(MethodBody update, byte[] nativeBytes, int offset) throws Exception {
        require(sha(nativeBytes).equals(COPY_UPDATE_PIN) && offset == 144 && nativeBytes[offset] == (byte)0x27,
            "Native copy-panel reference differs from the inspected default contract.");
        byte[] expected=nativeBytes.clone(); expected[offset]=(byte)0x26;
        require(Arrays.equals(expected,update.getCodeBytes()),
            "Native copy-panel changed outside the single unseen-owner Boolean default.");
        nativeHookContract(update,false);
    }
    static void patchIndependentDefault(ABC abc, InstanceInfo copy) throws Exception {
        MethodBody update=body(abc,copy,"UpdateSimInfo");
        int offset=independentDefaultOffset(abc,update); byte[] nativeBytes=update.getCodeBytes().clone();
        byte[] changed=nativeBytes.clone(); changed[offset]=(byte)0x26;
        // Same-width raw opcode substitution leaves every branch operand,
        // lexical scope, stack bound and exception region unchanged.
        update.setCodeBytes(changed);
        verifyIndependentDefaultBytes(update,nativeBytes,offset);
    }
    static void verifyIndependentDefault(ABC original, ABC saved) throws Exception {
        CasBytecodePatch.prefix(original,saved);
        int sourceIndex=original.findClassByName(COPY_TARGET), savedIndex=saved.findClassByName(COPY_TARGET);
        require(sourceIndex >= 0 && sourceIndex == savedIndex,"Native copy-panel class layout differs.");
        var source=original.instance_info.get(sourceIndex); var candidate=saved.instance_info.get(savedIndex);
        MethodBody update=body(original,source,"UpdateSimInfo");
        int offset=independentDefaultOffset(original,update);
        verifyIndependentDefaultBytes(body(saved,candidate,"UpdateSimInfo"),update.getCodeBytes(),offset);
        ByteArrayOutputStream left=new ByteArrayOutputStream(), right=new ByteArrayOutputStream();
        ABCOutputStream sourceOut=new ABCOutputStream(left), savedOut=new ABCOutputStream(right);
        sourceOut.writeInstanceInfo(source); savedOut.writeInstanceInfo(candidate);
        var sourceClass=original.class_info.get(sourceIndex); var savedClass=saved.class_info.get(savedIndex);
        sourceOut.writeU30(sourceClass.cinit_index); sourceOut.writeTraits(sourceClass.static_traits);
        savedOut.writeU30(savedClass.cinit_index); savedOut.writeTraits(savedClass.static_traits);
        require(Arrays.equals(left.toByteArray(),right.toByteArray()),"Native copy-panel traits or class signature changed.");
        Set<Integer> nativeMethods=new HashSet<>(List.of(source.iinit_index,sourceClass.cinit_index));
        for(Trait trait:source.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter)
            nativeMethods.add(((TraitMethodGetterSetter)trait).method_info);
        for(int index:nativeMethods) {
            MethodBody before=original.findBody(index), after=saved.findBody(index);
            require(before != null && after != null && Arrays.equals(bodyStructure(before,false),bodyStructure(after,false)),
                "Native copy-panel method metadata changed.");
            if(index != update.method_info) require(Arrays.equals(before.getCodeBytes(),after.getCodeBytes()),
                "Native explicit link/copy or widget-memory method changed.");
        }
    }
    static void verifyCleanup(ABC abc, InstanceInfo instance) {
        require(member(abc,instance.super_index).equals("WidgetBase"), "Selector inherited widget cleanup class differs.");
        Namespace ns=abc.constants.getNamespace(abc.constants.getMultiname(instance.super_index).namespace_index);
        require(ns.kind == Namespace.KIND_PACKAGE && abc.constants.getString(ns.name_index).equals("olympus.core.widget"),
            "Selector inherited widget cleanup namespace differs.");
        for(Trait trait:instance.instance_traits.traits) require(!name(abc,trait).equals("Unload"),
            "Selector acquired an unreviewed Unload override.");
        int embedded=abc.findClassByName("olympus.core.widget.WidgetBase");
        if(embedded >= 0) require(CasBytecodePatch.propertyCalls(abc,body(abc,abc.instance_info.get(embedded),"Unload")).contains("RemoveWidgetFunctions"),
            "Embedded WidgetBase cleanup no longer removes widget registrations.");
    }
    static byte[] patch(ABC original, ABC compiled) throws Exception {
        CasBytecodePatch.prefix(original,compiled);
        int target=original.findClassByName(TARGET);
        require(target >= 0 && target == compiled.findClassByName(TARGET) && original.instance_info.size() == compiled.instance_info.size(),
            "Selector class layout differs.");
        var nativeClass=original.instance_info.get(target); var compilerClass=compiled.instance_info.get(target);
        verifyCleanup(original,nativeClass);
        for(Trait trait:nativeClass.instance_traits.traits) require(!name(original,trait).startsWith("apex") && !name(original,trait).startsWith("Apex"),
            "Selector already contains owned observers.");
        var added=ownedTraits(compiled,compilerClass);
        MethodBody initialize=body(original,nativeClass,"Initialize"), refresh=body(original,nativeClass,"HandleRefreshSimIcons");
        int copyIndex=original.findClassByName(COPY_TARGET);
        require(copyIndex >= 0 && copyIndex == compiled.findClassByName(COPY_TARGET),"Native copy-panel class layout differs.");
        var copyClass=original.instance_info.get(copyIndex); MethodBody copyUpdate=body(original,copyClass,"UpdateSimInfo");
        int copyOffset=independentDefaultOffset(original,copyUpdate);
        nativeHookContract(initialize,false); nativeHookContract(refresh,true);
        int scopeDelta=initialize.init_scope_depth-body(compiled,compilerClass,"Initialize").init_scope_depth;
        require(initialize.init_scope_depth == 12 && refresh.init_scope_depth == 12 && scopeDelta == 9 &&
            refresh.init_scope_depth-body(compiled,compilerClass,"HandleRefreshSimIcons").init_scope_depth == scopeDelta,
            "Selector inspected lexical scope differs.");
        int nativeMethods=original.method_info.size(), nativeTraits=nativeClass.instance_traits.traits.size();
        byte[] structure=nativeStructure(original,nativeMethods,target,nativeTraits);
        Map<Integer,byte[]> code=new HashMap<>(), bodies=new HashMap<>();
        for(var b:original.bodies) { require(code.put(b.method_info,b.getCodeBytes().clone()) == null,"Duplicate native selector body.");
            bodies.put(b.method_info,bodyStructure(b,b == initialize || b == refresh)); }
        patchIndependentDefault(original,copyClass);
        List<MethodInfo> methods=new ArrayList<>(original.method_info); List<MethodBody> owned=new ArrayList<>();
        Map<Integer,Integer> remap=new HashMap<>();
        for(Trait trait:added) if(trait instanceof TraitMethodGetterSetter) {
            int old=((TraitMethodGetterSetter)trait).method_info; remap.put(old,methods.size()); methods.add(compiled.method_info.get(old));
            var b=compiled.findBody(old).clone(); b.method_info=remap.get(old);
            b.init_scope_depth+=scopeDelta; b.max_scope_depth+=scopeDelta; owned.add(b);
            ((TraitMethodGetterSetter)trait).method_info=b.method_info;
        }
        // Named private handlers only: no compiler method references survive.
        for(var b:owned) verifySafeBody(compiled, nameForMethod(added,b.method_info,compiled), b);
        compiled.instance_info=original.instance_info; compiled.class_info=original.class_info;
        compiled.script_info=original.script_info; compiled.metadata_info=original.metadata_info; compiled.method_info=methods;
        compiled.bodies=new ArrayList<>(original.bodies); compiled.bodies.addAll(owned);
        nativeClass.instance_traits.traits.addAll(added);
        int initName=traitName(compiled,nativeClass,"ApexSelectorInitialize"), captureName=traitName(compiled,nativeClass,"ApexSelectorCaptureFeed");
        splice(initialize,initName,false); splice(refresh,captureName,true);
        ByteArrayOutputStream out=new ByteArrayOutputStream(); compiled.saveToStream(out);
        byte[] result=out.toByteArray();
        ABC saved=new ABC(new ABCInputStream(new MemoryInputStream(result)),compiled.getSwf(),null);
        CasBytecodePatch.prefix(original,saved);
        require(Arrays.equals(structure,nativeStructure(saved,nativeMethods,target,nativeTraits)), "Native selector class/script/traits/signatures changed.");
        require(saved.bodies.size() == code.size()+METHODS.size() && saved.method_info.size() == nativeMethods+METHODS.size(),
            "Selector method/body inventory differs.");
        for(var row:code.entrySet()) {
            MethodBody b=saved.findBody(row.getKey()); require(b != null,"Serialized native selector body is absent.");
            boolean isInit=row.getKey() == initialize.method_info, isRefresh=row.getKey() == refresh.method_info;
            require(Arrays.equals(bodies.get(row.getKey()),bodyStructure(b,isInit || isRefresh)),"Native selector body metadata changed.");
            if(isInit || isRefresh) verifySplice(b,row.getValue(),isInit ? initName : captureName,isRefresh);
            else if(row.getKey() == copyUpdate.method_info) verifyIndependentDefaultBytes(b,row.getValue(),copyOffset);
            else require(Arrays.equals(row.getValue(),b.getCodeBytes()),"Unowned native selector body changed.");
        }
        ownedTraits(saved,saved.instance_info.get(target)); verifyCleanup(saved,saved.instance_info.get(target));
        return result;
    }
    static String nameForMethod(List<Trait> traits,int index,ABC abc) {
        for(Trait trait:traits) if(trait instanceof TraitMethodGetterSetter && ((TraitMethodGetterSetter)trait).method_info == index) return name(abc,trait);
        throw new IllegalArgumentException("Owned selector method name absent.");
    }
    public static void main(String[] args) throws Exception {
        require(args.length == 3 || args.length == 4,"Use original SWF, compiler SWF, output ABC, optional pinned cleanup-library SWF.");
        require(sha(Files.readAllBytes(Path.of(args[0]))).equals(PIN),
            "Selector resource differs from the pinned installed native bytes.");
        ABC original=CasBytecodePatch.load(args[0]), compiled=CasBytecodePatch.load(args[1]);
        int nativeCount=original.bodies.size(); boolean embedded=original.findClassByName("olympus.core.widget.WidgetBase") >= 0;
        String cleanup="\"cleanup_library_sha256\":null";
        if(args.length == 4) {
            require(sha(Files.readAllBytes(Path.of(args[3]))).equals(CLEANUP_PIN),"Native cleanup library differs from pinned installed bytes.");
            cleanup=verifyExternalCleanup(CasBytecodePatch.load(args[3])); embedded=true;
        }
        byte[] result=patch(original,compiled); Files.write(Path.of(args[2]),result);
        System.out.println("{\"native_method_count\":"+nativeCount+",\"apex_method_count\":5,\"owned_field_count\":4,"+
            "\"unchanged_native_methods\":"+(nativeCount-3)+",\"native_class_script_traits_preserved\":true,"+
            "\"native_initialize_tail_hook_verified\":true,\"native_refresh_entry_hook_verified\":true,"+
            "\"native_bodies_after_hook_stripping_exact\":true,\"native_lexical_scope_preserved\":true,"+
            "\"native_exception_regions\":0,\"unknown_native_exceptions_refused\":true,\"owned_local_scope_indexes_verified\":true,"+
            "\"callback_raw_copy_only_verified\":true,\"service_retained_view_read_only_verified\":true,"+
            "\"exact_widget_registration_linkage_verified\":true,\"initialize_preserves_captured_feed_verified\":true,"+
            "\"independent_occult_sync_default_verified\":true,\"independent_occult_sync_default_scope\":"+
            "\"Unseen base Sim in this selector widget instance only; in-memory explicit choices retained; no cross-session persistence or runtime native-effect proof\","+
            "\"selector_has_no_unload_override\":true,\"inherited_cleanup_bytecode_verified\":"+embedded+","+
            "\"inherited_cleanup_contract\":\"olympus.core.widget.WidgetBase.Unload -> RemoveWidgetFunctions (external native dependency when not embedded)\","+cleanup+"}");
    }
}
