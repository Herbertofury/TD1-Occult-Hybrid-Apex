"""Exact private one-shot pre-queue rejection witness and ACK continuation."""
from pathlib import Path
import cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexReadback','ApexCatalogKeyDown','ApexCatalogKeyboardFrame','ApexCatalogKeyboardCommand')
ADDED=('ApexCatalogUnconsumedMark','ApexCatalogUnconsumedBound','ApexCatalogUnconsumedCurrent','ApexCatalogUnconsumedReply')

def inject_main(source):
    source=pool.edit_method(source,'ApexCatalogKeyDown',[
      ('               apexKeyQueue=[];apexKeyIntent=0;\n               if(apexKeyFocus!=null)apexKeyFocus.visible=false;',
       '               apexKeyQueue=[];apexKeyIntent=0;\n               ApexCatalogUnconsumedMark(int(event.keyCode),panel,grid,lease,"shared-keyboard-handler-before-queue");\n               if(apexKeyFocus!=null)apexKeyFocus.visible=false;')])
    source=pool.edit_method(source,'ApexCatalogKeyboardFrame',[
      ('         if(apexKeyIntent!=0) {',
       '         if(apexKeyIntent!=0) {\n            if(apexPendingContext!=null)apexPendingContext.keyboard_unconsumed=null;')])
    source=pool.edit_method(source,'ApexCatalogKeyboardCommand',[
      ('            throw new Error("Wait for the catalog before using a key");',
       '            {ApexCatalogUnconsumedMark(int(codes[value]),panel,grid,lease,"semantic-navigation-before-queue");\n             throw new Error("Wait for the catalog before using a key");}')])
    source=pool.edit_method(source,'ApexReadback',[
      ('            if(keyboardNavigation && keyboardPublication==null)\n               throw new Error(',
       '            if(keyboardNavigation && keyboardPublication==null) {\n               if(ApexCatalogUnconsumedReply(fields,context,reply)) {ApexComplete();return;}\n               throw new Error('),
      ('"Navigation input lacks its retained consumed publication intent");\n            if(operation=="physique"',
       '"Navigation input lacks its retained consumed publication intent");\n            }\n            if(operation=="physique"')])
    reviewed=(ROOT/'Source/CASUi/catalog_unconsumed_consumer_methods.as').read_text(encoding='utf-8')
    for name in REPLACED:
        a,b=pool.method_extent(source,name);x,y=pool.method_extent(reviewed,name)
        if source[a:b].strip()!=reviewed[x:y].strip():raise ValueError('Reviewed pre-queue consumer body differs: '+name)
    at=source.rfind('\n   }')
    if at<0:raise ValueError('Exact Main class boundary required')
    return source[:at]+'\n'+(ROOT/'Source/CASUi/catalog_unconsumed_methods.as').read_text(encoding='utf-8')+source[at:]
