"""Exact private Main consumer of typed provider authority-loss receipts."""
from pathlib import Path
import cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexCatalogGridPrepare','ApexCatalogGridFrame','ApexCatalogGridInvalidate','ApexCatalogGridChanged',
          'ApexCatalogGridInput','ApexCatalogGridPending','ApexCatalogGridStatus','ApexCatalogGridRetireInactive',
          'ApexCatalogGridOwns','ApexCatalogGridDispose','ApexCardApply','ApexCardIncrementalApply','ApexCatalogFrame','ApexCardRestore',
          'ApexCatalogSelection','ApexCatalogClearEffects')
ADDED=('ApexCatalogAuthorityScope','ApexCatalogAuthorityEqual','ApexCatalogAuthorityAvailable','ApexCatalogAuthorityRemember',
       'ApexCatalogAuthorityHeld','ApexCatalogAuthorityEffectHeld','ApexCatalogAuthorityHold','ApexCatalogAuthorityRecover')

def inject_main(source):
    def edit(name,*changes):
        nonlocal source
        source=pool.edit_method(source,name,list(changes))
    edit('ApexCatalogGridPrepare',
         ('         var grid:Object=panel.mcTileList.mGridLayout;',
          '         var grid:Object=panel.mcTileList.mGridLayout;\n         if(ApexCatalogAuthorityHold(grid))return ApexCatalogAuthorityRecover(panel,grid);'))
    edit('ApexCatalogGridFrame',
         ('         // Finish only owned cancellation atoms before considering a new', '''         if(s.grid!=null && ApexCatalogAuthorityHold(s.grid)) {
            if(mCurrentPanel!=null && s.lease!=null && mCurrentPanel!==s.lease.panel && ApexCatalogGridProductPanel(mCurrentPanel)!="") {
               // Retire Main references only. The terminal provider owns release.
               s.lease=null;s.grid=null;s.retiring=null;
            } else {
               s.running=true;
               try {if(!ApexCatalogGridPrepare())return;}
               finally {s.running=false;}
            }
         }
         // Finish only owned cancellation atoms before considering a new'''),
         ('            if(s.frame<int.MAX_VALUE)s.frame++;',
          '            ApexCatalogAuthorityRemember(lease);\n            if(s.frame<int.MAX_VALUE)s.frame++;'),
         ('            s.last=s.grid.ApexGridStep(64,',
          '            if(ApexCatalogAuthorityHold(s.grid))return;\n            s.last=s.grid.ApexGridStep(64,'),
         ('            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));',
          '            if(ApexCatalogAuthorityHold(s.grid))return;\n            if(s.last!=null && s.last.error!=null)throw new Error(String(s.last.error));'),
         ('            if(s.lease!=null)s.lease.frame_validated=false;',
          '            if(s.lease!=null && !ApexCatalogAuthorityHold(s.grid))s.lease.frame_validated=false;'))
    edit('ApexCatalogGridInvalidate',
         ('         var s:Object=apexCatalogGrid;if(s==null || s.disposed)return;',
          '         var s:Object=apexCatalogGrid;if(s==null || s.disposed)return;\n         if(ApexCatalogAuthorityHold(s.grid))return;'))
    edit('ApexCatalogGridChanged',
         ('         ApexCatalogGridInvalidate("notification");', '''         var s:Object=apexCatalogGrid;
         if(s!=null && s.authority_owners!=null)for each(var held:Object in s.authority_owners) {
            if(held.blocked===true)held.probe=true;
         }
         ApexCatalogGridInvalidate("notification");'''))
    edit('ApexCatalogGridInput',
         ('         var s:Object=apexCatalogGrid;',
          '         var s:Object=apexCatalogGrid;\n         if(lease!=null && ApexCatalogAuthorityHold(lease.grid))return false;'))
    edit('ApexCatalogGridPending',
         ('         var s:Object=apexCatalogGrid;',
          '         if(ApexCatalogAuthorityHold(grid))return true;\n         var s:Object=apexCatalogGrid;'))
    edit('ApexCatalogGridStatus',
         ('         var lease:Object=s.lease;',
          '''         var blocked:Boolean=ApexCatalogAuthorityHold(s.grid);
         var held:Object=blocked ? ApexCatalogAuthorityHeld(s.grid) : null;
         if(held!=null)return {enabled:Boolean(s.enabled),active:false,generation:int(s.generation),
            frame:int(s.frame),running:Boolean(s.running),invalidations:int(s.invalidations),error:String(s.error),
            waiting_reason:"authority-lost",context:held.scope,authority:held.receipt,native:held.receipt,
            unattributed_effects:int(s.authority_unattributed_effects),appearance_written:false};
         var lease:Object=s.lease;'''),
         ('            context:lease==null ? null :',
          '            context:held!=null ? held.scope : lease==null ? null :'),
         ('            native:s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};',
          '            authority:held==null ? null : held.receipt,\n            native:held!=null ? held.receipt : s.grid==null ? null : s.grid.ApexGridStatus(),appearance_written:false};'))
    edit('ApexCatalogGridRetireInactive',
         ('         if(apexCatalogGrid!==s || s.disposed)return;',
          '         if(apexCatalogGrid!==s || s.disposed)return;\n         if(ApexCatalogAuthorityHold(s.grid)) {s.lease=null;s.grid=null;s.retiring=null;return;}'))
    edit('ApexCatalogGridOwns',
         ('         return s!=null && s.enabled===true && !s.disposed && grid===s.grid;',
          '         return s!=null && s.enabled===true && !s.disposed && (grid===s.grid || ApexCatalogAuthorityHold(grid));'))
    edit('ApexCatalogGridDispose',
         ('         s.disposed=true;s.enabled=false;',
          '''         if(apexCatalogEffects!=null)for each(var effectRecord:Object in apexCatalogEffects) {
            if(ApexCatalogAuthorityEffectHeld(effectRecord))effectRecord.authority_forget=true;
         }
         if(apexCardGeometry!=null && ApexCatalogAuthorityHold(apexCardGeometry.grid))ApexCardForget();
         if(apexPanelGeometry!=null)for(var key:String in apexPanelGeometry) {
            var saved:Object=apexPanelGeometry[key];
            if(saved!=null && saved.geometry!=null && ApexCatalogAuthorityHold(saved.geometry.grid))delete apexPanelGeometry[key];
         }
         s.disposed=true;s.enabled=false;'''),
         ('         if(s.lease!=null) {s.lease.active=false;s.lease.frame_validated=false;}',
          '         if(s.lease!=null && !ApexCatalogAuthorityHold(s.grid)) {s.lease.active=false;s.lease.frame_validated=false;}'),
         ('         try {if(s.grid!=null)s.grid.ApexGridCancel("dispose");}',
          '         try {if(s.grid!=null && !ApexCatalogAuthorityHold(s.grid))s.grid.ApexGridCancel("dispose");}'))
    edit('ApexCardApply',
         ('         if(!ApexCardActivate(panel,grid))',
          '         if(ApexCatalogAuthorityHold(grid))return Number(panel.mcPanelBackground.width);\n         if(!ApexCardActivate(panel,grid))'))
    edit('ApexCardRestore',
         ('         var grid:Object=geometry.grid;',
          '         var grid:Object=geometry.grid;\n         if(ApexCatalogAuthorityHold(grid)) {ApexCardForget();return;}'))
    edit('ApexCatalogSelection',
         ('         var started:int=flash.utils.getTimer();',
          '         if(ApexCatalogAuthorityHold(grid))return;\n         var started:int=flash.utils.getTimer();'),
         ('            kept.push(retained);',
          '            retained.grid=grid;\n            kept.push(retained);'),
         ('            if(!retain) {if(old.effect.parent!=null)',
          '            if(!retain && !ApexCatalogAuthorityEffectHeld(old)) {if(old.effect.parent!=null)'))
    edit('ApexCatalogClearEffects',
         ('            { if(row.effect.parent!=null)',
          '            { if(ApexCatalogAuthorityEffectHeld(row))continue;\n              if(row.effect.parent!=null)'))
    edit('ApexCardIncrementalApply',
         ('         var native:Object=',
          '         if(ApexCatalogAuthorityHold(grid))return Number(panel.mcPanelBackground.width);\n         var native:Object='))
    edit('ApexCatalogFrame',
         ('            if(apexCatalogDisplayFaults==null || !ApexCatalogDisplayFaulted(panel,grid)) {',
          '            if(!ApexCatalogAuthorityHold(grid) && (apexCatalogDisplayFaults==null || !ApexCatalogDisplayFaulted(panel,grid))) {'))
    reviewed=(ROOT/'Source/CASUi/catalog_authority_consumer_methods.as').read_text()
    for name in REPLACED:
        a,b=pool.method_extent(source,name);x,y=pool.method_extent(reviewed,name)
        if source[a:b].strip()!=reviewed[x:y].strip():raise ValueError('Reviewed Main consumer body differs: '+name)
    at=source.rfind('\n   }')
    if at<0:raise ValueError('Exact Main class boundary missing')
    return source[:at]+'\n'+(ROOT/'Source/CASUi/catalog_authority_methods.as').read_text()+source[at:]
