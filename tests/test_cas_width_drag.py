"""Real AS input handlers plus strict, UI-only native width receipts."""
import copy,math,shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'Source'),str(ROOT/'tests')]
from apex_core import cas_controls,cas_ui
from test_cas_panel_geometry import BASE,js
from test_cas_catalog_readback import source_method

def receipt(delta=200):
    before=344.8;maximum=900;scale=1;wanted=max(80,min(maximum,before+delta/scale))
    drag=dict(handler_invoked=True,appearance_written=False,delta_x=delta,menu_state=27,stage_width=2560,stage_height=1385,
        before_width=before,maximum_width=maximum,coordinate_scale=scale,requested_width=wanted,
        columns=12,card_scale=.35,gap_x=4,gap_y=4,handle=dict(x=2003.85,y=670.15,width=15,height=72),
        down=dict(x=2011.35,y=706.15),move=dict(x=2011.35+delta,y=706.15),up=dict(x=2011.35+delta,y=706.15))
    workspace=dict(preferences=dict(columns=12),card_preferences=dict(scale=.35,gap_x=4,gap_y=4),
        card_layout=dict(width=wanted),catalog_bounds=dict(stage_width=2560,stage_height=1385),
        panels=dict(catalog_controls=dict(width=dict(requested=wanted,dragging=False))))
    return dict(operation='catalog-width-drag',delta_x=delta),dict(menu_state=27,control=dict(operation='catalog-width-drag',drag=drag,workspace=workspace,appearance_written=False))

class WidthReceiverTests(unittest.TestCase):
    def test_exact_source_receiver_accepts_only_claimed_owner_nonce_uuid_and_drag(self):
        from test_cas_catalog_readback import HostReadbackTests
        helper=HostReadbackTests('test_pending_state_completes_without_full_inventory_or_producer_access');helper.setUp()
        self.addCleanup(cas_ui._RECORDS.clear);self.addCleanup(cas_ui._PEERS.clear)
        request,observed=receipt();packet=helper.packet();drag=observed['control']['drag'];drag['menu_state']=40
        packet['operation']='catalog-width-drag';packet['client']['catalog_workspace']=observed['control']['workspace']
        packet['client']['control']=observed['control'];helper.row['request']=request
        helper.row['wire']=helper.rid+'|12|catalog-width-drag|0|0|0|200'
        changes=[lambda p:p['client']['control'].pop('drag'),lambda p:p['client']['control'].update(extra=True),
            lambda p:p['client']['catalog_identity'].update(peer_nonce='c'*64),
            lambda p:p['client']['catalog_identity'].update(request_id='c'*32),
            lambda p:p['client']['catalog_identity']['after'].update(native_generation='92')]
        import json
        for change in changes:
            changed=copy.deepcopy(packet);change(changed)
            with self.subTest(packet=changed),self.assertRaises(ValueError):cas_ui.receive_socket(helper.token,helper.rid,json.dumps(changed),clock=lambda:1)
            self.assertEqual(helper.row['state'],'pending')
        cas_ui.receive_socket(helper.token,helper.rid,json.dumps(packet),clock=lambda:1)
        self.assertEqual(helper.row['state'],'completed');self.assertEqual(helper.row['result']['cas_request_id'],helper.rid)

    def test_signed_delta_wire_is_bounded_and_never_arbitrary_coordinates(self):
        for delta in (-2048,-200,-.05,.05,200,2048):
            request=dict(operation='catalog-width-drag',delta_x=delta)
            cas_ui.envelope('12',request)
            self.assertEqual(cas_controls.wire(request,None),(0,0,0,format(delta,'.6f').rstrip('0').rstrip('.')))
        for bad in (0,.04999,2048.1,-2048.1,True,None,float('nan'),float('inf')):
            with self.subTest(bad=bad),self.assertRaises(ValueError):cas_ui.envelope('12',dict(operation='catalog-width-drag',delta_x=bad))
        with self.assertRaises(ValueError):cas_ui.envelope('12',dict(operation='catalog-width-drag',delta_x=200,x=55))
        self.assertIn('catalog-width-drag',cas_ui._CATALOG_READBACK_OPERATIONS)

    def test_expand_shrink_and_safe_limit_preserve_independent_controls(self):
        for delta in (200,-200,500):
            request,client=receipt(delta);cas_controls.validate(client,request)
        request,client=receipt(500);d=client['control']['drag'];d.update(maximum_width=500,requested_width=500)
        client['control']['workspace']['card_layout']['width']=500
        client['control']['workspace']['panels']['catalog_controls']['width']['requested']=500
        cas_controls.validate(client,request)

    def test_no_optimistic_ack_for_wrong_handlers_geometry_fences_or_values(self):
        request,base=receipt()
        changes=[lambda c:c['control'].update(appearance_written=True),lambda c:c['control']['drag'].update(handler_invoked=False),
            lambda c:c['control']['drag'].update(delta_x=199),lambda c:c['control']['drag'].update(menu_state=28),
            lambda c:c['control']['drag'].update(coordinate_scale=0),lambda c:c['control']['drag']['down'].update(x=2000),
            lambda c:c['control']['drag']['move'].update(x=100),lambda c:c['control']['drag']['up'].update(y=700),
            lambda c:c['control']['drag']['handle'].update(width=-1),lambda c:c['control']['workspace']['preferences'].update(columns=13),
            lambda c:c['control']['workspace']['card_preferences'].update(scale=.36),lambda c:c['control']['workspace']['card_preferences'].update(gap_x=5),
            lambda c:c['control']['workspace']['panels']['catalog_controls']['width'].update(dragging=True),
            lambda c:c['control']['workspace']['card_layout'].update(width=344.8),lambda c:c['control']['workspace']['catalog_bounds'].update(stage_width=2559)]
        for change in changes:
            client=copy.deepcopy(base);change(client)
            with self.subTest(client=client),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)
        for field in ('card_preferences','preferences','card_layout','catalog_bounds','panels'):
            for value in (None,False,'wrong'):
                client=copy.deepcopy(base);client['control']['workspace'][field]=value
                with self.subTest(field=field,value=value),self.assertRaises(cas_controls.PostconditionMismatch):cas_controls.validate(client,request)

