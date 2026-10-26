"""New Main-only workflow continuation after exact frozen Scheduler."""
from pathlib import Path
import hashlib
import cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexCatalogGridPrepare', 'ApexCatalogGridLeaseCurrent', 'ApexCatalogGridFrame', 'ApexCatalogGridInput', 'ApexCatalogKeyboardPublicationReady', 'ApexReadback')
ADDED=('ApexCatalogKeyboardFailureDiagnostic',)
BEFORE={'ApexCatalogGridPrepare': 'f3103f7fdcadbc79637287c4d3b7fcc2eab82c14821e86f460099d38d66fe475', 'ApexCatalogGridLeaseCurrent': '08dab3818e0e76329496b95918e5093384245974655b99d26952cf04f0e88fab', 'ApexCatalogGridFrame': '25ed027fd1096a766a3e56edf6f7d70f95e30bf08bd238736d5859b629c382aa', 'ApexCatalogGridInput': '0c150f82b2d452e6721acba511c4305070e1ee604f68b224ed2f27567db110c8', 'ApexCatalogKeyboardPublicationReady': '3ec7480849dfc8334f2cbaa14fe46088de5417431152a46cb114bffa520ec792', 'ApexReadback': 'cb7031b197b32d31aeb70ce2b58358e544d29e8060dd34e46bf5193bd1f90558'}
def fragment():return (ROOT/'Source/CASUi/catalog_workflow_methods.as').read_text(encoding='utf-8')
def inject_main(source):
    owned=fragment()
    for name in REPLACED:
        start,end=pool.method_extent(source,name)
        if hashlib.sha256(source[start:end].encode()).hexdigest()!=BEFORE[name]:raise ValueError('Exact Scheduler source predecessor differs: '+name)
        left,right=pool.method_extent(owned,name);source=source[:start]+owned[left:right]+source[end:]
    end=source.rfind('\n   }')
    if end<0:raise ValueError('Main class boundary absent')
    for name in ADDED:
        if ('function '+name+'(')in source:raise ValueError('Workflow helper already exists')
        left,right=pool.method_extent(owned,name);source=source[:end]+'\n'+owned[left:right]+source[end:];end=source.rfind('\n   }')
    return source
