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
            "apexAwaiting", "apexAckId", "apexDisconnected", "apexSocketActive", "apexSocketError");
        Set<String> ownedNames = Set.of("ApexInitialize", "ApexResetSocket", "ApexDisconnect", "ApexTick",
            "ApexSocketConnect", "ApexSocketFailure", "ApexSocketSend", "ApexSocketData", "ApexSocketReply",
            "ApexQuote", "ApexEncode", "ApexSnapshot", "ApexExecute");
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
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload)
            require(Arrays.equals(nativeCode.get(body.method_info), serialized.findBody(body.method_info).getCodeBytes()),
                "Serialized unowned native method bytecode changed.");
        Files.write(Path.of(args[2]), saved.toByteArray());
        System.out.println("{\"native_method_count\":" + original.bodies.size() + ",\"apex_method_count\":" + ownedMethods.size() +
            ",\"native_lexical_scope_preserved\":true,\"unchanged_native_methods\":" + (nativeCode.size()-2) +
            ",\"native_initializer_bytecode_extended\":true,\"native_unload_bytecode_extended\":true,\"native_unload_cleanup_precedes_teardown\":true,\"owned_local_scope_indexes_verified\":true,\"serialized_lifecycle_hooks_verified\":true}");
    }
}
