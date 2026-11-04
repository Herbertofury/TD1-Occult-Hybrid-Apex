"""Exact native override entry gate; no global selection-helper suppression."""
from pathlib import Path
import hashlib
import cas_grid_pool as pool
import cas_grid_spares as previous
ROOT=Path(__file__).resolve().parents[1]
TARGET='olympus.layout.SelectableRecyclingGridLayout'
REPLACED=('PositionCells',);ADDED=()
OWNED=('ApexGridBegin','ApexGridNativeGuard','ApexGridMetrics')
REC='olympus.layout.RecyclingGridLayout'
KINDS=('position','reset','profile','scroll','selection','update','add','front','remove','removeAll','sort','bounds','padding','redraw','input')

def fragment():return (ROOT/'Source/CASUi/catalog_native_position_gate.as').read_text()

def helpers():
    source=previous.helpers()
    init=','.join('nativeEvent_'+kind+':0'for kind in KINDS)+',nativeEvent_unknown:0,nativeEventLast:"",'
    source=pool.edit_method(source,'ApexGridBegin',[('ready:new Dictionary(true),poolFlags:',init+'\n            ready:new Dictionary(true),poolFlags:')])
    # Fixed literal branches only. No per-event objects/arrays/strings, timers,
    # native queries, display writes, product handles or persistent listeners.
    cases=[]
    for kind in KINDS:
        cases.append('            case "'+kind+'": if(int(s.nativeEvent_'+kind+')<int.MAX_VALUE)s.nativeEvent_'+kind+'=int(s.nativeEvent_'+kind+')+1;s.nativeEventLast="'+kind+'";break;')
    counter='\n         switch(kind) {\n'+'\n'.join(cases)+'\n            default: if(int(s.nativeEvent_unknown)<int.MAX_VALUE)s.nativeEvent_unknown=int(s.nativeEvent_unknown)+1;s.nativeEventLast="unknown";break;\n         }'
    source=pool.edit_method(source,'ApexGridNativeGuard',[('var s:Object=apexGridState;var j:Object=s.job;','var s:Object=apexGridState;var j:Object=s.job;'+counter)])
    exported=','.join(kind+':int(s.nativeEvent_'+kind+')'for kind in KINDS)+',unknown:int(s.nativeEvent_unknown),last_kind:s.nativeEventLast==null ? "" : String(s.nativeEventLast)'
    source=pool.edit_method(source,'ApexGridMetrics',[('var s:Object=apexGridState;','var s:Object=apexGridState;\n         result.native_event_kinds={'+exported+'};')])
    return source

def inject(source):
    start,end=pool.method_extent(source,'PositionCells')
    before=source[start:end]
    # Original full body and original native callbacks, not a similar method.
    compact=''.join(before.split())
    if compact!='publicfunctionPositionCells():void{super.PositionCells();this.UpdateSelectionInCells();}':
        raise ValueError('Exact original native PositionCells body differs')
    after=fragment().strip()
    if not after.startswith('override public function '):raise ValueError('Native override fragment marker absent')
    after=after.removeprefix('override ')
    return source[:start]+after+source[end:]
