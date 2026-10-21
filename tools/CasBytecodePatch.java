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
                "ApexFormSelectionContext", "ApexCatalog", "ApexControlExecute", "ApexControlResult", "ApexBodyTypes", "ApexNativeLayers",
                "CallGameService", "CallUIService", "SendUIMessage", "SendMessage", "ApexMemberSelectionContext",
                "ApexResetSocket", "ApexDisconnect", "close", "connect", "ApexSocketSend")), "Socket callback executes native CAS or socket lifecycle work.");
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
    static void verifySocketLifetime(ABC abc, InstanceInfo instance) {
        var failure=ownedBody(abc,instance,"ApexSocketFailure").getCode().code;
        boolean queued=false,ownedFailure=false,ownedData=false;
        for(int i=0;i<failure.size();i++) {
            if(i>0 && opcode(failure.get(i-1),0x26) && property(abc,failure.get(i),0x61,"apexSocketResetPending")) queued=true;
            if(property(abc,failure.get(i),0x66,"currentTarget")) ownedFailure=true;
        }
        for(var op:ownedBody(abc,instance,"ApexSocketData").getCode().code)
            if(property(abc,op,0x66,"currentTarget")) ownedData=true;
        require(queued && ownedFailure && ownedData,"Socket events must own their exact source and queue cleanup only.");
        var tick=ownedBody(abc,instance,"ApexTick").getCode().code;
        int reset=-1,pending=-1,nativeRead=-1;
        for(int i=0;i<tick.size();i++) {
            if(pending<0 && (property(abc,tick.get(i),0x60,"apexSocketResetPending") || property(abc,tick.get(i),0x66,"apexSocketResetPending"))) pending=i;
            if(reset<0 && (property(abc,tick.get(i),0x46,"ApexResetSocket") || property(abc,tick.get(i),0x4f,"ApexResetSocket"))) reset=i;
            if(nativeRead<0 && opcode(tick.get(i),0x2c) && "CASGetSimInfo".equals(abc.constants.getString(tick.get(i).operands[0]))) nativeRead=i;
        }
        require(pending>=0 && pending<reset && reset<nativeRead,"The later UI Timer must process pending socket cleanup before native reads or new work.");
        var send=ownedBody(abc,instance,"ApexSocketSend");var rows=send.getCode().code;
        require(Set.of("charCodeAt","substr","writeUTFBytes","flush","ApexNativeExchange").containsAll(propertyCalls(abc,send)),
            "Socket frame dispatch has an unreviewed copy or native call.");
        int writes=0,flushes=0,retained=-1,issued=-1,lease=-1;boolean retainedArgument=false;
        for(int i=0;i<rows.size();i++) {
            if(property(abc,rows.get(i),0x61,"apexOutboundFrame")) retained=i;
            if(i>0 && opcode(rows.get(i-1),0x26) && property(abc,rows.get(i),0x61,"apexOutboundPending")) lease=i;
            if(property(abc,rows.get(i),0x46,"writeUTFBytes") || property(abc,rows.get(i),0x4f,"writeUTFBytes")) {
                writes++;issued=i;
                retainedArgument=i>0 && (property(abc,rows.get(i-1),0x60,"apexOutboundFrame") || property(abc,rows.get(i-1),0x66,"apexOutboundFrame"));
            }
            if(property(abc,rows.get(i),0x46,"flush") || property(abc,rows.get(i),0x4f,"flush")) flushes++;
        }
        require(writes==1 && flushes==1 && retained>=0 && retained<issued && lease>=0 && lease<issued && retainedArgument,
            "Socket frames require one retained, leased header/body write and one flush.");
        boolean escapesUnicode=false;
        for(var op:ownedBody(abc,instance,"ApexQuote").getCode().code)
            if(opcode(op,0x24) && op.operands[0]==126) escapesUnicode=true;
        require(escapesUnicode,"Socket JSON must escape Unicode so its length is its ASCII byte length.");
        var initialize=ownedBody(abc,instance,"ApexInitialize").getCode().code;
        boolean nativeRequired=false;
        for(int i=1;i<initialize.size();i++)
            if(opcode(initialize.get(i-1),0x26) && property(abc,initialize.get(i),0x61,"apexNativeTransportRequired"))nativeRequired=true;
        require(nativeRequired,"Matching CAS builds must require the native transport before any connection.");
        var exchange=ownedBody(abc,instance,"ApexNativeExchange");
        require(propertyCalls(abc,exchange).equals(Set.of("CallGameService")),"Native pipe exchange reaches an unreviewed service/helper.");
        boolean getter=false,prefix=false;
        for(var op:exchange.getCode().code)if(opcode(op,0x2c)) {
            String literal=abc.constants.getString(op.operands[0]);
            if("GetSimOccult".equals(literal))getter=true;if("APEXUI1|".equals(literal))prefix=true;
        }
        require(getter && prefix,"Native CAS pipe lacks its fixed versioned game-service envelope.");
        require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,"ApexConsumeFrame")),
            Set.of("CallGameService","CallUIService","ApexExecute","ApexReadback","ApexAccept")),
            "Transport frame parsing must not execute a native CAS mutation.");
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
                !Set.of("ApexSnapshot","ApexFormsTick").contains(name(abc,trait)))
            require(!propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexOwnerObservation"),
                "CAS owner observation has a caller outside the Timer snapshot.");
    }
    static void verifyFastOwnerReadback(ABC abc, InstanceInfo instance) {
        for(String method:Set.of("ApexFormsQueueOwner","ApexFormsReadNativeState","ApexInputTiming")) {
            int clocks=0;
            for(var op:ownedBody(abc,instance,method).getCode().code) {
                require(!property(abc,op,0x60,"flash"),"UI clock must not resolve flash as a dynamic scope object.");
                if(property(abc,op,0x46,"getTimer")||property(abc,op,0x4f,"getTimer")) {
                    var q=abc.constants.getMultiname(op.operands[0]);
                    require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                        abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                        "flash.utils".equals(abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index)) &&
                        op.operands[1]==0,"UI clock must call the actual imported flash.utils.getTimer function.");
                    clocks++;
                }
            }
            require(clocks==1,"UI clock must have one exact imported getTimer call per timing method.");
        }
        var queued=propertyCalls(abc,ownedBody(abc,instance,"ApexFormsQueueOwner"));
        require(queued.containsAll(Set.of("ApexFormsScheduleFrame","getTimer")) &&
            Collections.disjoint(queued,Set.of("ApexTick","CallGameService","ApexNativeExchange","ApexFormsOwnedTick")),
            "Form click may enqueue one next-frame intent, never execute native work inline.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexInputTiming")).equals(Set.of("getTimer")),
            "Input timing must only read the clock and update scalar counters.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsObservedSim")).equals(Set.of("test")),
            "Per-frame retained identity must not query or serialize the full household/panel.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsScheduleFrame")).equals(Set.of("addEventListener")),
            "Scheduling a deferred form click must only register the next frame callback.");
        var nextBody=ownedBody(abc,instance,"ApexFormsNextFrame");var next=propertyCalls(abc,nextBody);
        require(next.equals(Set.of("removeEventListener","ApexFormsOwnedTick","ApexFormsObservedSim","ApexFormsScheduleFrame")),
            "Next-frame form callback must detach and process its bound view without waiting for a network poll.");
        var gates=new HashSet<String>();boolean returned=false;
        for(var op:nextBody.getCode().code) {
            for(String gate:Set.of("apexDisconnected","apexTicking","apexPendingFields","apexReceiving","apexPendingPhase","apexNativeConnected","apexBoundSim"))
                if(property(abc,op,0x60,gate)||property(abc,op,0x66,gate))gates.add(gate);
            if(opcode(op,0x47))returned=true;
            if(property(abc,op,0x46,"ApexFormsOwnedTick")||property(abc,op,0x4f,"ApexFormsOwnedTick")) {
                require(returned&&gates.size()==7,"Next-frame form work lacks the connected idle same-Sim/lifetime gate.");break;
            }
        }
        var read=ownedBody(abc,instance,"ApexFormsReadNativeState");
        uniqueLiteral(abc,read,"STATE|");
        var reads=propertyCalls(abc,read);
        require(reads.containsAll(Set.of("ApexNativeExchange","split")) &&
            Collections.disjoint(reads,Set.of("CallGameService","CallUIService","ApexExecute","ApexAccept","ApexFormsOwnedTick")),
            "Fast owner acknowledgement must use only the bound native read, never a CAS mutation.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsDispose")).contains("removeEventListener"),
            "Form frame callback must be detached at widget disposal.");
    }
    static void verifyPairControls(ABC abc, InstanceInfo instance) {
        var clicks=propertyCalls(abc,ownedBody(abc,instance,"ApexPairClick"));
        require(clicks.isEmpty() && Collections.disjoint(clicks,
            Set.of("CallGameService","ApexPairExecute","ApexNativeExchange","ApexTick","ApexExecute")),
            "Retired floating pair controls must not draw or handle input.");
        var panel=propertyCalls(abc,ownedBody(abc,instance,"ApexPairPanel"));
        require(panel.containsAll(Set.of("ApexPairRead","ApexFormsScheduleFrame")) &&
            Collections.disjoint(panel,Set.of("CallGameService","ApexPairExecute","ApexExecute","ApexAccept")),
            "EA pair-panel callback must only validate and queue its exact pair action.");
        var read=ownedBody(abc,instance,"ApexPairRead");uniqueLiteral(abc,read,"PAIR|");
        require(Collections.disjoint(propertyCalls(abc,read),Set.of("CallGameService","ApexPairExecute","ApexExecute")),
            "Pair state is a data-only native read.");
        var execute=ownedBody(abc,instance,"ApexPairExecute");uniqueLiteral(abc,execute,"PAIRDO|");
        require(propertyCalls(abc,execute).containsAll(Set.of("ApexPairRead","ApexNativeExchange","ApexFormsReadNativeState")),
            "Pair action must validate and read back its exact native context.");
        Set<String> callers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexPairExecute"))
            callers.add(name(abc,trait));
        require(callers.equals(Set.of("ApexPairTick","ApexControlExecute")),
            "Only deferred pair intent and typed CLI execution may apply a pair action.");
    }
    static void verifyFormStrip(ABC abc, InstanceInfo instance) {
        verifyFastOwnerReadback(abc,instance);
        verifyPairControls(abc,instance);
        verifyMoleculeSelection(abc,instance);
        var expected=Map.of("ApexFormsTick",List.of("CasGetAvailableOccults","GetOccultIcon"),
            "ApexFormsClick",List.of("CASGetSimInfo"), "ApexFormsOwnedTick",List.of("SetSimOccult","GetOccultIcon"));
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex")) {
            String key=name(abc,trait); var body=abc.findBody(((TraitMethodGetterSetter)trait).method_info);
            var calls=propertyCalls(abc,body);
            if(!Set.of("ApexTick","ApexFormsApply").contains(key)) require(!calls.contains("ApexFormsTick"),"Native strip may run only on its owning UI Timer or typed workspace command.");
            if(!key.startsWith("ApexForms")) continue;
            List<String> services=new ArrayList<>(); var ops=body.getCode().code;
            for(int i=0;i<ops.size();i++) if(property(abc,ops.get(i),0x46,"CallGameService") || property(abc,ops.get(i),0x4f,"CallGameService")) {
                String literal=null;
                for(int p=Math.max(0,i-14);p<i;p++) if(opcode(ops.get(p),0x2c)) {
                    String text=abc.constants.getString(ops.get(p).operands[0]);
                    if(Set.of("CasGetAvailableOccults","GetOccultIcon","CASGetSimInfo","SetSimOccult").contains(text)) literal=text;
                }
                require(literal!=null,"Native form strip invokes an unreviewed game service."); services.add(literal);
            }
            require(services.equals(expected.getOrDefault(key,List.of())),"Native strip service order/inventory differs: "+key);
            require(Collections.disjoint(calls,Set.of("SendMessage","writeUTFBytes","ApexAccept","ApexExecute","ApexControlExecute")),
                "Native form strip bypasses its bounded same-pair navigation.");
            if(calls.contains("SendUIMessage")) {
                require(key.equals("ApexFormsBindUiKind"),"Only bound display metadata may refresh the CAS context menu.");
                int messages=0;
                for(int i=3;i<ops.size();i++) if(property(abc,ops.get(i),0x46,"SendUIMessage") || property(abc,ops.get(i),0x4f,"SendUIMessage")) {
                    require(ops.get(i).operands[1]==2 && stringLiteral(abc,ops.get(i-3),"CASContextMenuSetSimInfo") &&
                        opcode(ops.get(i-2),0xd0) && property(abc,ops.get(i-1),0x66,"mCurrSimInfo"),
                        "Bound display refresh may send only its UI SimInfo to the native context menu.");messages++;
                }
                require(messages==1,"Bound CAS display refresh requires one exact UI message.");
            }
        }
        Set<String> nativeOwnerCallers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexFormsOwnedTick"))
                nativeOwnerCallers.add(name(abc,trait));
        require(nativeOwnerCallers.equals(Set.of("ApexFormsTick","ApexFormsNextFrame")),"Independent form buttons may execute only on the owned strip Timer or guarded next frame.");
        var ownerCode=ownedBody(abc,instance,"ApexFormsOwnedTick").getCode().code;
        boolean tokenLow=false,tokenHigh=false;
        for(var op:ownerCode) if(opcode(op,0x2d)) {
            long value=abc.constants.getInt(op.operands[0]);
            if(value==0x20000000L) tokenLow=true;if(value==0x2fffffffL) tokenHigh=true;
        }
        require(tokenLow && tokenHigh,"Independent owner buttons require the reserved native capability-token bounds.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsTick")).contains("ApexFormSelectionContext"),
            "Native form strip lacks full fresh pair validation.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsOwnedTick")).containsAll(
            Set.of("ApexFormsGroupCatalog","ApexFormsClearTooltips","ApexFormsCompactButton")),
            "Life-state menu lacks grouping, exact owner controls or tooltip cleanup.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsDispose")).contains("ApexFormsClearTooltips") &&
            propertyCalls(abc,ownedBody(abc,instance,"ApexFormsClearTooltips")).contains("Shutdown") &&
            propertyCalls(abc,ownedBody(abc,instance,"ApexFormsTooltip")).contains("Initialize"),
            "Life-state hover descriptions lack the native tooltip lifecycle.");
        var groupCode=ownedBody(abc,instance,"ApexFormsGroupCatalog").getCode().code;
        require(groupCode.stream().anyMatch(op->property(abc,op,0x66,"family")) &&
            groupCode.stream().noneMatch(op->property(abc,op,0x66,"native_kind")),
            "Life-state menu must group exact named families, never native rendering genera.");
    }
    static void verifyMoleculeSelection(ABC abc,InstanceInfo instance) {
        var choose=ownedBody(abc,instance,"ApexMoleculeChooseOccult");
        var calls=propertyCalls(abc,choose);
        require(calls.contains("ApexFormsScheduleFrame") && Collections.disjoint(calls,
            Set.of("ApexFormsOwnedTick","ApexExecute","ApexAccept","ApexPairExecute","ApexFormsQueueOwner")),
            "Molecule click must retain its own deferred intent, never lose it to a busy form queue.");
        boolean retained=false;
        for(var op:choose.getCode().code)if(property(abc,op,0x61,"apexMoleculeIntent"))retained=true;
        require(retained,"Molecule choice must survive a pending CLI readback.");
        var drain=ownedBody(abc,instance,"ApexMoleculeDrain");
        require(propertyCalls(abc,drain).equals(Set.of("ApexClone","CallGameService")),
            "Draining a molecule choice may only check full-edit permission and queue its exact owner.");
        for(var op:choose.getCode().code) require(!property(abc,op,0x46,"CallGameService") && !property(abc,op,0x4f,"CallGameService"),
            "Occult input must not call any native game service inline.");
        int permissions=0;
        for(var op:drain.getCode().code) if(opcode(op,0x2c) && "CasIsForcedFullEditingEnabled".equals(abc.constants.getString(op.operands[0]))) permissions++;
        require(permissions==1,"Deferred occult selection must retain its one native full-edit permission check.");
        for(var op:choose.getCode().code)if(opcode(op,0x2c))require(!"CASGetSimInfo".equals(abc.constants.getString(op.operands[0])),
            "Occult input callback must not synchronize/serialize the native Sim model.");
        var gates=new HashSet<String>();
        for(var op:drain.getCode().code)for(String gate:Set.of("apexBoundSim","apexOwnerSession",
            "apexPendingFields","apexPendingPhase","apexReceiving","apexFormsDesiredId",
            "apexFormsNativeIntent","apexFormsNativeState"))
            if(property(abc,op,0x60,gate)||property(abc,op,0x66,gate))gates.add(gate);
        require(gates.size()==8,"Deferred molecule selection must validate its exact session and idle native owner.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexFormsOwnedTick")).contains("ApexMoleculeDrain"),
            "The selected molecule choice must be consumed by the owned UI lifecycle.");
        var read=ownedBody(abc,instance,"ApexMoleculeReadSelection");
        uniqueLiteral(abc,read,"GetSimOccult");
        require(Collections.disjoint(propertyCalls(abc,read),Set.of("ApexExecute","ApexAccept","ApexPairExecute","ApexFormsOwnedTick")),
            "Molecule highlight observation must not mutate a form.");
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
    static void verifyOwnerMetadataReadback(ABC abc, InstanceInfo instance) {
        var body=ownedBody(abc,instance,"ApexReadback");
        var code=body.getCode();code.markOffsets();var rows=code.code;
        int p=uniqueLiteral(abc,body,"POLL|");
        require(p>=18 && p+9<rows.size(),"Owner metadata readback is truncated.");
        require(property(abc,rows.get(p-13),0x66,"owner_deadline_tick") && opcode(rows.get(p-11),0x0c),
            "Owner metadata poll lost its bounded readback deadline.");
        require(property(abc,rows.get(p-10),0x60,"apexOutboundPending") && opcode(rows.get(p-9),0x96) &&
            opcode(rows.get(p-8),0x12) && rows.get(p-8).getTargetAddress()==rows.get(p+4).getAddress(),
            "Owner metadata poll can overwrite its outstanding transport frame.");
        require(stringLiteral(abc,rows.get(p-6),"poll|") && property(abc,rows.get(p-5),0x60,"apexTimer") &&
            property(abc,rows.get(p-4),0x66,"currentCount") && opcode(rows.get(p-3),0xa0) &&
            property(abc,rows.get(p-2),0x61,"apexAwaiting"),"Owner metadata reply lost its poll-stage ownership.");
        require(property(abc,rows.get(p-1),0x5d,"ApexSocketSend") && property(abc,rows.get(p+1),0x60,"apexNonce") &&
            opcode(rows.get(p+2),0xa0) && property(abc,rows.get(p+3),0x4f,"ApexSocketSend") &&
            rows.get(p+3).operands[1]==1,"Owner metadata poll does not retain its exact owning nonce/send.");
        for(int i=p-10;i<=p+3;i++) require(!property(abc,rows.get(i),0x46,"CallGameService") &&
            !property(abc,rows.get(i),0x4f,"CallGameService"),"Owner metadata poll executes an additional native action.");
    }
    static void verifyCatalogVariantReadback(ABC abc,InstanceInfo instance) {
        var body=ownedBody(abc,instance,"ApexReadback");var rows=body.getCode().code;
        int palette=uniqueLiteral(abc,body,"CasGetSwatchColorList");
        int wing=uniqueLiteral(abc,body,"Native wing base and color did not both read back exactly")-56;
        require(wing>=0 && wing+51<rows.size() && opcode(rows.get(wing+51),0x6c),
            "Catalog variant readback lacks its known exact requested-value slot.");
        int valueSlot=rows.get(wing+51).operands[0],count=0;
        for(int i=1;i+3<palette;i++) if(property(abc,rows.get(i),0x66,"selection_variant_id") &&
            opcode(rows.get(i+1),0x70) && opcode(rows.get(i+2),0x85) && opcode(rows.get(i+3),0x6d) &&
            rows.get(i+3).operands[0]==valueSlot) count++;
        require(count==1,"Exact child variant is not normalized before native palette completion.");
    }
    static int settledBootstrapAssignment(ABC abc,InstanceInfo instance) {
        var rows=ownedBody(abc,instance,"ApexFormsOwnedTick").getCode().code;int found=-1;
        for(int i=3;i+3<rows.size();i++) if(property(abc,rows.get(i),0x61,"apexFormsBootstrap") &&
            property(abc,rows.get(i-3),0x60,"apexFormsNativeState") && stringLiteral(abc,rows.get(i-2),"bound") &&
            opcode(rows.get(i-1),0xab)) {
            require(found<0,"Duplicate settled-owner bootstrap assignment.");found=i;
        }
        require(found>=0,"Already-bound native owner is not recognized before bootstrap.");return found;
    }
    static void verifySettledOwnerBootstrap(ABC abc,InstanceInfo instance) {
        var rows=ownedBody(abc,instance,"ApexFormsOwnedTick").getCode().code;
        int i=settledBootstrapAssignment(abc,instance);
        require(property(abc,rows.get(i+1),0x60,"apexFormsBootstrap") && opcode(rows.get(i+2),0x96) &&
            opcode(rows.get(i+3),0x12),"Native bootstrap rebinds an already-bound owner.");
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
    static void verifyTypedControls(ABC abc, InstanceInfo instance) {
        // Execute: four palette calls, two physique calls, preset write,
        // one product lookup, two family queries, equipped query, clear and
        // layered write. Result: preset query and palette query on next tick.
        // The existing-member view adds five reviewed calls: current Sim,
        // available occults, full-edit permission, edit mode and SetSimOccult.
        // Its next-tick result adds one available-occults readback.
        Map<String,Integer> counts=Map.of("ApexCatalog",1,"ApexControlExecute",35,"ApexControlResult",5,
            "ApexBodyTypes",1,"ApexNativeLayers",2);
        var snapshot=ownedBody(abc,instance,"ApexSnapshot").getCode().code;
        int detached=0;
        for(int i=0;i<snapshot.size();i++) if(property(abc,snapshot.get(i),0x46,"CallGameService")) {
            int next=i+1;
            while(next<snapshot.size() && (opcode(snapshot.get(next),0x80) || opcode(snapshot.get(next),0x82))) next++;
            require(next<snapshot.size() && property(abc,snapshot.get(next),0x46,"ApexClone") &&
                snapshot.get(next).operands[1]==1, "Native CAS inventory retains a borrowed getter record.");
            detached++;
        }
        require(detached>0, "Native CAS detached inventory has no verified native getters.");
        for(var entry:counts.entrySet()) {
            var body=ownedBody(abc,instance,entry.getKey());
            int calls=0;
            for(var op:body.getCode().code)
                if(property(abc,op,0x46,"CallGameService") || property(abc,op,0x4f,"CallGameService")) calls++;
            require(calls==entry.getValue(), "Typed CAS native service call inventory changed: "+entry.getKey()+" "+calls);
            require(Collections.disjoint(propertyCalls(abc,body), Set.of("PostServerCommand","connect","SaveAndExitCAS")),
                "Typed CAS control reaches an unrelated transport or native accept path.");
            int uiCalls=0;
            for(var op:body.getCode().code)if(property(abc,op,0x46,"CallUIService") || property(abc,op,0x4f,"CallUIService")) {
                uiCalls++;require(entry.getKey().equals("ApexControlExecute") && op.operands[1]==2,
                    "Typed CAS control has an unreviewed UI service call.");
            }
            require(uiCalls==(entry.getKey().equals("ApexControlExecute")?1:0),"Typed pair-panel refresh inventory differs.");
            if(uiCalls==1)uniqueLiteral(abc,body,"ApexConfigureFormPortraits");
        }
        require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,"ApexClone")),
            Set.of("CallGameService","CallUIService","SendUIMessage")), "Detached native data copier performs native work.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexBodyTypes")).containsAll(
            Set.of("GetSelected","GetSelectedIndices","SetSelection","dispatchEvent")) &&
            Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,"ApexBodyTypes")),
                Set.of("OnTabRight","OnTabLeft","HighlightSelectedItem","CallUIService","SetCatalogSlotSelected")),
            "Body-region navigation does not use the inspected PC selection grid.");
        var regionCode=ownedBody(abc,instance,"ApexBodyTypes").getCode().code;
        int regionDefinitions=0;
        for(int i=0;i+1<regionCode.size();i++) if(property(abc,regionCode.get(i),0x60,"TattooBodyData") &&
                property(abc,regionCode.get(i+1),0x66,"DATA")) regionDefinitions++;
        require(regionDefinitions==1,"Native tattoo definitions lack their exact imported class/data access.");
        verifyLiteralServices(abc,ownedBody(abc,instance,"ApexBodyTypes"),Map.of("CASGetSimInfo",3));
        verifyLiteralServices(abc,ownedBody(abc,instance,"ApexNativeLayers"),
            Map.of("CasHasPartOrTattooPaintLayer",2,"CasGetPartTattooPaintLayerPresent",2));
        for(String target:List.of("ApexControlExecute","ApexControlResult","ApexBodyTypes")) {
            Set<String> callers=new HashSet<>();
            for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex") &&
                propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains(target)) callers.add(name(abc,trait));
            require(callers.equals(Set.of(target.equals("ApexControlExecute") ? "ApexExecute" :
                target.equals("ApexControlResult") ? "ApexReadback" : "ApexControlExecute")),
                "Typed CAS control is called outside its owned Timer phase: "+target);
        }
        Set<String> layerCallers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex") &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexNativeLayers")) layerCallers.add(name(abc,trait));
        require(layerCallers.equals(Set.of("ApexControlExecute","ApexControlResult")),
            "Native layer inspection is called outside its exact owned control phases.");
        int viewSetters=0;
        var viewCode=ownedBody(abc,instance,"ApexControlExecute").getCode().code;
        for(int i=0;i<viewCode.size();i++) if(stringLiteral(abc,viewCode.get(i),"SetSimOccult")) {
            viewSetters++;
            require(i+2<viewCode.size() && opcode(viewCode.get(i+1),0x62) && viewCode.get(i+1).operands[0]==4 &&
                (property(abc,viewCode.get(i+2),0x46,"CallGameService") || property(abc,viewCode.get(i+2),0x4f,"CallGameService")) &&
                viewCode.get(i+2).operands[1]==2,
                "Occult view must call the literal native setter with its typed existing-kind index only.");
        }
        require(viewSetters==2,"Existing-kind and staged-owner native setter inventory changed.");
    }
    static void verifyPhysiqueGesture(ABC abc, InstanceInfo instance) {
        var start=ownedBody(abc,instance,"ApexControlExecute").getCode().code;
        var finish=ownedBody(abc,instance,"ApexReadback").getCode().code;
        int preview=-1,commit=-1,armed=-1,consumed=-1;boolean previewValue=false,commitValue=false,ownerGuard=false;
        for(int pass=0;pass<2;pass++) {
            var rows=pass==0?start:finish;int setters=0;
            for(int i=0;i<rows.size();i++) {
                if(opcode(rows.get(i),0x2c)) {
                    String text=abc.constants.getString(rows.get(i).operands[0]);
                    if("slider_mouse_up".equals(text) && i+1<rows.size()) {
                        if(pass==0 && opcode(rows.get(i+1),0x27)) previewValue=true;
                        if(pass==1 && opcode(rows.get(i+1),0x26)) commitValue=true;
                    }
                    if("SetSimPhysiqueValue".equals(text)) {
                        for(int n=i+1;n<Math.min(i+6,rows.size());n++)
                            if(property(abc,rows.get(n),0x46,"CallGameService") || property(abc,rows.get(n),0x4f,"CallGameService")) {
                                setters++;if(pass==0) preview=n;else commit=n;break;
                            }
                    }
                    if(pass==1 && "Native physique preview changed owner; no completion replay".equals(text)) ownerGuard=true;
                }
                if(i>0 && property(abc,rows.get(i),0x61,"physique_commit_pending")) {
                    if(pass==0 && opcode(rows.get(i-1),0x26)) armed=i;
                    if(pass==1 && opcode(rows.get(i-1),0x27)) consumed=i;
                }
            }
            require(setters==1,"Physique gesture must issue one preview and one later completion, never duplicate native setters.");
        }
        require(previewValue && commitValue && armed>=0 && armed<preview && consumed>=0 && consumed<commit && ownerGuard,
            "Physique gesture lacks preview/completion ordering, consumed one-shot state or exact-owner preview refusal.");
        for(int i=0;i<commit;i++) {
            if(opcode(finish.get(i),0x2c))
                require(!"CASGetSimInfo".equals(abc.constants.getString(finish.get(i).operands[0])),
                    "Full Sim synchronization must follow native slider completion, never run inside its preview.");
            require(!property(abc,finish.get(i),0x46,"ApexSnapshot") && !property(abc,finish.get(i),0x4f,"ApexSnapshot"),
                "A full appearance snapshot cannot run before slider completion.");
        }
        boolean timerGuard=false;
        for(var op:ownedBody(abc,instance,"ApexTick").getCode().code)
            if(property(abc,op,0x66,"physique_commit_pending")) timerGuard=true;
        require(timerGuard,"The owning Timer must avoid full Sim reads during its pending physique gesture.");
    }
    static void verifyLiteralServices(ABC abc,MethodBody body,Map<String,Integer> expected) {
        Set<String> observed=new HashSet<>();
        var code=body.getCode().code;
        for(int i=0;i<code.size();i++) if(property(abc,code.get(i),0x46,"CallGameService") ||
                property(abc,code.get(i),0x4f,"CallGameService")) {
            int argc=code.get(i).operands[1]; int literal=i-argc;
            require(literal>=0 && opcode(code.get(literal),0x2c),"Native region/layer service name is not a literal getter.");
            String service=abc.constants.getString(code.get(literal).operands[0]);
            require(expected.containsKey(service) && expected.get(service)==argc && observed.add(service),
                "Native region/layer inspection reaches an unreviewed or duplicate service: "+service);
        }
        require(observed.equals(expected.keySet()),"Native region/layer inspection lacks its exact getter inventory.");
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
        require(callers.equals(Set.of("ApexExecute","ApexReadback","ApexFormsTick")), "CAS form selection helper is called outside owned Timer command phases.");
        var execute=ownedBody(abc,instance,"ApexExecute").getCode().code;
        int dispatches=0;
        Set<String> required=Set.of("request_id","sim_id","index","expected_layer","target_layer","target_kind","feed_sequence");
        for(int i=0;i<execute.size();i++) if(stringLiteral(abc,execute.get(i),"ApexNavigateOwnerLayer")) {
            int at=i+1; Set<String> keys=new HashSet<>(); int pairs=0;
            for(;at<execute.size();at++) {
                var op=execute.get(at);
                if(opcode(op,0x2c)) {
                    String text=abc.constants.getString(op.operands[0]);
                    require(required.contains(text) && keys.add(text),"CAS navigation has an unexpected/duplicate typed field."); pairs++;
                }
                if(opcode(op,0x55)) {
                    require(op.operands[0]==7 && pairs==7 && keys.equals(required),"CAS navigation lacks its complete exact typed fields.");
                    require(at+1<execute.size() && property(abc,execute.get(at+1),0x46,"CallUIService") && execute.get(at+1).operands[1]==2,
                        "CAS navigation bypasses the complete native selector handler.");break;
                }
            }
            require(at<execute.size(),"CAS navigation payload is incomplete.");dispatches++;
        }
        require(dispatches==1,"CAS navigation requires exactly one complete native selector dispatch.");
        Set<String> properties=new HashSet<>();
        for(var op:execute) if(opcode(op,0x66)) properties.add(abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index));
        require(properties.containsAll(Set.of("selected_index","selected_layer","target_layer","form_flags","feed_sequence")),
            "CAS navigation fields do not originate from its fresh pair preflight.");
        for(var op:execute) if(opcode(op,0x2c)) require(!Set.of("CasSelectSim","CasSelectOccultForm").contains(abc.constants.getString(op.operands[0])),
            "CAS navigation duplicated the native selector's low-level writes.");
    }
    static void verifyMemberSelection(ABC abc, InstanceInfo instance) {
        MethodBody helper=ownedBody(abc,instance,"ApexMemberSelectionContext");
        require(Set.of("ApexOwnerSimRow","CallGameService","CallUIService","push","test","ApexEncode").containsAll(propertyCalls(abc,helper)),
            "Member navigation preflight invokes an unreviewed member.");
        var inspection=helper.getCode().code;
        Set<String> memberReads=new HashSet<>();
        for(int i=0;i<inspection.size();i++) if(property(abc,inspection.get(i),0x46,"CallGameService")) {
            int arguments=inspection.get(i).operands[1];
            require((arguments==1 || arguments==3) && i>=arguments && opcode(inspection.get(i-arguments),0x2c),
                "Member navigation native read is not one literal typed service.");
            String service=abc.constants.getString(inspection.get(i-arguments).operands[0]);
            require(Set.of("CASGetSimInfo","CasGetCASEditMode","CasIsNewFamily","CasIsEnteredFromPlayArea").contains(service) &&
                memberReads.add(service) && arguments==(service.equals("CASGetSimInfo")?3:1),
                "Member navigation uses an unreviewed native read or repeats one.");
        }
        require(memberReads.size()==4,"Member navigation lacks fresh native identity/mode/entry reads.");
        int reads=0;
        for(int i=0;i<inspection.size();i++) if(property(abc,inspection.get(i),0x46,"CallUIService")) {
            require(i>=2 && inspection.get(i).operands[1]==2 && opcode(inspection.get(i-1),0x20) &&
                opcode(inspection.get(i-2),0x2c) && "ApexReadOwnerPairFeed".equals(
                    abc.constants.getString(inspection.get(i-2).operands[0])),
                "Member navigation uses an unreviewed selector service.");
            reads++;
        }
        require(reads==1,"Member navigation lacks its bounded retained selector read.");
        for(String phase:List.of("ApexExecute","ApexReadback"))
            require(propertyCalls(abc,ownedBody(abc,instance,phase)).contains("ApexMemberSelectionContext"),
                "Member navigation lacks fresh next-tick destination validation.");
        var code=ownedBody(abc,instance,"ApexExecute").getCode().code;
        int calls=0, indexSlot=-1;
        for(int i=0;i+3<code.size();i++) if(property(abc,code.get(i),0x66,"target_index") &&
                opcode(code.get(i+1),0x73) && opcode(code.get(i+2),0x73) && opcode(code.get(i+3),0x6d))
            indexSlot=code.get(i+3).operands[0];
        require(indexSlot>0,"Member navigation lacks its typed validated target index.");
        for(int i=0;i<code.size();i++) if(property(abc,code.get(i),0x4f,"SendMessage") || property(abc,code.get(i),0x46,"SendMessage")) {
            require(i>=4 && code.get(i).operands[1]==2 && opcode(code.get(i-3),0x2c) &&
                "CASSelectSim".equals(abc.constants.getString(code.get(i-3).operands[0])) &&
                property(abc,code.get(i-4),0x60,"CommunicationManager") && slotLoad(code,i-2,indexSlot),
                "Member navigation must dispatch only the installed CASSelectSim handler.");
            calls++;
        }
        require(calls==1,"Member navigation requires exactly one native selector dispatch.");
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
    static void verifyEyebrowPaletteWidget(ABC abc, InstanceInfo instance) {
        Set<String> calls=propertyCalls(abc,ownedBody(abc,instance,"ApexSelectEyebrowSwatch"));
        require(calls.containsAll(Set.of("IsEnabled","SetType","SetSelection","GetSelectedIndices","GetDataFeed","RequestItemsAt","ApexClone")) &&
            !calls.contains("CallGameService") && !calls.contains("SetData"),
            "Eyebrow colors must use the native widget lifecycle, without a second direct native setter.");
        Set<String> callers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexSelectEyebrowSwatch"))
            callers.add(name(abc,trait));
        require(callers.equals(Set.of("ApexControlExecute","ApexReadback")),
            "Eyebrow palette selection is allowed only in owned command/next-tick phases.");
    }

    static boolean stringLiteral(ABC abc, AVM2Instruction instruction, String value) {
        return opcode(instruction,0x2c) && value.equals(abc.constants.getString(instruction.operands[0]));
    }
    static int uniqueLiteral(ABC abc, MethodBody body, String value) {
        int found=-1;
        for(int i=0;i<body.getCode().code.size();i++) if(stringLiteral(abc,body.getCode().code.get(i),value)) {
            require(found<0,"Wing readback has duplicate native contract literal: "+value); found=i;
        }
        require(found>=0,"Wing readback lacks native contract literal: "+value); return found;
    }
    static int uniqueProperty(ABC abc, MethodBody body, int opcode, String name) {
        int found=-1;
        for(int i=0;i<body.getCode().code.size();i++) if(property(abc,body.getCode().code.get(i),opcode,name)) {
            require(found<0,"Wing observation has duplicate property: "+name); found=i;
        }
        require(found>=0,"Wing observation lacks property: "+name); return found;
    }
    static void verifyWingObservation(ABC abc, InstanceInfo instance) {
        MethodBody body=ownedBody(abc,instance,"ApexWingObservation");
        var code=body.getCode(); code.markOffsets(); var rows=code.code;
        require(abc.method_info.get(body.method_info).param_types.length==0 && (abc.method_info.get(body.method_info).flags & 1)==0,
            "Wing observation must have no caller-provided query arguments.");
        Set<String> calls=propertyCalls(abc,body);
        require(Set.of("ApexClone","CallGameService","GetCatalogFilter","push").containsAll(calls),
            "Wing observation performs a native write or unreviewed helper call.");
        int base=uniqueLiteral(abc,body,"GetCatalogBaseItemSelected"), color=uniqueLiteral(abc,body,"GetCatalogVariantItemSelected");
        require(base>40 && color>base+10 && color+6<rows.size(),"Wing observation getter ordering differs.");
        int panel=uniqueProperty(abc,body,0x66,"CLOTHING_BODY_WINGS");
        require(panel>2 && property(abc,rows.get(panel-2),0x66,"mCurrState") && property(abc,rows.get(panel-1),0x60,"MenuState") &&
            opcode(rows.get(panel+1),0xab) && opcode(rows.get(panel+2),0x96) && opcode(rows.get(panel+4),0x11) &&
            rows.get(panel+4).getTargetAddress()==rows.get(panel+10).getAddress() &&
            property(abc,rows.get(panel+7),0x66,"mCurrentPanel") && opcode(rows.get(panel+8),0x20) &&
            opcode(rows.get(panel+9),0xab) && opcode(rows.get(panel+11),0x11) &&
            rows.get(panel+11).getTargetAddress()==rows.get(panel+17).getAddress() &&
            property(abc,rows.get(panel+14),0x66,"mCurrentPanel") && property(abc,rows.get(panel+15),0x66,"visible") &&
            opcode(rows.get(panel+16),0x96) && opcode(rows.get(panel+17),0x12) &&
            rows.get(panel+17).getTargetAddress()==rows.get(panel+39).getAddress() && opcode(rows.get(panel+38),0x48) && panel+39<base,
            "Wing observation lacks the exact current/visible panel refusal before native reads.");
        require(property(abc,rows.get(base-1),0x60,"CommunicationManager") && property(abc,rows.get(base-2),0x5d,"ApexClone") &&
            opcode(rows.get(base+1),0x65) && opcode(rows.get(base+2),0x6c) && opcode(rows.get(base+3),0x26) &&
            property(abc,rows.get(base+4),0x46,"CallGameService") && rows.get(base+4).operands[1]==3 &&
            property(abc,rows.get(base+5),0x46,"ApexClone") && rows.get(base+5).operands[1]==1 &&
            opcode(rows.get(base+6),0x82) && opcode(rows.get(base+7),0x6d),
            "Wing observation base getter signature, native true flag or immediate detachment differs.");
        int baseSlot=rows.get(base+7).operands[0], argsSlot=rows.get(base+2).operands[0];
        int args=uniqueLiteral(abc,body,"state");
        int[] argsOps={0x2c,0xd0,0x66,0x2c,0x5d,0x65,0x6c,0x66,0x46,0x2c,0x5d,0x65,0x6c,0x66,0x46,0x2c,0x24,0x2c,0x24,0x55,0x80,0x6d};
        for(int i=0;i<argsOps.length;i++) require(opcode(rows.get(args+i),argsOps[i]),"Wing observation native base query arguments differ.");
        require(property(abc,rows.get(args+2),0x66,"mCurrState") && stringLiteral(abc,rows.get(args+3),"tags") &&
            property(abc,rows.get(args+4),0x5d,"ApexClone") && property(abc,rows.get(args+7),0x66,"tags") &&
            property(abc,rows.get(args+8),0x46,"ApexClone") && rows.get(args+8).operands[1]==1 &&
            stringLiteral(abc,rows.get(args+9),"excludeTags") && property(abc,rows.get(args+10),0x5d,"ApexClone") &&
            property(abc,rows.get(args+13),0x66,"excludeTags") && property(abc,rows.get(args+14),0x46,"ApexClone") &&
            rows.get(args+14).operands[1]==1 && stringLiteral(abc,rows.get(args+15),"bodyType") && rows.get(args+16).operands[0]==0 &&
            stringLiteral(abc,rows.get(args+17),"layer") && rows.get(args+18).operands[0]==-1 && rows.get(args+19).operands[0]==5 &&
            rows.get(args+21).operands[0]==argsSlot,"Wing observation lacks copied filter arrays/NONE body/-1 layer.");
        int argsEvidence=uniqueProperty(abc,body,0x61,"base_arguments");
        require(argsEvidence<base && property(abc,rows.get(argsEvidence-1),0x46,"ApexClone") &&
            rows.get(argsEvidence-1).operands[1]==1 && opcode(rows.get(argsEvidence-2),0x6c) &&
            rows.get(argsEvidence-2).operands[0]==argsSlot,"Wing observation does not retain the exact owned base query arguments.");
        require(property(abc,rows.get(color-1),0x60,"CommunicationManager") && property(abc,rows.get(color-2),0x5d,"ApexClone") &&
            property(abc,rows.get(color+1),0x60,"CASBodyType") && property(abc,rows.get(color+2),0x66,"WINGS") &&
            property(abc,rows.get(color+3),0x46,"CallGameService") && rows.get(color+3).operands[1]==2 &&
            property(abc,rows.get(color+4),0x46,"ApexClone") && rows.get(color+4).operands[1]==1 &&
            opcode(rows.get(color+5),0x82) && opcode(rows.get(color+6),0x6d),
            "Wing observation color getter does not preserve the raw native WINGS value.");
        int colorSlot=rows.get(color+6).operands[0];
        require(baseSlot!=colorSlot,"Wing observation base and color raw values alias.");
        for(var entry:Map.of("base_return_type",baseSlot,"selected_color_type",colorSlot).entrySet()) {
            int at=uniqueProperty(abc,body,0x61,entry.getKey());
            require(opcode(rows.get(at-1),0x95) && opcode(rows.get(at-2),0x6c) && rows.get(at-2).operands[0]==entry.getValue(),
                "Wing observation coerces or substitutes the raw native type: "+entry.getKey());
        }
        for(var entry:Map.of("selected_base_ids",baseSlot,"selected_color_id",colorSlot).entrySet()) {
            int at=uniqueProperty(abc,body,0x61,entry.getKey());
            require(opcode(rows.get(at-1),0x6c) && rows.get(at-1).operands[0]==entry.getValue(),
                "Wing observation substitutes a raw native result: "+entry.getKey());
        }
        int qualifier=uniqueLiteral(abc,body,"qualified_success");
        require(opcode(rows.get(qualifier+1),0x27),"Wing observation can claim qualified edit success.");
        require(uniqueLiteral(abc,body,"native-wing-selection-read-only")<base &&
            uniqueLiteral(abc,body,"Exact visible native wing panel required")<base,
            "Wing observation lacks its exact visible-panel refusal and read-only scope.");
        Set<String> setters=Set.of("base_query","color_query","base_error","color_error","base_arguments",
            "base_return_type","base_is_array","selected_base_ids","selected_color_id","selected_color_type");
        int services=0, types=0, bounded=0;
        for(int i=0;i<rows.size();i++) {
            var op=rows.get(i);
            require(!Set.of(0x40,0x41,0x42,0x43,0x44,0x45,0x4a,0x4c,0x4e,0x53).contains(op.definition.instructionCode),
                "Wing observation reaches an unreviewed direct call/constructor.");
            if(property(abc,op,0x46,"CallGameService") || property(abc,op,0x4f,"CallGameService")) {
                require(i==base+4 || i==color+3,"Wing observation has an additional native service."); services++;
            }
            if(opcode(op,0x61)) require(setters.contains(abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index)),
                "Wing observation changes an unreviewed native/result property.");
            if(property(abc,op,0x4f,"push")) { require(i>0 && opcode(rows.get(i-1),0x95) && op.operands[1]==1,
                "Wing observation base-element types are coerced or fabricated."); types++; }
            if(opcode(op,0x24) && op.operands[0]==32 && i+1<rows.size() && opcode(rows.get(i+1),0xaf)) bounded++;
        }
        require(services==2 && types==1 && bounded==1,"Wing observation getter/type/bound inventory differs.");
        for(String state:List.of("refused","returned-null","returned-undefined","returned-value","refused-bound","failed"))
            require(rows.stream().anyMatch(op->stringLiteral(abc,op,state)),"Wing observation loses native query outcome: "+state);
        Set<String> callers=new HashSet<>();
        for(Trait trait:instance.instance_traits.traits) if(trait instanceof TraitMethodGetterSetter && name(abc,trait).startsWith("Apex") &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains("ApexWingObservation")) callers.add(name(abc,trait));
        require(callers.equals(Set.of("ApexReadback")),"Wing observation is called outside the owned Timer readback.");
    }
    static void verifyWingSelection(ABC abc, InstanceInfo instance) {
        verifyWingObservation(abc,instance);
        MethodBody body=ownedBody(abc,instance,"ApexReadback");
        var code=body.getCode(); code.markOffsets(); var rows=code.code;
        int refusal=uniqueLiteral(abc,body,"Native wing base and color did not both read back exactly"), guard=refusal-56;
        require(guard>=65 && guard+76<rows.size(),"Wing compound refusal is truncated.");
        int baseSlot=rows.get(guard-13).operands[0], colorSlot=rows.get(guard-1).operands[0];
        require(property(abc,rows.get(guard-40),0x60,"MenuState") && property(abc,rows.get(guard-39),0x66,"CLOTHING_BODY_WINGS") &&
            opcode(rows.get(guard-38),0x13) && rows.get(guard-38).getTargetAddress()==rows.get(guard-33).getAddress() &&
            stringLiteral(abc,rows.get(guard-36),"Compound wing readback requires the exact wing panel") && opcode(rows.get(guard-34),0x03),
            "Wing readback lacks its exact native wing panel refusal.");
        require(property(abc,rows.get(guard-29),0x66,"wing_observation") && opcode(rows.get(guard-27),0x6d) &&
            property(abc,rows.get(guard-19),0x66,"selected_base_ids") && property(abc,rows.get(guard-18),0x60,"Array") &&
            opcode(rows.get(guard-17),0x87) && property(abc,rows.get(guard-14),0x80,"Array") && opcode(rows.get(guard-13),0x6d) &&
            property(abc,rows.get(guard-5),0x66,"selected_color_id") && opcode(rows.get(guard-2),0x82) && opcode(rows.get(guard-1),0x6d) &&
            baseSlot!=colorSlot,"Wing compound readback does not use the uncoerced independent observation values.");
        int probe=uniqueProperty(abc,body,0x46,"ApexWingObservation");
        require(probe<guard && rows.get(probe).operands[1]==0 && property(abc,rows.get(probe-1),0x5d,"ApexWingObservation") &&
            property(abc,rows.get(probe+1),0x61,"wing_observation") && property(abc,rows.get(probe-6),0x66,"CLOTHING_BODY_WINGS") &&
            opcode(rows.get(probe-5),0x14) && rows.get(probe-5).getTargetAddress()==rows.get(probe+2).getAddress(),
            "Wing raw observation is not published before refusal on the exact native wing panel.");
        int[] guardOps={0x65,0x6c,0x20,0xab,0x2a,0x11,0x29,0x65,0x6c,0x66,0x24,0xab,0x96,
            0x2a,0x11,0x29,0x65,0x6c,0x24,0x66,0x60,0xb3,0x96,0x2a,0x11,0x29,
            0x65,0x6c,0x24,0x66,0x70,0x65,0x6c,0x66,0x70,0xab,0x96,0x2a,0x11,0x29,
            0x65,0x6c,0x60,0xb3,0x96,0x2a,0x11,0x29,0x65,0x6c,0x65,0x6c,0xac,0x96,0x12,
            0x5d,0x2c,0x4a,0x03};
        for(int i=0;i<guardOps.length;i++) require(opcode(rows.get(guard+i),guardOps[i]),
            "Wing compound refusal lost its exact null/count/type/base/color checks.");
        for(int at:new int[]{1,8,17,27}) require(rows.get(guard+at).operands[0]==baseSlot,
            "Wing compound refusal compares an unrelated base observation.");
        require(property(abc,rows.get(guard+9),0x66,"length") && rows.get(guard+10).operands[0]==1 &&
            rows.get(guard+18).operands[0]==0 && rows.get(guard+28).operands[0]==0 &&
            property(abc,rows.get(guard+20),0x60,"String") && property(abc,rows.get(guard+33),0x66,"selection_base_id") &&
            rows.get(guard+41).operands[0]==colorSlot && property(abc,rows.get(guard+42),0x60,"String") &&
            rows.get(guard+49).operands[0]==colorSlot,
            "Wing compound refusal lacks its exact unique String base or independently typed color.");
        int valueSlot=rows.get(guard+51).operands[0], contextSlot=rows.get(guard+32).operands[0];
        require(valueSlot!=baseSlot && valueSlot!=colorSlot,"Wing requested color aliases an observed result.");
        int variantAssignment=-1;
        for(int i=Math.max(0,guard-85);i<guard;i++) if(property(abc,rows.get(i),0x66,"selection_variant_id") &&
                i+3<rows.size() && opcode(rows.get(i+1),0x70) && opcode(rows.get(i+2),0x85) &&
                opcode(rows.get(i+3),0x6d) && rows.get(i+3).operands[0]==valueSlot &&
                opcode(rows.get(i-1),0x6c) && rows.get(i-1).operands[0]==contextSlot) variantAssignment=i;
        require(variantAssignment>=0,"Wing requested color does not originate from the retained explicit variant intent.");
        int[][] branches={{5,13},{14,23},{24,37},{38,45},{46,54}};
        for(int[] branch:branches) require(rows.get(guard+branch[0]).getTargetAddress()==rows.get(guard+branch[1]).getAddress(),
            "Wing compound refusal can branch around a base/color condition.");
        require(rows.get(guard+54).getTargetAddress()==rows.get(guard+59).getAddress(),
            "Wing failed compound readback can bypass its native refusal.");
        int publish=guard+59;
        require(property(abc,rows.get(publish+2),0x66,"client") &&
            stringLiteral(abc,rows.get(publish+3),"base_query") && stringLiteral(abc,rows.get(publish+4),"returned-value") &&
            stringLiteral(abc,rows.get(publish+5),"color_query") && stringLiteral(abc,rows.get(publish+6),"returned-value") &&
            stringLiteral(abc,rows.get(publish+7),"selected_base_ids") && opcode(rows.get(publish+9),0x6c) &&
            rows.get(publish+9).operands[0]==baseSlot && stringLiteral(abc,rows.get(publish+10),"selected_color_id") &&
            opcode(rows.get(publish+12),0x6c) && rows.get(publish+12).operands[0]==colorSlot &&
            stringLiteral(abc,rows.get(publish+13),"body_type") && property(abc,rows.get(publish+14),0x60,"CASBodyType") &&
            property(abc,rows.get(publish+15),0x66,"WINGS") && opcode(rows.get(publish+16),0x55) &&
            rows.get(publish+16).operands[0]==5 && property(abc,rows.get(publish+17),0x61,"wing_selection"),
            "Wing compound acknowledgement substitutes an unverified base/color observation.");
        for(int i=guard-33;i<=publish+17;i++) require(!property(abc,rows.get(i),0x46,"CallGameService") &&
            !property(abc,rows.get(i),0x4f,"CallGameService"),"Wing compound refusal performs a native service after raw observation.");
    }
    static void verifyCatalogWorkspace(ABC abc,InstanceInfo instance) {
        var click=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogOpen"));
        require(click.equals(Set.of("getTimer","ApexInputTiming")),"Catalog radial click must only queue and record timing.");
        var frame=ownedBody(abc,instance,"ApexCatalogFrame");boolean pending=false,receiving=false;
        for(var op:frame.getCode().code)if(op.definition.instructionCode==0x66 || op.definition.instructionCode==0x60) {
            final String member=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
            require(!"apexAwaiting".equals(member),"Catalog player input waits for the transport poll.");
            pending|="apexPendingFields".equals(member);receiving|="apexReceiving".equals(member);
        }
        require(pending&&receiving,"Catalog player input lacks active CAS command guards.");
        var selected=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogSelection"));
        require(selected.contains("GetAllDisplayObjectCells") && Collections.disjoint(selected,Set.of("CallGameService","CallUIService","ApexNativeExchange")),
            "Selection animation must only inspect native recycled cells, without game queries.");
        var equipped=ownedBody(abc,instance,"ApexCatalogReadEquipped");
        uniqueLiteral(abc,equipped,"EQUIPPED|");
        int nativeReads=0;
        for(var op:equipped.getCode().code)if(property(abc,op,0x46,"ApexNativeExchange")) {
            require(op.operands[1]==1,"Equipped inventory must encode its complete channel/outfit in one native pipe argument.");nativeReads++;
        }
        require(nativeReads==1,"Equipped inventory requires exactly one bounded native read.");
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
            "apexNativeTransportRequired", "apexNativeChannel", "apexNativeConnected",
            "apexSocket", "apexTimer", "apexFrame", "apexExpected", "apexNonce", "apexBoundSim",
            "apexAwaiting", "apexAckId", "apexDisconnected", "apexSocketActive", "apexHelloPending", "apexSocketError",
            "apexSocketResetPending", "apexOutboundFrame", "apexOutboundPending",
            "apexPendingFields", "apexPendingReply", "apexPendingContext", "apexReadbackTick", "apexPendingPhase", "apexClaimNonce", "apexTicking",
            "apexOwnerFeed", "apexOwnerFeedSequence", "apexOwnerSession", "apexOwnerFeedListener", "apexOwnerResetListener", "apexMoleculeRegistered", "apexMoleculeReadRegistered", "apexMoleculeListener", "apexMoleculeView", "apexMoleculeIntent",
            "apexFormsRoot", "apexFormsSignature", "apexFormsOwnedMask", "apexFormsCatalog", "apexFormsIntent", "apexFormsResult", "apexFormsMessage", "apexFormsApplying",
            "apexFormsPosition", "apexFormsScale", "apexFormsLocked", "apexFormsCollapsed", "apexFormsDragging", "apexFormsPanelWidth", "apexFormsHousehold", "apexFormsLayerButtons", "apexFormsGestureSequence", "apexFormsOwners", "apexFormsOwnerTotal", "apexFormsSelectedId", "apexFormsNativeState", "apexFormsDesiredId", "apexFormsNativeIntent", "apexFormsBootstrap", "apexFormsPage", "apexFormsPanelHeight", "apexFormsGroups", "apexFormsVariantFamily", "apexFormsTooltips", "apexFormsGroupKey",
            "apexFormsFrameQueued", "apexFormsFastState", "apexFormsNativeGeneration", "apexFormsGestureStarted", "apexFormsSwitchMilliseconds",
            "apexInputSamples", "apexInputOverBudget", "apexInputMaxMs", "apexInputTotalMs",
            "apexCatalogPrefs","apexCatalogStore","apexCatalogUi","apexCatalogRows","apexCatalogIntent","apexCatalogSignature","apexCatalogEffects","apexCatalogPage","apexCatalogItems","apexCatalogContext","apexCatalogError","apexCatalogRegistered","apexCatalogDrag","apexCatalogSaved",
            "apexCatalogTab", "apexCatalogSelectionFrames", "apexCatalogSelectionMaxMs", "apexCatalogSelectionOverBudget",
            "apexPairRoot", "apexPairContext", "apexPairIntent", "apexPairSignature", "apexPairTooltips", "apexPairMessage", "apexPairRegistered");
        Set<String> ownedNames = Set.of("ApexInitialize", "ApexResetSocket", "ApexDisconnect", "ApexTick", "ApexMoleculeChooseOccult", "ApexMoleculeReadSelection", "ApexMoleculeDrain", "ApexFormsBindUiKind", "ApexObserveMolecule", "ApexMoleculeListen",
            "ApexSocketConnect", "ApexSocketFailure", "ApexSocketSend", "ApexSocketData", "ApexSocketReply",
            "ApexNativeExchange", "ApexNativeOpen", "ApexNativeReceive", "ApexConsumeFrame",
            "ApexQuote", "ApexEncode", "ApexSnapshot", "ApexExecute", "ApexReadback", "ApexComplete", "ApexAccept",
            "ApexOwnerFeedRow", "ApexObserveOwnerFeed", "ApexOwnerSimRow", "ApexOwnerObservation", "ApexInvalidateOwnerFeed", "ApexOwnerHouseholdProbe", "ApexFormSelectionContext", "ApexMemberSelectionContext",
            "ApexClone", "ApexCatalog", "ApexControlExecute", "ApexControlResult", "ApexBodyTypes", "ApexNativeLayers", "ApexSelectEyebrowSwatch", "ApexWingObservation",
            "ApexFormsDispose", "ApexFormsText", "ApexFormsButton", "ApexFormsTick", "ApexFormsClick", "ApexFormsLayers", "ApexFormsStatus",
            "ApexFormsToolbar", "ApexFormsToolbarClick", "ApexFormsPlace", "ApexFormsDragStart", "ApexFormsDragEnd", "ApexFormsResetPosition", "ApexFormsObservedSim", "ApexFormsDragCancel", "ApexFormsApply", "ApexFormsOwnedTick", "ApexFormsCompactButton", "ApexFormsGroupCatalog", "ApexFormsTooltip", "ApexFormsClearTooltips",
            "ApexFormsQueueOwner", "ApexFormsNextFrame", "ApexFormsReadNativeState", "ApexFormsScheduleFrame", "ApexInputTiming",
            "ApexCatalogInitialize","ApexCatalogValidate","ApexCatalogPersist","ApexCatalogStyle","ApexCatalogDispose","ApexCatalogOpen","ApexCatalogFrame","ApexCatalogClearEffects","ApexCatalogSelection","ApexCatalogReadEquipped","ApexCatalogMenu","ApexCatalogButton","ApexCatalogSlider","ApexCatalogDraw","ApexCatalogClick","ApexCatalogSlideStart","ApexCatalogSlide","ApexCatalogSlideEnd","ApexCatalogStatus",
            "ApexPairDispose", "ApexPairRead", "ApexPairExecute", "ApexPairClick", "ApexPairLabel", "ApexPairButton", "ApexPairTick", "ApexPairStatus", "ApexPairPanel");
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
        verifyFormStrip(compiled, newClass);
        verifyMemberSelection(compiled,newClass);
        verifyQueuedHandshake(compiled, newClass);
        verifySocketLifetime(compiled,newClass);
        verifyExactItemSelection(compiled, newClass);
        verifyTypedControls(compiled, newClass);
        verifyPhysiqueGesture(compiled,newClass);
        verifyAcceptLinkage(compiled, newClass);
        verifyAcceptHouseholdBinding(compiled, newClass);
        verifyAcceptPrimaryLayerOnly(compiled, newClass);
        verifyCatalogMetadataLinkage(compiled, newClass);
        verifyCatalogMetadataDisabled(compiled, newClass);
        verifyEyebrowPaletteWidget(compiled, newClass);
        verifyWingSelection(compiled, newClass);
        verifyOwnerMetadataReadback(compiled,newClass);
        verifyCatalogVariantReadback(compiled,newClass);
        verifySettledOwnerBootstrap(compiled,newClass);
        verifyCatalogWorkspace(compiled,newClass);
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
        verifyFormStrip(serialized, serialized.instance_info.get(oi));
        verifyTimerPipeline(serialized, serialized.instance_info.get(oi));
        verifyQueuedHandshake(serialized, serialized.instance_info.get(oi));
        verifySocketLifetime(serialized,serialized.instance_info.get(oi));
        verifyExactItemSelection(serialized, serialized.instance_info.get(oi));
        verifyTypedControls(serialized, serialized.instance_info.get(oi));
        verifyWingSelection(serialized, serialized.instance_info.get(oi));
        verifyOwnerMetadataReadback(serialized,serialized.instance_info.get(oi));
        verifyCatalogVariantReadback(serialized,serialized.instance_info.get(oi));
        verifySettledOwnerBootstrap(serialized,serialized.instance_info.get(oi));
        verifyCatalogWorkspace(serialized,serialized.instance_info.get(oi));
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload)
            require(Arrays.equals(nativeCode.get(body.method_info), serialized.findBody(body.method_info).getCodeBytes()),
                "Serialized unowned native method bytecode changed.");
        Files.write(Path.of(args[2]), saved.toByteArray());
        System.out.println("{\"native_method_count\":" + original.bodies.size() + ",\"apex_method_count\":" + ownedMethods.size() +
            ",\"native_lexical_scope_preserved\":true,\"unchanged_native_methods\":" + (nativeCode.size()-2) +
            ",\"native_initializer_bytecode_extended\":true,\"native_unload_bytecode_extended\":true,\"native_unload_cleanup_precedes_teardown\":true,\"owned_local_scope_indexes_verified\":true,\"serialized_lifecycle_hooks_verified\":true,\"socket_callbacks_data_only_verified\":true,\"timer_command_phases_verified\":true,\"accept_commit_timer_owned_verified\":true,\"accept_native_class_linkage_verified\":true,\"accept_expected_household_bound_verified\":true,\"accept_primary_layer_only_verified\":true,\"catalog_metadata_localization_linkage_verified\":true,\"owner_pair_callback_data_only_verified\":true,\"owner_pair_listener_cleanup_verified\":true,\"owner_pair_timer_read_only_verified\":true,\"socket_connect_queue_only_verified\":true,\"socket_handshake_exact_constructor_timer_verified\":true,\"form_select_timer_owned_verified\":true,\"form_select_exact_same_original_pair_verified\":true,\"form_select_native_argument_order_verified\":true,\"form_select_next_tick_readback_verified\":true,\"earrings_exact_bodytype_and_swatch_guard_verified\":true}");
    }
}
