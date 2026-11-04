"""Exact Main-only successor; no provider, native body or field mutation."""
from pathlib import Path
import hashlib
import cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexCardRepairControls', 'ApexCardApply', 'ApexCatalogPanelKind', 'ApexCatalogGridInitialize', 'ApexCatalogGridPrepare', 'ApexCatalogGridLeaseCurrent', 'ApexCatalogGridFrame', 'ApexCatalogGridStatus')
ADDED=('ApexCatalogPanelVisible', 'ApexCatalogGridRetireInactive')
BEFORE={'ApexCardRepairControls': '9a4f1f8c446b22a705ffd0f36160232e83609833f89a6b4558bf460892a7d1ad', 'ApexCardApply': '082c58f7a40d4e1adf67f0c756df96cf179d0b4fc68e6730677cc227004eb7dc', 'ApexCatalogPanelKind': 'eb66c19f72b81d6e693cd7da719e264fb7a4059d62ab2f18acf027e748c3b882', 'ApexCatalogGridInitialize': '32aaf4bc6f98105517dadf581c4a03f034a871fe22c470addbe41762147a159e', 'ApexCatalogGridPrepare': 'e94ae9e589f0b9df283945120a57f1fa29ae78e41c43037c824e09f76fe67241', 'ApexCatalogGridLeaseCurrent': '62948c6300671735bd227c27b399244a44f7b075e0af77383d8ac21c0bf8dac9', 'ApexCatalogGridFrame': '7db3a1f0c717047d350fa9c8ed900ee7f397b35aebadd43fbc6757df970c3b5c', 'ApexCatalogGridStatus': '07e822c45b5428333d97a78dd16a8577e4b5bf67f13487682fafd984c871fa65'}

def fragment():return (ROOT/'Source/CASUi/catalog_scheduling_methods.as').read_text(encoding='utf-8')
def inject_main(source):
    owned=fragment()
    for name in REPLACED:
        start,end=pool.method_extent(source,name)
        if hashlib.sha256(source[start:end].encode()).hexdigest()!=BEFORE[name]:raise ValueError('Exact scheduling source predecessor differs: '+name)
        left,right=pool.method_extent(owned,name)
        source=source[:start]+owned[left:right]+source[end:]
    end=source.rfind('\n   }')
    if end<0:raise ValueError('Main class boundary absent')
    for name in ADDED:
        if ('function '+name+'(')in source:raise ValueError('Scheduling helper already exists')
        left,right=pool.method_extent(owned,name)
        source=source[:end]+'\n'+owned[left:right]+source[end:];end=source.rfind('\n   }')
    return source
