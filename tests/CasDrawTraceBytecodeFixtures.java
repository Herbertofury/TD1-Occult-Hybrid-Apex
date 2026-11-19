import java.util.*;
public class CasDrawTraceBytecodeFixtures {
    public static void main(String[] args)throws Exception {
        var original=CasBytecodePatch.load(args[0]);var compiled=CasBytecodePatch.load(args[1]);String mode=args[2];
        if(mode.startsWith("helper-")) {
            var instance=compiled.instance_info.get(compiled.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
            var step=CasBytecodePatch.ownedBody(compiled,instance,"ApexCatalogTraceStep");
            if(mode.equals("helper-return"))for(var op:step.getCode().code)if(op.definition.instructionCode==0x47) {
                op.definition=new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0x02,new int[0]).definition;break;
            }
            if(mode.equals("helper-catch"))for(var handler:step.exceptions)handler.type_index=1;
            if(mode.equals("helper-service"))for(var op:step.getCode().code)if(CasBytecodePatch.property(compiled,op,0x46,"getTimer")) {
                op.operands[0]=CasBytecodePatch.communicationBinding(compiled)[1];break;
            }
            boolean refused=false;try {CasBytecodePatch.verifyDrawTraceHelper(compiled,instance);}catch(IllegalArgumentException expected){refused=true;}
            CasBytecodePatch.require(refused!=mode.equals("helper-valid"),"Compiled helper misclassified "+mode);
            System.out.println("PASS "+mode);return;
        }
        var source=CasBytecodePatch.classMethod(original,CasBytecodePatch.DRAW_TRACE_TYPE,"Draw");
        if(mode.equals("pin")) {
            for(var op:source.getCode().code)if(op.operands!=null && op.operands.length>0) {op.operands[0]++;break;}
            source.setModified();
        }
        if(mode.equals("trait"))CasBytecodePatch.drawTraceStaticTrait(compiled).value_index=1;
        if(mode.equals("pin")||mode.equals("trait")) {
            boolean refused=false;try {CasBytecodePatch.makeDrawTraceAdapter(original,compiled);}catch(IllegalArgumentException expected){refused=true;}
            CasBytecodePatch.require(refused,"Changed Draw/trait pin was accepted.");System.out.println("PASS "+mode);return;
        }
        var body=CasBytecodePatch.makeDrawTraceAdapter(original,compiled);
        var callback=CasBytecodePatch.drawTraceStaticTrait(compiled).clone();((com.jpexs.decompiler.flash.abc.types.traits.TraitSlotConst)callback).slot_id=0;
        int main=original.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        original.class_info.get(main).static_traits.traits.add(callback);
        byte[] cinit=original.findBody(original.class_info.get(main).cinit_index).getCodeBytes().clone();
        compiled.instance_info=original.instance_info;compiled.class_info=original.class_info;compiled.method_info=original.method_info;
        compiled.script_info=original.script_info;compiled.metadata_info=original.metadata_info;compiled.bodies=new ArrayList<>(original.bodies);
        for(int i=0;i<compiled.bodies.size();i++)if(compiled.bodies.get(i).method_info==body.method_info)compiled.bodies.set(i,body);
        var bytes=new java.io.ByteArrayOutputStream();compiled.saveToStream(bytes);
        compiled=new com.jpexs.decompiler.flash.abc.ABC(new com.jpexs.decompiler.flash.abc.ABCInputStream(
            new com.jpexs.helpers.MemoryInputStream(bytes.toByteArray())),compiled.getSwf(),null);
        var actual=CasBytecodePatch.classMethod(compiled,CasBytecodePatch.DRAW_TRACE_TYPE,"Draw");
        if(mode.equals("guard"))actual.getCode().code.get(4).operands[0]++;
        if(mode.equals("retained"))actual.getCode().code.get(actual.getCode().code.size()-1).definition=
            new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0x02,new int[0]).definition;
        if(mode.equals("branch"))for(var op:actual.getCode().code)if(op.definition.instructionCode==0x10) {op.operands[0]++;break;}
        if(mode.equals("flow-stale-jump")||mode.equals("flow-stale-if")) {
            int target=mode.equals("flow-stale-jump")?0x10:0x12;
            var nativeOps=new ArrayList<com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction>();var ops=actual.getCode().code;
            for(int i=0;i<ops.size();) {
                if(i==2) {i+=3;continue;}
                if(ops.get(i).definition.instructionCode==0x62 && ops.get(i).operands[0]==source.max_regs) {i+=8;continue;}
                nativeOps.add(ops.get(i++));
            }
            boolean found=false;
            for(int i=0;i<nativeOps.size();i++)if(nativeOps.get(i).definition.instructionCode==target &&
                nativeOps.get(i).operands[0]!=source.getCode().code.get(i).operands[0]) {
                nativeOps.get(i).operands[0]=source.getCode().code.get(i).operands[0];found=true;break;
            }
            CasBytecodePatch.require(found,"An actually relocated native edge is required.");
            boolean refused=false;try {CasBytecodePatch.verifyRetainedDrawFlow(compiled,source,actual);}catch(IllegalArgumentException expected){refused=true;}
            CasBytecodePatch.require(refused,"Independent edge verifier accepted a stale offset: "+mode);
            System.out.println("PASS "+mode);return;
        }
        if(mode.equals("flow-null-receiver")) {
            for(var op:actual.getCode().code)if(op.definition.instructionCode==0x64) {
                op.definition=new com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction(0,0x20,new int[0]).definition;break;
            }
            boolean refused=false;try {CasBytecodePatch.verifyRetainedDrawFlow(compiled,source,actual);}catch(IllegalArgumentException expected){refused=true;}
            CasBytecodePatch.require(refused,"Null Function receiver passed the independent ABI gate.");System.out.println("PASS "+mode);return;
        }
        if(mode.equals("locals"))actual.max_regs++;
        if(mode.equals("exceptions"))actual.exceptions=new com.jpexs.decompiler.flash.abc.types.ABCException[]{new com.jpexs.decompiler.flash.abc.types.ABCException()};
        actual.setModified();boolean refused=false;
        try {CasBytecodePatch.verifyDrawTraceAdapter(original,compiled);}catch(IllegalArgumentException expected){refused=true;}
        CasBytecodePatch.require(refused!=mode.equals("valid"),"Draw trace verification misclassified "+mode);
        if(mode.equals("valid")) {
            CasBytecodePatch.require(Arrays.equals(cinit,compiled.findBody(compiled.class_info.get(main).cinit_index).getCodeBytes()),"Native cinit changed.");
            CasBytecodePatch.drawTraceStaticTrait(compiled);
            int returns=0,calls=0;for(var op:actual.getCode().code) {if(op.definition.instructionCode==0x47)returns++;if(op.definition.instructionCode==0x41)calls++;}
            CasBytecodePatch.require(returns==4 && calls==45,"Expected all4 retained returns and45 guarded trace markers.");
            CasBytecodePatch.require(CasBytecodePatch.propertyCalls(compiled,actual).equals(CasBytecodePatch.propertyCalls(original,source)),"Draw gained a timer/service/property call.");
            actual.getCode().checkValidOffsets(actual);
            // Removing only injected calls must recover native instruction kinds
            // and all non-branch operands in exact original order.
            var projected=new ArrayList<com.jpexs.decompiler.flash.abc.avm2.instructions.AVM2Instruction>();
            var destinations=new HashMap<Long,Integer>();destinations.put(0L,0);
            var code=actual.getCode().code;int i=0;
            while(i<code.size()) {
                if(i==2) {destinations.put(code.get(i).getAddress(),projected.size());i+=3;continue;}
                if(code.get(i).definition.instructionCode==0x62 && code.get(i).operands[0]==source.max_regs) {
                    destinations.put(code.get(i).getAddress(),projected.size());i+=8;continue;
                }
                destinations.put(code.get(i).getAddress(),projected.size());
                projected.add(code.get(i++));
            }
            destinations.put(actual.getCode().getEndOffset(),projected.size());
            CasBytecodePatch.require(projected.size()==source.getCode().code.size(),"Native instruction count differs after trace removal.");
            for(i=0;i<projected.size();i++) {
                var a=projected.get(i);var b=source.getCode().code.get(i);
                CasBytecodePatch.require(a.definition.instructionCode==b.definition.instructionCode &&
                    ((b.definition.instructionCode>=0x0c && b.definition.instructionCode<=0x1a)||Arrays.equals(a.operands,b.operands)),"Retained Draw operand differs.");
                if(b.definition.instructionCode>=0x0c && b.definition.instructionCode<=0x1a)CasBytecodePatch.require(Objects.equals(destinations.get(a.getTargetAddress()),
                    source.getCode().adr2pos(b.getTargetAddress())),"Native Draw branch reaches a different original instruction.");
            }
            verifyMarkerStacks(compiled,source,actual);
        }
        System.out.println("PASS "+mode);
    }
    static void verifyMarkerStacks(com.jpexs.decompiler.flash.abc.ABC abc,
        com.jpexs.decompiler.flash.abc.types.MethodBody before,com.jpexs.decompiler.flash.abc.types.MethodBody after) {
        var code=after.getCode().code;int checked=0;
        for(int start=0;start<code.size();start++)if(code.get(start).definition.instructionCode==0x62 && code.get(start).operands[0]==before.max_regs) {
            checked++;
            for(int depth=0;depth<=32;depth++)for(boolean enabled:new boolean[]{false,true}) {
                var locals=new Object[before.max_regs+1];for(int i=0;i<before.max_regs;i++)locals[i]=new Object();
                Object callback=enabled?new Object():null;Object globalScope=new Object();locals[before.max_regs]=callback;var saved=locals.clone();
                var stack=new ArrayList<Object>();for(int i=0;i<depth;i++)stack.add(new Object());var initial=new ArrayList<>(stack);
                int at=start,calls=0;
                while(at<start+8) {
                    var op=code.get(at);switch(op.definition.instructionCode) {
                        case 0x62:stack.add(locals[op.operands[0]]);break;
                        case 0x12:
                            Object condition=stack.remove(stack.size()-1);if(condition==null) {at=start+8;continue;}break;
                        case 0x20:stack.add(null);break;
                        case 0x64:stack.add(globalScope);break;
                        case 0x2c:stack.add(abc.constants.getString(op.operands[0]));break;
                        case 0xd1:stack.add(locals[1]);break;
                        case 0x41:
                            Object product=stack.remove(stack.size()-1);Object event=stack.remove(stack.size()-1);
                            Object receiver=stack.remove(stack.size()-1);Object function=stack.remove(stack.size()-1);
                            CasBytecodePatch.require(function==callback && receiver==globalScope && event instanceof String &&
                                (product==null||event.equals("draw.enter")&&product==locals[1]),"Trace Function receiver/arguments corrupt a live operand.");
                            calls++;stack.add(new Object());break;
                        case 0x29:stack.remove(stack.size()-1);break;
                        default:throw new IllegalArgumentException("Unreviewed trace opcode.");
                    }
                    at++;
                }
                CasBytecodePatch.require(stack.equals(initial) && Arrays.equals(locals,saved) && calls==(enabled?1:0),
                    "Trace on/off changes this, arguments, original locals or preexisting value-stack entries.");
            }
            start+=7;
        }
        CasBytecodePatch.require(checked==45,"Not every actual serialized marker was stack-tested.");
    }
}