@unittest.skipUnless(shutil.which('node'),'Node required for actual AS bodies')
class WidthHandlerTests(unittest.TestCase):
    def execute(self,code):
        methods=''.join(js(n,a,'catalog_columns_methods.as') for n,a in [('ApexColumnsWidthDown','event'),('ApexColumnsWidthMove','event'),('ApexColumnsWidthUp','event=null'),('ApexColumnsResizeEnd','value=null')])
        execute=source_method('ApexControlExecute','operation,state,category,index,value,reply,context',stop='if(operation=="catalog-layout-trace")')
        result=source_method('ApexControlResult','operation,state,category,index,value,context,client',stop='if(operation=="catalog-layout-trace")')
        r=subprocess.run(['node'],input=BASE+MOCK+methods+execute+result+code,capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_actual_dispatch_expands_then_shrinks_and_releases_same_native_handlers(self):
        self.execute('''
let c={catalog_before:{}};ApexControlExecute('catalog-width-drag',0,0,0,'200',{},c);
assert.deepEqual(events,['down','move','up']);assert.equal(c.width_drag.requested_width,500);
assert.equal(c.width_drag.handler_invoked,true);assert.equal(apexColumns.resize,null);
assert.equal(apexCatalogPrefs.columns,12);assert.equal(apexCardPrefs.scale,1);assert.equal(apexCardPrefs.gap_x,4);
assert.equal(ApexControlResult('catalog-width-drag',0,0,0,'200',c,{catalog_workspace:{}}).drag,c.width_drag);
events.length=0;c={catalog_before:{}};ApexControlExecute('catalog-width-drag',0,0,0,'-200',{},c);
assert.deepEqual(events,['down','move','up']);assert.equal(c.width_drag.requested_width,100);
assert.equal(apexColumns.resize,null);assert.equal(apexCatalogPrefs.columns,12);
''')

    def test_bad_delta_missing_scope_hidden_detached_and_viewport_refuse_before_input(self):
        self.execute('''
for(const value of ['NaN','0','0.01','2049','1e2'])assert.throws(()=>ApexControlExecute('catalog-width-drag',0,0,0,value,{}, {catalog_before:{}}));
assert.throws(()=>ApexControlExecute('catalog-width-drag',0,0,0,'200',{}, {}));
const original=handle.parent;handle.parent=null;assert.throws(()=>ApexControlExecute('catalog-width-drag',0,0,0,'200',{}, {catalog_before:{}}));handle.parent=original;
handle.visible=false;assert.throws(()=>ApexControlExecute('catalog-width-drag',0,0,0,'200',{}, {catalog_before:{}}));handle.visible=true;
assert.throws(()=>ApexControlExecute('catalog-width-drag',0,0,0,'2048',{}, {catalog_before:{}}));
assert.deepEqual(events,[]);assert.equal(apexColumns.preferred_width,0);
''')

    def test_detached_handle_grid_and_viewport_after_dispatch_cannot_ack(self):
        self.execute('''
let c={catalog_before:{}};ApexControlExecute('catalog-width-drag',0,0,0,'200',{},c);
handle.visible=false;assert.throws(()=>ApexControlResult('catalog-width-drag',0,0,0,'200',c,{catalog_workspace:{}}));handle.visible=true;
const grid=mCurrentPanel.mcTileList.mGridLayout;mCurrentPanel.mcTileList.mGridLayout={};
assert.throws(()=>ApexControlResult('catalog-width-drag',0,0,0,'200',c,{catalog_workspace:{}}));mCurrentPanel.mcTileList.mGridLayout=grid;
stage.stageWidth--;assert.throws(()=>ApexControlResult('catalog-width-drag',0,0,0,'200',c,{catalog_workspace:{}}));
assert.deepEqual(events,['down','move','up']);
''')

MOCK=r'''
var mCurrState=27;var apexCardGeometry={panel:mCurrentPanel,grid:mCurrentPanel.mcTileList.mGridLayout};
const events=[];const listeners={};
stage.parent=null;stage.visible=true;stage.localToGlobal=p=>p;stage.globalToLocal=p=>p;
stage.addEventListener=(type,fn)=>{listeners[type]=fn;};stage.removeEventListener=(type,fn)=>{if(listeners[type]===fn)delete listeners[type];};
stage.dispatchEvent=e=>{events.push(e.type);e.currentTarget=stage;e.stageX=e.localX;e.stageY=e.localY;const fn=listeners[e.type];if(fn)fn(e);};
for(const p of [mcClothingPanel,mcBodyModPanel,mcFaceModPanel,mcGenericCatalogPanel,mcFeaturedFaceLookPanel,mcSkinColorPanel])p.parent=stage;
Rectangle.prototype.__defineGetter__('right',function(){return this.x+this.width;});Rectangle.prototype.__defineGetter__('bottom',function(){return this.y+this.height;});
class ActualMouse extends Event {constructor(type,bubbles=false,cancelable=false,x=0,y=0,related=null,ctrl=false,alt=false,shift=false,down=false){super(type);this.localX=x;this.localY=y;this.buttonDown=down;}}
Object.assign(ActualMouse,MouseEvent);flash.events.MouseEvent=ActualMouse;
function ApexColumnsTakeover(){return mCurrentPanel!=null&&mCurrentPanel.visible;}
function ApexCatalogWidthEnvelope(){return {available:700,scale:1};}function ApexCatalogWidthMode(){return false;}
const handle=new Sprite('width');handle.parent=mCurrentPanel;handle.visible=true;handle.mouseEnabled=true;
handle.x=310;handle.y=300;handle.getBounds=()=>new Rectangle(1207,340,15,72);
handle.dispatchEvent=e=>{events.push(e.type);e.currentTarget=handle;const p=handle.localToGlobal(new Point(e.localX,e.localY));e.stageX=p.x;e.stageY=p.y;ApexColumnsWidthDown(e);};
apexColumns.width_handle=handle;
'''

@unittest.skipUnless(shutil.which('node'),'Node required for actual AS bodies')
class ReleasedSliderSourceTests(unittest.TestCase):
    def test_released_body_size_thumb_uses_the_real_post_redraw_transform(self):
        source=js('ApexCatalogSliderCommand','value','catalog_workspace_methods.as')
        setup=r'''
const assert=require('node:assert/strict');const uint=v=>v>>>0;
var apexCatalogDrag='',apexCatalogPrefs={columns:12,color:0x00c9eb},apexCardPrefs={scale:.2};
var thumb={x:0,parent:null};var track={getChildByName:n=>n==='thumb'?thumb:null};
var apexCatalogUi={getChildByName:n=>track};
var flash={display:{DisplayObjectContainer:Object,DisplayObject:Object}};
function ApexCatalogView(){}function ApexCatalogPersist(){}
function ApexCatalogSlide(event,fraction){apexCardPrefs.scale=.2+fraction*1.4;}
// Reproduce the actual captured Body drawer scalar x=30 after redraw. The
// command must set the new actual display object's transform, not fake ACK.
function ApexCatalogDraw(){thumb={x:30,parent:track};}
'''
        code=r'''
ApexCatalogSliderCommand('card_scale,0.107142857');
assert.ok(Math.abs(apexCardPrefs.scale-.3499999998)<1e-12);
assert.ok(Math.abs(thumb.x-32.1428571)<1e-9);assert.equal(apexCatalogDrag,'');
for(const n of ['columns','red','green','blue']){
 ApexCatalogSliderCommand(n+',0.34');
 const expected=n==='columns'?(12-2)/30:((apexCatalogPrefs.color>>({red:16,green:8,blue:0}[n]))&255)/255;
 assert.ok(Math.abs(thumb.x/300-expected)<1e-12);
}
'''
        result=subprocess.run(['node'],input=setup+source+code,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
