// Build-time adapter for FFDec's public ABC API. No game-process access.
// Retain native class/script construction, traits and method bytecode; append
// only Apex traits/methods, early grid + late Initialize calls and Unload cleanup.
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
    // Opcode-based relocation and projection, independent of FFDec's
    // isBranch classification (which does not include unconditional jump).
    static List<Integer> bootstrapEdges(AVM2Instruction op) {
        int n=op.definition.instructionCode;
        if(n>=0x0c && n<=0x1a)return List.of(0);
        if(n==0x1b) {
            require(op.operands!=null && op.operands.length>=3 && op.operands[1]>=0 &&
                op.operands.length==op.operands[1]+3,"Malformed initializer lookupswitch.");
            var edges=new ArrayList<Integer>();edges.add(0);
            for(int i=2;i<op.operands.length;i++)edges.add(i);return edges;
        }
        return List.of();
    }
    static long bootstrapTarget(AVM2Instruction op,int operand) {
        return op.getAddress()+(op.definition.instructionCode==0x1b?0:op.getBytesLength())+op.operands[operand];
    }
    static Map<Long,Integer> bootstrapAddresses(MethodBody body) {
        var result=new HashMap<Long,Integer>();var code=body.getCode().code;
        for(int i=0;i<code.size();i++)require(result.put(code.get(i).getAddress(),i)==null,"Duplicate initializer address.");
        result.put(body.getCode().getEndOffset(),code.size());return result;
    }
    static int bootstrapIndex(Map<Long,Integer> addresses,long address) {
        Integer result=addresses.get(address);require(result!=null,"Initializer edge is not on an instruction boundary.");return result;
    }
    static boolean bootstrapReachable(MethodBody body,int target,int blocked) {
        var code=body.getCode().code;var addresses=bootstrapAddresses(body);
        var seen=new HashSet<Integer>();var pending=new ArrayDeque<Integer>();pending.add(0);
        while(!pending.isEmpty()) {
            int at=pending.removeFirst();if(at==blocked || at>=code.size() || !seen.add(at))continue;
            if(at==target)return true;
            var op=code.get(at);int n=op.definition.instructionCode;
            for(int operand:bootstrapEdges(op))pending.add(bootstrapIndex(addresses,bootstrapTarget(op,operand)));
            if(n!=0x10 && n!=0x1b && n!=0x03 && n!=0x47 && n!=0x48)pending.add(at+1);
            for(var e:body.exceptions)if(op.getAddress()>=e.start && op.getAddress()<e.end)
                pending.add(bootstrapIndex(addresses,e.target));
        }
        return false;
    }
    static int gridBootstrapSeam(ABC abc,MethodBody body) {
        var code=body.getCode().code;int literal=-1,handled=-1,history=-1,returns=0;
        int main=abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        int historyClass=abc.findClassByName("dcc.history.HistoryHost");
        require(main>=0 && historyClass>=0,"Pinned native bootstrap classes are absent.");
        int callback=ownedGridName(abc,abc.instance_info.get(main),"HandleContextMenuSetMenuState");
        for(int i=0;i<code.size();i++) {
            var op=code.get(i);
            if(stringLiteral(abc,op,"CASContextMenuSetMenuState")) {
                require(literal<0,"Initializer has duplicate bootstrap listener seams.");literal=i;
            }
            if(property(abc,op,0x46,"HandleSetSimInfo") || property(abc,op,0x4f,"HandleSetSimInfo")) {
                require(handled<0,"Initializer has duplicate initial Sim deliveries.");handled=i;
            }
            if(i>=2 && property(abc,code.get(i-2),0x60,"HistoryHost") && opcode(code.get(i-1),0xd0) &&
                (property(abc,op,0x46,"Attach") || property(abc,op,0x4f,"Attach"))) {
                require(history<0,"Initializer has duplicate HistoryHost attachment.");history=i;
            }
            if(opcode(op,0x47))returns++;
        }
        require(literal>=1 && literal+4<code.size() && property(abc,code.get(literal-1),0x5d,"AddMessageListener") &&
            opcode(code.get(literal+1),0xd0) && property(abc,code.get(literal+2),0x66,"HandleContextMenuSetMenuState") &&
            code.get(literal+2).operands[0]==callback && property(abc,code.get(literal+3),0x46,"AddMessageListener") &&
            code.get(literal-1).operands[0]==code.get(literal+3).operands[0] && code.get(literal+3).operands[1]==2 &&
            opcode(code.get(literal+4),0x29),"Native bootstrap listener receiver/arguments/stack differ.");
        int seam=literal+5;
        require(handled>=0 && history>=2 && code.get(handled).operands[1]==1 && code.get(history).operands[1]==1 &&
            code.get(history-2).operands[0]==abc.instance_info.get(historyClass).name_index,
            "Native bootstrap Sim/history class/arguments differ.");
        require(handled>seam && history>handled && returns==1 && opcode(code.get(code.size()-1),0x47),
            "Native bootstrap must precede initial Sim delivery/history and retain one final return.");
        require(bootstrapReachable(body,seam,-1) && bootstrapReachable(body,handled,-1) && bootstrapReachable(body,history,-1) &&
            !bootstrapReachable(body,seam,literal+3) &&
            !bootstrapReachable(body,handled,seam) && !bootstrapReachable(body,history,seam),
            "A native control-flow path bypasses bootstrap or its established communication listener.");
        return seam;
    }
    static MethodBody gridBootstrapAdapter(ABC abc,MethodBody before,int bootstrapName,int initializeName) throws Exception {
        int seam=gridBootstrapSeam(abc,before);var old=new ArrayList<>(before.getCode().code);
        var body=before.clone();var code=body.getCode();var made=new ArrayList<AVM2Instruction>();
        var origins=new ArrayList<Integer>();var starts=new HashMap<Integer,Integer>();
        for(int i=0;i<old.size();i++) {
            starts.put(i,made.size());
            if(i==seam || i==old.size()-1) {
                made.add(new AVM2Instruction(0,0xd0,new int[0]));origins.add(-1);
                made.add(new AVM2Instruction(0,0x4f,new int[]{i==seam?bootstrapName:initializeName,0}));origins.add(-1);
            }
            var op=old.get(i);made.add(new AVM2Instruction(0,op.definition.instructionCode,op.operands==null?null:op.operands.clone()));origins.add(i);
        }
        starts.put(old.size(),made.size());long address=0;
        for(var op:made){op.setAddress(address);address+=op.getBytesLength();}
        final long end=address;var addresses=bootstrapAddresses(before);
        for(int i=0;i<made.size();i++)if(origins.get(i)>=0) {
            var op=made.get(i);var nativeOp=old.get(origins.get(i));
            for(int operand:bootstrapEdges(nativeOp)) {
                int at=starts.get(bootstrapIndex(addresses,bootstrapTarget(nativeOp,operand)));
                long dest=at==made.size()?end:made.get(at).getAddress();
                long offset=dest-op.getAddress()-(opcode(op,0x1b)?0:op.getBytesLength());
                require(offset>=-8388608 && offset<=8388607,"Initializer S24 edge overflow.");op.operands[operand]=(int)offset;
            }
        }
        code.code.clear();code.code.addAll(made);body.setCode(code);body.setModified();
        body.exceptions=new ABCException[before.exceptions.length];
        for(int i=0;i<before.exceptions.length;i++) {
            var e=before.exceptions[i].clone();int a=starts.get(bootstrapIndex(addresses,e.start));
            int b=starts.get(bootstrapIndex(addresses,e.end));int c=starts.get(bootstrapIndex(addresses,e.target));
            e.start=(int)(a==made.size()?end:made.get(a).getAddress());
            e.end=(int)(b==made.size()?end:made.get(b).getAddress());
            e.target=(int)(c==made.size()?end:made.get(c).getAddress());body.exceptions[i]=e;
        }
        body.max_stack=Math.max(before.max_stack,1);body.setModified();
        verifyGridBootstrapProjection(abc,before,body,bootstrapName,initializeName);return body;
    }
    static void verifyGridBootstrapProjection(ABC abc,MethodBody before,MethodBody after,int bootstrapName,int initializeName) throws Exception {
        int seam=gridBootstrapSeam(abc,before);var old=before.getCode().code;var code=after.getCode().code;
        var kept=new ArrayList<AVM2Instruction>();
        var canonical=new HashMap<Integer,Long>();int early=0,late=0;
        for(int i=0;i<code.size();) {
            int pos=kept.size();
            if((pos==seam && early==0) || (pos==old.size()-1 && late==0)) {
                int q=pos==seam?bootstrapName:initializeName;
                require(i+1<code.size() && opcode(code.get(i),0xd0) && opcode(code.get(i+1),0x4f) &&
                    Arrays.equals(code.get(i+1).operands,new int[]{q,0}),"Initializer hook has wrong receiver, QName or arguments.");
                canonical.put(pos,code.get(i).getAddress());
                if(pos==seam)early++;else late++;i+=2;continue;
            }
            canonical.putIfAbsent(pos,code.get(i).getAddress());kept.add(code.get(i++));
        }
        canonical.put(kept.size(),after.getCode().getEndOffset());
        require(early==1 && late==1 && kept.size()==old.size(),"Initializer hook/native inventory differs.");
        var originalAddresses=bootstrapAddresses(before);
        for(int i=0;i<old.size();i++) {
            var a=old.get(i);var b=kept.get(i);require(a.definition.instructionCode==b.definition.instructionCode &&
                (a.operands==null)==(b.operands==null) && (a.operands==null || a.operands.length==b.operands.length),
                "Original initializer opcode/operand shape changed.");
            if(a.operands!=null)for(int operand=0;operand<a.operands.length;operand++) {
                if(bootstrapEdges(a).contains(operand))require(Objects.equals(bootstrapTarget(b,operand),
                    canonical.get(bootstrapIndex(originalAddresses,bootstrapTarget(a,operand)))),"Original initializer jump/conditional/switch edge changed.");
                else require(a.operands[operand]==b.operands[operand],"Original initializer operand changed.");
            }
        }
        require(after.exceptions.length==before.exceptions.length,"Initializer exception inventory differs.");
        for(int i=0;i<before.exceptions.length;i++) {
            var a=before.exceptions[i];var b=after.exceptions[i];
            require(Objects.equals((long)b.start,canonical.get(bootstrapIndex(originalAddresses,a.start))) &&
                Objects.equals((long)b.end,canonical.get(bootstrapIndex(originalAddresses,a.end))) &&
                Objects.equals((long)b.target,canonical.get(bootstrapIndex(originalAddresses,a.target))) &&
                a.type_index==b.type_index && a.name_index==b.name_index,"Original initializer exception span/handler changed.");
        }
        require(after.max_regs==before.max_regs && after.max_stack==Math.max(before.max_stack,1) &&
            after.init_scope_depth==before.init_scope_depth && after.max_scope_depth==before.max_scope_depth,
            "Initializer hook changed original locals/stack/scope ABI.");
        after.getCode().checkValidOffsets(after);
    }
    static int ownedGridName(ABC abc,InstanceInfo instance,String method) {
        int result=-1;
        for(var trait:instance.instance_traits.traits)if(name(abc,trait).equals(method) && trait instanceof TraitMethodGetterSetter) {
            require(result<0,"Duplicate grid helper trait.");result=trait.name_index;
        }
        require(result>=0,"Missing grid helper trait: "+method);return result;
    }
    static boolean gridBudgetOp(AVM2Instruction op,int code,int... operands) {
        return opcode(op,code) && (op.operands==null ? operands.length==0 : Arrays.equals(op.operands,operands));
    }
    static int gridBudgetSlot(ABC abc,MethodBody body,String member,String type) {
        int slot=-1;
        for(var trait:body.traits.traits)if(name(abc,trait).equals(member)) {
            require(slot==-1 && trait instanceof TraitSlotConst,"Grid deadline activation slot is ambiguous: "+member);
            var field=(TraitSlotConst)trait;var q=abc.constants.getMultiname(field.type_index);
            require(field.kindType==Trait.TRAIT_SLOT && field.kindFlags==0 && field.slot_id>0 &&
                type.equals(abc.constants.getString(q.name_index)),"Grid deadline activation slot type differs: "+member);
            slot=field.slot_id;
        }
        require(slot>0,"Grid deadline activation slot is missing: "+member);return slot;
    }
    static boolean gridBudgetClock(ABC abc,AVM2Instruction lookup,AVM2Instruction call) {
        if(!opcode(lookup,0x5d) || lookup.operands==null || lookup.operands.length!=1 ||
           !gridBudgetOp(call,0x46,lookup.operands[0],0))return false;
        var q=abc.constants.getMultiname(lookup.operands[0]);
        if(q.kind!=Multiname.QNAME || q.namespace_index<=0 || !"getTimer".equals(abc.constants.getString(q.name_index)))return false;
        var ns=abc.constants.getNamespace(q.namespace_index);
        return ns.kind==Namespace.KIND_PACKAGE && "flash.utils".equals(abc.constants.getString(ns.name_index));
    }
    static void verifyGridStepBudget(ABC abc,MethodBody frame) {
        // Authenticate the ACTUAL two stack arguments, rather than accept a
        // nearby decoy64. Only these two reviewed compiler expressions exist:
        // Step(64,getTimer()+1), or Step(64,(stepStarted=getTimer())+1).
        var ops=frame.getCode().code;int step=-1;
        for(int i=0;i<ops.size();i++)if(property(abc,ops.get(i),0x46,"ApexGridStep") || property(abc,ops.get(i),0x4f,"ApexGridStep")) {
            require(step==-1,"Grid frame must contain exactly one native Step call.");step=i;
        }
        require(step>=0 && gridBudgetOp(ops.get(step),0x46,ops.get(step).operands[0],2),
            "Grid Step requires its exact result-producing two-argument call.");
        boolean plain=step>=5 && gridBudgetOp(ops.get(step-5),0x24,64) &&
            gridBudgetClock(abc,ops.get(step-4),ops.get(step-3)) &&
            gridBudgetOp(ops.get(step-2),0x24,1) && gridBudgetOp(ops.get(step-1),0xa0);
        boolean timed=false;
        if(step>=12 && gridBudgetOp(ops.get(step-12),0x24,64) && gridBudgetOp(ops.get(step-11),0x65,1) &&
           gridBudgetClock(abc,ops.get(step-10),ops.get(step-9)) && gridBudgetOp(ops.get(step-8),0x73) &&
           gridBudgetOp(ops.get(step-7),0x2a) && gridBudgetOp(ops.get(step-6),0xd7) &&
           gridBudgetOp(ops.get(step-4),0xd3) && gridBudgetOp(ops.get(step-3),0x08,3) &&
           gridBudgetOp(ops.get(step-2),0x24,1) && gridBudgetOp(ops.get(step-1),0xa0)) {
            timed=gridBudgetOp(ops.get(step-5),0x6d,gridBudgetSlot(abc,frame,"stepStarted","int"));
        }
        require(plain || timed,"Grid frame must pass literal64 and its exact fresh getTimer()+1 deadline.");
        int start=step-(timed?12:5);
        require(start>=3 && gridBudgetOp(ops.get(start-3),0x65,1) &&
            gridBudgetOp(ops.get(start-2),0x6c,gridBudgetSlot(abc,frame,"s","Object")) &&
            property(abc,ops.get(start-1),0x66,"grid"),"Grid Step receiver must be the owned scheduler's current grid.");
        // No branch/exception edge may enter midway and bypass a checked
        // receiver, argument, assignment, clock or deadline addition.
        var addresses=bootstrapAddresses(frame);
        for(var op:ops)for(int operand:bootstrapEdges(op)) {
            int target=bootstrapIndex(addresses,bootstrapTarget(op,operand));
            require(target<=start-3 || target>step,"Grid deadline has an unreviewed incoming control-flow edge.");
        }
        for(var error:frame.exceptions) {
            int target=bootstrapIndex(addresses,error.target);
            require(target<=start-3 || target>step,"Grid deadline has an unreviewed exception entry.");
        }
    }
    static void verifyGridController(ABC abc,InstanceInfo instance) {
        int initialize=ownedGridName(abc,instance,"ApexCatalogGridInitialize");
        var permit=ownedBody(abc,instance,"ApexCatalogGridPermit");
        uniqueLiteral(abc,permit,"GRIDPERMIT|1");
        require(propertyCalls(abc,permit).equals(Set.of("ApexNativeExchange","test")),
            "Early grid permit must only read its fixed native capture-scope response.");
        var bootstrap=ownedBody(abc,instance,"ApexCatalogGridBootstrap");
        var info=abc.method_info.get(bootstrap.method_info);
        require(info.param_types.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(info.ret_type).name_index)),
            "Early bootstrap must be a no-argument void method.");
        int calls=0;var code=bootstrap.getCode().code;
        for(int i=0;i<code.size();i++)if(property(abc,code.get(i),0x46,"ApexCatalogGridInitialize") || property(abc,code.get(i),0x4f,"ApexCatalogGridInitialize")) {
            require(i>=2 && opcode(code.get(i-1),0x26) && code.get(i).operands[0]==initialize && code.get(i).operands[1]==1 &&
                (opcode(code.get(i-2),0xd0) || (opcode(code.get(i-2),0x5d) && code.get(i-2).operands[0]==initialize)),
                "Early bootstrap must invoke its exact owned initializer with true on the original this.");calls++;
        }
        require(calls==1 && Set.of("ApexCatalogGridPermit","ApexCatalogGridInitialize","removeEventListener","RemoveMessageListener","ApexGridCancel").containsAll(propertyCalls(abc,bootstrap)),
            "Early bootstrap performs an unreviewed call or has no single initializer call.");
        for(String method:List.of("ApexCatalogGridProductPanel","ApexCatalogGridProductRow","ApexCatalogGridBootstrap","ApexCatalogGridInitialize","ApexCatalogGridPrepare",
            "ApexCatalogGridLeaseCurrent","ApexCatalogGridValidate","ApexCatalogGridInvalidate","ApexCatalogGridChanged",
            "ApexCatalogGridDispose","ApexCatalogGridOwns","ApexCatalogGridPending"))
            require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,method)),Set.of("CallGameService","CallUIService","ApexNativeExchange",
                "getLocal","flush","connect","writeUTFBytes","GetCatalogItemsSelected","RequestData","ResetAndPositionCells","PositionCells",
                "GetAllDisplayObjectCells","ApexCardScaleCells","ApexCardRowsAligned")),
                "Structural grid bootstrap/lease/cleanup performs engine, disk or bulk catalogue work: "+method);
        for(String producer:List.of("ApexCatalogGridPrepare","ApexCatalogGridRequest")) {
            var produced=ownedBody(abc,instance,producer).getCode().code;int validators=0;
            int inputName=ownedGridName(abc,instance,"ApexCatalogGridInput");
            for(int i=0;i<produced.size();i++)if(stringLiteral(abc,produced.get(i),"inputValidate")) {
                // FFDec emits a bound private method closure with getlex;
                // an explicit this receiver uses getlocal0/getproperty.
                boolean direct=i+1<produced.size() && opcode(produced.get(i+1),0x60) && produced.get(i+1).operands[0]==inputName;
                boolean explicit=i+2<produced.size() && ((opcode(produced.get(i+1),0x5d) && produced.get(i+1).operands[0]==inputName) ||
                    opcode(produced.get(i+1),0xd0)) && property(abc,produced.get(i+2),0x66,"ApexCatalogGridInput") &&
                    produced.get(i+2).operands[0]==inputName;
                require(direct || explicit,"Grid request binds an unreviewed write-input validator.");validators++;
            }
            require(validators>0,"Grid request omitted its fresh write-input validator: "+producer);
        }
        var productRow=ownedBody(abc,instance,"ApexCatalogGridProductRow");
        var rowInfo=abc.method_info.get(productRow.method_info);
        require(rowInfo.flags==0 && rowInfo.param_types.length==1 && productRow.exceptions.length==0 && productRow.traits.traits.isEmpty(),
            "Product row predicate must be a single synchronous unbound type check.");
        var rowOps=new ArrayList<AVM2Instruction>();
        for(var op:productRow.getCode().code)if(!Set.of(0xef,0xf0,0xf1).contains(op.definition.instructionCode))rowOps.add(op);
        require(rowOps.size()==6 && opcode(rowOps.get(0),0xd0) && opcode(rowOps.get(1),0x30) && opcode(rowOps.get(2),0xd1) &&
            opcode(rowOps.get(3),0x60) && opcode(rowOps.get(4),0xb3) && opcode(rowOps.get(5),0x48),
            "Product row predicate may only test its argument against the native CASCatalogProduct class.");
        var rowType=abc.constants.getMultiname(rowOps.get(3).operands[0]);var rowNs=abc.constants.getNamespace(rowType.namespace_index);
        require(rowType.kind==7 && rowNs.kind==22 && "CASCatalogProduct".equals(abc.constants.getString(rowType.name_index)) &&
            "gamedata.CAS.shared".equals(abc.constants.getString(rowNs.name_index)),"Product predicate uses an unresolved or foreign native type.");
        var productPanel=ownedBody(abc,instance,"ApexCatalogGridProductPanel");
        Set<String> productClasses=Set.of("SelectableRecyclingGridLayout","CASBodyPanelCellView","CASFacePanelCellView","CASGenericCatalogVariantCellView","CASBreedCatalogCellView");
        var observedProductClasses=new HashSet<String>();
        for(var op:productPanel.getCode().code)if(opcode(op,0x60)) {
            var q=abc.constants.getMultiname(op.operands[0]);String name=abc.constants.getString(q.name_index);
            require(!Set.of("olympus","widgets","gamedata").contains(name),"Product panel type must not use a runtime namespace object.");
            if(productClasses.contains(name)) {
                var ns=abc.constants.getNamespace(q.namespace_index);String space=name.equals("SelectableRecyclingGridLayout")?"olympus.layout":"widgets.CAS.controls";
                require(q.kind==7 && ns.kind==22 && space.equals(abc.constants.getString(ns.name_index)),"Product panel native class QName differs: "+name);
                observedProductClasses.add(name);
            }
        }
        require(observedProductClasses.equals(productClasses),"Product panel omitted a reviewed native grid/cell class.");
        var observe=ownedBody(abc,instance,"ApexCatalogGridObserve");
        uniqueLiteral(abc,observe,"CASGetSimInfo");uniqueLiteral(abc,observe,"CasGetCurrSimOutfitSlot");
        int freshReads=0;var reads=observe.getCode().code;
        for(int i=0;i<reads.size();i++)if(property(abc,reads.get(i),0x46,"CallGameService") || property(abc,reads.get(i),0x4f,"CallGameService")) {
            require(i>=3 && reads.get(i).operands[1]==3 && opcode(reads.get(i-1),0x26) && opcode(reads.get(i-2),0x20) &&
                (stringLiteral(abc,reads.get(i-3),"CASGetSimInfo") || stringLiteral(abc,reads.get(i-3),"CasGetCurrSimOutfitSlot")),
                "Grid identity read must use its exact fresh native read arguments.");freshReads++;
        }
        require(freshReads==2,"Grid identity observation must contain exactly the selected Sim/outfit read pair.");
        uniqueLiteral(abc,observe,"GRIDSTATE|");
        require(propertyCalls(abc,observe).containsAll(Set.of("CallGameService","ApexOwnerSimRow","ApexNativeExchange")),"Grid frame lacks fresh selected Sim/outfit observation.");
        var visualObserve=ownedBody(abc,instance,"ApexCatalogGridFrameObserve");
        uniqueLiteral(abc,visualObserve,"GRIDSTATE|");uniqueLiteral(abc,visualObserve,"CasGetCurrSimOutfitSlot");
        int visualReads=0;var visualOps=visualObserve.getCode().code;
        for(int i=0;i<visualOps.size();i++) {
            require(!stringLiteral(abc,visualOps.get(i),"CASGetSimInfo"),"Visual work requests the complete Sim-info object.");
            if(property(abc,visualOps.get(i),0x46,"CallGameService") || property(abc,visualOps.get(i),0x4f,"CallGameService")) {
                require(i>=3 && visualOps.get(i).operands[1]==3 && opcode(visualOps.get(i-1),0x26) &&
                    opcode(visualOps.get(i-2),0x20) && stringLiteral(abc,visualOps.get(i-3),"CasGetCurrSimOutfitSlot"),
                    "Visual frame must retain its exact fresh outfit getter.");visualReads++;
            }
        }
        require(visualReads==1 && propertyCalls(abc,visualObserve).containsAll(Set.of("ApexCatalogGridLeaseCurrent","ApexNativeExchange")),
            "Visual frame lacks fresh exact native context/outfit validation.");
        var incremental=ownedBody(abc,instance,"ApexCardIncrementalApply");
        require(Collections.disjoint(propertyCalls(abc,incremental),Set.of("ResetAndPositionCells","PositionCells",
            "ApexLayoutReset","ApexCardScaleCells","ApexCardRowsAligned","GetAllDisplayObjectCells","CallGameService","ApexNativeExchange")),
            "Incremental geometry invokes the legacy pool/engine path.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCardApply")).containsAll(Set.of("ApexCatalogGridOwns","ApexCardIncrementalApply")),
            "The armed grid does not bypass legacy full-pool geometry.");
        var frame=ownedBody(abc,instance,"ApexCatalogGridFrame");
        require(propertyCalls(abc,frame).containsAll(Set.of("ApexCatalogGridObserve","ApexCatalogGridFrameObserve","ApexGridBegin","ApexGridStep","getTimer")),
            "Grid scheduler lacks owned observation or bounded native stepping.");
        verifyGridStepBudget(abc,frame);
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogGridInput")).containsAll(Set.of("ApexCatalogGridObserve","ApexCatalogGridMatches","ApexCatalogGridInvalidate")),
            "Write-capable cells lack a fresh exact identity check.");
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
                "ApexResetSocket", "ApexDisconnect", "close", "connect", "ApexSocketSend",
                "ApexPanelNavigationSnapshot","ApexCatalogTimerStep","ApexCatalogTimerStatus")), "Socket callback executes native CAS or socket lifecycle work.");
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
    static boolean acceptCall(ABC abc,AVM2Instruction op,String method) {
        return property(abc,op,0x46,method)||property(abc,op,0x4f,method);
    }
    static int acceptCallIndex(ABC abc,MethodBody body,String method) {
        int result=-1;var code=body.getCode().code;
        for(int i=0;i<code.size();i++)if(acceptCall(abc,code.get(i),method)) {
            require(result<0,"Acceptance calls a one-shot boundary more than once: "+method);result=i;
        }
        require(result>=0,"Acceptance omits boundary: "+method);return result;
    }
    static boolean acceptValue(ABC abc,AVM2Instruction op,String member) {
        return property(abc,op,0x60,member)||property(abc,op,0x66,member);
    }
    static void acceptReads(ABC abc,MethodBody body,Set<String> required) {
        var found=new HashSet<String>();
        for(var op:body.getCode().code)for(String member:required)if(acceptValue(abc,op,member))found.add(member);
        require(found.equals(required),"Acceptance fresh identity/retained context read missing: "+required+" / "+found);
    }
    static boolean acceptElseThrows(ABC abc,List<AVM2Instruction> code,int branch,int opcode) {
        return branch>=0 && branch+4<code.size() && opcode(code.get(branch),opcode) &&
            property(abc,code.get(branch+1),0x5d,"Error") && opcode(code.get(branch+2),0x2c) &&
            property(abc,code.get(branch+3),0x4a,"Error") && opcode(code.get(branch+4),0x03) && branchTarget(code,branch)>branch+4;
    }
    static int acceptOriginalSlot(ABC abc,MethodBody body,String member,int wireIndex) {
        var c=body.getCode().code;int slot=-1;
        for(int i=0;i+9<c.size();i++)if(property(abc,c.get(i),0x60,"apexAcceptWait") &&
                property(abc,c.get(i+1),0x66,member) && opcode(c.get(i+2),0x70) && opcode(c.get(i+3),0x10)) {
            int join;
            if(wireIndex>=0) {
                require(property(abc,c.get(i+4),0x60,"apexPendingFields") && opcode(c.get(i+5),0x24) && c.get(i+5).operands[0]==wireIndex &&
                    opcode(c.get(i+6),0x66) && abc.constants.getMultiname(c.get(i+6).operands[0]).kind==Multiname.MULTINAMEL &&
                    opcode(c.get(i+7),0x70),"Acceptance original UUID/household is not its retained or exact wire field.");join=i+8;
            } else {require(property(abc,c.get(i+4),0x60,"apexClaimNonce"),"Acceptance nonce is not its original retained/claimed nonce.");join=i+5;}
            require(branchTarget(c,i+3)==join && opcode(c.get(join),0x85) && opcode(c.get(join+1),0x6d),"Acceptance original identity does not join one owned String slot.");
            require(slot<0,"Acceptance retained identity is ambiguous.");slot=c.get(join+1).operands[0];
        }
        require(slot>=0,"Acceptance lost its original retained identity: "+member);return slot;
    }
    static void verifyAcceptReadiness(ABC abc,InstanceInfo instance) {
        var body=ownedBody(abc,instance,"ApexAccept");var c=body.getCode().code;
        int idSlot=acceptOriginalSlot(abc,body,"id",0),nonceSlot=acceptOriginalSlot(abc,body,"owner",-1);
        acceptOriginalSlot(abc,body,"household",6);
        int ready=acceptCallIndex(abc,body,"ApexAcceptReady"),prepare=acceptCallIndex(abc,body,"ApexAcceptNative");
        int save=uniqueLiteral(abc,body,"SaveAndExitCAS"),key=uniqueLiteral(abc,body,"apex_accept_id"),nonce=uniqueLiteral(abc,body,"apex_accept_nonce");
        require(prepare<ready && ready<save && ready>=1 && property(abc,c.get(ready-1),0x60,"apexAcceptWait") && c.get(ready).operands[1]==1 &&
            ready+3<c.size() && opcode(c.get(ready+1),0x96) && opcode(c.get(ready+2),0x12) && opcode(c.get(ready+3),0x47) && branchTarget(c,ready+2)==ready+4,
            "Acceptance genuine-not-ready must RETURN before any native save; no alternate branch/delay.");
        require(!bootstrapReachable(body,save,ready),"A CFG path bypasses acceptance readiness before native save.");
        require(prepare>=2 && property(abc,c.get(prepare-2),0x60,"apexAcceptWait") && stringLiteral(abc,c.get(prepare-1),"PREPARE") && c.get(prepare).operands[1]==2,
            "Acceptance preparation is not the exact retained once-only PREPARE.");
        int phase=-1,consume=-1;boolean resuming=false;
        for(int i=1;i<c.size();i++) {
            if(property(abc,c.get(i),0x61,"apexPendingPhase") && opcode(c.get(i-1),0x24) && c.get(i-1).operands[0]==9) {require(phase<0,"Readiness waiting phase is written repeatedly.");phase=i;}
            if(i>ready && i<save && property(abc,c.get(i),0x61,"apexAcceptWait") && opcode(c.get(i-1),0x20)) {require(consume<0,"Acceptance consumes its original wait repeatedly.");consume=i;}
            if(i+2<c.size() && property(abc,c.get(i-1),0x60,"apexPendingPhase") && opcode(c.get(i),0x24) && c.get(i).operands[0]==9 && opcode(c.get(i+1),0xab))resuming=true;
        }
        require(phase>=0 && phase<prepare && resuming && consume>ready && consume<save && !bootstrapReachable(body,save,consume),
            "Acceptance lacks phase9 admission or consume-before-save on every CFG path.");
        require(key==save+3 && nonce==key+3 && slotLoad(c,key+1,idSlot) && slotLoad(c,nonce+1,nonceSlot) &&
            opcode(c.get(nonce+3),0x55) && c.get(nonce+3).operands[0]==3 && property(abc,c.get(nonce+4),0x46,"CallGameService") && c.get(nonce+4).operands[1]==2,
            "Native Save must carry only validation=false and its exact original UUID/nonce tuple.");
        boolean heldId=false,heldNonce=false;
        for(int i=0;i<phase;i++)if(stringLiteral(abc,c.get(i),"id")&&slotLoad(c,i+1,idSlot))heldId=true;
        else if(stringLiteral(abc,c.get(i),"owner")&&slotLoad(c,i+1,nonceSlot))heldNonce=true;
        require(heldId&&heldNonce,"Readiness wait did not retain the same original UUID/nonce passed to Save.");
        var readyBody=ownedBody(abc,instance,"ApexAcceptReady");var r=readyBody.getCode().code;
        acceptReads(abc,readyBody,Set.of("apexAcceptInput","apexDisconnected","apexSocketActive","apexNonce","owner","stage","apexAcceptStage",
            "channel","apexNativeChannel","apexFormsDesiredId","apexFormsIntent","apexFormsNativeIntent","apexMoleculeIntent","apexPairIntent","apexFormsApplying",
            "simId","householdId","household","occultLayer","occultType","allOccultTypes","shell","mask","mode","result","rendered","mCurrState","TattooMode",
            "apexFormsNativeState","apexFormsSelectedId","formOwner","preparedGeneration","apexFormsNativeGeneration"));
        int read=acceptCallIndex(abc,readyBody,"ApexAcceptNative");
        require(read>=2 && opcode(r.get(read-2),0xd1) && stringLiteral(abc,r.get(read-1),"READY") && r.get(read).operands[1]==2,
            "Acceptance readiness must read the original retained READY receipt.");
        for(String literal:Set.of("CASGetSimInfo","CasGetCASEditMode","CasIsNewFamily","CasIsEnteredFromPlayArea","GetSimOccult"))
            require(uniqueLiteral(abc,readyBody,literal)<read,"Acceptance readiness native context is not fresh before READY.");
        boolean timed=false,input=false,nonceGuard=false;
        for(int i=0;i+7<r.size();i++) {
            if(opcode(r.get(i),0x25)&&r.get(i).operands[0]==10000&&opcode(r.get(i+1),0xaf)&&acceptElseThrows(abc,r,i+2,0x12))timed=true;
            if(property(abc,r.get(i),0x60,"apexAcceptInput")&&acceptElseThrows(abc,r,i+1,0x12))input=true;
            if(property(abc,r.get(i),0x60,"apexNonce")&&opcode(r.get(i+1),0xd1)&&property(abc,r.get(i+2),0x66,"owner")&&
                opcode(r.get(i+3),0xac)&&opcode(r.get(i+4),0x96)&&opcode(r.get(i+5),0x2a)&&opcode(r.get(i+6),0x11)&&
                guardedThrow(abc,r,trueRefusal(r,i+6)))nonceGuard=true;
        }
        require(timed&&input&&nonceGuard,"Acceptance readiness timeout/input/original nonce refusal lost its exact branch polarity.");
        var nativeBody=ownedBody(abc,instance,"ApexAcceptNative");var n=nativeBody.getCode().code;
        require(propertyCalls(abc,nativeBody).equals(Set.of("CallGameService","split","test","slice","join","indexOf","substr")),"Readiness receipt parser invokes an unreviewed service/helper.");
        verifyBoundedNativeRefusal(abc,nativeBody);
        uniqueLiteral(abc,nativeBody,"APEXACCEPT1|");uniqueLiteral(abc,nativeBody,"GetSimOccult");
        boolean length=false,stamp=false,model=false,phaseProof=false,flag=false;
        for(int i=0;i+6<n.size();i++) {
            if(property(abc,n.get(i),0x66,"length")&&opcode(n.get(i+1),0x24)&&n.get(i+1).operands[0]==18&&
               opcode(n.get(i+2),0xab)&&opcode(n.get(i+3),0x96)&&opcode(n.get(i+4),0x2a)&&opcode(n.get(i+5),0x11)&&guardedThrow(abc,n,trueRefusal(n,i+5)))length=true;
            if(property(abc,n.get(i),0x66,"stamp")&&acceptElseThrows(abc,n,i+1,0x19))stamp=true;
            if(opcode(n.get(i),0x24)&&(n.get(i).operands[0]==15||n.get(i).operands[0]==16)&&opcode(n.get(i+1),0x66)&&
               stringLiteral(abc,n.get(i+2),"0")&&opcode(n.get(i+3),0xac)) {if(n.get(i).operands[0]==15)phaseProof=true;else model=true;}
            if(stringLiteral(abc,n.get(i),"READY")&&opcode(n.get(i+1),0xac)&&acceptElseThrows(abc,n,i+3,0x19))flag=true;
        }
        require(length&&stamp&&model&&phaseProof&&flag,"Readiness receipt length/scalar stamp/real phase/model/READY equality proof changed.");
        var user=ownedBody(abc,instance,"ApexAcceptUserInput");require(propertyCalls(abc,user).isEmpty(),"Readiness input callback must queue cancellation only, never block EA controls or call native.");
        boolean queued=false;for(int i=1;i<user.getCode().code.size();i++)if(property(abc,user.getCode().code.get(i),0x61,"apexAcceptInput")&&opcode(user.getCode().code.get(i-1),0x26))queued=true;
        require(queued,"Readiness input callback omitted its cancellation flag.");
        var frame=ownedBody(abc,instance,"ApexAcceptReadyFrame");require(propertyCalls(abc,frame).equals(Set.of("ApexAccept")),"Only the owned readiness frame may resume the same accepted operation.");
        acceptReads(abc,frame,Set.of("apexAcceptWait","apexPendingPhase","apexTicking"));
        var listen=ownedBody(abc,instance,"ApexAcceptListen");require(propertyCalls(abc,listen).equals(Set.of("removeEventListener","addEventListener")),"Readiness listener setup may not mutate/query the game.");
        acceptReads(abc,listen,Set.of("stage","apexAcceptStage","ENTER_FRAME","MOUSE_DOWN","KEY_DOWN","ApexAcceptReadyFrame","ApexAcceptUserInput"));
        var abort=ownedBody(abc,instance,"ApexAcceptAbort");require(acceptCallIndex(abc,abort,"ApexAcceptListen")<uniqueLiteral(abc,abort,"APEXACCEPT1|CANCEL|"),"Readiness cancellation must detach listeners before transport/native cleanup.");
        acceptReads(abc,abort,Set.of("request","reply","owner","id","apexNonce","apexSocketActive"));
        var reset=ownedBody(abc,instance,"ApexResetSocket");require(acceptCallIndex(abc,reset,"ApexAcceptAbort")<uniqueLiteral(abc,reset,"CLOSE|"),"Room retirement must cancel retained acceptance before closing its original channel.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexDisconnect")).contains("ApexResetSocket"),"Unload must retire the original readiness continuation.");
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
        int slot = -1, fieldsSlot=-1;
        // Readback owns a typed local alias; Accept reads the retained wire
        // directly. An unrelated array[6] (for example a native owner cursor's
        // generation) is not a household request field.
        for(int i=0;i+2<code.size();i++)if(property(abc,code.get(i),0x60,"apexPendingFields") &&
            opcode(code.get(i+1),0x80) && "Array".equals(abc.constants.getString(abc.constants.getMultiname(code.get(i+1).operands[0]).name_index)) &&
            opcode(code.get(i+2),0x6d)) {
            require(fieldsSlot<0,"CAS wire alias is ambiguous.");fieldsSlot=code.get(i+2).operands[0];
        }
        for (int i=0; i+4<code.size(); i++) {
            if (!opcode(code.get(i),0x24) || code.get(i).operands[0]!=6 ||
                !opcode(code.get(i+1),0x66) ||
                abc.constants.getMultiname(code.get(i+1).operands[0]).kind!=Multiname.MULTINAMEL) continue;
            if(i==0 || !(property(abc,code.get(i-1),0x60,"apexPendingFields") || fieldsSlot>=0 &&
                opcode(code.get(i-1),0x6c) && code.get(i-1).operands[0]==fieldsSlot))continue;
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
                    for(String candidate:List.of("ApexObserveOwnerFeed","ApexInvalidateOwnerFeed","ApexPresentationNotify"))
                        if(property(abc,op,0x66,candidate) || property(abc,op,0x60,candidate)) callback=candidate;
                }
                require(call.operands[1]==2 && (("CASRefreshSimIcons".equals(event) && "ApexObserveOwnerFeed".equals(callback)) ||
                    ("CASClearSimsForReset".equals(event) && "ApexInvalidateOwnerFeed".equals(callback)) ||
                    ("CASSetSimInfo".equals(event) && "ApexPresentationNotify".equals(callback))) && events.add(event),
                    "CAS owner listener does not use the exact callback without a class remapping.");
                listeners++;
            }
            require(listeners==3, "CAS owner listener registration/cleanup inventory differs.");
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
    static void verifyReadOnlyInputGate(ABC abc,InstanceInfo instance) {
        var body=ownedBody(abc,instance,"ApexFormsCommandBlocksInput");
        require(propertyCalls(abc,body).isEmpty(),"Input lease classification must not call native code or mutate an appearance.");
        uniqueLiteral(abc,body,"status");
        var required=Set.of("apexReceiving","apexPendingFields","apexPendingPhase","apexBoundSim",
            "apexClaimNonce","apexNonce","apexPendingReply","mutation_started","length","mCurrSimInfo","simId");
        var found=new HashSet<String>();boolean phase=false,length=false;
        var rows=body.getCode().code;
        for(int i=0;i<rows.size();i++) {
            for(String key:required) if(property(abc,rows.get(i),0x60,key)||property(abc,rows.get(i),0x66,key))found.add(key);
            if(i+1<rows.size()&&property(abc,rows.get(i),0x60,"apexPendingPhase")&&opcode(rows.get(i+1),0x24)&&rows.get(i+1).operands[0]==1)phase=true;
            if(i+1<rows.size()&&property(abc,rows.get(i),0x66,"length")&&opcode(rows.get(i+1),0x24)&&rows.get(i+1).operands[0]==7)length=true;
        }
        require(found.equals(required)&&phase&&length,"Only an exact same-Sim same-nonce unmutated status readback may release form input.");
        for(String caller:Set.of("ApexFormsNextFrame","ApexFormsOwnedTick","ApexMoleculeDrain","ApexPairPanel","ApexPairTick"))
            require(propertyCalls(abc,ownedBody(abc,instance,caller)).contains("ApexFormsCommandBlocksInput"),
                "Native form and pair input must share the exact CLI write-ownership gate.");
    }
    static void verifyFastOwnerReadback(ABC abc, InstanceInfo instance) {
        verifyReadOnlyInputGate(abc,instance);
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
        require(next.equals(Set.of("removeEventListener","ApexFormsOwnedTick","ApexFormsObservedSim","ApexFormsScheduleFrame","ApexFormsCommandBlocksInput")),
            "Next-frame form callback must detach and process its bound view without waiting for a network poll.");
        var gates=new HashSet<String>();boolean returned=false;
        for(var op:nextBody.getCode().code) {
            for(String gate:Set.of("apexDisconnected","apexTicking","apexPendingPhase","apexNativeConnected","apexBoundSim"))
                if(property(abc,op,0x60,gate)||property(abc,op,0x66,gate))gates.add(gate);
            if(opcode(op,0x47))returned=true;
            if(property(abc,op,0x46,"ApexFormsOwnedTick")||property(abc,op,0x4f,"ApexFormsOwnedTick")) {
                require(returned&&gates.size()==5,"Next-frame form work lacks the connected idle same-Sim/lifetime gate.");break;
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
        int menuFrames=0;
        for(var op:ownedBody(abc,instance,"ApexFormsClick").getCode().code)
            if(property(abc,op,0x4f,"ApexFormsScheduleFrame"))menuFrames++;
        require(menuFrames==2,"Variant opening and same-owner dismissal must render on the next frame, without waiting for the network Timer.");
        int toolbarFrames=0;
        for(var op:ownedBody(abc,instance,"ApexFormsToolbarClick").getCode().code)
            if(property(abc,op,0x4f,"ApexFormsScheduleFrame"))toolbarFrames++;
        require(toolbarFrames==3,"Variant Back and ordinary toolbar changes must share deferred next-frame presentation.");
        var paletteSnapshot=ownedBody(abc,instance,"ApexSnapshot");
        uniqueLiteral(abc,paletteSnapshot,"history_palette");
        uniqueLiteral(abc,paletteSnapshot,"not-queried-outside-bound-pelt-owner");
        uniqueLiteral(abc,paletteSnapshot,"Incomplete native pelt palette");
        uniqueLiteral(abc,paletteSnapshot,"Untyped native pelt swatch ID");
        uniqueLiteral(abc,paletteSnapshot,"Incomplete native pelt color list");
        int resolvedPalette=uniqueLiteral(abc,paletteSnapshot,"Unresolved native pelt swatch color");
        var paletteOps=paletteSnapshot.getCode().code;int paletteReads=0,listRead=-1;
        for(int n=2;n<paletteOps.size();n++)
            if(property(abc,paletteOps.get(n),0x46,"CallGameService") && paletteOps.get(n).operands[1]==2 &&
               stringLiteral(abc,paletteOps.get(n-2),"CasGetSwatchColorSelected") &&
               opcode(paletteOps.get(n-1),0x24) && paletteOps.get(n-1).operands[0]==6)paletteReads++;
        require(paletteReads==1,"History must retain the typed native FURTONE palette read.");
        for(int n=2;n<paletteOps.size();n++)
            if(property(abc,paletteOps.get(n),0x46,"CallGameService") && paletteOps.get(n).operands[1]==2 &&
               stringLiteral(abc,paletteOps.get(n-2),"CasGetSwatchColorList") &&
               opcode(paletteOps.get(n-1),0x24) && paletteOps.get(n-1).operands[0]==6) {
                require(listRead<0,"Ambiguous native FURTONE color list.");listRead=n;
            }
        boolean exactId=false,nativeColor=false;
        for(int n=listRead+1;n<resolvedPalette;n++) {
            exactId|=property(abc,paletteOps.get(n),0x66,"dataID");
            nativeColor|=property(abc,paletteOps.get(n),0x66,"color");
        }
        require(listRead>=0 && resolvedPalette>listRead && exactId && nativeColor,
            "Selected pelt dataID strings must resolve through EA's exact native color palette.");
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
        require(nativeOwnerCallers.equals(Set.of("ApexFormsTick","ApexFormsNextFrame","ApexPresentationFrame","ApexPresentationPrime")),
            "Independent form buttons may execute only on the owned Timer, guarded gesture frame or guarded member bootstrap.");
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
        require(propertyCalls(abc,drain).equals(Set.of("ApexClone","CallGameService","ApexFormsCommandBlocksInput")),
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
            "apexFormsDesiredId",
            "apexFormsNativeIntent","apexFormsNativeState"))
            if(property(abc,op,0x60,gate)||property(abc,op,0x66,gate))gates.add(gate);
        require(gates.size()==5,"Deferred molecule selection must validate its exact session and idle native owner.");
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
    static void verifyPresentationBootstrap(ABC abc,InstanceInfo instance) {
        var frame=ownedBody(abc,instance,"ApexPresentationFrame");
        var calls=propertyCalls(abc,frame);
        require(calls.equals(Set.of("ApexPresentationStop","ApexPresentationReady","getTimer","test","ApexTick","ApexPresentationSchedule",
            "ApexFormsTryLocalCatalog","ApexFormsOwnedTick","ApexFormsObservedSim","ApexSocketFailure","ApexPresentationPrime")),
            "Member presentation may only advance its checked bootstrap, never navigate or execute a new mutation.");
        var required=new HashSet<String>();
        int drainAt=-1,framePosition=0;
        for(var row:frame.getCode().code) {
            if(property(abc,row,0x4f,"ApexTick")||property(abc,row,0x46,"ApexTick"))drainAt=framePosition;
            for(String key:Set.of("apexDisconnected","apexTicking","mCurrSimInfo","apexPendingFields","apexReceiving","apexPendingPhase"))
                if(property(abc,row,0x60,key)||property(abc,row,0x66,key))required.add(key);
            for(String key:Set.of("apexPendingFields","apexReceiving","apexPendingPhase"))
                require((!property(abc,row,0x60,key)&&!property(abc,row,0x66,key))||drainAt>=0,
                    "Member bootstrap must drain owned ACKs; command execution remains gated inside ApexTick.");
            if(opcode(row,0x61))require(Set.of("apexPresentationFrames","apexPresentationMilliseconds","apexPresentationFirstFrameDelay","apexPresentationPrimeMs").contains(
                abc.constants.getString(abc.constants.getMultiname(row.operands[0]).name_index)),
                "Member presentation cannot overwrite a command, owner or transport state.");
            if(property(abc,row,0x4f,"ApexTick")||property(abc,row,0x46,"ApexTick"))
                require(row.operands[1]==1,"Bootstrap must identify its frame event to the checked dispatcher.");
            framePosition++;
        }
        require(required.size()==6&&drainAt>=0,"Member presentation lacks its lifetime/reentrancy/exact native-Sim and post-ACK claim gates.");
        var prime=ownedBody(abc,instance,"ApexPresentationPrime");
        var primeCalls=propertyCalls(abc,prime);
        require(primeCalls.containsAll(Set.of("ApexNativeOpen","ApexFormsTryLocalCatalog","ApexFormsOwnedTick","ApexPresentationReady")) &&
            Collections.disjoint(primeCalls,Set.of("CallGameService","ApexExecute","ApexReadback","ApexPairExecute","ApexNativeExchange")),
            "Local presentation must validate the opened native lease without a fresh native Sim-info call or CLI execution.");
        var primeGuards=new HashSet<String>();boolean nativeOpen=false;
        for(var op:prime.getCode().code) {
            for(String key:Set.of("apexDisconnected","apexTicking","apexPendingFields","apexReceiving","apexPendingPhase",
                "apexMoleculeIntent","apexFormsNativeIntent","apexFormsDesiredId","apexPairIntent","mCurrSimInfo","simId","householdId"))
                if(property(abc,op,0x60,key)||property(abc,op,0x66,key))primeGuards.add(key);
            if(property(abc,op,0x46,"ApexNativeOpen")||property(abc,op,0x4f,"ApexNativeOpen")) {
                require(primeGuards.size()==12,"Local presentation cannot bypass a claimed command, queued gesture or exact delivered identity.");nativeOpen=true;
            }
            if(opcode(op,0x61)) require(property(abc,op,0x61,"apexFormsHousehold")||property(abc,op,0x61,"apexPresentationCatalogMs")||property(abc,op,0x61,"apexPresentationMenuMs"),"Local presentation may only cache the validated household and bounded read-only timing counters.");
        }
        require(nativeOpen,"Local presentation lost its exact native opening check.");
        var open=ownedBody(abc,instance,"ApexNativeOpen");
        uniqueLiteral(abc,open,"BUSY");
        require(propertyCalls(abc,open).equals(Set.of("ApexNativeExchange","test","substr")),
            "A busy prior member transport must retry its bounded bootstrap without executing a new action.");
        var ready=ownedBody(abc,instance,"ApexPresentationReady");var identity=new HashSet<String>();
        for(var row:ready.getCode().code)for(String key:Set.of("apexNativeConnected","apexNonce","apexBoundSim","apexFormsRoot",
            "apexFormsSelectedId","apexFormsNativeState","apexFormsDesiredId","apexFormsOwnerTotal","apexFormsOwners","apexPairSignature","apexFormsNativeGeneration","mCurrSimInfo","apexPresentationSim","apexFormsLocalCatalog"))
            if(property(abc,row,0x60,key)||property(abc,row,0x66,key))identity.add(key);
        require(identity.size()==14&&propertyCalls(abc,ready).isEmpty(),"Member UI readiness must match its complete bound owner/catalog/pair identity.");
        uniqueLiteral(abc,ready,"bound");
        var notify=ownedBody(abc,instance,"ApexPresentationNotify");
        require(propertyCalls(abc,notify).equals(Set.of("test","getTimer","ApexPresentationReady","ApexPresentationStop","ApexPresentationSchedule")),
            "Native member notification may only validate identity and queue the bounded presentation frame.");
        var notificationGuards=new HashSet<String>();boolean pendingTargetBeforeReturn=false,firstNotifyReturn=false;
        for(var row:notify.getCode().code) {
            if(!firstNotifyReturn&&(property(abc,row,0x60,"apexPresentationSim")||property(abc,row,0x66,"apexPresentationSim")))pendingTargetBeforeReturn=true;
            if(opcode(row,0x47)&&!firstNotifyReturn) {
                firstNotifyReturn=true;require(pendingTargetBeforeReturn,"Returning to the already-bound member must not retain a stale incoming target.");
            }
            if(property(abc,row,0x46,"getTimer")||property(abc,row,0x4f,"getTimer"))
                require(notificationGuards.size()==7,"Repeated incoming notifications must retain their original start timestamp.");
            for(String key:Set.of("apexDisconnected","apexPresentationListener","simId","apexBoundSim","apexPresentationSim","apexPresentationStarted","apexPresentationMilliseconds"))
                if(property(abc,row,0x60,key)||property(abc,row,0x66,key))notificationGuards.add(key);
            if(opcode(row,0x61))require(Set.of("apexPresentationSim","apexPresentationStarted","apexPresentationMilliseconds","apexPresentationFrames","apexPresentationFirstFrameDelay","apexPresentationPrimeMs","apexPresentationCatalogMs","apexPresentationMenuMs","apexPresentationStateMs","apexPresentationPairMs","apexPresentationIconsMs","apexPresentationGraphicsMs").contains(
                abc.constants.getString(abc.constants.getMultiname(row.operands[0]).name_index)),
                "Native member notification must not replace owner, command or transport state.");
        }
        require(notificationGuards.size()==7,"Native member notification lost its delivered identity/lifetime/timestamp gates.");
        var schedule=ownedBody(abc,instance,"ApexPresentationSchedule");boolean budget=false;
        for(var row:schedule.getCode().code)if(opcode(row,0x25)&&row.operands[0]==2000)budget=true;
        require(budget&&propertyCalls(abc,schedule).equals(Set.of("ApexPresentationReady","getTimer","addEventListener")),
            "Fast member setup must be bounded and leave slow/loading peers on the ordinary timer.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexPresentationStop")).equals(Set.of("removeEventListener")),
            "Completed/closed member setup must detach its frame listener.");
        var tick=ownedBody(abc,instance,"ApexTick");var rows=tick.getCode().code;int at=-1;
        for(int i=0;i<rows.size();i++)if(property(abc,rows.get(i),0x66,"ENTER_FRAME")){require(at<0,"Ambiguous bootstrap event guard.");at=i;}
        require(at>=0,"Bootstrap must not execute a queued CLI mutation/readback on its frame.");
        int receiveAt=-1;
        for(int i=0;i<at;i++) {
            if(property(abc,rows.get(i),0x4f,"ApexNativeReceive")||property(abc,rows.get(i),0x46,"ApexNativeReceive"))receiveAt=i;
            require(!property(abc,rows.get(i),0x4f,"ApexExecute")&&!property(abc,rows.get(i),0x4f,"ApexReadback"),
                "Bootstrap cannot execute a command before receiving its ACK and yielding outstanding work.");
        }
        require(receiveAt>=0,"Bounded member bootstrap must drain its native ACK before the command yield guard.");
        var guards=new HashSet<String>();boolean returned=false;
        for(int i=at+1;i<rows.size();i++) {
            for(String key:Set.of("apexPendingFields","apexReceiving"))
                if(property(abc,rows.get(i),0x60,key)||property(abc,rows.get(i),0x66,key))guards.add(key);
            if(opcode(rows.get(i),0x47)){returned=true;break;}
            require(!property(abc,rows.get(i),0x4f,"ApexExecute")&&!property(abc,rows.get(i),0x4f,"ApexReadback"),
                "Bootstrap event can reach a command before its yield guard.");
        }
        require(returned&&guards.size()==2,"Bootstrap must yield received or outstanding CLI work to its owning Timer.");
        var local=ownedBody(abc,instance,"ApexFormsTryLocalCatalog");
        uniqueLiteral(abc,local,"LOCALOWNERS|");uniqueLiteral(abc,local,"Prepared native form page lost its exact continuation");
        require(propertyCalls(abc,local).containsAll(Set.of("ApexNativeExchange","ApexFormsConsumeCatalog"))&&
            Collections.disjoint(propertyCalls(abc,local),Set.of("CallGameService","ApexExecute","ApexReadback","ApexPairExecute","ApexFormsOwnedTick")),
            "Prepared menu loading must read exact native pages without issuing a game edit or CLI command.");
        var localGuards=new HashSet<String>();
        for(var op:local.getCode().code)for(String key:Set.of("apexDisconnected","apexNativeChannel","mCurrSimInfo","simId","apexBoundSim","apexFormsLocalOffset","apexFormsOwnerTotal","apexFormsOwners"))
            if(property(abc,op,0x60,key)||property(abc,op,0x66,key))localGuards.add(key);
        require(localGuards.size()==8,"Prepared menu lacks its exact current member/channel and complete page gates.");
        var consume=ownedBody(abc,instance,"ApexFormsConsumeCatalog");
        uniqueLiteral(abc,consume,"Late peer form catalogue differs from the prepared native page");
        require(Collections.disjoint(propertyCalls(abc,consume),Set.of("CallGameService","ApexNativeExchange","ApexExecute","ApexReadback","ApexFormsOwnedTick")),
            "Menu parsing and duplicate verification must remain data-only.");
    }
    static void verifyOwnerMetadataReadback(ABC abc, InstanceInfo instance) {
        var body=ownedBody(abc,instance,"ApexReadback");
        require(propertyCalls(abc,body).contains("ApexFormsReadNativeState"),
            "Owner readback must reconcile the bound native owner without waiting for a changed-owner heartbeat.");
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
    static void verifyImmediatePairAcknowledgement(ABC abc,InstanceInfo instance) {
        for(String caller:Set.of("ApexFormsOwnedTick","ApexReadback"))
            require(propertyCalls(abc,ownedBody(abc,instance,caller)).contains("ApexFormsRefreshBoundPair"),
                "Both native strip and typed owner selection must finish the same EA pair presentation.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexReadback")).contains("ApexPresentationReady"),
            "Typed owner acknowledgement must retain the final presentation readiness check.");
        var body=ownedBody(abc,instance,"ApexFormsRefreshBoundPair");
        require(propertyCalls(abc,body).equals(Set.of("ApexPairRead","ApexPairLabel","CallUIService",
                "ApexFormsReadNativeState","ApexFormsBindUiKind")),
            "Shared pair presentation must not rebind, copy, convert or poll a native model.");
        var rows=body.getCode().code;
        int refresh=-1,read=-1,assignment=-1;
        for(int i=0;i<rows.size();i++) {
            var row=rows.get(i);
            if(property(abc,row,0x46,"CallUIService")||property(abc,row,0x4f,"CallUIService"))refresh=i;
            if(refresh>=0&&i>refresh&&(property(abc,row,0x46,"ApexFormsReadNativeState")||property(abc,row,0x4f,"ApexFormsReadNativeState")))read=i;
            if(refresh>=0&&i>refresh&&property(abc,row,0x61,"apexPairSignature"))assignment=i;
        }
        require(refresh>=0&&read>refresh&&assignment>read,
            "Immediate native pair refresh must acknowledge its fresh bound state without another polling tick.");
        var required=Set.of("protocol","enabled","sim_id","apexBoundSim","apexFormsNativeState",
            "apexFormsDesiredId","apexFormsSelectedId","apexFormsNativeGeneration");
        var observed=new HashSet<String>();
        for(int i=refresh+1;i<assignment;i++) for(String name:required)
            if(property(abc,rows.get(i),0x60,name)||property(abc,rows.get(i),0x66,name))observed.add(name);
        require(observed.equals(required),"Immediate pair readiness lacks its typed exact-Sim/owner/generation acknowledgement.");
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
    static void verifyBoundedNativeRefusal(ABC abc,MethodBody body) {
        var code=body.getCode().code;int p=uniqueLiteral(abc,body,"REFUSED|");
        uniqueLiteral(abc,body,"Native acceptance readiness refused: ");
        require(p>=2 && p+22<code.size() && gridBudgetOp(code.get(p-2),0xd3) && gridBudgetOp(code.get(p-1),0x70) &&
            property(abc,code.get(p+1),0x46,"indexOf") && code.get(p+1).operands[1]==1 &&
            gridBudgetOp(code.get(p+2),0x24,0) && gridBudgetOp(code.get(p+3),0xac) && gridBudgetOp(code.get(p+4),0x2a) && opcode(code.get(p+5),0x12) &&
            gridBudgetOp(code.get(p+6),0x29) && gridBudgetOp(code.get(p+7),0xd3) && gridBudgetOp(code.get(p+8),0x70) &&
            property(abc,code.get(p+9),0x66,"length") && gridBudgetOp(code.get(p+10),0x25,1024) && gridBudgetOp(code.get(p+11),0xae) && opcode(code.get(p+12),0x12) &&
            property(abc,code.get(p+13),0x5d,"Error") && stringLiteral(abc,code.get(p+14),"Native acceptance readiness refused: ") &&
            gridBudgetOp(code.get(p+15),0xd3) && gridBudgetOp(code.get(p+16),0x70) && gridBudgetOp(code.get(p+17),0x24,8) &&
            property(abc,code.get(p+18),0x46,"substr") && code.get(p+18).operands[1]==1 && gridBudgetOp(code.get(p+19),0xa0) &&
            property(abc,code.get(p+20),0x4a,"Error") && code.get(p+20).operands[1]==1 && gridBudgetOp(code.get(p+21),0x03),
            "Native refusal must match its exact prefix,1024 bound,substring and throwing-only branch.");
        require(bootstrapTarget(code.get(p+5),0)==code.get(p+12).getAddress() &&
            bootstrapTarget(code.get(p+12),0)==code.get(p+22).getAddress(),"Native bounded refusal has unreviewed branch polarity or targets.");
        int prefixes=0,slices=0;for(var op:code){if(property(abc,op,0x46,"indexOf"))prefixes++;if(property(abc,op,0x46,"substr"))slices++;}
        require(prefixes==1 && slices==1,"Native refusal helpers may only occur in the reviewed bounded throw.");
    }
    static int typedIndexReadEnd(ABC abc,MethodBody body,int start) {
        var code=body.getCode().code;var signature=abc.method_info.get(body.method_info);
        require(signature.param_types.length==7 && "int".equals(abc.constants.getString(
            abc.constants.getMultiname(signature.param_types[3]).name_index)),"Native occult index must remain formal int argument four.");
        if(start<code.size() && gridBudgetOp(code.get(start),0x62,4)) {
            // Historical direct-register compilation: no preceding write may
            // replace the formal parameter with an unrelated local value.
            for(int i=0;i<start;i++)require(!gridBudgetOp(code.get(i),0x63,4),"Native occult formal index register was overwritten.");
            return start+1;
        }
        int slot=gridBudgetSlot(abc,body,"index","int"),store=-1;
        require((signature.flags&2)!=0 && start+1<code.size() && gridBudgetOp(code.get(start),0x65,1) &&
            gridBudgetOp(code.get(start+1),0x6c,slot),"Native occult index is not its owned activation parameter.");
        for(int i=0;i<code.size();i++)if(gridBudgetOp(code.get(i),0x6d,slot)) {
            require(store==-1 && i>=2 && gridBudgetOp(code.get(i-2),0x65,1) && gridBudgetOp(code.get(i-1),0x62,4),
                "Native occult activation index must be copied once from formal argument four.");store=i;
        }
        require(store>=0 && store<start,"Native occult activation index initialization is missing.");
        for(int i=0;i<store;i++)require(!gridBudgetOp(code.get(i),0x63,4),"Native occult formal index was overwritten before capture.");
        require(!bootstrapReachable(body,start,store),"Native occult activation index capture does not dominate its setter.");
        return start+2;
    }
    static void verifyTypedControls(ABC abc, InstanceInfo instance) {
        // Execute: four palette calls, two physique calls, preset write,
        // one product lookup, two family queries, equipped query, clear and
        // layered write. Result: preset query and palette query on next tick.
        // The existing-member view adds five reviewed calls: current Sim,
        // available occults, full-edit permission, edit mode and SetSimOccult.
        // Its next-tick result adds one available-occults readback.
        Map<String,Integer> counts=Map.of("ApexCatalog",2,"ApexControlExecute",35,"ApexControlResult",5,
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
        var viewBody=ownedBody(abc,instance,"ApexControlExecute");var viewCode=viewBody.getCode().code;
        for(int i=0;i<viewCode.size();i++) if(stringLiteral(abc,viewCode.get(i),"SetSimOccult")) {
            viewSetters++;
            int call=typedIndexReadEnd(abc,viewBody,i+1);
            require(call<viewCode.size() &&
                (property(abc,viewCode.get(call),0x46,"CallGameService") || property(abc,viewCode.get(call),0x4f,"CallGameService")) &&
                viewCode.get(call).operands.length==2 && viewCode.get(call).operands[1]==2,
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
    static void verifyCatalogThinReadback(ABC abc,InstanceInfo instance) {
        var allowed=ownedBody(abc,instance,"ApexCatalogReadbackOnly");
        require(propertyCalls(abc,allowed).isEmpty(),"Thin readback eligibility must perform no work.");
        Set<String> operations=new HashSet<>();
        for(var op:allowed.getCode().code)if(opcode(op,0x2c))operations.add(abc.constants.getString(op.operands[0]));
        require(operations.equals(Set.of("catalog-state","catalog-search","catalog-style",
            "catalog-cards","catalog-card-reset","catalog-width-drag","panel-layout","catalog-trace","catalog-layout-trace")),
            "Thin readback operation allowlist includes an inventory or appearance path.");
        var context=ownedBody(abc,instance,"ApexCatalogReadbackContext");
        uniqueLiteral(abc,context,"CasGetCurrSimOutfitSlot");uniqueLiteral(abc,context,"STATE|");
        require(propertyCalls(abc,context).equals(Set.of("test","split","CallGameService","ApexNativeExchange")),
            "Thin readback context must only read exact outfit and authenticated owner state.");
        var snapshot=ownedBody(abc,instance,"ApexCatalogSnapshot");
        uniqueLiteral(abc,snapshot,"native-cas-catalog-client");
        require(propertyCalls(abc,snapshot).equals(Set.of("ApexEncode","ApexCatalogStatus")),
            "Thin snapshot invokes native inventory or repeats display readback.");
        require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,"ApexControlResult")),
            Set.of("ApexCatalogStatus","ApexCatalogTraceStatus","ApexLayoutTraceStatus")),
            "Control result must reuse its same-event captured catalogue workspace.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexReadback")).containsAll(
            Set.of("ApexCatalogReadbackOnly","ApexCatalogReadbackContext","ApexCatalogSnapshot","ApexSnapshot")),
            "Readback lost its separate thin/full snapshot paths.");
    }
    static void ownedSignature(ABC abc,InstanceInfo instance,String method,List<String> parameters,String returned) {
        var body=ownedBody(abc,instance,method);var info=abc.method_info.get(body.method_info);
        require(info.param_types.length==parameters.size() && returned.equals(abc.constants.getString(abc.constants.getMultiname(info.ret_type).name_index)),
            "Reviewed diagnostic/navigation method signature differs: "+method);
        for(int n=0;n<parameters.size();n++)require(parameters.get(n).equals(abc.constants.getString(abc.constants.getMultiname(info.param_types[n]).name_index)),
            "Reviewed diagnostic/navigation parameter type differs: "+method);
        Multiname reference=null,actual=null;
        for(var trait:instance.instance_traits.traits) {
            if(name(abc,trait).equals("ApexCatalogReadbackContext"))reference=abc.constants.getMultiname(trait.name_index);
            if(name(abc,trait).equals(method))actual=abc.constants.getMultiname(trait.name_index);
        }
        require(reference!=null && actual!=null && reference.kind==Multiname.QNAME && actual.kind==Multiname.QNAME &&
            reference.namespace_index==actual.namespace_index && abc.constants.getNamespace(actual.namespace_index).kind==0x05 &&
            // FFDec retains one extra lexical level for TimerStep's reviewed
            // nested diagnostic catch. The later common native-scope delta is
            // applied to both sides; no generic depth range is accepted.
            body.init_scope_depth==ownedBody(abc,instance,"ApexCatalogReadbackContext").init_scope_depth+(method.equals("ApexCatalogTimerStep")?1:0),
            "Reviewed diagnostic/navigation method lost its private same-class lexical owner: "+method);
        for(var op:body.getCode().code)require(!Set.of(0x40,0x41,0x44,0x4c,0x4e).contains(op.definition.instructionCode),
            "Reviewed diagnostic/navigation method has an indirect/anonymous callback: "+method);
    }
    static Set<String> methodCallers(ABC abc,InstanceInfo instance,String target) {
        var result=new HashSet<String>();
        for(var trait:instance.instance_traits.traits)if(trait instanceof TraitMethodGetterSetter &&
            propertyCalls(abc,abc.findBody(((TraitMethodGetterSetter)trait).method_info)).contains(target))result.add(name(abc,trait));
        return result;
    }
    static void verifyPanelNavigation(ABC abc,InstanceInfo instance) {
        ownedSignature(abc,instance,"ApexPanelNavigationSnapshot",List.of("Object","Object","int"),"Object");
        var snapshot=ownedBody(abc,instance,"ApexPanelNavigationSnapshot");
        require(propertyCalls(abc,snapshot).equals(Set.of("isFinite")),
            "Panel navigation snapshot performs native, inventory, layout or diagnostic work.");
        for(String literal:List.of("native-cas-navigation-client","appearance_written","navigation_identity","request_id","peer_nonce",
            "before","after","requested_menu_state","not-available-current-panel","cached-current-panel-only"))uniqueLiteral(abc,snapshot,literal);
        var identity=snapshot.getCode().code;int mismatch=uniqueLiteral(abc,snapshot,"Panel navigation changed its bound native Sim/form/outfit context");
        require(mismatch>=17 && mismatch+3<identity.size() && opcode(identity.get(mismatch-17),0x62) &&
            stringLiteral(abc,identity.get(mismatch-16),"menu_state") && opcode(identity.get(mismatch-15),0xab) && opcode(identity.get(mismatch-14),0x96) &&
            opcode(identity.get(mismatch-13),0x2a) && opcode(identity.get(mismatch-12),0x12) && opcode(identity.get(mismatch-11),0x29) &&
            opcode(identity.get(mismatch-10),0xd1) && opcode(identity.get(mismatch-9),0x62) && opcode(identity.get(mismatch-8),0x66) &&
            opcode(identity.get(mismatch-7),0xd2) && opcode(identity.get(mismatch-6),0x62) && opcode(identity.get(mismatch-5),0x66) &&
            identity.get(mismatch-17).operands[0]==identity.get(mismatch-9).operands[0] && identity.get(mismatch-9).operands[0]==identity.get(mismatch-6).operands[0] &&
            abc.constants.getMultiname(identity.get(mismatch-8).operands[0]).kind==Multiname.MULTINAMEL &&
            abc.constants.getMultiname(identity.get(mismatch-5).operands[0]).kind==Multiname.MULTINAMEL &&
            opcode(identity.get(mismatch-4),0xac) && opcode(identity.get(mismatch-3),0x96) && opcode(identity.get(mismatch-2),0x12) &&
            property(abc,identity.get(mismatch-1),0x5d,"Error") && property(abc,identity.get(mismatch+1),0x4a,"Error") && opcode(identity.get(mismatch+2),0x03) &&
            bootstrapTarget(identity.get(mismatch-12),0)==identity.get(mismatch-2).getAddress() &&
            bootstrapTarget(identity.get(mismatch-2),0)==identity.get(mismatch+3).getAddress(),
            "Panel navigation must compare every original before/after field strictly, excluding only menu state.");
        require(methodCallers(abc,instance,"ApexPanelNavigationSnapshot").equals(Set.of("ApexReadback")),
            "Panel navigation snapshot escaped its deferred owned readback.");
        require(methodCallers(abc,instance,"ApexCatalogReadbackContext").equals(Set.of("ApexExecute","ApexReadback")),
            "Exact catalogue/navigation context escaped its owned admission/readback phases.");
        for(String phase:List.of("ApexExecute","ApexReadback")) {
            var body=ownedBody(abc,instance,phase);
            require(propertyCalls(abc,body).containsAll(Set.of("ApexOwnerSimRow","ApexCatalogReadbackContext","CallGameService")),
                "Panel navigation lacks its fresh owned native cursor: "+phase);
            boolean scoped=false;
            for(var op:body.getCode().code)scoped|=stringLiteral(abc,op,"panel-navigation");
            require(scoped,"Panel navigation lacks its separate typed operation: "+phase);
        }
        var read=ownedBody(abc,instance,"ApexReadback");var code=read.getCode().code;
        int navigation=-1;
        for(int n=0;n<code.size();n++)if(property(abc,code.get(n),0x46,"ApexPanelNavigationSnapshot")) {
            require(navigation<0 && code.get(n).operands[1]==3,"Panel navigation snapshot must have one complete before/after/request argument route.");navigation=n;
        }
        require(navigation>=0,"Panel navigation next-tick snapshot is absent.");
        boolean bound=false;
        for(int n=Math.max(0,navigation-28);n<navigation;n++)bound|=stringLiteral(abc,code.get(n),"panel-navigation");
        require(bound,"Panel navigation snapshot is not behind its explicit operation branch.");
        boolean guardedFallback=false;
        for(int n=0;n+2<code.size();n++)if(stringLiteral(abc,code.get(n),"panel-navigation") && opcode(code.get(n+1),0xab) && opcode(code.get(n+2),0x96))guardedFallback=true;
        require(guardedFallback,"Panel navigation cannot invoke a full diagnostic error fallback.");
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
        verifyCanineCatalog(abc,instance);
        var click=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogOpen"));
        require(click.equals(Set.of("getTimer","ApexInputTiming")),"Catalog radial click must only queue and record timing.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogInvalidate")).isEmpty(),
            "Outfit/part catalog invalidation must only mark dirty, without native work.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogObserveBinding")).equals(Set.of("isFinite")),
            "Native catalog alignment observer must only detach primitive parameters.");
        var frame=ownedBody(abc,instance,"ApexCatalogFrame");boolean pending=false,receiving=false;
        for(var op:frame.getCode().code)if(op.definition.instructionCode==0x66 || op.definition.instructionCode==0x60) {
            final String member=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
            require(!"apexAwaiting".equals(member),"Catalog player input waits for the transport poll.");
            pending|="apexPendingFields".equals(member);receiving|="apexReceiving".equals(member);
        }
        require(pending&&receiving,"Catalog player input lacks active CAS command guards.");
        int restores=0;
        for(var op:frame.getCode().code)if(property(abc,op,0x46,"ApexCardRestore") || property(abc,op,0x4f,"ApexCardRestore"))restores++;
        require(restores==1,"Hidden clothing grids must retain geometry; only the error path may restore in a frame.");
        var dispose=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogDispose"));
        require(dispose.contains("ApexCardForget") && !dispose.contains("ApexCardRestore"),
            "CAS unload must release layout references without redrawing retired catalogue tuning.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCardForget")).isEmpty(),
            "Retired card geometry must not call a native grid or enumerate its cells.");
        var selected=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogSelection"));
        require(selected.contains("ApexCatalogCells") && Collections.disjoint(selected,Set.of("CallGameService","CallUIService","ApexNativeExchange")),
            "Selection animation must only inspect native recycled cells, without game queries.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogCells")).equals(Set.of("GetAllDisplayObjectCells")),
            "The per-frame cell cache may only enumerate the actual recycled grid.");
        require(propertyCalls(abc,ownedBody(abc,instance,"ApexEquippedNavigation")).isEmpty(),
            "Leaving equipped view cannot fetch or mutate native data.");
        var resolver=propertyCalls(abc,ownedBody(abc,instance,"ApexEquippedResolve"));
        require(Collections.disjoint(resolver,Set.of("ApexNativeExchange","SetCatalogSlotSelected","ClearSelectedBodyType","GetCatalogBaseItems")),
            "Equipped resolution must read selected slots, without scanning or changing the catalog.");
        require(selected.containsAll(Set.of("moveTo","lineTo","curveTo")) && !selected.contains("drawRoundRect"),
            "Selection outline must explicitly close all four edges in GFx.");
        var equipped=ownedBody(abc,instance,"ApexCatalogReadEquipped");
        uniqueLiteral(abc,equipped,"EQUIPPED|");
        int nativeReads=0;
        for(var op:equipped.getCode().code)if(property(abc,op,0x46,"ApexNativeExchange")) {
            require(op.operands[1]==1,"Equipped inventory must encode its complete channel/outfit in one native pipe argument.");nativeReads++;
        }
        require(nativeReads==1,"Equipped inventory requires exactly one bounded native read.");
        var slide=propertyCalls(abc,ownedBody(abc,instance,"ApexCatalogSlide"));
        require(Collections.disjoint(slide,Set.of("CallGameService","CallUIService","ApexNativeExchange","PositionCells","ApexCatalogDraw")),
            "Catalog slider input cannot rebuild the grid, panel or perform native requests.");
        boolean margin=false;
        var layoutCalls=propertyCalls(abc,ownedBody(abc,instance,"ApexCardApply"));
        uniqueLiteral(abc,ownedBody(abc,instance,"ApexCardApply"),"cards:");
        require(layoutCalls.contains("ApexLayoutReset") && !layoutCalls.contains("PositionCells"),
            "Card layout must reset the native row cache; ordinary positioning can retain NaN.");
        for(String method:List.of("ApexCardApply","ApexCardRestore")) {
            var transaction=ownedBody(abc,instance,method);boolean readsLease=false,acquires=false,releases=false;
            var code=transaction.getCode().code;
            for(int at=0;at<code.size();at++) {
                readsLease|=property(abc,code.get(at),0x66,"SuppressUpdates");
                if(at>0 && property(abc,code.get(at),0x61,"SuppressUpdates")) {
                    acquires|=opcode(code.get(at-1),0x26);releases|=opcode(code.get(at-1),0x27);
                }
            }
            require(readsLease && acquires && releases && transaction.exceptions.length>0,
                "Card geometry must respect the native suppression lease and restore its owned lease through finally: "+method);
            require(Collections.disjoint(propertyCalls(abc,transaction),Set.of("CallGameService","CallUIService","ApexNativeExchange")),
                "Grid geometry transaction cannot fetch or mutate Sim appearance data.");
        }
        for(var op:ownedBody(abc,instance,"ApexCardApply").getCode().code)
            if(op.definition.instructionCode==0x5d || op.definition.instructionCode==0x60) {
                String member=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
                require(!member.equals("olympus"),"Card spacing uses an unresolved package root instead of the native Margin class.");
                if(member.equals("Margin")) {
                    var qname=abc.constants.getMultiname(op.operands[0]);
                    require(qname.kind==Multiname.QNAME && qname.namespace_index>0 &&
                        abc.constants.getNamespace(qname.namespace_index).kind==Namespace.KIND_PACKAGE &&
                        abc.constants.getString(abc.constants.getNamespace(qname.namespace_index).name_index).equals("olympus.core.widget"),
                        "Card spacing Margin does not bind the actual native package class.");
                    margin=true;
                }
            }
        require(margin,"Card spacing has no native Margin class binding.");
        var execute=ownedBody(abc,instance,"ApexExecute");
        int rebind=uniqueLiteral(abc,execute,"CASChangeMenuState");boolean notified=false;
        for(int i=rebind+1;i<Math.min(rebind+8,execute.getCode().code.size());i++) {
            var op=execute.getCode().code.get(i);
            if(property(abc,op,0x46,"SendUIMessage") || property(abc,op,0x4f,"SendUIMessage")) {
                require(op.operands[1]==2,"Native radial navigation needs its exact message/state pair.");notified=true;break;
            }
        }
        require(notified,"Semantic panel navigation does not notify the native radial binding.");
        for(String method:Set.of("ApexCatalogSlide","ApexCatalogValidate"))
            for(var op:ownedBody(abc,instance,method).getCode().code)
                require(!property(abc,op,0x61,"apexCatalogSignature"),"Color/style changes must not invalidate native grid layout.");
    }
    static void verifyCanineCatalog(ABC abc,InstanceInfo instance) {
        var source=ownedBody(abc,instance,"ApexSearchSource");
        uniqueLiteral(abc,source,"werewolf/werewolf_human_cc");
        uniqueLiteral(abc,source,"canine-context");
        require(Collections.disjoint(propertyCalls(abc,source),Set.of("CallGameService","ApexNativeExchange","SetCatalogSlotSelected")),
            "Canine catalogue context must use retained UI identity only.");
        var categories=new HashSet<String>();var identity=new HashSet<String>();
        for(var op:source.getCode().code)if(op.definition.instructionCode==0x66 || op.definition.instructionCode==0x60) {
            String n=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
            if(n==null)continue;
            if(n.startsWith("PROFILE_"))categories.add(n);
            if(n.startsWith("apexForms"))identity.add(n);
        }
        require(categories.equals(Set.of("PROFILE_HEAD_WHOLE_HEADS","PROFILE_HEAD_EARS","PROFILE_HEAD_EYES",
            "PROFILE_HEAD_NOSE","PROFILE_HEAD_MOUTH","PROFILE_HEAD_CHEEK","PROFILE_HEAD_CHIN","PROFILE_HEAD_JAW",
            "PROFILE_HEAD_FOREHEAD","PROFILE_BODY_FUR","PROFILE_GENERIC_PELT")),"Canine catalogue escaped its reviewed categories.");
        require(identity.containsAll(Set.of("apexFormsSelectedId","apexFormsNativeState","apexFormsDesiredId","apexFormsNativeIntent")),
            "Canine catalogue lacks its settled exact named owner checks.");
        var catalog=ownedBody(abc,instance,"ApexCatalog");
        uniqueLiteral(abc,catalog,"canine-context");uniqueLiteral(abc,catalog,"occult");
        require(propertyCalls(abc,catalog).containsAll(Set.of("ApexSearchSource","ApexClone")) &&
            Collections.disjoint(propertyCalls(abc,catalog),Set.of("SetCatalogSlotSelected","CasSetSimOccult","SaveAndExitCAS")),
            "Canine catalogue must detach queries without changing form or equipping a part.");
    }
    static MethodBody classMethod(ABC abc,String type,String method) {
        int index=abc.findClassByName(type);
        require(index>=0,"Native adapter class absent: "+type);
        MethodBody found=null;
        for(var trait:abc.instance_info.get(index).instance_traits.traits)
            if(name(abc,trait).equals(method) && trait instanceof TraitMethodGetterSetter) {
                require(found==null,"Ambiguous native adapter: "+method);
                found=abc.findBody(((TraitMethodGetterSetter)trait).method_info);
            }
        require(found!=null,"Native adapter body absent: "+method);return found;
    }
    static MethodBody cardHeightAdapter(ABC original,ABC compiled) {
        String type="widgets.CAS.controls.CASClothingPanelCellViewMain";
        var before=classMethod(original,type,"height");var after=classMethod(compiled,type,"height");
        require(before.exceptions.length==0 && after.exceptions.length==0,"Unreviewed card getter exceptions.");
        uniqueLiteral(compiled,after,"apexCatalogCardScale");
        require(propertyCalls(compiled,after).equals(Set.of("getChildByName")),"Card getter must only inspect its owned marker.");
        boolean scale=false,height=false,multiply=false;
        for(var op:after.getCode().code) {
            scale|=property(compiled,op,0x66,"scaleY") || property(compiled,op,0x60,"scaleY");
            height|=property(compiled,op,0x66,"height");multiply|=opcode(op,0xa2);
            require(!opcode(op,0x40) && !opcode(op,0x44) && !opcode(op,0x67),"Card getter has an unreviewed function/scope reference.");
        }
        require(scale&&height&&multiply,"Card getter does not apply native height times owned scale.");
        var body=after.clone();body.method_info=before.method_info;
        int delta=before.init_scope_depth-after.init_scope_depth;
        require(delta>=0 && delta<=16,"Card getter lexical scope differs.");
        body.init_scope_depth+=delta;body.max_scope_depth+=delta;body.setCode(body.getCode());return body;
    }
    static MethodBody staticMethod(ABC abc,String type,String method) {
        int index=abc.findClassByName(type);require(index>=0,"Companion class absent: "+type);
        MethodBody found=null;
        for(var trait:abc.class_info.get(index).static_traits.traits)
            if(name(abc,trait).equals(method) && trait instanceof TraitMethodGetterSetter) {
                require(found==null,"Ambiguous Companion adapter: "+method);
                found=abc.findBody(((TraitMethodGetterSetter)trait).method_info);
            }
        require(found!=null,"Companion adapter absent: "+method);return found;
    }
    static List<MethodBody> companionAdapters(ABC original,ABC compiled) {
        var result=new ArrayList<MethodBody>();
        if(original.findClassByName("dcc.history.AgeFilter")<0)return result;
        var routes=Map.of("dcc.history.AgeFilter",List.of("Read","Current"),
            "dcc.history.SavedOutfitNames",List.of("EyeContext"),
            "dcc.history.SkinAdjust",List.of("ContextKey"),
            "dcc.history.OutfitPreview",List.of("Context"));
        var main=compiled.instance_info.get(compiled.findClassByName("widgets.CAS.Customizer.CASCustomizerMain"));
        var provider=ownedBody(compiled,main,"ApexSearchSource");
        uniqueLiteral(compiled,provider,"appearance-context");uniqueLiteral(compiled,provider,"apexAppearanceLease");
        for(var field:List.of("apexBoundSim","apexFormsSelectedId","apexFormsNativeGeneration",
            "apexFormsNativeState","apexFormsDesiredId","apexFormsNativeIntent","apexMoleculeIntent")) {
            boolean present=false;for(var op:provider.getCode().code)
                present|=property(compiled,op,0x66,field)||property(compiled,op,0x60,field);
            require(present,"Companion lease lacks settled identity: "+field);
        }
        require(Collections.disjoint(propertyCalls(compiled,provider),Set.of("CallGameService","ApexNativeExchange")),
            "Companion lease must use cached UI primitives only.");
        for(var entry:routes.entrySet())for(var method:entry.getValue()) {
            var before=staticMethod(original,entry.getKey(),method);
            var after=staticMethod(compiled,entry.getKey(),method);
            var calls=propertyCalls(compiled,after);
            if(method.equals("Current"))require(calls.equals(Set.of("Read")),"Companion cached Sim must be revalidated immediately.");
            else {
                for(var literal:List.of("ApexCatalogSearchSource","appearance-context")) {
                    int occurrences=0;for(var op:after.getCode().code)if(stringLiteral(compiled,op,literal))occurrences++;
                    require(occurrences==(method.equals("Context")?2:1),"Companion lease read inventory differs: "+method);
                }
                require(calls.contains("CallUIService"),"Companion adapter has no named-form lease.");
            }
            if(method.equals("Context"))uniqueLiteral(compiled,after,"CasGetCurrSimOutfitSlot");
            else require(!calls.contains("CallGameService"),"Companion context performs a native Sim query.");
            if(method.equals("EyeContext")) {
                boolean lease=false;for(var op:after.getCode().code)lease|=property(compiled,op,0x66,"apexAppearanceLease");
                require(lease,"Companion eye context accepts a stale named form.");
            }
            for(var call:calls)require(!call.startsWith("Set") && !call.startsWith("CasSet") && !call.startsWith("Clear"),
                "Companion context performs a native write: "+call);
            require(before.exceptions.length==(method.equals("Read")?1:0) && after.exceptions.length==0,
                "Unreviewed Companion adapter exception table.");
            for(var op:after.getCode().code)
                require(!opcode(op,0x40) && !opcode(op,0x44) && !opcode(op,0x67),"Companion adapter has unreviewed lexical references.");
            var body=after.clone();body.method_info=before.method_info;
            int delta=before.init_scope_depth-after.init_scope_depth;
            require(delta>=0 && delta<=16,"Companion adapter scope differs.");
            body.init_scope_depth+=delta;body.max_scope_depth+=delta;body.setCode(body.getCode());result.add(body);
        }
        require(result.size()==5,"Companion adapter inventory differs.");return result;
    }
    static List<MethodBody> lazySwatchAdapters(ABC original,ABC compiled) {
        var result=new ArrayList<MethodBody>();
        if(original.findClassByName("dcc.history.HistoryHost")<0)return result;
        for(String type:List.of("dcc.history.HairSwatches","dcc.history.SwatchRepair")) {
            var before=staticMethod(original,type,"Decorate");
            var after=staticMethod(compiled,type,"Decorate");
            require(before.exceptions.length==0 && after.exceptions.length==0,
                "Lazy swatch adapter has an unreviewed exception region.");
            require(propertyCalls(compiled,after).equals(propertyCalls(original,before)),
                "Lazy swatch adapter must preserve exactly the donor call routes: "+type);
            var code=after.getCode().code;int expensive=-1;int returns=0;boolean hover=false,open=false;
            for(int i=0;i<code.size();i++) {
                var op=code.get(i);
                if(property(compiled,op,0x46,"GetColorSwatchDataFeed") || property(compiled,op,0x46,"CallGameService")) {
                    expensive=i;break;
                }
                returns+=opcode(op,0x47)?1:0;hover|=opcode(op,0xd3);
                open|=type.endsWith("HairSwatches") ? property(compiled,op,0x66,"origin") || property(compiled,op,0x60,"origin") :
                    property(compiled,op,0x46,"Base");
            }
            require(expensive>=0 && returns>=2 && hover && open,
                "Closed swatches must return before native queries or grid allocation: "+type);
            for(var op:code)require(!opcode(op,0x40) && !opcode(op,0x44) && !opcode(op,0x67),
                "Lazy swatch adapter has an unreviewed lexical reference.");
            var body=after.clone();body.method_info=before.method_info;
            int delta=before.init_scope_depth-after.init_scope_depth;
            require(delta>=0 && delta<=16,"Lazy swatch lexical scope differs.");
            body.init_scope_depth+=delta;body.max_scope_depth+=delta;body.setCode(body.getCode());result.add(body);
        }
        return result;
    }
    static final String DRAW_TRACE_TYPE="widgets.CAS.controls.CASClothingPanelCellViewMain";
    static final String DRAW_TRACE_PIN="1f289754f5a45f86a44986a4e61840ab4a647e83a1a8c5d8afc82f1322e359f8";
    static String byteHash(byte[] bytes) {
        try {return HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes));}
        catch(java.security.NoSuchAlgorithmException impossible) {throw new IllegalStateException(impossible);}
    }
    static TraitSlotConst drawTraceStaticTrait(ABC abc) {
        int index=abc.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        require(index>=0,"Draw trace Main class missing.");TraitSlotConst result=null;
        for(var trait:abc.class_info.get(index).static_traits.traits)if(name(abc,trait).equals("apexCatalogDrawTraceStep")) {
            require(result==null && trait instanceof TraitSlotConst,"Ambiguous draw trace callback trait.");
            result=(TraitSlotConst)trait;
        }
        require(result!=null && result.value_index==0 && result.type_index>0 &&
            abc.constants.getString(abc.constants.getMultiname(result.type_index).name_index).equals("Function"),
            "Draw trace must be an uninitialized nullable Function trait.");
        var q=abc.constants.getMultiname(result.name_index);
        require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
            abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
            abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index).isEmpty(),
            "Draw trace callback must use the public namespace.");return result;
    }
    static List<AVM2Instruction> drawTraceCall(ABC abc,int local,String event) {
        var block=new ArrayList<AVM2Instruction>();
        block.add(new AVM2Instruction(0,0x62,new int[]{local}));
        var guard=new AVM2Instruction(0,0x12,new int[]{0});block.add(guard);
        block.add(new AVM2Instruction(0,0x62,new int[]{local}));
        block.add(new AVM2Instruction(0,0x64,new int[0]));
        block.add(new AVM2Instruction(0,0x2c,new int[]{abc.constants.getStringId(event,true)}));
        block.add(new AVM2Instruction(0,event.equals("draw.enter")?0xd1:0x20,new int[0]));
        block.add(new AVM2Instruction(0,0x41,new int[]{2}));
        block.add(new AVM2Instruction(0,0x29,new int[0]));
        int skip=0;for(int i=2;i<block.size();i++)skip+=block.get(i).getBytesLength();guard.operands[0]=skip;
        return block;
    }
    static MethodBody makeDrawTraceAdapter(ABC original,ABC compiled) {
        var before=classMethod(original,DRAW_TRACE_TYPE,"Draw");
        require(byteHash(before.getCodeBytes()).equals(DRAW_TRACE_PIN),"Pinned native Draw bytes differ.");
        require(before.exceptions.length==0 && before.max_regs==24,"Pinned Draw exception/local layout differs.");
        verifyDrawTraceCallAbi(original);
        var callback=drawTraceStaticTrait(compiled);
        int main=original.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        var old=before.getCode().code;int local=before.max_regs;
        require(old.size()>2 && opcode(old.get(0),0xd0) && opcode(old.get(1),0x30),
            "Native Draw scope prologue differs.");
        var insertions=new TreeMap<Integer,List<AVM2Instruction>>();
        var prefix=new ArrayList<AVM2Instruction>();
        prefix.add(new AVM2Instruction(0,0x60,new int[]{original.instance_info.get(main).name_index}));
        prefix.add(new AVM2Instruction(0,0x66,new int[]{callback.name_index}));
        prefix.add(new AVM2Instruction(0,0x63,new int[]{local}));
        prefix.addAll(drawTraceCall(compiled,local,"draw.enter"));insertions.put(2,prefix);
        var counts=new HashMap<String,Integer>();int returns=0;
        for(int i=0;i<old.size();i++) {
            var op=old.get(i);require(!opcode(op,0x1b),"Draw trace has an unreviewed switch.");String phase=null;
            if(opcode(op,0x47)) {insertions.computeIfAbsent(i,k->new ArrayList<>()).addAll(drawTraceCall(compiled,local,"draw.leave"));returns++;}
            if(opcode(op,0x46)||opcode(op,0x4f)||opcode(op,0x45)||opcode(op,0x4e)) {
                var called=original.constants.getString(original.constants.getMultiname(op.operands[0]).name_index);
                if(called.equals("Paint"))phase="favorite";
                else if(called.equals("Draw")&&(opcode(op,0x45)||opcode(op,0x4e)))phase="super";
                else if(called.equals("LoadThumbnail"))phase="thumbnail";
                else if(called.equals("Decorate"))phase="decoration";
                else if(Set.of("GetColorSwatchDataFeed","GetColorSwatchArray","GetDataLength","SetDataFeed","ShowGrid","RefreshLayout").contains(called))phase="swatches";
                else if(Set.of("LoadImage","SetTag").contains(called))phase="icons";
            }
            if(phase!=null) {
                counts.merge(phase,1,Integer::sum);
                insertions.computeIfAbsent(i,k->new ArrayList<>()).addAll(drawTraceCall(compiled,local,phase+".enter"));
                insertions.computeIfAbsent(i+1,k->new ArrayList<>()).addAll(drawTraceCall(compiled,local,phase+".leave"));
            }
        }
        require(returns==4 && counts.equals(Map.of("favorite",1,"super",1,"thumbnail",5,"decoration",4,"swatches",7,"icons",2)),
            "Pinned Draw phase/return inventory differs: "+counts);
        var body=before.clone();var code=body.getCode();var rewritten=new ArrayList<AVM2Instruction>();
        var starts=new HashMap<Long,AVM2Instruction>();var originals=new ArrayList<AVM2Instruction>();
        for(int i=0;i<old.size();i++) {
            var additions=insertions.getOrDefault(i,List.of());var copy=old.get(i).clone();
            starts.put(old.get(i).getAddress(),additions.isEmpty()?copy:additions.get(0));
            rewritten.addAll(additions);rewritten.add(copy);originals.add(copy);
        }
        rewritten.addAll(insertions.getOrDefault(old.size(),List.of()));
        long address=0;for(var op:rewritten) {op.setAddress(address);address+=op.getBytesLength();}
        long oldEnd=before.getCode().getEndOffset();
        for(int i=0;i<old.size();i++)if(old.get(i).isBranch() || old.get(i).isJump()) {
            long target=old.get(i).getTargetAddress();
            require(target==oldEnd || starts.containsKey(target),"Native Draw branch has no retained target.");
            long destination=target==oldEnd?address:starts.get(target).getAddress();
            var op=originals.get(i);op.operands[0]=Math.toIntExact(destination-op.getAddress()-op.getBytesLength());
        }
        code.code.clear();code.code.addAll(rewritten);body.max_regs=before.max_regs+1;body.max_stack=before.max_stack+4;
        body.setCode(code);body.setModified();code.checkValidOffsets(body);return body;
    }
    static void verifyRetainedDrawFlow(ABC abc,MethodBody before,MethodBody after) {
        // Independent of the assembler's isBranch/isJump helpers. AVM2 jump
        // opcode0x10 is NOT an IfTypeIns, and must be checked explicitly.
        var old=before.getCode().code;var code=after.getCode().code;
        var projected=new ArrayList<AVM2Instruction>();var destinations=new HashMap<Long,Integer>();
        int markers=0,prefixes=0;
        for(int i=0;i<code.size();) {
            var op=code.get(i);
            if(i==2) {
                require(opcode(op,0x60) && property(abc,op,0x60,"CASCustomizerMain") &&
                    property(abc,code.get(i+1),0x66,"apexCatalogDrawTraceStep") &&
                    opcode(code.get(i+2),0x63) && code.get(i+2).operands[0]==before.max_regs,
                    "Draw must preserve scope setup before its one-local diagnostic prefix.");
                destinations.put(op.getAddress(),projected.size());prefixes++;i+=3;continue;
            }
            if(opcode(op,0x62) && op.operands[0]==before.max_regs) {
                require(i+8<=code.size() && opcode(code.get(i+1),0x12) && opcode(code.get(i+2),0x62) &&
                    code.get(i+2).operands[0]==before.max_regs && opcode(code.get(i+3),0x64) &&
                    opcode(code.get(i+4),0x2c) && (opcode(code.get(i+5),0x20)||opcode(code.get(i+5),0xd1)) &&
                    opcode(code.get(i+6),0x41) && code.get(i+6).operands[0]==2 && opcode(code.get(i+7),0x29),
                    "Trace marker changes the original value stack or function receiver/argument convention.");
                long end=i+8==code.size()?after.getCode().getEndOffset():code.get(i+8).getAddress();
                require(code.get(i+1).getTargetAddress()==end,"Disabled trace guard does not preserve the original value stack.");
                destinations.put(op.getAddress(),projected.size());markers++;i+=8;continue;
            }
            destinations.put(op.getAddress(),projected.size());projected.add(op);i++;
        }
        destinations.put(after.getCode().getEndOffset(),projected.size());
        require(prefixes==1 && markers==45 && projected.size()==old.size(),"Native Draw projection/marker count differs.");
        for(int i=0;i<old.size();i++) {
            var a=projected.get(i);var b=old.get(i);int number=b.definition.instructionCode;
            boolean relative=number>=0x0c && number<=0x1a;
            require(a.definition.instructionCode==number && (relative||Arrays.equals(a.operands,b.operands)),
                "Native Draw non-control instruction/operand changed.");
            if(relative)require(Objects.equals(destinations.get(a.getTargetAddress()),before.getCode().adr2pos(b.getTargetAddress())),
                "Native Draw conditional/unconditional control-flow edge changed.");
        }
    }
    static void verifyDrawTraceCallAbi(ABC original) {
        // Independently compiled donor code invokes a Function with two captured
        // arguments using getglobalscope as receiver. Do not substitute null.
        boolean found=false;
        for(var body:original.bodies) {
            var code=body.getCode().code;
            for(int i=7;i<code.size();i++)if(opcode(code.get(i),0x41) && code.get(i).operands[0]==2 &&
                opcode(code.get(i-7),0x65) && opcode(code.get(i-6),0x6c) && opcode(code.get(i-5),0x64) &&
                opcode(code.get(i-4),0x65) && opcode(code.get(i-3),0x6c) &&
                opcode(code.get(i-2),0x65) && opcode(code.get(i-1),0x6c))found=true;
        }
        require(found,"Pinned donor lacks the independently compiled Function-call receiver convention.");
    }
    static void verifyDrawTraceAdapter(ABC original,ABC serialized) {
        var before=classMethod(original,DRAW_TRACE_TYPE,"Draw");var after=classMethod(serialized,DRAW_TRACE_TYPE,"Draw");
        var expected=makeDrawTraceAdapter(original,serialized);
        require(Arrays.equals(expected.getCodeBytes(),after.getCodeBytes()) && after.exceptions.length==0 &&
            after.max_regs==before.max_regs+1 && after.max_stack==before.max_stack+4 &&
            after.init_scope_depth==before.init_scope_depth && after.max_scope_depth==before.max_scope_depth,
            "Serialized Draw trace changed retained native instructions, guards, branches, locals or exceptions.");
        verifyRetainedDrawFlow(serialized,before,after);
    }
    static void verifyDrawTraceHelper(ABC abc,InstanceInfo instance) {
        var routes=Map.of("ApexCatalogTraceConfigure",Set.of("ApexCatalogTraceStatus","getTimer","ApexCatalogTraceDispose","ApexLayoutTraceDispose"),
            "ApexCatalogTraceStep",Set.of("pop","split","max","substr","getTimer","push","ApexCatalogTraceDispose"),
            "ApexCatalogTraceDispose",Set.<String>of(),"ApexCatalogTraceStatus",Set.of("max","getTimer","push","ApexCatalogTraceDispose","ApexCatalogTimerStatus"));
        for(var entry:routes.entrySet()) {
            var body=ownedBody(abc,instance,entry.getKey());
            require(propertyCalls(abc,body).equals(entry.getValue()),"Draw trace helper gained a service, IO or unreviewed callback: "+entry.getKey());
            for(var op:body.getCode().code)if((opcode(op,0x60)||opcode(op,0x5d)) &&
                abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index).equals("getTimer")) {
                var q=abc.constants.getMultiname(op.operands[0]);
                require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                    abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                    abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index).equals("flash.utils"),
                    "Draw trace clock is not the actual Flash utility function.");
            }
        }
        var step=ownedBody(abc,instance,"ApexCatalogTraceStep");boolean earlyReturn=false,enabled=false,clock=false,catchAll=false;
        for(var op:step.getCode().code) {
            if(property(abc,op,0x46,"getTimer")) {clock=true;break;}
            earlyReturn|=opcode(op,0x47);enabled|=property(abc,op,0x66,"enabled");
        }
        for(var handler:step.exceptions)catchAll|=handler.type_index==0;
        require(earlyReturn && enabled && clock && catchAll,"Draw trace lacks its disabled return or catch-all diagnostic boundary.");
    }
    static void verifyTimerTraceHelper(ABC abc,InstanceInfo instance) {
        ownedSignature(abc,instance,"ApexCatalogTimerStep",List.of("String","int"),"int");
        ownedSignature(abc,instance,"ApexCatalogTimerStatus",List.of(),"Object");
        var step=ownedBody(abc,instance,"ApexCatalogTimerStep");var status=ownedBody(abc,instance,"ApexCatalogTimerStatus");
        require(propertyCalls(abc,step).equals(Set.of("pop","split","max","indexOf","substr","getTimer","push","substring","ApexCatalogTraceDispose")) &&
            propertyCalls(abc,status).equals(Set.of("push")),"Timer diagnostics gained native, IO, display or unreviewed work.");
        var info=abc.method_info.get(step.method_info);
        require(info.flagHas_optional() && info.optional.length==1 && info.optional[0].value_kind==ValueKind.CONSTANT_Int &&
            abc.constants.getInt(info.optional[0].value_index)==0,"Timer trace generation must default to zero.");
        for(var body:List.of(step,status))for(var op:body.getCode().code) {
            if(opcode(op,0x60) || opcode(op,0x5d)) {
                String root=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
                require(Set.of("apexCatalogTrace","apexPendingPhase","apexPendingFields","apexReceiving","apexWire","apexFormsIntent",
                    "Math","getTimer","ApexCatalogTraceDispose").contains(root),"Timer trace accesses an unreviewed lexical/native root.");
                if(root.equals("getTimer")) {
                    var q=abc.constants.getMultiname(op.operands[0]);
                    require(q.kind==Multiname.QNAME && q.namespace_index>0 && abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                        "flash.utils".equals(abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index)),
                        "Timer diagnostic clock is not the actual Flash utility function.");
                }
            }
        }
        int firstClock=-1,disabledReturn=-1;boolean enabled=false,leave=false,catchAll=false,depth=false,limit=false;
        var rows=step.getCode().code;
        for(int n=0;n<rows.size();n++) {
            var op=rows.get(n);
            if(firstClock<0 && property(abc,op,0x46,"getTimer"))firstClock=n;
            if(firstClock<0) {
                enabled|=property(abc,op,0x66,"enabled");leave|=stringLiteral(abc,op,"tick.leave");
                if(n>0 && opcode(op,0x48) && opcode(rows.get(n-1),0x24) && rows.get(n-1).operands[0]==0)disabledReturn=n;
            }
            depth|=opcode(op,0x24) && op.operands[0]==8;limit|=opcode(op,0x24) && op.operands[0]==16;
        }
        for(var handler:step.exceptions)catchAll|=handler.type_index==0;
        require(disabledReturn>=0 && firstClock>disabledReturn && enabled && leave && catchAll && depth && limit,
            "Timer diagnostics lost disabled return, matching tick leave, bounded retention or catch-all boundary.");
        for(String phase:List.of("tick","receive","native-info","clone","execute","readback","snapshot","ack-encode","ack-send","forms"))
            require(rows.stream().anyMatch(op->stringLiteral(abc,op,phase)),"Timer diagnostic phase inventory is incomplete: "+phase);
        for(String field:List.of("appearance_written","record_limit","depth_limit"))
            require(status.getCode().code.stream().filter(op->stringLiteral(abc,op,field)).count()==2,
                "Timer diagnostic empty/active status scope or bounds differ.");
        require(methodCallers(abc,instance,"ApexCatalogTimerStatus").equals(Set.of("ApexCatalogTraceStatus")),
            "Timer status escaped explicit Draw diagnostic status.");
        require(methodCallers(abc,instance,"ApexCatalogTimerStep").equals(Set.of("ApexTick","ApexExecute","ApexReadback","ApexComplete","ApexSocketReply")),
            "Timer diagnostics escaped reviewed owned phases.");
        var expected=Map.of("ApexTick",List.of("tick.enter","receive.enter","receive.leave","native-info.enter","native-info.leave","clone.enter","clone.leave",
                "readback.enter","readback.leave","execute.enter","execute.leave","forms.enter","forms.leave","tick.leave"),
            "ApexExecute",List.of("native-info.enter","native-info.leave"),
            "ApexReadback",List.of("native-info.enter","native-info.leave","snapshot.enter","snapshot.leave","snapshot.enter","snapshot.leave"),
            "ApexComplete",List.of("ack-encode.enter","ack-encode.leave"),"ApexSocketReply",List.of("ack-send.enter","ack-send.leave"));
        for(var entry:expected.entrySet())verifyTimerTraceMarkers(abc,ownedBody(abc,instance,entry.getKey()),entry.getValue());
    }
    static void verifyTimerTraceMarkers(ABC abc,MethodBody body,List<String> expected) {
        var rows=body.getCode().code;var observed=new ArrayList<String>();int generationSlot=-1;
        for(int at=0;at<rows.size();at++)if(property(abc,rows.get(at),0x46,"ApexCatalogTimerStep") || property(abc,rows.get(at),0x4f,"ApexCatalogTimerStep")) {
            String event=null;
            if(at>0 && opcode(rows.get(at-1),0x2c))event=abc.constants.getString(rows.get(at-1).operands[0]);
            else if(at>2 && opcode(rows.get(at-3),0x2c))event=abc.constants.getString(rows.get(at-3).operands[0]);
            require(event!=null,"Timer diagnostic event must be a fixed inserted marker.");observed.add(event);
            if(event.equals("tick.enter")) {
                require(at>=17 && at+3<rows.size() && property(abc,rows.get(at),0x46,"ApexCatalogTimerStep") && rows.get(at).operands[1]==1 &&
                    opcode(rows.get(at-17),0x24) && rows.get(at-17).operands[0]==0 && opcode(rows.get(at-16),0x6d) &&
                    property(abc,rows.get(at-15),0x60,"apexCatalogTrace") && opcode(rows.get(at-14),0x20) && opcode(rows.get(at-13),0xab) &&
                    opcode(rows.get(at-12),0x96) && opcode(rows.get(at-11),0x2a) && opcode(rows.get(at-10),0x12) && opcode(rows.get(at-9),0x29) &&
                    property(abc,rows.get(at-8),0x60,"apexCatalogTrace") && property(abc,rows.get(at-7),0x66,"enabled") &&
                    opcode(rows.get(at-6),0x26) && opcode(rows.get(at-5),0xac) && opcode(rows.get(at-4),0x12) &&
                    opcode(rows.get(at-3),0x65) && property(abc,rows.get(at-2),0x5d,"ApexCatalogTimerStep") && opcode(rows.get(at+1),0x73) && opcode(rows.get(at+2),0x6d) &&
                    rows.get(at-16).operands[0]==rows.get(at+2).operands[0] &&
                    bootstrapTarget(rows.get(at-10),0)==rows.get(at-4).getAddress() && bootstrapTarget(rows.get(at-4),0)==rows.get(at+3).getAddress(),
                    "Timer tick entry lost its exact default-zero/disabled guard and retained generation.");
                generationSlot=rows.get(at+2).operands[0];
            } else if(event.equals("tick.leave")) {
                require(at>=8 && at+1<rows.size() && generationSlot>=0 && opcode(rows.get(at-8),0x65) && opcode(rows.get(at-7),0x6c) &&
                    rows.get(at-7).operands[0]==generationSlot && opcode(rows.get(at-6),0x24) && rows.get(at-6).operands[0]==0 &&
                    opcode(rows.get(at-5),0x13) && property(abc,rows.get(at-4),0x5d,"ApexCatalogTimerStep") &&
                    opcode(rows.get(at-2),0x65) && opcode(rows.get(at-1),0x6c) && rows.get(at-1).operands[0]==generationSlot &&
                    property(abc,rows.get(at),0x4f,"ApexCatalogTimerStep") && rows.get(at).operands[1]==2 &&
                    bootstrapTarget(rows.get(at-5),0)==rows.get(at+1).getAddress(),
                    "Timer tick finally lost its matching nonzero copied generation.");
            } else {
                require(at>=22 && at+1<rows.size() && property(abc,rows.get(at),0x4f,"ApexCatalogTimerStep") && rows.get(at).operands[1]==1 &&
                    property(abc,rows.get(at-22),0x60,"apexCatalogTrace") && opcode(rows.get(at-21),0x20) && opcode(rows.get(at-20),0xab) &&
                    opcode(rows.get(at-19),0x96) && opcode(rows.get(at-18),0x2a) && opcode(rows.get(at-17),0x12) && opcode(rows.get(at-16),0x29) &&
                    property(abc,rows.get(at-15),0x60,"apexCatalogTrace") && property(abc,rows.get(at-14),0x66,"enabled") &&
                    opcode(rows.get(at-13),0x26) && opcode(rows.get(at-12),0xac) && opcode(rows.get(at-11),0x2a) && opcode(rows.get(at-10),0x12) &&
                    opcode(rows.get(at-9),0x29) && property(abc,rows.get(at-8),0x60,"apexCatalogTrace") && property(abc,rows.get(at-7),0x66,"timer_profile") &&
                    opcode(rows.get(at-6),0x20) && opcode(rows.get(at-5),0xab) && opcode(rows.get(at-4),0x96) && opcode(rows.get(at-3),0x12) &&
                    property(abc,rows.get(at-2),0x5d,"ApexCatalogTimerStep") &&
                    bootstrapTarget(rows.get(at-17),0)==rows.get(at-11).getAddress() && bootstrapTarget(rows.get(at-10),0)==rows.get(at-3).getAddress() &&
                    bootstrapTarget(rows.get(at-3),0)==rows.get(at+1).getAddress(),
                    "Timer phase marker lost its exact disabled/null-profile short circuit: "+event);
            }
        }
        require(observed.equals(expected),"Timer diagnostic marker inventory/order differs.");
    }
    static void verifyOwnedLexicalRoots(ABC abc,Set<Integer> methods) {
        for(int method:methods)for(var op:abc.findBody(method).getCode().code)
            if(opcode(op,0x60)||opcode(op,0x5d)) {
                String root=abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index);
                require(!Set.of("olympus","gamedata","widgets","apex").contains(root),
                    "Owned CAS method uses an unresolved package root instead of an imported class: "+root);
            }
    }
    static void verifySearchScrollerBinding(ABC abc,InstanceInfo instance) {
        var publish=ownedBody(abc,instance,"ApexSearchPublish");int constructs=0;
        for(var op:publish.getCode().code)if((opcode(op,0x60)||opcode(op,0x5d)||opcode(op,0x4a)) &&
            abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index).equals("ScrollerEvent")) {
            var q=abc.constants.getMultiname(op.operands[0]);
            require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index).equals("olympus.events"),
                "Search scroll event is not the actual native event class.");
            if(opcode(op,0x4a))constructs++;
        }
        require(constructs==1,"Search must dispatch one real native event before remapping a popup's numeric feed index.");
    }
    static void verifyLayoutTraceHelper(ABC abc,InstanceInfo instance) {
        var routes=Map.of("ApexLayoutTraceConfigure",Set.of("ApexLayoutTraceDispose","ApexLayoutTraceStatus","ApexCatalogTraceDispose","getTimer","ApexImageBoundaryProbe"),
            "ApexLayoutTraceDispose",Set.of("ApexImageBoundaryProbe"),"ApexLayoutTraceStatus",Set.of("getTimer","max","ApexLayoutTraceDispose","ApexImageBoundaryProbe"),
            "ApexImageBoundaryProbe",Set.of("min","GetAllDisplayObjectCells"),
            "ApexLayoutReset",Set.of("ResetAndPositionCells","getTimer","max","ApexLayoutTraceDispose","ApexProfileResetAndPositionCells","ApexGridProviderIdentity","push"));
        for(var entry:routes.entrySet()) {
            var body=ownedBody(abc,instance,entry.getKey());
            require(propertyCalls(abc,body).equals(entry.getValue()),"Layout diagnostic helper gained an unreviewed native callback: "+entry.getKey());
            for(var op:body.getCode().code)if((opcode(op,0x60)||opcode(op,0x5d)) &&
                abc.constants.getString(abc.constants.getMultiname(op.operands[0]).name_index).equals("getTimer")) {
                var q=abc.constants.getMultiname(op.operands[0]);
                require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                    abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                    abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index).equals("flash.utils"),
                    "Layout diagnostic clock is not the actual Flash utility function.");
            }
        }
        var imageOps=ownedBody(abc,instance,"ApexImageBoundaryProbe").getCode().code;
        int statsCalls=0,enableCalls=0;
        for(int i=0;i<imageOps.size();i++)if(opcode(imageOps.get(i),0x41)) {
            var op=imageOps.get(i);
            if(op.operands[0]==0) {
                require(i>=5 && stringLiteral(abc,imageOps.get(i-3),"ApexImageTraceStats") &&
                    opcode(imageOps.get(i-2),0x66) && opcode(imageOps.get(i-1),0xd3) &&
                    opcode(imageOps.get(i-4),0xd7) && opcode(imageOps.get(i-5),0x2a),
                    "Image stats callback is not the exact actual-image method/receiver.");statsCalls++;
            } else {
                require(op.operands[0]==1 && i>=7 && stringLiteral(abc,imageOps.get(i-5),"ApexImageTraceEnable") &&
                    opcode(imageOps.get(i-4),0x66) && opcode(imageOps.get(i-3),0xd3) &&
                    opcode(imageOps.get(i-2),0x65) && imageOps.get(i-2).operands[0]==1 &&
                    opcode(imageOps.get(i-1),0x6c) && imageOps.get(i-1).operands[0]==1 &&
                    opcode(imageOps.get(i-6),0xd7) && opcode(imageOps.get(i-7),0x2a),
                    "Image enable callback substitutes its target, receiver or bounded budget.");enableCalls++;
            }
        }
        require(statsCalls==1 && enableCalls==1,"Image probe must invoke only its two explicit actual-image methods.");
        var reset=ownedBody(abc,instance,"ApexLayoutReset");
        int nativeCalls=0,profileCalls=0,providers=0;boolean earlyReturn=false,enabled=false,clock=false;
        for(var op:reset.getCode().code) {
            if(property(abc,op,0x46,"getTimer")) {clock=true;break;}
            earlyReturn|=opcode(op,0x47);enabled|=property(abc,op,0x66,"enabled");
        }
        for(var op:reset.getCode().code) {
            if(property(abc,op,0x46,"ResetAndPositionCells") || property(abc,op,0x4f,"ResetAndPositionCells"))nativeCalls++;
            if(property(abc,op,0x46,"ApexProfileResetAndPositionCells") || property(abc,op,0x4f,"ApexProfileResetAndPositionCells"))profileCalls++;
            if(property(abc,op,0x46,"ApexGridProviderIdentity"))providers++;
        }
        require(earlyReturn && enabled && clock && nativeCalls==2 && profileCalls==1 && providers==1 && reset.exceptions.length==1,
            "Layout diagnostics must retain the disabled native path, one profile call and native exception propagation.");
    }
    static MethodBody favoriteLookupAdapter(ABC original,ABC compiled) {
        if(original.findClassByName("dcc.history.HistoryHost")<0)return null;
        var before=staticMethod(original,"widgets.CAS.dcc.DCCFavorites","Has");
        var after=staticMethod(compiled,"widgets.CAS.dcc.DCCFavorites","Has");
        require(before.exceptions.length==0 && after.exceptions.length==0 &&
            propertyCalls(original,before).equals(propertyCalls(compiled,after)),
            "Favorite lookup must retain the original settings/key routes.");
        int oldReads=0,newReads=0;
        for(var op:before.getCode().code)if(property(original,op,0x66,"AccountSettings"))oldReads++;
        for(var op:after.getCode().code) {
            if(property(compiled,op,0x66,"AccountSettings"))newReads++;
            require(!opcode(op,0x40) && !opcode(op,0x44) && !opcode(op,0x67),"Unreviewed favorite lookup lexical reference.");
        }
        require(oldReads==3 && newReads==1,"Favorite lookup must resolve the live account map exactly once.");
        var body=after.clone();body.method_info=before.method_info;
        int delta=before.init_scope_depth-after.init_scope_depth;
        require(delta>=0 && delta<=16,"Favorite lookup scope differs.");
        body.init_scope_depth+=delta;body.max_scope_depth+=delta;body.setCode(body.getCode());return body;
    }
    static int[] communicationBinding(ABC abc) {
        int manager=-1,call=-1;
        for(var method:abc.bodies)for(var op:method.getCode().code) {
            if(manager<0 && property(abc,op,0x60,"CommunicationManager"))manager=op.operands[0];
            if(call<0 && property(abc,op,0x46,"CallUIService"))call=op.operands[0];
        }
        require(manager>=0 && call>=0,"Native UI communication binding absent.");return new int[]{manager,call};
    }
    static MethodBody retainedPrefix(ABC abc,MethodBody before,List<AVM2Instruction> prefix,int branch,int stack) {
        var body=before.clone();body.exceptions=new ABCException[before.exceptions.length];
        for(int i=0;i<before.exceptions.length;i++)body.exceptions[i]=before.exceptions[i].clone();
        body.insertAll(0,prefix);body.getCode().code.get(branch).operands[0]=1;
        body.max_stack=Math.max(stack,body.max_stack);body.setModified();
        int extra=body.getCodeBytes().length-before.getCodeBytes().length;require(extra>0,"Empty native prefix.");
        for(int i=0;i<before.exceptions.length;i++) {
            body.exceptions[i].start=before.exceptions[i].start+extra;
            body.exceptions[i].end=before.exceptions[i].end+extra;
            body.exceptions[i].target=before.exceptions[i].target+extra;
        }
        verifyRetainedPrefix(body,before);return body;
    }
    static void verifyRetainedPrefix(MethodBody after,MethodBody before) {
        byte[] saved=after.getCodeBytes(),old=before.getCodeBytes();int extra=saved.length-old.length;
        require(extra>0 && Arrays.equals(old,Arrays.copyOfRange(saved,extra,saved.length)),
            "Original native consumer bytes changed outside its dispatcher.");
        require(after.exceptions.length==before.exceptions.length,"Native consumer exception inventory differs.");
        for(int i=0;i<before.exceptions.length;i++) {
            var a=after.exceptions[i];var b=before.exceptions[i];
            require(a.start==b.start+extra && a.end==b.end+extra && a.target==b.target+extra &&
                a.type_index==b.type_index && a.name_index==b.name_index,"Native exception region was not retained exactly.");
        }
    }
    static List<MethodBody> consumerAdapters(ABC original,ABC compiled) {
        var result=new ArrayList<MethodBody>();
        if(original.findClassByName("dcc.history.HistoryHost")<0)return result;
        var binding=communicationBinding(compiled);
        for(String type:List.of("dcc.history.SavedOutfitNames","dcc.history.CurrentRemove")) {
            String method=type.endsWith("SavedOutfitNames")?"Commit":"Click";
            int index=original.findClassByName(type),callback=-1;
            for(var trait:original.class_info.get(index).static_traits.traits)
                if(name(original,trait).equals(method) && trait instanceof TraitMethodGetterSetter)callback=trait.name_index;
            require(callback>=0,"Native consumer callback absent.");var before=staticMethod(original,type,method);
            require(original.method_info.get(before.method_info).param_types.length==1,"Native consumer signature differs.");
            var prefix=List.of(new AVM2Instruction(0,0x60,new int[]{binding[0]}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("ApexPanelConsumer",true)}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("kind",true)}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId(method.equals("Commit")?"save":"remove",true)}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("callback",true)}),
                new AVM2Instruction(0,0x60,new int[]{original.instance_info.get(index).name_index}),
                new AVM2Instruction(0,0x66,new int[]{callback}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("event",true)}),
                new AVM2Instruction(0,0xd1,new int[0]),new AVM2Instruction(0,0x55,new int[]{3}),
                new AVM2Instruction(0,0x46,new int[]{binding[1],2}),new AVM2Instruction(0,0x12,new int[]{1}),
                new AVM2Instruction(0,0x47,new int[0]));
            result.add(retainedPrefix(compiled,before,prefix,11,8));
        }
        int sinks=0;int sharedSink=staticMethod(original,"dcc.history.HistoryHost","CurrentOutfitClick").method_info;
        for(var before:original.bodies)if(propertyCalls(original,before).containsAll(Set.of("SavePart","PendingName","SetValue"))) {
            require(before.method_info==sharedSink,"Unreviewed saved-outfit persistence body.");
            require(original.method_info.get(before.method_info).param_types.length==1,"Saved-outfit sink signature differs.");
            var prefix=List.of(new AVM2Instruction(0,0x60,new int[]{binding[0]}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("ApexPanelPersistGate",true)}),
                new AVM2Instruction(0,0xd1,new int[0]),new AVM2Instruction(0,0x46,new int[]{binding[1],2}),
                new AVM2Instruction(0,0x12,new int[]{1}),new AVM2Instruction(0,0x47,new int[0]));
            result.add(retainedPrefix(compiled,before,prefix,4,3));sinks++;
        }
        // Attach creates an anonymous function from the SAME MethodInfo that
        // backs the public CurrentOutfitClick trait. The decompiler prints it
        // twice, but prefixing that single body must protect both call paths.
        int references=0;
        for(var op:staticMethod(original,"dcc.history.HistoryHost","Attach").getCode().code)
            if(opcode(op,0x40) && op.operands[0]==sharedSink)references++;
        require(sinks==1 && references==1 && result.size()==3,"Native outfit save/remove shared-body inventory differs.");return result;
    }
    static void verifyConsumerPrefix(ABC abc,MethodBody after,MethodBody before) {
        verifyRetainedPrefix(after,before);var code=after.getCode().code;
        require(property(abc,code.get(0),0x60,"CommunicationManager"),"Consumer dispatcher manager differs.");
        if(stringLiteral(abc,code.get(1),"ApexPanelConsumer")) {
            String type=stringLiteral(abc,code.get(3),"save")?"dcc.history.SavedOutfitNames":"dcc.history.CurrentRemove";
            String method=type.endsWith("SavedOutfitNames")?"Commit":"Click";int index=abc.findClassByName(type),callback=-1;
            for(var trait:abc.class_info.get(index).static_traits.traits)if(name(abc,trait).equals(method))callback=trait.name_index;
            require(code.size()>13 && stringLiteral(abc,code.get(2),"kind") &&
                stringLiteral(abc,code.get(3),method.equals("Commit")?"save":"remove") &&
                stringLiteral(abc,code.get(4),"callback") && opcode(code.get(5),0x60) &&
                code.get(5).operands[0]==abc.instance_info.get(index).name_index && opcode(code.get(6),0x66) &&
                code.get(6).operands[0]==callback && stringLiteral(abc,code.get(7),"event") && opcode(code.get(8),0xd1) &&
                opcode(code.get(9),0x55) && code.get(9).operands[0]==3 && property(abc,code.get(10),0x46,"CallUIService") &&
                code.get(10).operands[1]==2 && opcode(code.get(11),0x12) && code.get(11).operands[0]==1 && opcode(code.get(12),0x47),
                "Outfit consumer must retain its exact callback/event and absent-service fallback.");
        } else require(code.size()>6 && stringLiteral(abc,code.get(1),"ApexPanelPersistGate") && opcode(code.get(2),0xd1) &&
            property(abc,code.get(3),0x46,"CallUIService") && code.get(3).operands[1]==2 && opcode(code.get(4),0x12) &&
            code.get(4).operands[0]==1 && opcode(code.get(5),0x47),"Outfit persistence sink lost its freshness gate.");
    }
    static MethodBody currentOutfitAdapter(ABC original,ABC compiled) {
        if(original.findClassByName("dcc.history.HistoryHost")<0)return null;
        var before=staticMethod(original,"dcc.history.HistoryHost","RefreshCurrentOutfit");
        var body=before.clone();var code=body.getCode().code;
        require(body.exceptions.length==0 && code.size()>2 && property(original,code.get(0),0x60,"HistoryHost") &&
            property(original,code.get(1),0x66,"dccHistoryRuntimeDrawer"),
            "Current outfit refresh has an unreviewed scope or exception region.");
        int manager=-1,call=-1;
        for(var method:compiled.bodies)for(var op:method.getCode().code) {
            if(manager<0 && property(compiled,op,0x60,"CommunicationManager"))manager=op.operands[0];
            if(call<0 && property(compiled,op,0x46,"CallUIService"))call=op.operands[0];
        }
        require(manager>=0 && call>=0,"Current outfit dispatcher lost its native communication binding.");
        var q=compiled.constants.getMultiname(manager);
        require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
            compiled.constants.getString(compiled.constants.getNamespace(q.namespace_index).name_index).equals("olympus.io"),
            "Outfit dispatcher is not bound to the native communication manager.");
        body.insertAll(0,List.of(new AVM2Instruction(0,0x60,new int[]{manager}),
            new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId("ApexPanelRefreshGate",true)}),
            new AVM2Instruction(0,0x20,new int[0]),new AVM2Instruction(0,0x46,new int[]{call,2}),
            new AVM2Instruction(0,0x12,new int[]{1}),new AVM2Instruction(0,0x47,new int[0])));
        // insertAll relocates a newly inserted branch while adding its sibling
        // return. Pin the final relative target to the one-byte return skip.
        body.getCode().code.get(4).operands[0]=1;
        body.max_stack=Math.max(3,body.max_stack);body.setModified();
        verifyCurrentOutfitAdapter(compiled,body,before.getCodeBytes());return body;
    }
    static void verifyCurrentOutfitAdapter(ABC abc,MethodBody body,byte[] original) {
        var code=body.getCode().code;var saved=body.getCodeBytes();
        require(code.size()>8 && body.exceptions.length==0 &&
            property(abc,code.get(0),0x60,"CommunicationManager") && stringLiteral(abc,code.get(1),"ApexPanelRefreshGate") &&
            opcode(code.get(2),0x20) && property(abc,code.get(3),0x46,"CallUIService") && code.get(3).operands[1]==2 &&
            opcode(code.get(4),0x12) && code.get(4).operands[0]==1 && opcode(code.get(5),0x47),
            "Outfit refresh must queue through the owned UI service and retain the absent-service fallback: "+
                code.subList(0,Math.min(8,code.size())).stream().map(op->op.definition.instructionName+Arrays.toString(op.operands)).toList());
        int bytes=saved.length-original.length;
        require(bytes>0 && Arrays.equals(original,Arrays.copyOfRange(saved,bytes,saved.length)),
            "Original outfit refresh bytes changed outside the owned queue dispatcher.");
    }
    static void verifyPanelScheduling(ABC abc,InstanceInfo instance) {
        var gate=ownedBody(abc,instance,"ApexPanelRefreshGate");
        require(propertyCalls(abc,gate).isEmpty(),"Outfit refresh input must only coalesce retained intent.");
        var forbidden=Set.of("CallGameService","CallUIService","ApexNativeExchange","RemoveAllItems","AddItemsFromIterable","flush");
        for(String method:List.of("ApexPanelsDragStart","ApexPanelsDragMove","ApexPanelsDragEnd","ApexPanelsScale","ApexPanelsClick","ApexPanelsCommand"))
            require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,method)),forbidden),
                "Panel input performs engine, feed or disk work: "+method);
        var work=ownedBody(abc,instance,"ApexPanelsWork");
        require(propertyCalls(abc,work).containsAll(Set.of("GetCatalogItemsSelected","GetCatalogProduct","CurrentCategoryPart",
            "Register","AddEyeColor","Record","AddItem","ReplaceItemAt","RemoveItemAt","PositionCells","ApexPanelsStamp")) &&
            Collections.disjoint(propertyCalls(abc,work),Set.of("RemoveAllItems","AddItemsFromIterable")),
            "Incremental outfit preview lost native donor routes or its complete appearance freshness check.");
        var frame=ownedBody(abc,instance,"ApexPanelsFrame");
        require(propertyCalls(abc,frame).containsAll(Set.of("getTimer","ApexPanelsWork","ApexPanelsContext","flush")),
            "Panel scheduler lost frame timing, context verification or deferred persistence.");
    }
    static List<MethodBody> columnSchedulingAdapters(ABC original,ABC compiled) {
        var result=new ArrayList<MethodBody>();
        if(original.findClassByName("dcc.history.HistoryHost")<0)return result;
        String type="widgets.CAS.Customizer.CASCustomizerMain";
        var routes=Map.of("RefreshAndShowPanel","ApexColumnsTakeover","ApplyDynamicColumns","ApexColumnsSet",
            "LoadThumbnailScaleSetting","ApexColumnsTakeover","FlushThumbnailScaleReflow","ApexColumnsTakeover",
            "HandleThumbnailScaleMove","ApexColumnsScale","HandleThumbnailScaleUp","ApexColumnsScaleEnd",
            "HandleDynamicResizeMoveRight","ApexColumnsResize","HandleDynamicResizeUpRight","ApexColumnsResizeEnd");
        int manager=-1,call=-1;
        for(var method:compiled.bodies)for(var op:method.getCode().code) {
            if(manager<0 && property(compiled,op,0x60,"CommunicationManager"))manager=op.operands[0];
            if(call<0 && property(compiled,op,0x46,"CallUIService"))call=op.operands[0];
        }
        require(manager>=0 && call>=0,"Column dispatcher native communication binding absent.");
        for(var entry:routes.entrySet()) {
            var before=classMethod(original,type,entry.getKey());var body=before.clone();var code=body.getCode().code;
            require(body.exceptions.length==0 && code.size()>2 && opcode(code.get(0),0xd0) && opcode(code.get(1),0x30),
                "Unreviewed column adapter scope: "+entry.getKey());
            int at=2;
            if(entry.getKey().equals("RefreshAndShowPanel")) {
                at=-1;
                for(int i=0;i<code.size();i++)if(property(original,code.get(i),0x4f,"ShowPanel")) {
                    require(at<0,"Multiple native panel publication calls.");at=i+1;
                }
                require(at>=0,"Native panel publication call absent.");
            }
            boolean argument=Set.of("ApplyDynamicColumns","HandleThumbnailScaleMove","HandleThumbnailScaleUp",
                "HandleDynamicResizeMoveRight","HandleDynamicResizeUpRight").contains(entry.getKey());
            body.insertAll(at,List.of(new AVM2Instruction(0,0x60,new int[]{manager}),
                new AVM2Instruction(0,0x2c,new int[]{compiled.constants.getStringId(entry.getValue(),true)}),
                new AVM2Instruction(0,argument?0xd1:0x20,new int[0]),
                new AVM2Instruction(0,0x46,new int[]{call,2}),new AVM2Instruction(0,0x12,new int[]{1}),
                new AVM2Instruction(0,0x47,new int[0])));
            body.getCode().code.get(at+4).operands[0]=1;body.max_stack=Math.max(3,body.max_stack);body.setModified();
            byte[] saved=body.getCodeBytes(),old=before.getCodeBytes();
            int start=(int)body.getCode().code.get(at).getAddress(),extra=saved.length-old.length;
            require(extra>0 && Arrays.equals(Arrays.copyOfRange(old,0,start),Arrays.copyOfRange(saved,0,start)) &&
                Arrays.equals(Arrays.copyOfRange(old,start,old.length),Arrays.copyOfRange(saved,start+extra,saved.length)),
                "Column adapter changed original bytes outside its owned dispatcher: "+entry.getKey());
            result.add(body);
        }
        require(result.size()==8,"Column scheduler adapter inventory differs.");return result;
    }
    static List<MethodBody> equippedAdapters(ABC original,ABC compiled) {
        var result=new ArrayList<MethodBody>();
        var routes=Map.of(
            "widgets.CAS.Customizer.ClothingPanel",Map.of("Refresh","ApexEquippedRefresh",
                "OnCatalogClick","ApexEquippedClick","OnToggleVariationGrid","ApexEquippedPrepare",
                "RemoveSelectedItem","ApexEquippedPrepare","SelectCatalogProduct","ApexEquippedPrepare"),
            "widgets.CAS.data.CatalogDataFeed",Map.of("RequestData","ApexCatalogPerformance"),
            "widgets.CAS.Customizer.Panes.PeltMarkings.PeltMarkingsPane",Map.of(
                "ParentVisible","ApexFormPairPanel","OnPaintLayerPressed","ApexFormPairPanel",
                "GetPeltColors","CasGetSwatchColorList"),
            "widgets.CAS.Customizer.Panes.PeltMarkings.PeltPaintLayerButton",Map.of("Refresh","ApexFormPairPanel"));
        for(var entry:routes.entrySet())for(var method:entry.getValue().entrySet()) {
            var before=classMethod(original,entry.getKey(),method.getKey());
            var after=classMethod(compiled,entry.getKey(),method.getKey());
            uniqueLiteral(compiled,after,method.getValue());
            if(method.getKey().equals("GetPeltColors")) {
                require(propertyCalls(compiled,after).equals(propertyCalls(original,before)),
                    "Palette enable recovery must retain exactly the native read calls.");
                var code=after.getCode().code;int enable=-1,color=-1,count=0;
                for(int n=0;n<code.size();n++) {
                    if(property(compiled,code.get(n),0x61,"enabled")&&n>0&&opcode(code.get(n-1),0x26)) {enable=n;count++;}
                    if(property(compiled,code.get(n),0x61,"color"))color=n;
                }
                require(count==1&&enable>=0&&color>enable,
                    "An exact resolved native pelt color must re-enable its layer before painting the color.");
            }
            if(method.getKey().equals("Refresh") && entry.getKey().equals("widgets.CAS.Customizer.ClothingPanel"))
                require(propertyCalls(compiled,after).contains("SetSelectionStateMultiple") &&
                    !propertyCalls(compiled,after).contains("SelectAll") && !propertyCalls(compiled,after).contains("SetSelectionState"),
                    "Progressive equipped selection must update only the newly appended index, not redraw all previous cards.");
            if(method.getKey().equals("RequestData")) {
                uniqueLiteral(compiled,after,"ApexCatalogSearchSource");
                boolean timer=false;
                for(var op:after.getCode().code)if(op.definition.instructionCode==0x5d || op.definition.instructionCode==0x60) {
                    var q=compiled.constants.getMultiname(op.operands[0]);
                    String member=compiled.constants.getString(q.name_index);
                    require(!member.equals("flash"),"Catalog profiler uses an unresolved Flash package root.");
                    if(member.equals("getTimer")) {
                        require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                            compiled.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                            compiled.constants.getString(compiled.constants.getNamespace(q.namespace_index).name_index).equals("flash.utils"),
                            "Catalog profiler clock does not bind the actual Flash utility function.");timer=true;
                    }
                }
                require(timer,"Native catalog profiler has no bound clock.");
            }
            require(propertyCalls(compiled,after).containsAll(propertyCalls(original,before)),
                "Equipped adapter removed a native call: "+method.getKey());
            require(before.exceptions.length==0 && after.exceptions.length==0,"Unreviewed equipped adapter exceptions.");
            for(var op:after.getCode().code)
                require(!opcode(op,0x40) && !opcode(op,0x44) && !opcode(op,0x67),"Equipped adapter has unreviewed scope/function references.");
            var body=after.clone();body.method_info=before.method_info;
            int delta=before.init_scope_depth-after.init_scope_depth;
            require(delta>=0 && delta<=16,"Equipped adapter lexical scope differs.");
            body.init_scope_depth+=delta;body.max_scope_depth+=delta;body.setCode(body.getCode());result.add(body);
        }
        require(result.size()==10,"Equipped/wing owner adapter inventory differs.");return result;
    }
    static void verifyNativeCatalogSearch(ABC abc,InstanceInfo instance) {
        var forbidden=Set.of("CallGameService","CallUIService","ApexNativeExchange","ApexSearchPublish","ApexSearchNativeKey",
            "RemoveAllItems","AddItemsFromIterable","Refresh","RequestData");
        for(String method:List.of("ApexSearchChanged","ApexSearchText","ApexSearchClear","ApexSearchKey","ApexSearchSource","ApexSearchSelection"))
            require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,method)),forbidden),
                "Search input/source callbacks perform catalog or native work: "+method);
        var publish=ownedBody(abc,instance,"ApexSearchPublish");
        require(Collections.disjoint(propertyCalls(abc,publish),Set.of("CallGameService","CallUIService","ApexNativeExchange","UpdateSelections","ReplaceWithVariation","SetVariation")) &&
            propertyCalls(abc,publish).containsAll(Set.of("ApexSearchContext","RemoveAllItems","AddItemsFromIterable","SetSelectionStateMultiple")),
            "Search publication must only filter the original native feed and its selection display.");
        int compare=-1,clear=-1;var publication=publish.getCode().code;
        for(int i=0;i<publication.size();i++) {
            var op=publication.get(i);
            if(compare<0 && property(abc,op,0x46,"RequestItemAt"))compare=i;
            if(property(abc,op,0x4f,"RemoveAllItems")||property(abc,op,0x46,"RemoveAllItems")) {clear=i;break;}
        }
        boolean unchangedReturn=false;
        for(int i=compare+1;i<clear;i++)unchangedReturn|=opcode(publication.get(i),0x47);
        require(compare>=0 && clear>compare && unchangedReturn,
            "Unchanged search results must return before native card removal/rebinding.");
        for(String member:List.of("context","panel","rows","feed","matches","body_type","data_id","selection_keys","apexEquippedActive")) {
            boolean found=false;
            for(var op:publish.getCode().code) found|=property(abc,op,0x66,member)||property(abc,op,0x60,member);
            require(found,"Search publication lost its eligibility/context gate: "+member);
        }
        for(String member:List.of("context","panel","publishing","selection_feed","currentTarget","eligible","isSelected")) {
            boolean found=false;
            for(var op:ownedBody(abc,instance,"ApexSearchSelection").getCode().code)
                found|=property(abc,op,0x66,member)||property(abc,op,0x60,member);
            require(found,"Search selection observation lost its exact native/feed gate: "+member);
        }
        for(String member:List.of("apexKeyQueue","apexKeyIntent","apexKeyIndex","apexKeyItem")) {
            boolean found=false;
            for(var op:publish.getCode().code) found|=property(abc,op,0x61,member)||property(abc,op,0x68,member);
            require(found,"Search publication retains a stale keyboard selection: "+member);
        }
        var adopt=ownedBody(abc,instance,"ApexSearchAdopt");
        require(Collections.disjoint(propertyCalls(abc,adopt),Set.of("CallGameService","CallUIService","ApexNativeExchange")),
            "Deferred source adoption cannot perform native queries or writes.");
        for(String member:List.of("feed","state","sim","owner","generation","apexBoundSim","apexFormsSelectedId","apexFormsNativeGeneration")) {
            boolean found=false;
            for(var op:adopt.getCode().code)found|=property(abc,op,0x66,member)||property(abc,op,0x60,member);
            require(found,"Deferred source adoption lost its exact native context: "+member);
        }
        var frame=ownedBody(abc,instance,"ApexSearchFrame");
        int channels=0;
        for(var op:frame.getCode().code) {
            if(property(abc,op,0x66,"apexNativeChannel")||property(abc,op,0x60,"apexNativeChannel"))channels++;
            require(!property(abc,op,0x66,"apexBoundSim")&&!property(abc,op,0x60,"apexBoundSim"),
                "Native search commands require the opaque transport channel, not the Sim ID.");
            require(!property(abc,op,0x60,"JSON")&&!property(abc,op,0x5d,"JSON")&&!property(abc,op,0x66,"JSON"),
                "The game's GFx runtime has no JSON class; search must use the bounded worker projection.");
        }
        require(channels==2,"Search submit/read must each carry their native channel.");
        uniqueLiteral(abc,frame,"SEARCHPAGE|");
        for(String member:List.of("index_sha256","offset","ticket")) {
            boolean found=false;
            for(var op:frame.getCode().code)found|=property(abc,op,0x66,member);
            require(found,"Compact search page lost its current ticket/index/page check: "+member);
        }
        var attach=ownedBody(abc,instance,"ApexSearchAttach");
        uniqueLiteral(abc,attach,"$TextFont");
        for(String member:List.of("embedFonts","displayAsPassword")) {
            boolean found=false;
            for(var op:attach.getCode().code)found|=property(abc,op,0x61,member)||property(abc,op,0x68,member);
            require(found,"Search field lost its readable game font setting: "+member);
        }
        uniqueLiteral(abc,frame,"GetCatalogItem");
        require(propertyCalls(abc,frame).contains("ApexSearchNativeKey"),"Native search must verify the exact swatch against an eligible parent card.");
        var nativeKey=ownedBody(abc,instance,"ApexSearchNativeKey");
        uniqueLiteral(abc,nativeKey,"GetCatalogColorFamilies");
        require(propertyCalls(abc,nativeKey).equals(Set.of("CallGameService")),
            "Swatch resolution may only read the native family; never equip, publish or request worker data.");
        for(String member:List.of("eligible","families","body_type","data_id","variation_id","mItems","dataID")) {
            boolean found=false;
            for(var op:nativeKey.getCode().code)found|=property(abc,op,0x66,member);
            require(found,"Swatch resolution lost its native eligibility, body or family cache gate: "+member);
        }
        require(propertyCalls(abc,frame).containsAll(Set.of("ApexSearchContext","ApexNativeExchange","ApexEquippedDecimal","ApexSearchPublish")),
            "Search worker lacks exact owner/resource resolution or native feed publication.");
    }
    static void verifyCatalogCompanion(ABC abc,InstanceInfo instance) {
        for(String name:List.of("ApexCompanionCommand","ApexCompanionStatus")) {
            var code=ownedBody(abc,instance,name).getCode().code;int checkedGrids=0;
            for(int i=0;i<code.size();++i)if(property(abc,code.get(i),0x46,"ApexCatalogCells")) {
                int before=i-1;
                while(before>=0 && (opcode(code.get(before),0xf0)||opcode(code.get(before),0xf1)))--before;
                require(before>=0 && property(abc,code.get(before),0x66,"mGridLayout"),
                    "Donor favorites must enumerate the native card layout, not its scrolling container: "+name);
                ++checkedGrids;
            }
            require(checkedGrids==1,"Donor favorites grid inventory differs: "+name);
        }
        for(var op:ownedBody(abc,instance,"ApexCompanionCommand").getCode().code)
            require(!property(abc,op,0x66,"apexPendingFields") && !property(abc,op,0x66,"apexReceiving") &&
                !property(abc,op,0x60,"apexPendingFields") && !property(abc,op,0x60,"apexReceiving"),
                "A checked donor command cannot reject its own pending/receiving lease.");
        var initialize=ownedBody(abc,instance,"ApexCompanionInitialize");int definitions=0;
        for(var op:initialize.getCode().code)if(opcode(op,0x5d)||opcode(op,0x60)) {
            var q=abc.constants.getMultiname(op.operands[0]);String member=q.name_index>0?abc.constants.getString(q.name_index):"";
            require(!member.equals("flash"),"Companion discovery uses an unresolved Flash package root.");
            if(member.equals("getDefinitionByName")) {
                require(q.kind==Multiname.QNAME && q.namespace_index>0 &&
                    abc.constants.getNamespace(q.namespace_index).kind==Namespace.KIND_PACKAGE &&
                    abc.constants.getString(abc.constants.getNamespace(q.namespace_index).name_index).equals("flash.utils"),
                    "Companion discovery does not bind the Flash definition resolver.");definitions++;
            }
        }
        require(definitions==2,"Companion discovery resolver inventory differs.");
        var forbidden=Set.of("CallGameService","CallUIService","ApexNativeExchange","RemoveAllItems","AddItemsFromIterable","flush");
        for(String method:List.of("ApexCompanionCard","ApexCompanionIntent","ApexCompanionButton","ApexCompanionKeyDown","ApexCompanionResizeStart","ApexCompanionResizeEnd"))
            require(Collections.disjoint(propertyCalls(abc,ownedBody(abc,instance,method)),forbidden),"Companion input performs native, catalogue or disk work: "+method);
        var card=ownedBody(abc,instance,"ApexCompanionCard");
        require(propertyCalls(abc,card).containsAll(Set.of("stopImmediatePropagation","ApexCompanionIntent","ApexCompanionKey")),"Right-click companion input must intercept equip and queue its own intent.");
        for(String member:List.of("buttonIdx","mCellEvent","currentTarget","grid")) {
            boolean found=false;for(var op:card.getCode().code)found|=property(abc,op,0x66,member);
            require(found,"Companion right-click lost its native event or owner gate: "+member);
        }
        var intent=ownedBody(abc,instance,"ApexCompanionIntent");
        require(propertyCalls(abc,intent).contains("ApexSearchContext"),"Companion intent must capture exact appearance context.");
        var apply=ownedBody(abc,instance,"ApexCompanionApply");
        require(Collections.disjoint(propertyCalls(abc,apply),Set.of("CallGameService","SetCASPart","SetPreset","SetOccultType")),"Companion preference routes cannot write native appearance.");
        require(propertyCalls(abc,apply).containsAll(Set.of("indexOf","ApexCompanionKey","dispatchEvent")),"Companion apply lacks source membership or its native random-favorite route.");
        var badges=ownedBody(abc,instance,"ApexCompanionBadges");
        require(propertyCalls(abc,badges).containsAll(Set.of("ApexCatalogCells","GetGridIndexOfCell","RequestItemAt")) &&
            Collections.disjoint(propertyCalls(abc,badges),Set.of("CallGameService","ApexNativeExchange","flush")),"Badges must use recycled visible cells without native or disk work.");
        var dispose=ownedBody(abc,instance,"ApexCompanionDispose");
        require(propertyCalls(abc,dispose).containsAll(Set.of("removeEventListener","Shutdown","removeChild")),"Companion must retire native listeners, tooltips and display ownership.");
    }
    static String commonGeometryNs(ABC a,int index){if(index==0)return "*";var n=a.constants.getNamespace(index);String text=a.constants.getString(n.name_index);
        // FFDec names the imported class's file-private namespace with its
        // unchanged provider-specific class index. Normalize only that exact
        // self namespace; all foreign/private/protected bindings stay exact.

        return n.kind+":"+text;}
    static String commonGeometryQName(ABC a,int index){
        if(index==0)return "*";var q=a.constants.getMultiname(index);var out=new StringBuilder();
        out.append(q.kind).append(':').append(a.constants.getString(q.name_index)).append(':').append(commonGeometryNs(a,q.namespace_index));
        if(q.namespace_set_index>0){out.append('[');for(int n:a.constants.getNamespaceSet(q.namespace_set_index).namespaces)out.append(commonGeometryNs(a,n)).append(';');out.append(']');}
        if(q.qname_index>0)out.append('<').append(commonGeometryQName(a,q.qname_index)).append('>');
        if(q.params!=null)for(int p:q.params)out.append('<').append(commonGeometryQName(a,p)).append('>');return out.toString();
    }
    static String commonGeometrySemantic(ABC a,MethodBody b)throws Exception{
        var text=new StringBuilder();var info=a.method_info.get(b.method_info);
        text.append(info.flags).append('|').append(commonGeometryQName(a,info.ret_type));for(int p:info.param_types)text.append('|').append(commonGeometryQName(a,p));
        text.append('|').append(b.max_regs).append('|').append(b.max_stack).append('|').append(b.max_scope_depth-b.init_scope_depth);
        for(var t:b.traits.traits){require(t instanceof TraitSlotConst,"Indexed helper activation has a non-slot trait");var slot=(TraitSlotConst)t;
            text.append("|local:").append(commonGeometryQName(a,t.name_index)).append(':').append(commonGeometryQName(a,slot.type_index)).append(':').append(slot.slot_id).append(':').append(slot.value_index).append(':').append(slot.value_kind);}

        var addresses=bootstrapAddresses(b);
        int debugBase=Integer.MAX_VALUE;for(var i:b.getCode().code)
            if(i.definition.instructionCode==0xef && i.operands.length==4 && i.operands[0]==1 && i.operands[3]>0)debugBase=Math.min(debugBase,i.operands[3]);
        var multinames=Set.of(0x04,0x05,0x45,0x46,0x4a,0x4c,0x4e,0x4f,0x59,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x66,0x68,0x6a,0x80,0x86,0xb2);
        for(var i:b.getCode().code){text.append('\n').append(i.definition.instructionCode);if(i.operands==null)continue;
            for(int n=0;n<i.operands.length;n++){
                text.append(':');if(bootstrapEdges(i).contains(n))text.append('@').append(bootstrapIndex(addresses,bootstrapTarget(i,n)));
                else if(n==0&&multinames.contains(i.definition.instructionCode))text.append(commonGeometryQName(a,i.operands[n]));
                else if(n==1&&i.definition.instructionCode==0xef)text.append(a.constants.getString(i.operands[n]));
                else if(n==3&&i.definition.instructionCode==0xef&&i.operands[0]==1&&i.operands[n]>0)text.append("owned-source+").append(i.operands[n]-debugBase);
                else if(n==0&&i.definition.instructionCode==0xf1)text.append("owned-helper-source");
                else if(n==0&&i.definition.instructionCode==0x2c)text.append(a.constants.getString(i.operands[n]));
                else if(n==0&&i.definition.instructionCode==0x2d)text.append(a.constants.getInt(i.operands[n]));
                else if(n==0&&i.definition.instructionCode==0x2e)text.append(a.constants.getUInt(i.operands[n]));
                else if(n==0&&i.definition.instructionCode==0x2f)text.append(a.constants.getDouble(i.operands[n]));
                else text.append(i.operands[n]);
            }
        }
        for(var e:b.exceptions)text.append("\ncatch:").append(bootstrapIndex(addresses,e.start)).append(':')
            .append(bootstrapIndex(addresses,e.end)).append(':').append(bootstrapIndex(addresses,e.target))
            .append(':').append(commonGeometryQName(a,e.type_index)).append(':').append(commonGeometryQName(a,e.name_index));
        return text.toString();
    }

    static final Map<String,String> COMMON_GEOMETRY_SEMANTICS=Map.ofEntries(
        Map.entry("ApexCatalogPanelKey","55f955c55f339601c70f03ba91ed5d1f6b9319446cfa4ed9bc577f1943dc2408"),
        Map.entry("ApexCatalogPanelKind","e1d242336a75f262c0970b6d8d5b1dfc2a5df9f51a381c3a6d5aa103d0ec11ea"),
        Map.entry("ApexCatalogOptional","9323437faa47479f88f31c5d6bdb6d238f706f01af278a2207442a4f68de7407"),
        Map.entry("ApexCardStateFor","0195b9c8bc9cafb605d1ffb2a9df5ea95af9db44c289e80f22e9b069c6ca3a33"),
        Map.entry("ApexCardActivate","dee9247a93058d7670c574f78b272fcd11d1bcd72fdad6b2451f453817f615db"),
        Map.entry("ApexCatalogVisibleRect","8f79ddc6704bc8ce9d34c10158dabbf6fda2e54e57c217eae8695c20bd029501"),
        Map.entry("ApexCatalogSafeRight","d4a67411cace69dc1e7f6e41c71edb60112584839ec5c89093a14b8ad791004a"),
        Map.entry("ApexCatalogNavigationRects","149a6647aeae5b60b0d1da1fdb4fda5785a9b49e0109f6ceb45eac80091c7108"),
        Map.entry("ApexCatalogWidthEnvelope","48476bd1b399c60c3479c4ba90ef4b57c0a8ca888872e61032ee29d1c49d1c98"),
        Map.entry("ApexCatalogWidthRequest","133e6f3568f3e6f95daaad63402b84c4d227794cca9d56847b910814bdd3b736"),
        Map.entry("ApexCatalogWidthMode","f988d122849168876430c96306aa4168813e9e59549782511e9b8410e3e8cb24"),
        Map.entry("ApexSkinToneApply","28df4fbda6fd8ce203da0e2dd69b14c3d31b55f3dbc4d76bb946f78b0f7c0947"),
        Map.entry("ApexColumnsTrack","e8f0ed72555fd5e881ecc14f7b63144603ab17d46836a9925edad77b743beda0"),
        Map.entry("ApexColumnsScaleDown","0ace3aeafcc98d83bf3b590ac85a0c3def41aaf8968a64711ce99f7153ed6f3a"),
        Map.entry("ApexColumnsScaleMove","1b6ea38dff37441761cab745ac0dde29006d1a6b02dea33debaebb4882617ccc"),
        Map.entry("ApexColumnsScaleUp","e183723f12da19a17e0fd781d347234c40faf501f33d9f506523797f5d98ff07"),
        Map.entry("ApexColumnsWidthDown","d5d5d231b873c9677a571d4d3fdfcd802b8d23d8f448a083b0d318c0f351950a"),
        Map.entry("ApexColumnsWidthMove","4dbab2be52ef351126ac2813b747bc4514bbc6f981ef3aa9a3c412cfa6870966"),
        Map.entry("ApexColumnsWidthUp","382c691564dca8ce8e8d72f4bbabdd4155b023e020a0f7752f9cb16f6b7bcd06"),
        Map.entry("ApexColumnsWidthHandle","000eb0911a6543fd3f21f319b780a64a9d420ccd16f4a8ee6f0992605900a0e1"));
    static Set<String> commonGeometryCalls(ABC abc,MethodBody body) {
        var result=new HashSet<String>();for(var i:body.getCode().code)
            if(Set.of(0x46,0x4f,0x45,0x4e,0x4a).contains(i.definition.instructionCode))result.add(abc.constants.getString(abc.constants.getMultiname(i.operands[0]).name_index));
        return result;
    }
    static void verifyCommonCatalogGeometry(ABC abc,InstanceInfo instance) {
        for(var entry:COMMON_GEOMETRY_SEMANTICS.entrySet()) {
            String name=entry.getKey();var b=ownedBody(abc,instance,name);
            var trait=instance.instance_traits.traits.stream().filter(q->q instanceof TraitMethodGetterSetter && name(abc,q).equals(name)).map(q->(TraitMethodGetterSetter)q).findFirst().orElseThrow();
            var q=abc.constants.getMultiname(trait.name_index);var ns=abc.constants.getNamespace(q.namespace_index);
            require(q.kind==Multiname.QNAME && ns.kind==Namespace.KIND_PRIVATE && abc.constants.getString(ns.name_index).equals("widgets.CAS.Customizer:CASCustomizerMain"),"Common geometry method escaped exact private Main namespace: "+name);
            require(b.init_scope_depth==ownedBody(abc,instance,"ApexColumnsTakeover").init_scope_depth && b.exceptions.length==0 && b.traits.traits.isEmpty(),"Common geometry lexical/activation scope differs: "+name);
            try {String semantic=commonGeometrySemantic(abc,b).replaceAll("(?<=5:)CASCustomizerMain\\.as\\$[0-9]+","CASCustomizerMain.as\\$SELF");require(byteHash(semantic.getBytes(java.nio.charset.StandardCharsets.UTF_8)).equals(entry.getValue()),"Reviewed common geometry semantic differs: "+name);} catch(Exception e){throw new IllegalArgumentException(e);}
        }
        {var b=ownedBody(abc,instance,"ApexCatalogPanelKey");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "String".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogPanelKey");require(commonGeometryCalls(abc,b).equals(Set.of()),"Common geometry callees differ: ApexCatalogPanelKey");}
        {var b=ownedBody(abc,instance,"ApexCatalogPanelKind");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "String".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogPanelKind");require(commonGeometryCalls(abc,b).equals(Set.of()),"Common geometry callees differ: ApexCatalogPanelKind");}
        {var b=ownedBody(abc,instance,"ApexCatalogOptional");var i=abc.method_info.get(b.method_info);require(i.param_types.length==2 && i.optional.length==0 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogOptional");require(commonGeometryCalls(abc,b).equals(Set.of()),"Common geometry callees differ: ApexCatalogOptional");}
        {var b=ownedBody(abc,instance,"ApexCardStateFor");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCardStateFor");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCatalogPanelKey")),"Common geometry callees differ: ApexCardStateFor");}
        {var b=ownedBody(abc,instance,"ApexCardActivate");var i=abc.method_info.get(b.method_info);require(i.param_types.length==2 && i.optional.length==0 && "Boolean".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCardActivate");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCardStateFor","ApexCatalogPanelKey","ApexCatalogPanelKind")),"Common geometry callees differ: ApexCardActivate");}
        {var b=ownedBody(abc,instance,"ApexCatalogVisibleRect");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogVisibleRect");require(commonGeometryCalls(abc,b).equals(Set.of("Error","Sprite","getBounds","isFinite")),"Common geometry callees differ: ApexCatalogVisibleRect");}
        {var b=ownedBody(abc,instance,"ApexCatalogSafeRight");var i=abc.method_info.get(b.method_info);require(i.param_types.length==6 && i.optional.length==0 && "Number".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogSafeRight");require(commonGeometryCalls(abc,b).equals(Set.of("isFinite","max","min")),"Common geometry callees differ: ApexCatalogSafeRight");}
        {var b=ownedBody(abc,instance,"ApexCatalogNavigationRects");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==1 && "Array".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogNavigationRects");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCatalogOptional","ApexCatalogVisibleRect","GetLoadedWidgetByName","push")),"Common geometry callees differ: ApexCatalogNavigationRects");require(i.optional[0].value_index==12 && i.optional[0].value_kind==12 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.param_types[i.param_types.length-1]).name_index)),"Width diagnostic option must remain exact default-null Object");}
        {var b=ownedBody(abc,instance,"ApexCatalogWidthEnvelope");var i=abc.method_info.get(b.method_info);require(i.param_types.length==2 && i.optional.length==1 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogWidthEnvelope");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCatalogNavigationRects","ApexCatalogPanelKind","ApexCatalogSafeRight","ApexCatalogVisibleRect","Error","Point","abs","getBounds","isFinite","localToGlobal","max","min","push")),"Common geometry callees differ: ApexCatalogWidthEnvelope");require(i.optional[0].value_index==12 && i.optional[0].value_kind==12 && "Object".equals(abc.constants.getString(abc.constants.getMultiname(i.param_types[i.param_types.length-1]).name_index)),"Width diagnostic option must remain exact default-null Object");}
        {var b=ownedBody(abc,instance,"ApexCatalogWidthRequest");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "Number".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogWidthRequest");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCardStateFor","ApexCatalogWidthEnvelope","ApexCatalogWidthMode","isFinite","max","min")),"Common geometry callees differ: ApexCatalogWidthRequest");}
        {var b=ownedBody(abc,instance,"ApexCatalogWidthMode");var i=abc.method_info.get(b.method_info);require(i.param_types.length==0 && i.optional.length==0 && "Boolean".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexCatalogWidthMode");require(commonGeometryCalls(abc,b).equals(Set.of("isFinite")),"Common geometry callees differ: ApexCatalogWidthMode");}
        {var b=ownedBody(abc,instance,"ApexSkinToneApply");var i=abc.method_info.get(b.method_info);require(i.param_types.length==2 && i.optional.length==0 && "Number".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexSkinToneApply");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCardActivate","ApexCardFit","ApexCardRepairControls","ApexCatalogOptional","ApexCatalogPanelKind","ApexCatalogWidthRequest","ApexSwatchGroupGeometry","Error","GetAllDisplayObjectCells","Point","PositionCells","abs","isFinite","isNaN","localToGlobal","min")),"Common geometry callees differ: ApexSkinToneApply");}
        {var b=ownedBody(abc,instance,"ApexColumnsTrack");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "Sprite".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsTrack");require(commonGeometryCalls(abc,b).equals(Set.of("Sprite","addChild","addEventListener","beginFill","drawRoundRect","endFill","getChildByName")),"Common geometry callees differ: ApexColumnsTrack");}
        {var b=ownedBody(abc,instance,"ApexColumnsScaleDown");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsScaleDown");require(commonGeometryCalls(abc,b).equals(Set.of("ApexColumnsScale","ApexColumnsTakeover","addEventListener","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsScaleDown");}
        {var b=ownedBody(abc,instance,"ApexColumnsScaleMove");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsScaleMove");require(commonGeometryCalls(abc,b).equals(Set.of("ApexColumnsScale","ApexColumnsScaleEnd","Event","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsScaleMove");}
        {var b=ownedBody(abc,instance,"ApexColumnsScaleUp");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsScaleUp");require(commonGeometryCalls(abc,b).equals(Set.of("ApexColumnsScaleEnd","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsScaleUp");}
        {var b=ownedBody(abc,instance,"ApexColumnsWidthDown");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsWidthDown");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCatalogWidthEnvelope","ApexCatalogWidthMode","ApexColumnsResizeEnd","ApexColumnsScaleEnd","ApexColumnsTakeover","ApexColumnsUp","Event","addEventListener","isFinite","max","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsWidthDown");}
        {var b=ownedBody(abc,instance,"ApexColumnsWidthMove");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsWidthMove");require(commonGeometryCalls(abc,b).equals(Set.of("ApexCatalogWidthEnvelope","ApexColumnsResizeEnd","ApexColumnsSave","ApexColumnsTakeover","Event","isFinite","max","min","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsWidthMove");}
        {var b=ownedBody(abc,instance,"ApexColumnsWidthUp");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==1 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsWidthUp");require(commonGeometryCalls(abc,b).equals(Set.of("ApexColumnsResizeEnd","preventDefault","stopImmediatePropagation")),"Common geometry callees differ: ApexColumnsWidthUp");}
        {var b=ownedBody(abc,instance,"ApexColumnsWidthHandle");var i=abc.method_info.get(b.method_info);require(i.param_types.length==1 && i.optional.length==0 && "void".equals(abc.constants.getString(abc.constants.getMultiname(i.ret_type).name_index)),"Common geometry signature differs: ApexColumnsWidthHandle");require(commonGeometryCalls(abc,b).equals(Set.of("Initialize","Sprite","TooltipObject","addChild","addEventListener","beginFill","drawRect","drawRoundRect","endFill","getBounds","lineStyle","lineTo","max","moveTo","push")),"Common geometry callees differ: ApexColumnsWidthHandle");}
        var nullable=abc.method_info.get(ownedBody(abc,instance,"ApexColumnsWidthUp").method_info).optional[0];
        require(nullable.value_index==com.jpexs.decompiler.flash.abc.types.ValueKind.CONSTANT_Null && nullable.value_kind==com.jpexs.decompiler.flash.abc.types.ValueKind.CONSTANT_Null,"Width-up default must remain exact null Event");
        require(!propertyCalls(abc,ownedBody(abc,instance,"ApexColumnsResize")).contains("ApexColumnsSet"),"Width resize cannot overwrite the chosen column count");
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
        Set<String> ownedFields = Set.of("apexPanelGeometry","apexCatalogGrid","apexLayoutTrace","apexCatalogTrace","apexColumns", "apexPanels", "apexWire", "apexReceiving", "apexLastId", "apexLastReply",
            "apexNativeTransportRequired", "apexNativeChannel", "apexNativeConnected",
            "apexSocket", "apexTimer", "apexFrame", "apexExpected", "apexNonce", "apexBoundSim",
            "apexAwaiting", "apexAckId", "apexDisconnected", "apexSocketActive", "apexHelloPending", "apexSocketError",
            "apexSocketResetPending", "apexOutboundFrame", "apexOutboundPending",
            "apexPendingFields", "apexPendingReply", "apexPendingContext", "apexReadbackTick", "apexPendingPhase", "apexClaimNonce", "apexTicking", "apexAcceptWait", "apexAcceptInput", "apexAcceptStage",
            "apexPresentationQueued", "apexPresentationStarted", "apexPresentationMilliseconds", "apexPresentationFrames", "apexPresentationListener", "apexPresentationSim","apexPresentationFirstFrameDelay","apexPresentationPrimeMs","apexPresentationCatalogMs","apexPresentationMenuMs","apexPresentationStateMs","apexPresentationPairMs","apexPresentationIconsMs","apexPresentationGraphicsMs",
            "apexOwnerFeed", "apexOwnerFeedSequence", "apexOwnerSession", "apexOwnerFeedListener", "apexOwnerResetListener", "apexMoleculeRegistered", "apexMoleculeReadRegistered", "apexMoleculeListener", "apexMoleculeView", "apexMoleculeIntent",
            "apexFormsRoot", "apexFormsSignature", "apexFormsOwnedMask", "apexFormsCatalog", "apexFormsIntent", "apexFormsResult", "apexFormsMessage", "apexFormsApplying",
            "apexFormsPosition", "apexFormsScale", "apexFormsLocked", "apexFormsCollapsed", "apexFormsDragging", "apexFormsPanelWidth", "apexFormsHousehold", "apexFormsLayerButtons", "apexFormsGestureSequence", "apexFormsOwners", "apexFormsOwnerTotal", "apexFormsSelectedId", "apexFormsNativeState", "apexFormsDesiredId", "apexFormsNativeIntent", "apexFormsBootstrap", "apexFormsPage", "apexFormsPanelHeight", "apexFormsGroups", "apexFormsVariantFamily", "apexFormsTooltips", "apexFormsGroupKey",
            "apexFormsCatalogPages","apexFormsLocalCatalog","apexFormsLocalOffset",
            "apexFormsFrameQueued", "apexFormsFastState", "apexFormsNativeGeneration", "apexFormsGestureStarted", "apexFormsSwitchMilliseconds",
            "apexInputSamples", "apexInputOverBudget", "apexInputMaxMs", "apexInputTotalMs",
            "apexCatalogPrefs","apexCatalogDisplayFaults","apexCatalogStore","apexCatalogUi","apexCatalogRows","apexCatalogIntent","apexCatalogSignature","apexCatalogEffects","apexCatalogPage","apexCatalogItems","apexCatalogContext","apexCatalogError","apexCatalogRegistered","apexCatalogDrag","apexCatalogSaved",
            "apexCatalogTab", "apexCatalogSelectionFrames", "apexCatalogSelectionMaxMs", "apexCatalogSelectionOverBudget", "apexCatalogStyleSignature", "apexCatalogLayoutChanges", "apexCatalogRefreshRegistered", "apexCatalogDirty", "apexCatalogSlot", "apexCatalogBinding", "apexCatalogBindingRegistered", "apexCatalogBindingDirty", "apexCatalogBoundWidth", "apexCatalogHeaderSignature",
            "apexCardPrefs","apexCardGeometry","apexCardLayout","apexCardReflowAttempts",
            "apexCatalogFrameCells","apexEquippedActive","apexEquippedOpening","apexEquippedProducts","apexEquippedBindings","apexEquippedDirty",
            "apexEquippedIndex","apexEquippedRefreshPending","apexEquippedInteraction","apexEquippedServices","apexEquippedUnresolved",
            "apexCatalogPerformance","apexCatalogFrameTiming","apexSearch","apexCompanion",
            "apexEquippedTiming",
            "apexEquippedRetirePending",
            "apexEquippedPublication",
              "apexKeyStage","apexKeyIntent","apexKeyIndex","apexKeyFeed","apexKeyContext","apexKeyFocus","apexKeyMessage","apexKeyBounds","apexKeyItem","apexKeyQueue","apexKeyReceipt","apexKeyInjecting","apexKeyReceived","apexKeyLastCode","apexKeyRejected",
            "apexPairRoot", "apexPairContext", "apexPairIntent", "apexPairSignature", "apexPairTooltips", "apexPairMessage", "apexPairRegistered");
        Set<String> ownedNames = Set.of("ApexCatalogGridProductPanel","ApexCatalogGridProductRow","ApexCatalogPanelKey","ApexCatalogPanelKind","ApexCatalogOptional","ApexCardStateFor","ApexCardActivate","ApexCatalogVisibleRect","ApexCatalogSafeRight","ApexCatalogNavigationRects","ApexCatalogWidthEnvelope","ApexCatalogWidthRequest","ApexCatalogWidthMode","ApexSkinToneApply","ApexColumnsTrack","ApexColumnsScaleDown","ApexColumnsScaleMove","ApexColumnsScaleUp","ApexColumnsWidthDown","ApexColumnsWidthMove","ApexColumnsWidthUp","ApexColumnsWidthHandle","ApexCatalogGridPermit","ApexCatalogGridBootstrap","ApexCatalogGridInitialize","ApexCatalogGridPrepare","ApexCatalogGridLeaseCurrent","ApexCatalogGridValidate","ApexCatalogGridObserve","ApexCatalogGridFrameObserve","ApexCatalogGridMatches","ApexCatalogGridInput","ApexCatalogGridRequest","ApexCatalogGridFrame","ApexCatalogGridInvalidate","ApexCatalogGridChanged","ApexCatalogGridOwns","ApexCatalogGridPending","ApexCatalogGridStatus","ApexCatalogGridDispose","ApexImageBoundaryProbe","ApexLayoutTraceConfigure","ApexLayoutTraceDispose","ApexLayoutTraceStatus","ApexLayoutReset","ApexCatalogTraceConfigure","ApexCatalogTraceStatus","ApexCatalogTraceDispose","ApexCatalogTraceStep","ApexPanelsConsumerCancel","ApexPanelsCapture","ApexPanelsAction","ApexPanelConsumer","ApexPanelPersistGate","ApexPanelsConsume","ApexPanelsTooltip","ApexPanelsPreview","ApexColumnsInitialize","ApexColumnsTakeover","ApexColumnsSave","ApexColumnsSet","ApexColumnsScale","ApexColumnsScaleEnd","ApexColumnsResize","ApexColumnsResizeEnd","ApexColumnsDown","ApexColumnsMove","ApexColumnsUp","ApexColumnsFrame","ApexColumnsDispose","ApexPanelsInitialize","ApexPanelsDrawer","ApexPanelsChanged","ApexPanelsButton","ApexPanelsAdopt","ApexPanelsApply","ApexPanelsDragStart","ApexPanelsDragMove","ApexPanelsDragEnd","ApexPanelsScale","ApexPanelsWheel","ApexPanelsClick","ApexPanelsFrame","ApexPanelRefreshGate","ApexPanelsContext","ApexPanelsStamp","ApexPanelsWork","ApexPanelsCommand","ApexPanelsStatus","ApexPanelsDispose","ApexInitialize", "ApexResetSocket", "ApexDisconnect", "ApexTick", "ApexIdleMemberChanged", "ApexMoleculeChooseOccult", "ApexMoleculeReadSelection", "ApexMoleculeDrain", "ApexFormsBindUiKind", "ApexObserveMolecule", "ApexMoleculeListen",
            "ApexSocketConnect", "ApexSocketFailure", "ApexSocketSend", "ApexSocketData", "ApexSocketReply",
            "ApexNativeExchange", "ApexNativeOpen", "ApexNativeReceive", "ApexConsumeFrame","ApexFormsConsumeCatalog","ApexFormsTryLocalCatalog",
            "ApexPresentationReady", "ApexPresentationStop", "ApexPresentationSchedule", "ApexPresentationFrame", "ApexPresentationNotify", "ApexPresentationPrime",
            "ApexQuote", "ApexEncode", "ApexCatalogReadbackOnly", "ApexCatalogReadbackContext", "ApexCatalogSnapshot", "ApexPanelNavigationSnapshot", "ApexCatalogTimerStep", "ApexCatalogTimerStatus", "ApexSnapshot", "ApexExecute", "ApexReadback", "ApexComplete", "ApexAccept", "ApexAcceptListen", "ApexAcceptUserInput", "ApexAcceptReadyFrame", "ApexAcceptAbort", "ApexAcceptNative", "ApexAcceptReady",
            "ApexOwnerFeedRow", "ApexObserveOwnerFeed", "ApexOwnerSimRow", "ApexOwnerObservation", "ApexInvalidateOwnerFeed", "ApexOwnerHouseholdProbe", "ApexFormSelectionContext", "ApexMemberSelectionContext",
            "ApexClone", "ApexCatalog", "ApexControlExecute", "ApexControlResult", "ApexBodyTypes", "ApexNativeLayers", "ApexSelectEyebrowSwatch", "ApexWingObservation",
            "ApexFormsDispose", "ApexFormsText", "ApexFormsButton", "ApexFormsTick", "ApexFormsClick", "ApexFormsLayers", "ApexFormsStatus",
            "ApexFormsToolbar", "ApexFormsToolbarClick", "ApexFormsPlace", "ApexFormsDragStart", "ApexFormsDragEnd", "ApexFormsResetPosition", "ApexFormsObservedSim", "ApexFormsDragCancel", "ApexFormsApply", "ApexFormsOwnedTick", "ApexFormsCompactButton", "ApexFormsGroupCatalog", "ApexFormsTooltip", "ApexFormsClearTooltips",
            "ApexFormsQueueOwner", "ApexFormsNextFrame", "ApexFormsReadNativeState", "ApexFormsScheduleFrame", "ApexInputTiming", "ApexFormsRefreshBoundPair", "ApexFormsCommandBlocksInput",
            "ApexCatalogInitialize","ApexCatalogValidate","ApexCatalogPersist","ApexCatalogStyle","ApexCatalogDispose","ApexCatalogOpen","ApexCatalogFrame","ApexCatalogClearEffects","ApexCatalogSelection","ApexCatalogReadEquipped","ApexCatalogMenu","ApexCatalogButton","ApexCatalogSlider","ApexCatalogDraw","ApexCatalogClick","ApexCatalogSlideStart","ApexCatalogSlide","ApexCatalogSlideEnd","ApexCatalogStatus",
            "ApexCatalogDisplayFaulted","ApexCatalogDisplayFault","ApexCatalogDisplayFaultStatus",
            "ApexCatalogView", "ApexCatalogSliderCommand", "ApexCatalogInvalidate", "ApexCatalogObserveBinding", "ApexCatalogApplyBinding",
            "ApexCardIncrementalApply","ApexCardValidate","ApexCardCommand","ApexCardReset","ApexCardRestore","ApexCardForget","ApexCardScaleCells","ApexCardApply","ApexCardReadback","ApexCardRowsAligned","ApexCardGridReadback","ApexCardFit","ApexCardRepairControls",
            "ApexCatalogKeyboardVisibility","ApexCatalogKeyboardTyping","ApexCatalogKeyboardInput","ApexCatalogKeyboardCommand","ApexCatalogKeyboardPublication","ApexCatalogKeyboardPublicationReady","ApexCatalogKeyboardScopeEqual","ApexCatalogKeyboardInitialize","ApexCatalogKeyboardDispose","ApexCatalogKeyDown","ApexCatalogKeyboardFrame",
            "ApexSearchInitialize","ApexSearchContext","ApexSearchRestore","ApexSearchDispose","ApexSearchReset","ApexSearchSource","ApexSearchAdopt",
            "ApexSearchText","ApexSearchChanged","ApexSearchClear","ApexSearchKey","ApexSearchLabels","ApexSearchFocus",
            "ApexSearchAttach","ApexSearchQuery","ApexSearchPublish","ApexSearchFrame","ApexSearchNativeKey","ApexSearchStatus","ApexSearchChooseFolder","ApexSearchSuggestions","ApexSearchOrder","ApexSearchSelection",
            "ApexCompanionInitialize","ApexCompanionValidKey","ApexCompanionKey","ApexCompanionAllows","ApexCompanionSave","ApexCompanionRecentOrder","ApexCompanionReceipt",
            "ApexCompanionChanged","ApexCompanionIntent","ApexCompanionCard","ApexCompanionButton","ApexCompanionGlyph",
            "ApexCompanionAttach","ApexCompanionApply","ApexCompanionBadges","ApexCompanionFrame","ApexCompanionCommand",
            "ApexCompanionStatus","ApexCompanionDispose",
            "ApexCompanionKeyDown","ApexCompanionResizeStart","ApexCompanionResizeEnd",
              "ApexCatalogCells","ApexEquippedInitialize","ApexEquippedDispose","ApexEquippedNavigation","ApexCatalogPerformance",
            "ApexEquippedRefresh","ApexEquippedOpen","ApexEquippedFrame","ApexEquippedResolve","ApexEquippedKey","ApexEquippedDecimal","ApexEquippedPrepare","ApexEquippedClick",
            "ApexPairDispose", "ApexPairRead", "ApexPairExecute", "ApexPairClick", "ApexPairLabel", "ApexPairButton", "ApexPairTick", "ApexPairStatus", "ApexPairPanel");
        Set<String> seenNames = new HashSet<>();
        int initializeName = -1, disconnectName = -1, gridBootstrapName=-1;
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
                    if (key.equals("ApexCatalogGridBootstrap")) gridBootstrapName = trait.name_index;
                }
            }
        }
        require(added.size() == ownedFields.size() + ownedNames.size() && initializeName >= 0 && disconnectName >= 0 && gridBootstrapName>=0,
            "Unexpected Apex trait inventory.");
        verifyCommonCatalogGeometry(compiled,newClass);
        verifyGridController(compiled,newClass);
        verifyTimerPipeline(compiled, newClass);
        verifyDrawTraceHelper(compiled,newClass);
        verifyTimerTraceHelper(compiled,newClass);
        verifyPanelNavigation(compiled,newClass);
        verifyLayoutTraceHelper(compiled,newClass);
        verifyOwnedLexicalRoots(compiled,ownedMethods);
        verifySearchScrollerBinding(compiled,newClass);
        require(propertyCalls(compiled,ownedBody(compiled,newClass,"ApexIdleMemberChanged")).equals(Set.of("test")),
            "Idle member observation must validate retained primitives without native queries or selection.");
        verifyOwnerObservation(compiled, newClass);
        verifyFormSelection(compiled, newClass);
        verifyFormStrip(compiled, newClass);
        verifyMemberSelection(compiled,newClass);
        verifyQueuedHandshake(compiled, newClass);
        verifySocketLifetime(compiled,newClass);
        verifyExactItemSelection(compiled, newClass);
        verifyTypedControls(compiled, newClass);
        verifyPhysiqueGesture(compiled,newClass);
        verifyAcceptReadiness(compiled,newClass);
        verifyAcceptLinkage(compiled, newClass);
        verifyAcceptHouseholdBinding(compiled, newClass);
        verifyAcceptPrimaryLayerOnly(compiled, newClass);
        verifyCatalogMetadataLinkage(compiled, newClass);
        verifyCatalogMetadataDisabled(compiled, newClass);
        verifyCatalogThinReadback(compiled,newClass);
        verifyEyebrowPaletteWidget(compiled, newClass);
        verifyWingSelection(compiled, newClass);
        verifyOwnerMetadataReadback(compiled,newClass);
        verifyPresentationBootstrap(compiled,newClass);
        verifyCatalogVariantReadback(compiled,newClass);
        verifySettledOwnerBootstrap(compiled,newClass);
        verifyImmediatePairAcknowledgement(compiled,newClass);
        verifyCatalogWorkspace(compiled,newClass);
        verifyNativeCatalogSearch(compiled,newClass);
        verifyCatalogCompanion(compiled,newClass);
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
        MethodBody heightAdapter=cardHeightAdapter(original,compiled);
        var equippedBodies=equippedAdapters(original,compiled);
        var companionBodies=companionAdapters(original,compiled);
        var outfitBody=currentOutfitAdapter(original,compiled);
        if(outfitBody!=null)equippedBodies.add(outfitBody);
        var columnBodies=columnSchedulingAdapters(original,compiled);equippedBodies.addAll(columnBodies);
        var lazySwatchBodies=lazySwatchAdapters(original,compiled);equippedBodies.addAll(lazySwatchBodies);
        var favoriteBody=favoriteLookupAdapter(original,compiled);if(favoriteBody!=null)equippedBodies.add(favoriteBody);
        var consumerBodies=consumerAdapters(original,compiled);equippedBodies.addAll(consumerBodies);
        MethodBody drawTraceBody=null;
        if(original.findClassByName("dcc.history.HistoryHost")>=0) {drawTraceBody=makeDrawTraceAdapter(original,compiled);equippedBodies.add(drawTraceBody);}
        var traceCallback=drawTraceStaticTrait(compiled).clone();
        int traceMain=original.findClassByName("widgets.CAS.Customizer.CASCustomizerMain");
        for(var trait:original.class_info.get(traceMain).static_traits.traits)
            require(!name(original,trait).equals("apexCatalogDrawTraceStep"),"Native class already owns the diagnostic callback name.");
        ((TraitSlotConst)traceCallback).slot_id=0;
        original.class_info.get(traceMain).static_traits.traits.add(traceCallback);
        equippedBodies.addAll(companionBodies);
        var adapterIds=new HashSet<Integer>();adapterIds.add(heightAdapter.method_info);
        for(var body:equippedBodies)adapterIds.add(body.method_info);
        compiled.instance_info = original.instance_info;
        compiled.method_info = methods;
        compiled.class_info = original.class_info;
        compiled.script_info = original.script_info;
        compiled.metadata_info = original.metadata_info;
        compiled.bodies = new ArrayList<>(original.bodies);
        int heightIndex=-1;
        for(int i=0;i<compiled.bodies.size();i++)if(compiled.bodies.get(i).method_info==heightAdapter.method_info)heightIndex=i;
        require(heightIndex>=0,"Native card getter index absent.");compiled.bodies.set(heightIndex,heightAdapter);
        for(var body:equippedBodies) {
            int index=-1;for(int i=0;i<compiled.bodies.size();i++)if(compiled.bodies.get(i).method_info==body.method_info)index=i;
            require(index>=0,"Equipped native method index absent.");compiled.bodies.set(index,body);
        }
        compiled.bodies.addAll(newBodies);
        for (Trait trait : added) if (trait instanceof TraitMethodGetterSetter) {
            var method = (TraitMethodGetterSetter)trait; method.method_info = remap.get(method.method_info);
        }
        var nativeInitOriginal=nativeInit.clone();
        var initialized=gridBootstrapAdapter(original,nativeInitOriginal,gridBootstrapName,initializeName);
        // Resolve the exact native seam before appending traits whose QNames
        // belong to the compiler's extended constant pool, not original's.
        nativeClass.instance_traits.traits.addAll(added);
        nativeInit.setCode(initialized.getCode());nativeInit.exceptions=initialized.exceptions;
        nativeInit.max_stack=initialized.max_stack;nativeInit.setModified();
        extendUnloadPrologue(nativeUnload, disconnectName);
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload)
            require(Arrays.equals(nativeCode.get(body.method_info), body.getCodeBytes()), "Unowned native method bytecode changed.");
        ByteArrayOutputStream saved = new ByteArrayOutputStream();
        compiled.saveToStream(saved);
        ABC serialized = new ABC(new ABCInputStream(new MemoryInputStream(saved.toByteArray())), compiled.getSwf(), null);
        verifyLifecycle(serialized.findBody(nativeInit.method_info), nativeCode.get(nativeInit.method_info), initializeName, "Initialize");
        verifyGridBootstrapProjection(serialized,nativeInitOriginal,serialized.findBody(nativeInit.method_info),gridBootstrapName,initializeName);
        verifyCommonCatalogGeometry(serialized,serialized.instance_info.get(oi));
        verifyGridController(serialized,serialized.instance_info.get(oi));
        verifyUnloadPrologue(serialized.findBody(nativeUnload.method_info), nativeCode.get(nativeUnload.method_info), disconnectName);
        verifyAcceptReadiness(serialized,serialized.instance_info.get(oi));
        verifyAcceptLinkage(serialized, serialized.instance_info.get(oi));
        verifyAcceptHouseholdBinding(serialized, serialized.instance_info.get(oi));
        verifyAcceptPrimaryLayerOnly(serialized, serialized.instance_info.get(oi));
        verifyCatalogMetadataLinkage(serialized, serialized.instance_info.get(oi));
        verifyCatalogMetadataDisabled(serialized, serialized.instance_info.get(oi));
        verifyCatalogThinReadback(serialized,serialized.instance_info.get(oi));
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
        verifyPresentationBootstrap(serialized,serialized.instance_info.get(oi));
        verifyCatalogVariantReadback(serialized,serialized.instance_info.get(oi));
        verifySettledOwnerBootstrap(serialized,serialized.instance_info.get(oi));
        verifyImmediatePairAcknowledgement(serialized,serialized.instance_info.get(oi));
        verifyCatalogWorkspace(serialized,serialized.instance_info.get(oi));
        verifyNativeCatalogSearch(serialized,serialized.instance_info.get(oi));
        verifyCatalogCompanion(serialized,serialized.instance_info.get(oi));
        verifyPanelScheduling(serialized,serialized.instance_info.get(oi));
        verifyDrawTraceHelper(serialized,serialized.instance_info.get(oi));
        verifyTimerTraceHelper(serialized,serialized.instance_info.get(oi));
        verifyPanelNavigation(serialized,serialized.instance_info.get(oi));
        verifyLayoutTraceHelper(serialized,serialized.instance_info.get(oi));
        verifyOwnedLexicalRoots(serialized,new HashSet<>(remap.values()));
        verifySearchScrollerBinding(serialized,serialized.instance_info.get(oi));
        if(outfitBody!=null)verifyCurrentOutfitAdapter(serialized,serialized.findBody(outfitBody.method_info),nativeCode.get(outfitBody.method_info));
        require(Arrays.equals(heightAdapter.getCodeBytes(),serialized.findBody(heightAdapter.method_info).getCodeBytes()),
            "Serialized owned card getter changed.");
        for(var body:equippedBodies)require(Arrays.equals(body.getCodeBytes(),serialized.findBody(body.method_info).getCodeBytes()),
            "Serialized equipped adapter changed.");
        for(var body:consumerBodies)verifyConsumerPrefix(serialized,serialized.findBody(body.method_info),original.findBody(body.method_info));
        if(drawTraceBody!=null)verifyDrawTraceAdapter(original,serialized);
        var savedTraceTrait=drawTraceStaticTrait(serialized);
        require(savedTraceTrait.name_index==traceCallback.name_index,"Serialized nullable Draw callback trait differs.");
        for (MethodBody body : original.bodies) if (body != nativeInit && body != nativeUnload && !adapterIds.contains(body.method_info))
            require(Arrays.equals(nativeCode.get(body.method_info), serialized.findBody(body.method_info).getCodeBytes()),
                "Serialized unowned native method bytecode changed.");
        Files.write(Path.of(args[2]), saved.toByteArray());
        System.out.println("{\"native_method_count\":" + original.bodies.size() + ",\"apex_method_count\":" + ownedMethods.size() +
            ",\"native_lexical_scope_preserved\":true,\"card_height_marker_adapter_verified\":true,\"native_equipped_category_adapters_verified\":true,\"native_wing_paint_owner_adapters\":3,\"native_pelt_palette_reenable_verified\":true,\"native_column_scheduler_adapters\":"+columnBodies.size()+",\"native_draw_trace_adapters\":"+(drawTraceBody==null?0:1)+",\"native_draw_trace_guard_verified\":true,\"native_draw_trace_cfg_verified\":"+(drawTraceBody!=null)+",\"native_draw_trace_call_abi_verified\":"+(drawTraceBody!=null)+",\"native_outfit_consumers\":"+consumerBodies.size()+",\"native_favorite_lookup_map_verified\":true,\"native_lazy_swatch_adapters\":"+lazySwatchBodies.size()+",\"native_current_outfit_refresh_queue_verified\":true,\"companion_named_form_adapters\":"+companionBodies.size()+",\"unchanged_native_methods\":" + (nativeCode.size()-2-adapterIds.size()) +
            ",\"native_grid_bootstrap_pre_sim_delivery_verified\":true,\"native_grid_bootstrap_cfg_projection_verified\":true,\"native_grid_controller_scope_verified\":true,\"native_initializer_bytecode_extended\":true,\"native_unload_bytecode_extended\":true,\"native_unload_cleanup_precedes_teardown\":true,\"owned_local_scope_indexes_verified\":true,\"serialized_lifecycle_hooks_verified\":true,\"socket_callbacks_data_only_verified\":true,\"timer_command_phases_verified\":true,\"accept_commit_timer_owned_verified\":true,\"accept_readiness_original_uuid_once_only_verified\":true,\"accept_readiness_busy_wait_no_save_verified\":true,\"accept_native_class_linkage_verified\":true,\"accept_expected_household_bound_verified\":true,\"accept_primary_layer_only_verified\":true,\"catalog_metadata_localization_linkage_verified\":true,\"owner_pair_callback_data_only_verified\":true,\"owner_pair_listener_cleanup_verified\":true,\"owner_pair_timer_read_only_verified\":true,\"socket_connect_queue_only_verified\":true,\"socket_handshake_exact_constructor_timer_verified\":true,\"form_select_timer_owned_verified\":true,\"form_select_exact_same_original_pair_verified\":true,\"form_select_native_argument_order_verified\":true,\"form_select_next_tick_readback_verified\":true,\"earrings_exact_bodytype_and_swatch_guard_verified\":true}");
    }
}
