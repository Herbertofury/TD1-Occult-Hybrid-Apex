// Execute the serialized native Reset and appended profiler on the same tiny
// synthetic host. No game/GFx object, native service or production callback.
import java.util.*;
import com.jpexs.decompiler.flash.abc.ABC;
import com.jpexs.decompiler.flash.abc.types.MethodBody;

public class CasGridResetProfileFixtures {
    static class Host {
        final Map<String,Object> self=new HashMap<>();final List<String> effects=new ArrayList<>();
        final Object grid=new Object();final int target;int clock=1000,timers=0;String fails="";RuntimeException failure;
        Host(int before,int after,boolean suppressed,boolean previous) {
            target=after;self.put("mbSuppressUpdates",suppressed);self.put("mCells",new ArrayList<>(Collections.nCopies(before,1)));
            self.put("mGridView",grid);self.put("mPrevRectangleUpdate",previous?new HashMap<>(Map.of("y",42)):null);
        }
        void work(String phase,int elapsed) {effects.add(phase);clock+=elapsed;if(fails.equals(phase))throw failure;}
    }
    static Object pop(List<Object> stack) {return stack.remove(stack.size()-1);}
    static boolean truth(Object value) {return value!=null && (!(value instanceof Boolean)||((Boolean)value)) && (!(value instanceof Number)||((Number)value).intValue()!=0);}
    static Object run(ABC abc,MethodBody body,Host host) {
        var code=body.getCode().code;var addresses=new HashMap<Long,Integer>();
        for(int n=0;n<code.size();n++)addresses.put(code.get(n).getAddress(),n);
        Object[] locals=new Object[8];locals[0]=host.self;var stack=new ArrayList<Object>();
        int ip=0,steps=0;
        while(ip<code.size()) {
            if(++steps>1000)throw new AssertionError("Profiler fixture looped.");
            var op=code.get(ip++);int command=op.definition.instructionCode;int[] operands=op.operands;
            switch(command) {
                case 0xd0:stack.add(locals[0]);break;
                case 0x30:pop(stack);break;
                case 0x62:stack.add(locals[operands[0]]);break;
                case 0x63:locals[operands[0]]=pop(stack);break;
                case 0x24:stack.add((int)(byte)operands[0]);break;
                case 0x26:stack.add(true);break;
                case 0x27:stack.add(false);break;
                case 0x20:stack.add(null);break;
                case 0x2c:stack.add(abc.constants.getString(operands[0]));break;
                case 0x60: {
                    String name=CasGridBytecodePatch.name(abc,operands[0]);
                    stack.add(name.equals("GridEvent")?Map.of("RESIZE","resize"):host.self.get(name));break;
                }
                case 0x5d:stack.add(CasGridBytecodePatch.name(abc,operands[0]));break;
                case 0x66: {
                    String name=CasGridBytecodePatch.name(abc,operands[0]);Object receiver=pop(stack);
                    stack.add(receiver instanceof List?((List<?>)receiver).size():((Map<?,?>)receiver).get(name));break;
                }
                case 0x61: {
                    Object value=pop(stack);Object receiver=pop(stack);
                    ((Map<String,Object>)receiver).put(CasGridBytecodePatch.name(abc,operands[0]),value);
                    host.effects.add("previous.y=0");break;
                }
                case 0x12:if(!truth(pop(stack)))ip=addresses.get(op.getTargetAddress());break;
                case 0x0e: {
                    int right=((Number)pop(stack)).intValue(),left=((Number)pop(stack)).intValue();
                    if(!(left>right))ip=addresses.get(op.getTargetAddress());break;
                }
                case 0x46: {
                    if(!CasGridBytecodePatch.name(abc,operands[0]).equals("getTimer") || operands[1]!=0)throw new AssertionError("Unexpected profile call.");
                    pop(stack);host.timers++;stack.add(host.clock);break;
                }
                case 0xa1: {
                    int right=((Number)pop(stack)).intValue(),left=((Number)pop(stack)).intValue();stack.add(left-right);break;
                }
                case 0x73:stack.add(((Number)pop(stack)).intValue());break;
                case 0x4a: {
                    var args=new ArrayList<Object>();for(int n=0;n<operands[1];n++)args.add(0,pop(stack));pop(stack);
                    stack.add(args);break;
                }
                case 0x4f: {
                    var args=new ArrayList<Object>();for(int n=0;n<operands[1];n++)args.add(0,pop(stack));Object receiver=pop(stack);
                    String name=CasGridBytecodePatch.name(abc,operands[0]);
                    if(name.equals("SetupCells")) {host.work("setup",7);host.self.put("mCells",new ArrayList<>(Collections.nCopies(host.target,1)));}
                    else if(name.equals("PositionCellsInternal")) {CasGridBytecodePatch.require(args.equals(List.of(true)),"Position lost reset argument.");host.work("position",3);}
                    else if(name.equals("InitializeCellData")) {CasGridBytecodePatch.require(args.equals(List.of(true)),"Bind lost reset argument.");host.work("bind",11);}
                    else if(name.equals("dispatchEvent")) {
                        CasGridBytecodePatch.require(receiver==host.grid && args.size()==1,"Wrong resize owner.");
                        var event=(List<?>)args.get(0);CasGridBytecodePatch.require(event.size()==3 && event.get(0).equals("resize") && event.get(1)==null && ((List<?>)event.get(2)).isEmpty(),"Resize payload changed.");
                        host.work("resize",5);
                    }else throw new AssertionError("Unexpected native method: "+name);
                    break;
                }
                case 0x55: {
                    var object=new LinkedHashMap<String,Object>();for(int n=0;n<operands[0];n++){Object value=pop(stack);String key=(String)pop(stack);object.put(key,value);}stack.add(object);break;
                }
                case 0x47:return null;
                case 0x48:return pop(stack);
                default:throw new AssertionError("Unsupported fixture instruction "+Integer.toHexString(command));
            }
        }
        throw new AssertionError("No return.");
    }
    static void scenario(String name,int before,int after,boolean suppressed,boolean previous,String fail)throws Exception {
        ABC original=CasGridGetterFixtures.original(),candidate=CasGridBytecodePatch.reparse(original);
        CasGridBytecodePatch.append(candidate);candidate=CasGridBytecodePatch.reparse(candidate);CasGridBytecodePatch.verify(original,candidate);
        var nativeBody=original.findBody(CasGridBytecodePatch.method(original,"ResetAndPositionCells").method_info);
        var profile=candidate.findBody(CasGridBytecodePatch.method(candidate,CasGridBytecodePatch.PROFILE).method_info);
        Host nativeHost=new Host(before,after,suppressed,previous),profileHost=new Host(before,after,suppressed,previous);
        var failure=new RuntimeException("same native failure");nativeHost.failure=profileHost.failure=failure;nativeHost.fails=profileHost.fails=fail;
        Object result=null;RuntimeException nativeThrown=null,profileThrown=null;
        try{run(original,nativeBody,nativeHost);}catch(RuntimeException thrown){nativeThrown=thrown;}
        try{result=run(candidate,profile,profileHost);}catch(RuntimeException thrown){profileThrown=thrown;}
        CasGridBytecodePatch.require(nativeHost.effects.equals(profileHost.effects) && nativeThrown==profileThrown,"Profiler changed native effects/exception: "+name);
        if(!fail.isEmpty())CasGridBytecodePatch.require(profileThrown==failure && result==null,"Native throw became a result.");
        else {
            var expected=new HashMap<String,Object>();expected.put("suppressed",suppressed);expected.put("before_count",suppressed?-1:before);expected.put("after_count",suppressed?-1:after);
            expected.put("setup_ms",suppressed?0:7);expected.put("position_ms",suppressed||after==0?0:3);expected.put("bind_ms",suppressed||after==0?0:11);
            expected.put("resize_ms",suppressed?0:5);expected.put("total_ms",suppressed?0:after==0?12:26);
            CasGridBytecodePatch.require(expected.equals(result),"Profile report differs: "+name+" "+result);
            CasGridBytecodePatch.require(profileHost.timers==(suppressed?0:after==0?6:10),"Unbounded timer calls.");
        }
        System.out.println("PASS "+name);
    }
    public static void main(String[] args)throws Exception {
        scenario("grow",48,640,false,true,"");scenario("empty",48,0,false,true,"");
        scenario("no-previous-rectangle",2,3,false,false,"");scenario("suppressed",48,640,true,true,"");
        for(String phase:List.of("setup","position","bind","resize"))scenario("throw-"+phase,2,3,false,true,phase);
    }
}
