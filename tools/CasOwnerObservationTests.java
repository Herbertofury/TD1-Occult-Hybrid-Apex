// Synthetic data-only feed/lifetime/readback contracts, no installed assets.
import java.io.*;
import java.util.*;
import com.jpexs.decompiler.flash.abc.*;
import com.jpexs.decompiler.flash.abc.avm2.instructions.*;
import com.jpexs.decompiler.flash.abc.types.*;
import com.jpexs.decompiler.flash.abc.types.traits.*;
import com.jpexs.helpers.MemoryInputStream;

public class CasOwnerObservationTests {
    static AVM2Instruction op(int opcode,int... operands) { return CasAcceptLayerTests.op(opcode,operands); }
    static int member(ABC abc,String name) { return CasAcceptLayerTests.member(abc,name); }
    static AVM2Instruction string(ABC abc,String value) { return op(0x2c,abc.constants.getStringId(value,true)); }
    static void body(ABC abc,InstanceInfo instance,String name,List<AVM2Instruction> code) {
        CasAcceptLayerTests.body(abc,instance,name,code);
    }
    static ABC fixture(String variant) {
        ABC abc=new ABC((com.jpexs.decompiler.flash.tags.ABCContainerTag)null);
        InstanceInfo instance=new InstanceInfo(new Traits());instance.interfaces=new int[0];abc.instance_info.add(instance);
        ClassInfo clazz=new ClassInfo(new Traits());clazz.cinit_index=0;abc.class_info.add(clazz);
        for(String name:List.of("ApexInitialize","ApexDisconnect")) {
            boolean add=name.equals("ApexInitialize");String prefix=add?"initialize-":"cleanup-";
            List<AVM2Instruction> code=new ArrayList<>();
            if(!variant.equals(prefix+"missing")) code.addAll(List.of(
                op(0x5d,member(abc,add?"AddMessageListener":"RemoveMessageListener")),
                string(abc,variant.equals(prefix+"event")?"OtherEvent":"CASRefreshSimIcons"),
                op(0x60,member(abc,variant.equals(prefix+"callback")?"OtherCallback":"ApexObserveOwnerFeed")),
                op(add?0x46:0x4f,member(abc,add?"AddMessageListener":"RemoveMessageListener"),variant.equals(prefix+"mapping")?3:2)));
            if(!variant.equals(prefix+"reset-missing"))code.addAll(List.of(
                op(0x5d,member(abc,add?"AddMessageListener":"RemoveMessageListener")),
                string(abc,variant.equals(prefix+"reset-event")?"OtherEvent":"CASClearSimsForReset"),
                op(0x60,member(abc,variant.equals(prefix+"reset-callback")?"ApexObserveOwnerFeed":"ApexInvalidateOwnerFeed")),
                op(add?0x46:0x4f,member(abc,add?"AddMessageListener":"RemoveMessageListener"),2)));
            code.add(op(0x47));body(abc,instance,name,code);
        }
        for(String name:List.of("ApexObserveOwnerFeed","ApexOwnerFeedRow","ApexOwnerSimRow","ApexInvalidateOwnerFeed","ApexOwnerHouseholdProbe")) {
            List<AVM2Instruction> code=new ArrayList<>();
            String call=null;
            if(variant.equals("callback-native") && name.equals("ApexObserveOwnerFeed")) call="CallGameService";
            if(variant.equals("callback-indirect") && name.equals("ApexObserveOwnerFeed")) call="ArbitraryNativeHelper";
            if(variant.equals("callback-observation") && name.equals("ApexObserveOwnerFeed")) call="ApexOwnerObservation";
            if(variant.equals("feed-helper-native") && name.equals("ApexOwnerFeedRow")) call="CallGameService";
            if(variant.equals("sim-helper-native") && name.equals("ApexOwnerSimRow")) call="SendUIMessage";
            if(variant.equals("reset-native") && name.equals("ApexInvalidateOwnerFeed"))call="CallGameService";
            if(variant.equals("probe-native") && name.equals("ApexOwnerHouseholdProbe"))call="CallGameService";
            if(call!=null)code.add(op(0x46,member(abc,call),0));
            code.add(op(0x47));body(abc,instance,name,code);
        }
        List<AVM2Instruction> observe=new ArrayList<>();
        if(!variant.equals("missing-timer-gate"))observe.add(op(0x60,member(abc,"apexTicking")));
        if(!variant.equals("missing-lifetime-gate"))observe.add(op(0x60,member(abc,"apexDisconnected")));
        if(!variant.equals("missing-return-gate"))observe.add(op(0x48));
        for(int read=0;read<(variant.equals("missing-fresh-read")?2:3);read++) {
            String service=read==1?"CasGetHouseholdSims":"CASGetSimInfo";
            if(variant.equals("getter-order") && read==0)service="CasGetHouseholdSims";
            if(variant.equals("getter-all-selected"))service="CASGetSimInfo";
            if(read==0 && variant.equals("getter-mutator"))service="CasSelectSim";
            if(!variant.equals("getter-dynamic") || read!=0)observe.add(string(abc,service));
            if(!service.equals("CasGetHouseholdSims"))observe.addAll(List.of(op(variant.equals("getter-payload") && read==0?0x26:0x20),
                op(variant.equals("getter-refresh") && read==0?0x27:0x26)));
            observe.add(op(0x46,member(abc,"CallGameService"),service.equals("CasGetHouseholdSims")?(variant.equals("household-argc")?2:1):
                (variant.equals("getter-argc") && read==0?2:3)));
        }
        observe.add(op(0x46,member(abc,"ApexOwnerSimRow"),1));
        observe.add(op(0x46,member(abc,"ApexOwnerHouseholdProbe"),1));
        if(!variant.equals("selector-missing"))observe.addAll(List.of(string(abc,variant.equals("selector-name")?"CASRemoveCurrentSim":"ApexReadOwnerPairFeed"),
            op(variant.equals("selector-payload")?0x26:0x20),op(0x46,member(abc,"CallUIService"),variant.equals("selector-argc")?1:2)));
        if(variant.equals("observation-mutation"))observe.add(op(0x4f,member(abc,"SendUIMessage"),1));
        observe.add(op(0x48));body(abc,instance,"ApexOwnerObservation",observe);
        body(abc,instance,"ApexSnapshot",List.of(op(0x46,member(abc,variant.equals("snapshot-missing")?"OtherSnapshot":"ApexOwnerObservation"),0),op(0x48)));
        body(abc,instance,"ApexTick",variant.equals("wrong-caller")?List.of(op(0x46,member(abc,"ApexOwnerObservation"),0),op(0x47)):List.of(op(0x47)));
        return abc;
    }
    static void check(ABC abc,String variant) {
        boolean valid=variant.equals("valid");
        try {
            CasBytecodePatch.verifyOwnerObservation(abc,abc.instance_info.get(0));
            if(!valid)throw new AssertionError("Invalid CAS owner observation accepted: "+variant);
        } catch(IllegalArgumentException error) {
            if(valid || !error.getMessage().startsWith("CAS owner"))throw new AssertionError(error);
        }
    }
    public static void main(String[] args)throws Exception {
        List<String> variants=List.of("valid","callback-native","callback-indirect","callback-observation","feed-helper-native","sim-helper-native",
            "initialize-event","cleanup-event","initialize-callback","cleanup-callback","initialize-mapping","cleanup-mapping",
            "initialize-missing","cleanup-missing","getter-mutator","getter-dynamic","getter-payload","getter-refresh","getter-argc","household-argc",
            "missing-timer-gate","missing-lifetime-gate","missing-return-gate","missing-fresh-read","observation-mutation","snapshot-missing","wrong-caller",
            "initialize-reset-missing","cleanup-reset-missing","initialize-reset-event","cleanup-reset-event",
            "initialize-reset-callback","cleanup-reset-callback","reset-native","probe-native","getter-order","getter-all-selected",
            "selector-missing","selector-name","selector-payload","selector-argc");
        for(String variant:variants) {
            ABC abc=fixture(variant);check(abc,variant);
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();abc.saveToStream(bytes);
            check(new ABC(new ABCInputStream(new MemoryInputStream(bytes.toByteArray())),null,null),variant);
        }
        System.out.println("{\"synthetic_fixtures\":"+variants.size()+",\"serialized_rechecks\":"+variants.size()+",\"all_passed\":true}");
    }
}
