// Build-time adapter for FFDec's public ABC API. No game-process access.
// Retain native class/script construction, traits and method bytecode; append
// only Apex traits/methods and one call at the native Initialize return.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import com.jpexs.decompiler.flash.SWF;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction;

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
        int initializeName = -1, initializeMethod = -1;
        for (Trait trait : newClass.instance_traits.traits) {
            String key = name(compiled, trait);
            if (key.startsWith("Apex") || key.startsWith("apex")) {
                added.add(trait.clone());
                if (trait instanceof TraitMethodGetterSetter) {
                    int method = ((TraitMethodGetterSetter)trait).method_info;
                    ownedMethods.add(method);
                    if (key.equals("ApexInitialize")) { initializeName = trait.name_index; initializeMethod = method; }
                }
            }
        }
        require(added.size() == 11 && initializeMethod >= 0, "Unexpected Apex trait inventory.");
        MethodBody nativeInit = null, compilerInit = null;
        for (Trait trait : nativeClass.instance_traits.traits) if (name(original, trait).equals("Initialize"))
            nativeInit = original.findBody(((TraitMethodGetterSetter)trait).method_info);
        for (Trait trait : newClass.instance_traits.traits) if (name(compiled, trait).equals("Initialize"))
            compilerInit = compiled.findBody(((TraitMethodGetterSetter)trait).method_info);
        require(nativeInit != null && compilerInit != null, "Native Initialize body missing.");
        int scopeDelta = nativeInit.init_scope_depth - compilerInit.init_scope_depth;
        require(scopeDelta == 9, "Inspected native lexical scope differs.");
        int originalCount = original.method_info.size();
        // Include nested function bodies reached by Apex's newfunction opcodes.
        boolean changed;
        do {
            changed = false;
            for (MethodBody body : compiled.bodies) if (ownedMethods.contains(body.method_info))
                for (AVM2Instruction instruction : body.getCode().code)
                    if (instruction.definition.instructionCode == 0x40 && ownedMethods.add(instruction.operands[0])) changed = true;
        } while (changed);
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
        int returnIndex = -1;
        for (int i = 0; i < nativeInit.getCode().code.size(); i++) if (nativeInit.getCode().code.get(i).definition.instructionCode == 0x47) {
            require(returnIndex == -1, "Native Initialize has multiple returns."); returnIndex = i;
        }
        require(returnIndex >= 0, "Native Initialize return absent.");
        nativeInit.insertAll(returnIndex, List.of(new AVM2Instruction(0, 0xd0, new int[0]),
            new AVM2Instruction(0, 0x4f, new int[]{initializeName, 0})));
        nativeInit.max_stack = Math.max(nativeInit.max_stack, 1);
        for (MethodBody body : original.bodies) if (body != nativeInit)
            require(Arrays.equals(nativeCode.get(body.method_info), body.getCodeBytes()), "Unowned native method bytecode changed.");
        try (OutputStream out = Files.newOutputStream(Path.of(args[2]))) { compiled.saveToStream(out); }
        System.out.println("{\"native_method_count\":" + original.bodies.size() + ",\"apex_method_count\":" + ownedMethods.size() +
            ",\"native_lexical_scope_preserved\":true,\"unchanged_native_methods\":" + (nativeCode.size()-1) + ",\"native_initializer_bytecode_extended\":true,\"owned_local_scope_indexes_verified\":true}");
    }
}
