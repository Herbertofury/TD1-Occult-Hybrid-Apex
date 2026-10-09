// Build-time adapter for FFDec's public ABC API. No game-process access.
// Retain native class/script construction, traits and method bytecode; append
// only Apex traits/methods, one Initialize call and one Unload cleanup call.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.ABCInputStream;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;
import com.jpexs.helpers.MemoryInputStream;

public class CasBytecodePatch {
    static ABC load(String path) throws Exception {
        return new SWF(new FileInputStream(path), false).getAbcList().get(0).getABC();
    }
    static String name(ABC abc, Trait trait) {
        return abc.constants.getString(abc.constants.getMultiname(trait.name_index).name_index);
    }
    static void require(boolean condition, String message) {
        if (!condition) throw new IllegalArgumentException(message);
    }
    static void extendReturn(MethodBody body, int methodName, String lifecycle) {
        int returnIndex = -1;
        for (int i = 0; i < body.getCode().code.size(); i++)
            if (body.getCode().code.get(i).definition.instructionCode == 0x47) {
                require(returnIndex == -1, "Native " + lifecycle + " has multiple returns.");
                returnIndex = i;
            }
        require(returnIndex >= 0, "Native " + lifecycle + " return absent.");
        body.insertAll(returnIndex, List.of(new AVM2Instruction(0, 0xd0, new int[0]),
            new AVM2Instruction(0, 0x4f, new int[]{methodName, 0})));
        // FFDec instruction insertion updates the decoded instructions and
        // offsets, but leaves MethodBody's serialized byte cache intact.
        body.setModified();
        body.max_stack = Math.max(body.max_stack, 1);
    }
    static void verifyLifecycle(MethodBody body, byte[] original, int methodName, String lifecycle) {
        require(!Arrays.equals(body.getCodeBytes(), original), "Native " + lifecycle + " hook was not serialized.");
        var code = body.getCode().code;
        require(code.size() >= 3, "Native " + lifecycle + " hook is incomplete.");
        var local = code.get(code.size()-3);
        var call = code.get(code.size()-2);
        var ret = code.get(code.size()-1);
        require(local.definition.instructionCode == 0xd0 && call.definition.instructionCode == 0x4f &&
            Arrays.equals(call.operands, new int[]{methodName, 0}) && ret.definition.instructionCode == 0x47,
            "Native " + lifecycle + " hook does not precede its return.");
    }
    static void extendUnloadPrologue(MethodBody body, int methodName) {
        var code = body.getCode().code;
        require(code.size() >= 3 && code.get(0).definition.instructionCode == 0xd0 &&
            code.get(1).definition.instructionCode == 0x30,
            "Native Unload scope prologue differs from the inspected contract.");
        require(body.exceptions.length == 0, "Native Unload has unreviewed exception regions.");
        // The original scope setup stays first. Stop owned Timer/Socket work
        // BEFORE super.Unload releases native widget registrations/resources.
        body.insertAll(2, List.of(new AVM2Instruction(0, 0xd0, new int[0]),
            new AVM2Instruction(0, 0x4f, new int[]{methodName, 0})));
        body.setModified();
        body.max_stack = Math.max(body.max_stack, 1);
    }
    static void verifyUnloadPrologue(MethodBody body, byte[] original, int methodName) {
        byte[] saved = body.getCodeBytes();
        require(!Arrays.equals(saved, original), "Native Unload hook was not serialized.");
        var code = body.getCode().code;
        require(code.size() >= 5 && code.get(0).definition.instructionCode == 0xd0 &&
            code.get(1).definition.instructionCode == 0x30 && code.get(2).definition.instructionCode == 0xd0 &&
            code.get(3).definition.instructionCode == 0x4f &&
            Arrays.equals(code.get(3).operands, new int[]{methodName, 0}),
            "Native Unload cleanup does not precede original teardown.");
        int hookBytes = saved.length - original.length;
        require(hookBytes > 0 && Arrays.equals(Arrays.copyOfRange(original, 0, 2), Arrays.copyOfRange(saved, 0, 2)) &&
            Arrays.equals(Arrays.copyOfRange(original, 2, original.length), Arrays.copyOfRange(saved, 2+hookBytes, saved.length)),
            "Native Unload body bytes changed outside the owned prologue call.");
    }
    static void prefix(ABC original, ABC compiled) throws Exception {
        for (String kind : List.of("String", "Int", "UInt", "Double", "Namespace", "NamespaceSet", "Multiname")) {
            var pool = original.constants.getClass();
            Method count = pool.getMethod("get" + kind + "Count");
            Method get = pool.getMethod("get" + kind, int.class);
            int n = (Integer)count.invoke(original.constants);
            require((Integer)count.invoke(compiled.constants) >= n, "Constant pool shrank: " + kind);
            for (int i = 1; i < n; i++) {
                Object left = get.invoke(original.constants, i), right = get.invoke(compiled.constants, i);
                boolean same = kind.equals("NamespaceSet") ? Arrays.equals(((NamespaceSet)left).namespaces, ((NamespaceSet)right).namespaces)
                    : String.valueOf(left).equals(String.valueOf(right));
                require(same, "Native constant changed: " + kind + " " + i);
            }
        }
    }
    static Set<String> propertyCalls(ABC abc, MethodBody body) {
        Set<String> calls = new HashSet<>();
        for (var instruction : body.getCode().code) {
            int opcode = instruction.definition.instructionCode;
            if (opcode == 0x46 || opcode == 0x4c || opcode == 0x4f)
                calls.add(abc.constants.getString(abc.constants.getMultiname(instruction.operands[0]).name_index));
        }
        return calls;
    }
    static void verifyTimerPipeline(ABC abc, InstanceInfo instance) {
        Map<String,Set<String>> calls = new HashMap<>();
        for (Trait trait : instance.instance_traits.traits) if (trait instanceof TraitMethodGetterSetter) {
            String key = name(abc, trait);
            if (key.startsWith("Apex"))
                calls.put(key, propertyCalls(abc, abc.findBody(((TraitMethodGetterSetter)trait).method_info)));
        }
        require(calls.containsKey("ApexReadback") && calls.containsKey("ApexComplete"),
            "Owned deferred CAS readback methods are missing.");
        for(String event:List.of("ApexSocketData","ApexSocketConnect","ApexSocketFailure"))
            require(Collections.disjoint(calls.get(event), Set.of("ApexExecute", "ApexReadback", "ApexSnapshot", "ApexComplete", "ApexAccept",
                "ApexFormSelectionContext", "CallGameService", "CallUIService", "SendUIMessage")), "Socket callback executes native CAS work.");
        require(calls.get("ApexSocketConnect").equals(Set.of("split")), "CAS CONNECT callback must queue only.");
        require(calls.get("ApexTick").containsAll(Set.of("CallGameService","ApexSocketSend","connect","addEventListener")),
            "Queued CAS handshake lacks the actual native Timer/Socket constructor path.");
        require(calls.get("ApexTick").containsAll(Set.of("ApexExecute", "ApexReadback", "ApexAccept")),
            "Native Timer does not dispatch both owned command phases.");
        require(Collections.disjoint(calls.get("ApexExecute"), Set.of("ApexReadback", "ApexComplete", "ApexAccept")),
            "CAS mutation phase completes its result before a later Timer tick.");
        require(calls.get("ApexReadback").containsAll(Set.of("ApexSnapshot", "ApexComplete")),
            "Deferred CAS readback does not complete its client snapshot.");
        require(Collections.disjoint(calls.get("ApexReadback"), Set.of("ApexAccept")) &&
            Collections.disjoint(calls.get("ApexComplete"), Set.of("ApexAccept")),
            "CAS accept commit is not isolated to its ACK-armed Timer phase.");
    }
    static void verifyAcceptLinkage(ABC abc, InstanceInfo instance) {
        MethodBody accept = null;
        for (Trait trait : instance.instance_traits.traits)
            if (trait instanceof TraitMethodGetterSetter && name(abc, trait).equals("ApexAccept"))
                accept = abc.findBody(((TraitMethodGetterSetter)trait).method_info);
        require(accept != null, "Owned CAS accept method is missing.");
        int telemetryLoads = 0, telemetryCalls = 0;
        var code = accept.getCode().code;
        for (int index = 0; index < code.size(); index++) {
            var instruction = code.get(index);
            int opcode = instruction.definition.instructionCode;
            if (opcode != 0x60 && opcode != 0x5d && opcode != 0x5e && opcode != 0x66 &&
                opcode != 0x46 && opcode != 0x4c && opcode != 0x4f) continue;
            Multiname member = abc.constants.getMultiname(instruction.operands[0]);
            String memberName = abc.constants.getString(member.name_index);
            require(!"olympus".equals(memberName) && !"extensions".equals(memberName),
                "CAS accept uses an unresolved runtime package lookup.");
            if ("CASTelemetryExtension".equals(memberName)) {
                require(opcode == 0x60 && member.kind == Multiname.QNAME && member.namespace_index > 0,
                    "CAS accept telemetry class is not loaded through its native QName.");
                Namespace namespace = abc.constants.getNamespace(member.namespace_index);
                require(namespace.kind == Namespace.KIND_PACKAGE &&
                    "olympus.extensions".equals(abc.constants.getString(namespace.name_index)),
                    "CAS accept telemetry class has an incorrect package namespace.");
                require(index + 1 < code.size(), "CAS accept telemetry call is missing.");
                var call = code.get(index + 1);
                require(call.definition.instructionCode == 0x4f && call.operands.length == 2 &&
                    call.operands[1] == 0 && "ReportHouseholdSimIDs".equals(abc.constants.getString(
                        abc.constants.getMultiname(call.operands[0]).name_index)),
                    "CAS accept telemetry call is not bound to its native class receiver.");
                telemetryLoads++;
            }
            if ("ReportHouseholdSimIDs".equals(memberName)) telemetryCalls++;
        }
        require(telemetryLoads == 1 && telemetryCalls == 1,
            "CAS accept telemetry linkage inventory differs from the inspected native caller.");
    }
    static MethodBody ownedBody(ABC abc, InstanceInfo instance, String method) {
        for (Trait trait : instance.instance_traits.traits)
            if (trait instanceof TraitMethodGetterSetter && name(abc, trait).equals(method))
                return abc.findBody(((TraitMethodGetterSetter)trait).method_info);
        throw new IllegalArgumentException("Owned CAS method is missing: " + method);
    }
    static boolean property(ABC abc, AVM2Instruction instruction, int opcode, String member) {
        return instruction.definition.instructionCode == opcode && instruction.operands != null &&
            member.equals(abc.constants.getString(abc.constants.getMultiname(instruction.operands[0]).name_index));
    }
    static boolean opcode(AVM2Instruction instruction, int value) {
        return instruction.definition.instructionCode == value;
    }
    static int householdRequestSlot(ABC abc, MethodBody body) {
        var code = body.getCode().code;
        int slot = -1;
        for (int i=0; i+4<code.size(); i++) {
            if (!opcode(code.get(i),0x24) || code.get(i).operands[0]!=6 ||
                !opcode(code.get(i+1),0x66) ||
                abc.constants.getMultiname(code.get(i+1).operands[0]).kind!=Multiname.MULTINAMEL) continue;
            int next=i+2;
            if (opcode(code.get(next),0x70)) next++; // Explicit String().
            require(opcode(code.get(next),0x85) && opcode(code.get(next+1),0x6d),
                "CAS accept household request is not retained as a String slot.");
            require(slot==-1, "CAS accept household request field is read ambiguously.");
            slot=code.get(next+1).operands[0];
        }
        require(slot>=0, "CAS accept household does not originate in wire field 6.");
        return slot;
    }
    static void verifyAcceptHouseholdBinding(ABC abc, InstanceInfo instance) {
        MethodBody readback=ownedBody(abc,instance,"ApexReadback");
        MethodBody accept=ownedBody(abc,instance,"ApexAccept");
        int preflightSlot=householdRequestSlot(abc,readback);
        int expectedSlot=householdRequestSlot(abc,accept);
        var preflight=readback.getCode().code; boolean preflightCompared=false;
        for (int i=0;i+4<preflight.size();i++)
            if (property(abc,preflight.get(i),0x66,"householdId") && opcode(preflight.get(i+1),0x70) &&
                opcode(preflight.get(i+2),0x65) && preflight.get(i+2).operands[0]==1 &&
                opcode(preflight.get(i+3),0x6c) && preflight.get(i+3).operands[0]==preflightSlot &&
                opcode(preflight.get(i+4),0x13)) preflightCompared=true;
        require(preflightCompared, "CAS accept intent does not compare the observed household to its request.");
        var commit=accept.getCode().code; int observedSlot=-1; int nativeCall=-1;
        for (int i=0;i<commit.size();i++) {
            var instruction=commit.get(i);
            if (opcode(instruction,0x2c) && "SaveAndExitCAS".equals(abc.constants.getString(instruction.operands[0])))
                nativeCall=i;
            if (property(abc,instruction,0x66,"householdId") && i+1<commit.size() && opcode(commit.get(i+1),0x70))
                for(int k=i+2;k<=i+6 && k<commit.size();k++)
                    if(opcode(commit.get(k),0x6d)) observedSlot=commit.get(k).operands[0];
        }
        boolean commitCompared=false;
        for(int i=0;i+5<commit.size() && i<nativeCall;i++)
            if(opcode(commit.get(i),0x65) && commit.get(i).operands[0]==1 &&
                opcode(commit.get(i+1),0x6c) && commit.get(i+1).operands[0]==observedSlot &&
                opcode(commit.get(i+2),0x65) && commit.get(i+2).operands[0]==1 &&
                opcode(commit.get(i+3),0x6c) && commit.get(i+3).operands[0]==expectedSlot &&
                opcode(commit.get(i+4),0xab) && opcode(commit.get(i+5),0x96)) commitCompared=true;
        require(observedSlot>=0 && nativeCall>=0 && commitCompared,
            "CAS native commit does not compare its fresh household to the bound request before saving.");
    }
    static boolean builtinInt(ABC abc, AVM2Instruction instruction) {
        if (!property(abc,instruction,0x60,"int")) return false;
        Multiname member=abc.constants.getMultiname(instruction.operands[0]);
        if(member.kind!=Multiname.QNAME || member.namespace_index<=0) return false;
        Namespace namespace=abc.constants.getNamespace(member.namespace_index);
        return namespace.kind==Namespace.KIND_PACKAGE && "".equals(abc.constants.getString(namespace.name_index));
    }
    static int branchTarget(List<AVM2Instruction> code, int at) {
        long address=0;
        for(int i=0;i<at;i++) address+=code.get(i).getBytesLength();
        long target=address+code.get(at).getBytesLength()+code.get(at).operands[0];
        address=0;
        for(int i=0;i<code.size();i++) {
            if(address==target) return i;
            address+=code.get(i).getBytesLength();
        }
        return -1;
    }
    static boolean guardedThrow(ABC abc, List<AVM2Instruction> code, int at) {
        return at>=0 && at+4<code.size() && opcode(code.get(at),0x12) &&
            property(abc,code.get(at+1),0x5d,"Error") && opcode(code.get(at+2),0x2c) &&
            property(abc,code.get(at+3),0x4a,"Error") && opcode(code.get(at+4),0x03) &&
            branchTarget(code,at)>at+4;
    }
    static int trueRefusal(List<AVM2Instruction> code, int branch) {
        int target=branchTarget(code,branch);
        Set<Integer> visited=new HashSet<>();
        // A true operand of the compiler's OR chain only visits these joining
        // dup/iftrue pairs before the final iffalse/throw. It cannot evaluate
        // another getter, native call or arbitrary instruction on that path.
        while(target>=0 && target+1<code.size() && opcode(code.get(target),0x2a) &&
              opcode(code.get(target+1),0x11)) {
            if(!visited.add(target) || visited.size()>16) return -1;
            target=branchTarget(code,target+1);
        }
        return target;
    }
    static boolean slotLoad(List<AVM2Instruction> code, int at, int slot) {
        return at>=0 && at+1<code.size() && opcode(code.get(at),0x65) && code.get(at).operands[0]==1 &&
            opcode(code.get(at+1),0x6c) && code.get(at+1).operands[0]==slot;
    }
    static void verifyAcceptPrimaryLayerOnly(ABC abc, InstanceInfo instance) {
        var preflight=ownedBody(abc,instance,"ApexReadback").getCode().code;
        int typedBranch=-1, zeroBranch=-1, typeCount=0, zeroCount=0;
        for(int i=2;i+5<preflight.size();i++) {
            if(!property(abc,preflight.get(i),0x66,"occultLayer") ||
               !property(abc,preflight.get(i-1),0x66,"sim") || !property(abc,preflight.get(i-2),0x66,"client")) continue;
            if(builtinInt(abc,preflight.get(i+1)) && opcode(preflight.get(i+2),0xb3) &&
               opcode(preflight.get(i+3),0x96) && opcode(preflight.get(i+4),0x2a) && opcode(preflight.get(i+5),0x11)) {
                typedBranch=i+5; typeCount++;
            }
            if(opcode(preflight.get(i+1),0x73) && opcode(preflight.get(i+2),0x24) && preflight.get(i+2).operands[0]==0 &&
               opcode(preflight.get(i+3),0xab) && opcode(preflight.get(i+4),0x96) && opcode(preflight.get(i+5),0x12)) {
                zeroBranch=i+5; zeroCount++;
            }
        }
        require(typeCount==1 && zeroCount==1 && typedBranch<zeroBranch &&
                branchTarget(preflight,typedBranch)==zeroBranch && guardedThrow(abc,preflight,zeroBranch),
                "CAS accept intent lacks an exact typed primary-layer refusal before its acknowledgement.");
        var commit=ownedBody(abc,instance,"ApexAccept").getCode().code;
        int nativeSimSlot=-1, rawLayerSlot=-1, rawLayerRead=-1, nativeSave=-1;
        for(int i=0;i<commit.size();i++) {
            if(opcode(commit.get(i),0x2c) && "SaveAndExitCAS".equals(abc.constants.getString(commit.get(i).operands[0]))) nativeSave=i;
            if(opcode(commit.get(i),0x2c) && "CASGetSimInfo".equals(abc.constants.getString(commit.get(i).operands[0])) && i+5<commit.size() &&
               property(abc,commit.get(i+3),0x46,"CallGameService") && commit.get(i+3).operands[1]==3 &&
               opcode(commit.get(i+4),0x80) && opcode(commit.get(i+5),0x6d)) nativeSimSlot=commit.get(i+5).operands[0];
        }
        int rawCount=0;
        for(int i=2;i+4<commit.size();i++)
            if(property(abc,commit.get(i),0x66,"occultLayer") && slotLoad(commit,i-2,nativeSimSlot) &&
               opcode(commit.get(i+1),0x10) && opcode(commit.get(i+2),0x20) &&
               opcode(commit.get(i+3),0x82) && opcode(commit.get(i+4),0x6d)) {
                rawLayerRead=i; rawLayerSlot=commit.get(i+4).operands[0]; rawCount++;
            }
        typedBranch=-1; zeroBranch=-1; typeCount=0; zeroCount=0;
        for(int i=0;i+7<commit.size();i++) {
            if(!slotLoad(commit,i,rawLayerSlot)) continue;
            if(builtinInt(abc,commit.get(i+2)) && opcode(commit.get(i+3),0xb3) &&
               opcode(commit.get(i+4),0x96) && opcode(commit.get(i+5),0x2a) && opcode(commit.get(i+6),0x11)) {
                typedBranch=i+6; typeCount++;
            }
            if(opcode(commit.get(i+2),0x73) && opcode(commit.get(i+3),0x24) && commit.get(i+3).operands[0]==0 &&
               opcode(commit.get(i+4),0xab) && opcode(commit.get(i+5),0x96) &&
               opcode(commit.get(i+6),0x2a) && opcode(commit.get(i+7),0x11)) {
                zeroBranch=i+7; zeroCount++;
            }
        }
        int refuseAt=typedBranch<0 ? -1 : trueRefusal(commit,typedBranch);
        require(nativeSimSlot>=0 && rawCount==1 && rawLayerSlot>=0 && rawLayerRead<typedBranch &&
                typeCount==1 && zeroCount==1 && typedBranch<zeroBranch && zeroBranch<nativeSave &&
                trueRefusal(commit,zeroBranch)==refuseAt && guardedThrow(abc,commit,refuseAt) && refuseAt+4<nativeSave,
                "CAS native commit lacks a fresh raw typed primary-layer refusal before saving. " +
                "native="+nativeSimSlot+", raw="+rawCount+"/"+rawLayerSlot+"/"+rawLayerRead+
                ", type="+typeCount+"/"+typedBranch+", zero="+zeroCount+"/"+zeroBranch+
                ", refuse="+refuseAt+", save="+nativeSave);
    }
    static void verifyCatalogMetadataLinkage(ABC abc, InstanceInfo instance) {
        var code=ownedBody(abc,instance,"ApexSnapshot").getCode().code;
        int localizedConstructors=0, localizedStrings=0, getterCalls=0;
        for(int i=0;i<code.size();i++) {
            var instruction=code.get(i);
            if(opcode(instruction,0x2c) && "GetCatalogItem".equals(abc.constants.getString(instruction.operands[0])) &&
               i+3<code.size() && property(abc,code.get(i+3),0x46,"CallGameService") && code.get(i+3).operands[1]==2) getterCalls++;
            if(property(abc,instruction,0x46,"toString") && instruction.operands[1]==0) localizedStrings++;
            if(!property(abc,instruction,0x5d,"LocKey") && !property(abc,instruction,0x4a,"LocKey")) continue;
            Multiname member=abc.constants.getMultiname(instruction.operands[0]);
            require(member.kind==Multiname.QNAME && member.namespace_index>0,
                "CAS catalog localization class is not bound to its native QName.");
            Namespace namespace=abc.constants.getNamespace(member.namespace_index);
            require(namespace.kind==Namespace.KIND_PACKAGE && "olympus.localization".equals(abc.constants.getString(namespace.name_index)),
                "CAS catalog localization class has an incorrect package namespace.");
            if(opcode(instruction,0x4a)) {
                require(instruction.operands[1]==1 && i>=4 && property(abc,code.get(i-1),0x66,"title") &&
                    property(abc,code.get(i-4),0x5d,"LocKey") && code.get(i-4).operands[0]==instruction.operands[0],
                    "CAS catalog localization does not consume the native title record.");
                localizedConstructors++;
            }
        }
        require(getterCalls==1 && localizedConstructors==1 && localizedStrings==1,
            "CAS catalog metadata lacks its read-only getter and typed localization contract.");
    }
    static void verifyOwnerObservation(ABC abc, InstanceInfo instance) {
        Set<String> forbidden = Set.of("CallGameService", "CallUIService", "SendUIMessage", "PostServerCommand",
            "ApexExecute", "ApexReadback", "ApexSnapshot", "ApexAccept", "ApexSocketSend", "ApexSocketReply");
        for (String method : List.of("ApexObserveOwnerFeed", "ApexOwnerFeedRow", "ApexOwnerSimRow", "ApexInvalidateOwnerFeed", "ApexOwnerHouseholdProbe"))
            require(Collections.disjoint(propertyCalls(abc, ownedBody(abc, instance, method)), forbidden) &&
                Set.of("ApexOwnerFeedRow", "test", "push", "isFinite").containsAll(propertyCalls(abc, ownedBody(abc, instance, method))),
                "CAS owner feed callback/helper performs native or transport work.");
        for (String method : List.of("ApexInitialize", "ApexDisconnect")) {
            MethodBody body = ownedBody(abc, instance, method);
            String operation = method.equals("ApexInitialize") ? "AddMessageListener" : "RemoveMessageListener";
            int listeners = 0;
            Set<String> events = new HashSet<>();
            var code = body.getCode().code;
            for (int index=0; index<code.size(); index++) if (property(abc, code.get(index), 0x46, operation) ||
                    property(abc, code.get(index), 0x4f, operation)) {
                var call=code.get(index);
                String event=null, callback=null;
                for (int prior=Math.max(0,index-4); prior<index; prior++) {
                    var op=code.get(prior);
                    if (op.definition.instructionCode==0x2c) event=abc.constants.getString(op.operands[0]);
                    for(String candidate:List.of("ApexObserveOwnerFeed","ApexInvalidateOwnerFeed"))
                        if(property(abc,op,0x66,candidate) || property(abc,op,0x60,candidate)) callback=candidate;
                }
                require(call.operands[1]==2 && (("CASRefreshSimIcons".equals(event) && "ApexObserveOwnerFeed".equals(callback)) ||
                    ("CASClearSimsForReset".equals(event) && "ApexInvalidateOwnerFeed".equals(callback))) && events.add(event),
                    "CAS owner listener does not use the exact callback without a class remapping.");
                listeners++;
            }
            require(listeners==2, "CAS owner listener registration/cleanup inventory differs.");
        }
        var body=ownedBody(abc,instance,"ApexOwnerObservation");
        Set<String> calls=propertyCalls(abc,body);
        require(Set.of("CallGameService","CallUIService","ApexOwnerSimRow","ApexOwnerHouseholdProbe","ApexEncode","push").containsAll(calls),
            "CAS owner Timer observation performs native mutation or dispatch.");
        int getters=0;
        List<String> services=new ArrayList<>();
        int selectorReads=0;
        var code=body.getCode().code;
        boolean ticking=false, disconnected=false, earlyReturn=false;
        for(int index=0;index<code.size();index++) if(property(abc,code.get(index),0x46,"CallGameService") ||
                property(abc,code.get(index),0x4f,"CallGameService")) {
            if(getters==0) {
                for(int prior=0;prior<index;prior++) {
                    if(property(abc,code.get(prior),0x60,"apexTicking") || property(abc,code.get(prior),0x66,"apexTicking")) ticking=true;
                    if(property(abc,code.get(prior),0x60,"apexDisconnected") || property(abc,code.get(prior),0x66,"apexDisconnected")) disconnected=true;
                    if(opcode(code.get(prior),0x48)) earlyReturn=true;
                }
                require(ticking && disconnected && earlyReturn, "CAS owner native reads lack their Timer/lifetime gate.");
            }
            String service=null;
            for(int prior=Math.max(0,index-5);prior<index;prior++) {
                var op=code.get(prior);
                if(op.definition.instructionCode==0x2c) service=abc.constants.getString(op.operands[0]);
            }
            require("CASGetSimInfo".equals(service) || "CasGetHouseholdSims".equals(service),
                "CAS owner Timer observation calls an unverified native service.");
            require("CASGetSimInfo".equals(service) ? code.get(index).operands[1]==3 && index>=2 &&
                opcode(code.get(index-2),0x20) && opcode(code.get(index-1),0x26) : code.get(index).operands[1]==1,
                "CAS owner Timer getter argument contract differs from the inspected native caller.");
            getters++;
            services.add(service);
        }
        require(getters==3 && services.equals(List.of("CASGetSimInfo","CasGetHouseholdSims","CASGetSimInfo")) &&
            calls.contains("ApexOwnerSimRow") && calls.contains("ApexOwnerHouseholdProbe"), "CAS owner fresh getter inventory differs.");
        for(int index=0;index<code.size();index++) if(property(abc,code.get(index),0x46,"CallUIService") ||
                property(abc,code.get(index),0x4f,"CallUIService")) {
            require(index>=2 && code.get(index).operands[1]==2 && opcode(code.get(index-1),0x20) &&
                opcode(code.get(index-2),0x2c) && "ApexReadOwnerPairFeed".equals(abc.constants.getString(code.get(index-2).operands[0])),
                "CAS owner selector read does not use the exact owned read-only UI service.");
            selectorReads++;
        }
        require(selectorReads==1, "CAS owner selector read-only service inventory differs.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexSnapshot")).contains("ApexOwnerObservation"),
            "CAS owner observation is absent from the Timer snapshot.");
        // A timer readback, rather than the globally dispatched feed callback,
        // owns the two selected reads and household comparison.
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex") &&
                !name(abc,trait).equals("ApexSnapshot"))
            require(!propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexOwnerObservation"),
                "CAS owner observation has a caller outside the Timer snapshot.");
    }
    static void verifyQueuedHandshake(ABC abc, InstanceInfo instance) {
        var callback=ownedBody(abc,instance,"ApexSocketConnect").getCode().code;
        boolean exactEvent=false, queued=false;
        for(int i=0;i+2<callback.size();i++) {
            if(property(abc,callback.get(i),0x66,"currentTarget") && property(abc,callback.get(i+1),0x60,"apexSocket") &&
                    opcode(callback.get(i+2),0xac)) exactEvent=true;
            if(opcode(callback.get(i),0x26) && property(abc,callback.get(i+1),0x61,"apexHelloPending")) queued=true;
        }
        require(exactEvent && queued && propertyCalls(abc,ownedBody(abc,instance,"ApexSocketConnect")).equals(Set.of("split")),
            "CAS CONNECT callback does not queue its exact Socket event only.");
        var tick=ownedBody(abc,instance,"ApexTick").getCode().code;
        int constructor=-1, listener=-1, getter=-1, hello=-1, consumed=-1, simSlot=-1;
        for(int i=0;i<tick.size();i++) {
            if(property(abc,tick.get(i),0x4a,"Socket") && tick.get(i).operands[1]==0) constructor=i;
            if(i>=4 && (property(abc,tick.get(i),0x46,"addEventListener") || property(abc,tick.get(i),0x4f,"addEventListener")) &&
                    property(abc,tick.get(i-1),0x60,"ApexSocketConnect")) {
                require(tick.get(i).operands[1]==2 && property(abc,tick.get(i-2),0x66,"CONNECT") &&
                    property(abc,tick.get(i-3),0x60,"Event") && property(abc,tick.get(i-4),0x60,"apexSocket"),
                    "CAS queued handshake listener differs from its actual Socket constructor path.");
                listener=i;
            }
            if(opcode(tick.get(i),0x2c)) {
                String value=abc.constants.getString(tick.get(i).operands[0]);
                if("CASGetSimInfo".equals(value)) {
                    require(getter<0 && i+3<tick.size() && opcode(tick.get(i+1),0x20) && opcode(tick.get(i+2),0x26) &&
                        property(abc,tick.get(i+3),0x46,"CallGameService") && tick.get(i+3).operands[1]==3,
                        "CAS queued handshake lacks its exact fresh native Sim getter.");
                    getter=i;
                }
                if("HELLO|".equals(value)) {
                    require(hello<0 && i+4<tick.size() && opcode(tick.get(i+1),0x65) && tick.get(i+1).operands[0]==1 &&
                        opcode(tick.get(i+2),0x6c) && opcode(tick.get(i+3),0xa0) &&
                        property(abc,tick.get(i+4),0x4f,"ApexSocketSend") && tick.get(i+4).operands[1]==1,
                        "CAS queued handshake does not send its exact owned Sim payload.");
                    hello=i; simSlot=tick.get(i+2).operands[0];
                }
            }
            if(i>0 && opcode(tick.get(i-1),0x27) && property(abc,tick.get(i),0x61,"apexHelloPending")) consumed=i;
        }
        boolean originalBound=false;
        for(int i=2;i<tick.size();i++) if(property(abc,tick.get(i),0x61,"apexBoundSim") && slotLoad(tick,i-2,simSlot)) originalBound=true;
        require(getter>=0 && constructor>getter && listener>constructor && consumed>listener && hello>consumed && hello-consumed<=16 && originalBound,
            "CAS handshake native identity/constructor/queued Timer ordering differs.");
    }
    static void verifyExactItemSelection(ABC abc, InstanceInfo instance) {
        var code=ownedBody(abc,instance,"ApexExecute").getCode().code;
        boolean earrings=false, expectedBody=false, exactSwatch=false;
        for(int i=0;i<code.size();i++) {
            if(property(abc,code.get(i),0x66,"EARRINGS") && i>0 && property(abc,code.get(i-1),0x60,"CASBodyType")) earrings=true;
            if(opcode(code.get(i),0x2c)) {
                String value=abc.constants.getString(code.get(i).operands[0]);
                if("Native catalog item's body type differs from the requested panel; no item changed".equals(value))
                    for(int p=Math.max(0,i-14);p<i;p++) if(property(abc,code.get(p),0x66,"body_type")) expectedBody=true;
                if("Choose one exact returned catalog swatch dataID; base/ambiguous variant requests are not changed".equals(value))
                    exactSwatch=i>=3 && opcode(code.get(i-3),0x24) && code.get(i-3).operands[0]==1 && opcode(code.get(i-2),0x13);
            }
        }
        require(earrings && expectedBody, "CAS Earrings selection lacks its exact native BodyType refusal.");
        require(exactSwatch, "CAS item selection lacks its exact one-swatch ambiguity refusal.");
    }
    static void verifyFormSelection(ABC abc, InstanceInfo instance) {
        String helper="ApexFormSelectionContext";
        MethodBody body=ownedBody(abc,instance,helper);
        require(Set.of("CallGameService","CallUIService","ApexOwnerSimRow","ApexEncode","test").containsAll(propertyCalls(abc,body)),
            "CAS form selection preflight performs unreviewed native work.");
        List<String> getters=new ArrayList<>();
        int selectorReads=0;
        var code=body.getCode().code;
        for(int i=0;i<code.size();i++) {
            var instruction=code.get(i);
            if(property(abc,instruction,0x46,"CallGameService") || property(abc,instruction,0x4f,"CallGameService")) {
                String service=null;
                for(int prior=Math.max(0,i-5);prior<i;prior++) if(opcode(code.get(prior),0x2c))
                    service=abc.constants.getString(code.get(prior).operands[0]);
                require(Set.of("CASGetSimInfo","CasGetCASEditMode","CasIsNewFamily","CasIsEnteredFromPlayArea").contains(service),
                    "CAS form selection preflight invokes a native mutation.");
                require("CASGetSimInfo".equals(service) ? instruction.operands[1]==3 && i>=2 &&
                    opcode(code.get(i-2),0x20) && opcode(code.get(i-1),0x26) : instruction.operands[1]==1,
                    "CAS form selection getter argument contract differs.");
                getters.add(service);
            }
            if(property(abc,instruction,0x46,"CallUIService") || property(abc,instruction,0x4f,"CallUIService")) {
                require(i>=2 && instruction.operands[1]==2 && opcode(code.get(i-1),0x20) &&
                    opcode(code.get(i-2),0x2c) && "ApexReadOwnerPairFeed".equals(abc.constants.getString(code.get(i-2).operands[0])),
                    "CAS form selection does not use the exact read-only selector service.");
                selectorReads++;
            }
        }
        require(getters.equals(List.of("CASGetSimInfo","CasGetCASEditMode","CasIsNewFamily","CasIsEnteredFromPlayArea","CASGetSimInfo")) && selectorReads==1,
            "CAS form selection lacks fresh bounded read-only preflight.");
        Set<String> callers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex") &&
                propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains(helper)) callers.add(name(abc,trait));
        require(callers.equals(Set.of("ApexExecute","ApexReadback")), "CAS form selection helper is called outside owned Timer command phases.");
        var execute=ownedBody(abc,instance,"ApexExecute").getCode().code;
        int indexSlot=-1, flagSlot=-1;
        for(int i=0;i+5<execute.size();i++) {
            if(property(abc,execute.get(i),0x66,"selected_index") && opcode(execute.get(i+1),0x73) &&
                    opcode(execute.get(i+2),0x73) && opcode(execute.get(i+3),0x6d))
                indexSlot=execute.get(i+3).operands[0];
            if(property(abc,execute.get(i),0x66,"target_layer") && opcode(execute.get(i+1),0x73) &&
                    opcode(execute.get(i+2),0x24) && execute.get(i+2).operands[0]==0 && opcode(execute.get(i+3),0xaf) &&
                    opcode(execute.get(i+4),0x76) && opcode(execute.get(i+5),0x6d)) flagSlot=execute.get(i+5).operands[0];
        }
        require(indexSlot>0 && flagSlot>0 && indexSlot!=flagSlot, "CAS form selection lacks its typed observed index/layer payloads.");
        List<String> writes=new ArrayList<>();
        for(int i=0;i<execute.size();i++) if(opcode(execute.get(i),0x2c)) {
            String service=abc.constants.getString(execute.get(i).operands[0]);
            if("CasSelectSim".equals(service)) {
                require(i+3<execute.size() && slotLoad(execute,i+1,indexSlot) &&
                    property(abc,execute.get(i+3),0x46,"CallGameService") && execute.get(i+3).operands[1]==2,
                    "CAS form selection does not select its typed already observed index.");
                writes.add(service);
            }
            if("CasSelectOccultForm".equals(service)) {
                require(i+5<execute.size() && opcode(execute.get(i+1),0x2c) &&
                    "select".equals(abc.constants.getString(execute.get(i+1).operands[0])) &&
                    slotLoad(execute,i+2,flagSlot) && opcode(execute.get(i+4),0x55) && execute.get(i+4).operands[0]==1 &&
                    property(abc,execute.get(i+5),0x4f,"CallGameService") && execute.get(i+5).operands[1]==2,
                    "CAS form selection occult payload is not its exact typed select Boolean.");
                writes.add(service);
            }
        }
        require(writes.equals(List.of("CasSelectSim","CasSelectOccultForm")), "CAS form selection native write order/inventory differs.");

    }
    static void verifyCatalogMetadataDisabled(ABC abc, InstanceInfo instance) {
        MethodInfo method=abc.method_info.get(ownedBody(abc,instance,"ApexSnapshot").method_info);
        require(method.param_types.length==1 && method.flagHas_optional() && method.optional.length==1 &&
            method.optional[0].value_kind==ValueKind.CONSTANT_False,
            "CAS catalog bulk metadata must default to disabled until its native contract is proven.");
        int readers=0;
        for(String name:List.of("ApexExecute","ApexReadback","ApexAccept")) {
            for(var instruction:ownedBody(abc,instance,name).getCode().code) {
                if(property(abc,instruction,0x46,"ApexSnapshot")) {
                    require(instruction.operands[1]==0,
                        "CAS catalog unverified bulk metadata cannot be enabled by inventory, history or acceptance.");
                    readers++;
                }
            }
        }
        require(readers>=3,"CAS catalog inventory readers are unavailable for the disabled-query verification.");
    }
    public static void main(String[] args) throws Exception {
        require(args.length == 3, "Use original SWF, compiler SWF, output ABC.");
        ABC original = load(args[0]), compiled = load(args[1]);
        Map<Integer,byte[]> nativeCode = new HashMap<>();
        for (MethodBody body : original.bodies) nativeCode.put(body.method_info, body.getCodeBytes().clone());
        prefix(original, compiled);
        String target = "widgets.CAS.Customizer.CASCustomizerMain";
        int oi = original.findClassByName(target), ci = compiled.findClassByName(target);
        require(oi >= 0 && ci == oi && original.instance_info.size() == compiled.instance_info.size(), "Class layout changed.");
        InstanceInfo nativeClass = original.instance_info.get(oi), newClass = compiled.instance_info.get(ci);
        List<Trait> added = new ArrayList<>();
        Set<Integer> ownedMethods = new HashSet<>();
        Set<String> ownedFields = Set.of("apexWire", "apexReceiving", "apexLastId", "apexLastReply",
            "apexSocket", "apexTimer", "apexFrame", "apexExpected", "apexNonce", "apexBoundSim",
            "apexAwaiting", "apexAckId", "apexDisconnected", "apexSocketActive", "apexHelloPending", "apexSocketError",
            "apexPendingFields", "apexPendingReply", "apexPendingContext", "apexReadbackTick", "apexPendingPhase", "apexClaimNonce", "apexTicking",
            "apexOwnerFeed", "apexOwnerFeedSequence", "apexOwnerSession", "apexOwnerFeedListener", "apexOwnerResetListener");
        Set<String> ownedNames = Set.of("ApexInitialize", "ApexResetSocket", "ApexDisconnect", "ApexTick",
            "ApexSocketConnect", "ApexSocketFailure", "ApexSocketSend", "ApexSocketData", "ApexSocketReply",
            "ApexQuote", "ApexEncode", "ApexSnapshot", "ApexExecute", "ApexReadback", "ApexComplete", "ApexAccept",
            "ApexOwnerFeedRow", "ApexObserveOwnerFeed", "ApexOwnerSimRow", "ApexOwnerObservation", "ApexInvalidateOwnerFeed", "ApexOwnerHouseholdProbe", "ApexFormSelectionContext");
        Set<String> seenNames = new HashSet<>();
        int initializeName = -1, disconnectName = -1;
        for (Trait trait : newClass.instance_traits.traits) {
            String key = name(compiled, trait);
            if (key.startsWith("Apex") || key.startsWith("apex")) {
                require(seenNames.add(key), "Duplicate Apex trait: " + key);
                require(ownedFields.contains(key) && trait instanceof TraitSlotConst ||
                    ownedNames.contains(key) && trait instanceof TraitMethodGetterSetter,
                    "Unreviewed Apex trait: " + key);
                added.add(trait.clone());
                if (trait instanceof TraitMethodGetterSetter) {
                    int method = ((TraitMethodGetterSetter)trait).method_info;
                    ownedMethods.add(method);
                    if (key.equals("ApexInitialize")) initializeName = trait.name_index;
                    if (key.equals("ApexDisconnect")) disconnectName = trait.name_index;
                }
            }
        }
        require(added.size() == ownedFields.size() + ownedNames.size() && initializeName >= 0 && disconnectName >= 0,
            "Unexpected Apex trait inventory.");
        verifyTimerPipeline(compiled, newClass);
        verifyOwnerObservation(compiled, newClass);
        verifyFormSelection(compiled, newClass);
        verifyQueuedHandshake(compiled, newClass);
        verifyExactItemSelection(compiled, newClass);
        verifyAcceptLinkage(compiled, newClass);
        verifyAcceptHouseholdBinding(compiled, newClass);
        verifyAcceptPrimaryLayerOnly(compiled, newClass);
        verifyCatalogMetadataLinkage(compiled, newClass);
        verifyCatalogMetadataDisabled(compiled, newClass);
        MethodBody nativeInit = null, compilerInit = null, nativeUnload = null, compilerUnload = null;
        for (Trait trait : nativeClass.instance_traits.traits) {
            String key = name(original, trait);
            if (key.equals("Initialize")) nativeInit = original.findBody(((TraitMethodGetterSetter)trait).method_info);
            if (key.equals("Unload")) nativeUnload = original.findBody(((TraitMethodGetterSetter)trait).method_info);
        }
        for (Trait trait : newClass.instance_traits.traits) {
            String key = name(compiled, trait);
            if (key.equals("Initialize")) compilerInit = compiled.findBody(((TraitMethodGetterSetter)trait).method_info);
            if (key.equals("Unload")) compilerUnload = compiled.findBody(((TraitMethodGetterSetter)trait).method_info);
        }
        require(nativeInit != null && compilerInit != null && nativeUnload != null && compilerUnload != null,
            "Native lifecycle body missing.");
        int scopeDelta = nativeInit.init_scope_depth - compilerInit.init_scope_depth;
        require(scopeDelta == 9 && nativeUnload.init_scope_depth - compilerUnload.init_scope_depth == scopeDelta,
            "Inspected native lexical scope differs.");
        // Include nested function bodies reached by Apex's newfunction opcodes.
        boolean changed;
        do {
            changed = false;
            for (MethodBody body : compiled.bodies) if (ownedMethods.contains(body.method_info))
                for (AVM2Instruction instruction : body.getCode().code)
                    if (instruction.definition.instructionCode == 0x40 && ownedMethods.add(instruction.operands[0])) changed = true;
        } while (changed);
        // This reviewed fragment uses named handlers, not anonymous functions.
        // Do not let a corrupted compiler reference silently pull a native or
        // otherwise unreviewed method into the owned-method transplant.
        require(ownedMethods.size() == ownedNames.size(), "Unexpected nested Apex function inventory.");
        Map<Integer,Integer> remap = new HashMap<>();
        List<MethodInfo> methods = new ArrayList<>(original.method_info);
        List<MethodBody> newBodies = new ArrayList<>();
        for (int method : new TreeSet<>(ownedMethods)) {
            remap.put(method, methods.size());
            methods.add(compiled.method_info.get(method));
            MethodBody body = compiled.findBody(method);
            require(body != null, "Owned method body missing.");
            newBodies.add(body.clone());
        }
        for (MethodBody body : newBodies) {
            body.method_info = remap.get(body.method_info);
            body.init_scope_depth += scopeDelta; body.max_scope_depth += scopeDelta;
            var code = body.getCode();
            for (int i = 0; i < code.code.size(); i++) {
                var instruction = code.code.get(i);
                // getscopeobject indexes the method's LOCAL scope stack. The
                // added outer lexical scopes do not change that index. Shifting
                // it would select slot 10 in an activation with only two slots,
                // preventing ApexCharacter/ApexExecute from being verified.
                if (instruction.definition.instructionCode == 0x65)
                    require(instruction.operands[0] >= 0 &&
                        instruction.operands[0] < body.max_scope_depth - body.init_scope_depth,
                        "Owned method has an out-of-range local scope index.");
                // Outer-scope addressing needs a separate, reviewed mapping;
                // none of the current Apex methods relies on that instruction.
                require(instruction.definition.instructionCode != 0x67,
                    "Owned method uses unreviewed outer-scope addressing.");
                if (instruction.definition.instructionCode == 0x40 || instruction.definition.instructionCode == 0x44) {
                    require(remap.containsKey(instruction.operands[0]), "Owned function references an unowned compiler method.");
                    instruction.setOperand(0, remap.get(instruction.operands[0]), code, body);
                }
            }
            body.setCode(code);
        }
        compiled.instance_info = original.instance_info;
        compiled.method_info = methods;
        compiled.class_info = original.class_info;
        compiled.script_info = original.script_info;
        compiled.metadata_info = original.metadata_info;
        compiled.bodies = new ArrayList<>(original.bodies);
        compiled.bodies.addAll(newBodies);
        for (Trait trait : added) if (trait instanceof TraitMethodGetterSetter) {
            var method = (TraitMethodGetterSetter)trait; method.method_info = remap.get(method.method_info);
        }
        nativeClass.instance_traits.traits.addAll(added);
        extendReturn(nativeInit, initializeName, "Initialize");
        extendUnloadPrologue(nativeUnload, disconnectName);
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload)
            require(Arrays.equals(nativeCode.get(body.method_info), body.getCodeBytes()), "Unowned native method bytecode changed.");
        ByteArrayOutputStream saved = new ByteArrayOutputStream();
        compiled.saveToStream(saved);
        ABC serialized = new ABC(new ABCInputStream(new MemoryInputStream(saved.toByteArray())), compiled.getSwf(), null);
        verifyLifecycle(serialized.findBody(nativeInit.method_info), nativeCode.get(nativeInit.method_info), initializeName, "Initialize");
        verifyUnloadPrologue(serialized.findBody(nativeUnload.method_info), nativeCode.get(nativeUnload.method_info), disconnectName);
        verifyAcceptLinkage(serialized, serialized.instance_info.get(oi));
        verifyAcceptHouseholdBinding(serialized, serialized.instance_info.get(oi));
        verifyAcceptPrimaryLayerOnly(serialized, serialized.instance_info.get(oi));
        verifyCatalogMetadataLinkage(serialized, serialized.instance_info.get(oi));
        verifyCatalogMetadataDisabled(serialized, serialized.instance_info.get(oi));
        verifyOwnerObservation(serialized, serialized.instance_info.get(oi));
        verifyFormSelection(serialized, serialized.instance_info.get(oi));
        verifyTimerPipeline(serialized, serialized.instance_info.get(oi));
        verifyQueuedHandshake(serialized, serialized.instance_info.get(oi));
        verifyExactItemSelection(serialized, serialized.instance_info.get(oi));
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload)
            require(Arrays.equals(nativeCode.get(body.method_info), serialized.findBody(body.method_info).getCodeBytes()),
                "Serialized unowned native method bytecode changed.");
        Files.write(Path.of(args[2]), saved.toByteArray());
        System.out.println("{\"native_method_count\":" + original.bodies.size() + ",\"apex_method_count\":" + ownedMethods.size() +
            ",\"native_lexical_scope_preserved\":true,\"unchanged_native_methods\":" + (nativeCode.size()-2) +
            ",\"native_initializer_bytecode_extended\":true,\"native_unload_bytecode_extended\":true,\"native_unload_cleanup_precedes_teardown\":true,\"owned_local_scope_indexes_verified\":true,\"serialized_lifecycle_hooks_verified\":true,\"socket_callbacks_data_only_verified\":true,\"timer_command_phases_verified\":true,\"accept_commit_timer_owned_verified\":true,\"accept_native_class_linkage_verified\":true,\"accept_expected_household_bound_verified\":true,\"accept_primary_layer_only_verified\":true,\"catalog_metadata_localization_linkage_verified\":true,\"owner_pair_callback_data_only_verified\":true,\"owner_pair_listener_cleanup_verified\":true,\"owner_pair_timer_read_only_verified\":true,\"socket_connect_queue_only_verified\":true,\"socket_handshake_exact_constructor_timer_verified\":true,\"form_select_timer_owned_verified\":true,\"form_select_exact_same_original_pair_verified\":true,\"form_select_native_argument_order_verified\":true,\"form_select_next_tick_readback_verified\":true,\"earrings_exact_bodytype_and_swatch_guard_verified\":true}");
    }
}
