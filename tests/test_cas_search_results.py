"""Run the actual AS search path against native-shaped feeds and worker pages.

The harness never opens CAS or reads installed content. It checks the cards and
selections that a recycling grid consumes, not just the echoed input text.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/catalog_search_methods.as'


def javascript_function(name, parameters=''):
    source = SOURCE.read_text(encoding='utf-8')
    part = source.split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private function ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'for each\s*\(var\s+(\w+)\s*:\s*[\w.]+\s+in\s+([^\n)]+)\)',
                  r'for(var \1 of \2)', body)
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'catch\((\w+):[\w.]+\)', r'catch(\1)', body)
    body = re.sub(r'([\w.]+) is Array', r'Array.isArray(\1)', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


METHODS = {
    'ApexSearchInitialize': '', 'ApexSearchContext': '', 'ApexSearchRestore': '',
    'ApexSearchDispose': '', 'ApexSearchReset': 'context', 'ApexSearchSource': 'value',
    'ApexSearchAdopt': 'panel', 'ApexSearchSelection': 'event', 'ApexSearchText': 'text',
    'ApexSearchLabels': '', 'ApexSearchSuggestions': '', 'ApexSearchAttach': 'panel',
    'ApexSearchQuery': '', 'ApexSearchOrder': 'left,right', 'ApexSearchPublish': '',
    'ApexSearchFrame': '', 'ApexSearchNativeKey': 'raw,exact,bodyType', 'ApexSearchStatus': '',
    'ApexSearchChanged': 'event', 'ApexSearchClear': 'event', 'ApexSearchKey': 'event',
    'ApexSearchFocus': 'event', 'ApexSearchChooseFolder': 'event',
}


HARNESS = r'''
const assert=require('node:assert/strict');
var now=1000;
function int(value){return Number(value)|0;}function uint(value){return Number(value)>>>0;}
class Sprite{
    constructor(){Object.assign(this,{x:0,y:0,width:0,height:0,parent:null,visible:true,children:[]});
        this.graphics={clear(){},lineStyle(){},beginFill(){},drawRoundRect(){},drawRect(){},endFill(){}};}
    addChild(child){this.children.push(child);child.parent=this;return child;}
    removeChild(child){this.children.splice(this.children.indexOf(child),1);child.parent=null;}
    addEventListener(){}
}
class TextField extends Sprite{constructor(){super();this.text='';}}
class ScrollerEvent{constructor(type){this.type=type;}}ScrollerEvent.SCROLL='scroll';
var flash={utils:{getTimer(){return now;}},display:{Sprite},text:{TextField,TextFieldType:{INPUT:'input'},
    TextFormat:class{constructor(font,size,color){Object.assign(this,{font,size,color});}}},
    events:{Event:{CHANGE:'change'},KeyboardEvent:{KEY_DOWN:'keyDown'},FocusEvent:{FOCUS_IN:'focusIn',FOCUS_OUT:'focusOut'},MouseEvent:{CLICK:'click',MOUSE_DOWN:'mouseDown'}}};
var DataFeedEvent={UPDATE:'feedUpdate'},olympus={events:{DataFeedEvent,ScrollerEvent}};
function ApexFormsText(parent,text,x,y,width,size,color){const field=new TextField();Object.assign(field,{text,x,y,width,size,color});return parent.addChild(field);}
var apexSearch,apexBoundSim='12',apexFormsSelectedId='native/2',apexFormsNativeGeneration='42',mCurrState=123;
var mCurrSimInfo={simId:'12'},mCurrentPanel=null,apexEquippedActive=false,apexPendingFields=null,apexReceiving=false;
var stage={focus:null},apexNativeChannel='opaque-channel',apexCompanion=null;
var apexFormsNativeState='bound',apexFormsDesiredId='',apexFormsNativeIntent=null,apexMoleculeIntent=null;
var apexKeyQueue=[{key:13}],apexKeyIntent=13,apexKeyIndex=2,apexKeyItem={},apexKeyBounds='old';
var multiple=false,MenuState={SupportsMultipleSelections(){return multiple;}};
var submissions=[],nativeCalls=[],nativeItems={},families={},allow=()=>true;
var CommunicationManager={CallUIService(){return false;},CallGameService(name,value){
    nativeCalls.push({name,value});
    if(name==='GetCatalogItem')return nativeItems[value]||null;
    if(name==='GetCatalogColorFamilies')return families[value.base]||null;
    throw Error('Unexpected native service: '+name);
}};
function RegisterServiceHandler(){return true;}function UnregisterServiceHandler(){}
function ApexCompanionAllows(product){return allow(product);}
function ApexCompanionRecentOrder(a,b){return 0;}
function ApexEncode(value){return JSON.stringify(value);}
function ApexEquippedDecimal(value){return BigInt(value).toString();}
function resource(id,body=3){return {id:String(id),body};}
function wire(rows,total,offset,next,ticket,sha='a'.repeat(64)){
    return ['SEARCHPAGE',ticket,sha,total,offset,next===null?'-':next,
        rows.map(r=>'034AEECB:00000000:'+BigInt(r.id).toString(16).padStart(16,'0')+','+(r.body===null?'-':r.body)).join(';')].join('|');
}
var pages=new Map(),tickets=new Map(),ticketNext=1,waitTickets=new Set(),forcedWire=null;
function setPages(text,parts){pages.set(text,parts);}
function ApexNativeExchange(wireText){
    const fields=wireText.split('|');assert.equal(fields[1],apexNativeChannel);
    if(fields[0]==='SEARCH'){
        const query=JSON.parse(fields.slice(2).join('|'));submissions.push(query);
        const ticket=String(ticketNext++);tickets.set(ticket,{query});return 'SEARCH|'+ticket;
    }
    assert.equal(fields[0],'SEARCHPAGE');const ticket=fields[2];const record=tickets.get(ticket);
    if(forcedWire!==null)return forcedWire(ticket,record.query);
    if(waitTickets.has(ticket))return 'SEARCHWAIT|'+ticket;
    const parts=pages.get(record.query.text);assert.ok(parts,'No worker fixture for '+record.query.text);
    const page=parts.find(p=>p.offset===record.query.offset);assert.ok(page);
    return wire(page.rows,page.total,page.offset,page.next,ticket);
}
class Feed{
    constructor(rows,selected=[]){this.items=rows.slice();this.selected=new Set(selected);this.handlers=new Set();this.removes=0;this.adds=0;}
    get length(){return this.items.length;}
    RequestItemAt(index){return this.items[index]||null;}
    GetSelectedIndices(){return [...this.selected];}
    RemoveAllItems(){this.items=[];this.selected.clear();this.removes++;}
    AddItemsFromIterable(rows){this.items.push(...rows);this.adds++;}
    UpdateSelections(){throw Error('Search re-queried native variants');}
    addEventListener(type,handler){assert.equal(type,'feedUpdate');this.handlers.add(handler);}
    removeEventListener(type,handler){assert.equal(type,'feedUpdate');this.handlers.delete(handler);}
    SetSelectionStateMultiple(indices,state){for(const index of indices)this.selection(index,state);}
    selection(index,state){
        assert.ok(index>=0&&index<this.items.length);
        if(state)this.selected.add(index);else this.selected.delete(index);
        const event={currentTarget:this,mDataArray:[this.items[index]],mUserDataArray:[{isSelected:state}]};
        for(const handler of this.handlers)handler(event);
    }
}
function product(id,body=3,modded=false){const variation={data_id:(BigInt(id)+1000n).toString(),image:'native-swatch'};
    return {data_id:String(id),body_type:body,groupId:body,is_modded:modded,variation,
        GetVariation(){return variation;}};}
function makePanel(feed){
    const panel=new Sprite();panel.mcFilterPane=panel.addChild(new Sprite());
    panel.mcFilterPane.mcFilterBubble=panel.mcFilterPane.addChild(new Sprite());
    Object.assign(panel.mcFilterPane.mcFilterBubble,{y:150,mcBackground:{width:560}});
    panel.mcTileList=panel.addChild(new Sprite());Object.assign(panel.mcTileList,{y:210,height:1000});
    panel.mcTileList.mGridLayout={GetDataFeed(){return feed;}};panel.scrolls=0;panel.popup=null;
    panel.mcTileList.Controller={dispatchEvent(event){assert.equal(event.type,'scroll');panel.scrolls++;panel.popup=null;}};
    panel.txtNoResults={visible:feed.length===0,y:210};panel.mcColorSwatchPanel=panel.addChild(new Sprite());panel.mcColorSwatchPanel.y=176;
    return panel;
}
function boot(rows,selected=[]){const feed=new Feed(rows,selected);const panel=makePanel(feed);mCurrentPanel=panel;
    ApexSearchInitialize();ApexSearchSource({rows,feed,state:mCurrState,selected});ApexSearchFrame();
    assert.equal(apexSearch.rows.length,rows.length);return {feed,panel};}
function frame(ms=0){now+=ms;ApexSearchFrame();}
function finish(limit=100){for(let i=0;i<limit&&apexSearch.pending;i++)frame(60);assert.equal(apexSearch.pending,false);}
function ids(feed){return feed.items.map(p=>p.data_id);}
const A=product('9007199254740993',3,true),B=product('9007199254740995',3,false),C=product('9007199254740997',3,true),D=product('9007199254740999',3,false);
'''


@unittest.skipUnless(shutil.which('node'), 'Node is required for the actual AS search harness')
class SearchResultTests(unittest.TestCase):
    def run_case(self, case):
        methods = ''.join(javascript_function(name, parameters) for name, parameters in METHODS.items())
        result = subprocess.run(['node', '-'], input=HARNESS + methods + case, capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pages_filter_visible_native_cards_and_append_without_rebuilding_them(self):
        self.run_case(r'''
const {feed,panel}=boot([A,B,C,D],[1]);const originalVariant=B.GetVariation();panel.popup={index:1};
setPages('hair',[{offset:0,total:3,next:2,rows:[resource(A.data_id),resource(C.data_id)]},
    {offset:2,total:3,next:null,rows:[resource(D.data_id)]}]);
ApexSearchText('hair');assert.deepEqual(ids(feed),[A.data_id,B.data_id,C.data_id,D.data_id]);
frame();assert.deepEqual(ids(feed),[]);assert.equal(panel.popup,null);assert.equal(submissions.length,0);
frame(181);frame(60);frame();assert.deepEqual(ids(feed),[A.data_id,C.data_id]);assert.equal(apexSearch.pending,true);
assert.strictEqual(feed.RequestItemAt(0),A);assert.equal(feed.removes,1);
finish();assert.deepEqual(ids(feed),[A.data_id,C.data_id,D.data_id]);assert.equal(feed.removes,1);
assert.equal(apexSearch.appends,2);assert.equal(apexSearch.shown,3);assert.equal(submissions[0].body_type,3);
assert.equal(nativeCalls.length,0);assert.equal(apexKeyIntent,0);assert.equal(apexKeyIndex,-1);
ApexSearchText('');frame();assert.deepEqual(feed.items,[A,B,C,D]);assert.deepEqual(feed.GetSelectedIndices(),[1]);
assert.strictEqual(B.GetVariation(),originalVariant);assert.equal(apexSearch.ready,true);assert.equal(apexSearch.message.visible,false);
''')

    def test_native_selected_item_changes_and_removals_survive_clear(self):
        self.run_case(r'''
const {feed}=boot([A,B,C],[0]);setPages('match',[{offset:0,total:1,next:null,rows:[resource(B.data_id)]}]);
ApexSearchText('match');finish();assert.deepEqual(ids(feed),[B.data_id]);
feed.selection(0,true);ApexSearchText('');frame();assert.deepEqual(feed.GetSelectedIndices(),[1]);
ApexSearchText('match');finish();feed.selection(0,false);ApexSearchText('');frame();
assert.deepEqual(feed.GetSelectedIndices(),[]);assert.strictEqual(feed.RequestItemAt(0),A);
''')

    def test_multiple_selection_groups_keep_hidden_other_groups_without_stale_same_group(self):
        self.run_case(r'''
multiple=true;const other=product('9007199254741223',29);const {feed}=boot([A,B,other],[0,2]);
setPages('match',[{offset:0,total:1,next:null,rows:[resource(B.data_id)]}]);
ApexSearchText('match');finish();feed.selection(0,true);ApexSearchText('');frame();
assert.deepEqual(feed.GetSelectedIndices(),[1,2]);assert.equal(apexSearch.body_type,null);
''')

    def test_exact_native_swatch_family_matches_the_eligible_base_and_caches_duplicate_rows(self):
        self.run_case(r'''
const {feed}=boot([A,B]);const swatch='18446744073709551601';
nativeItems[swatch]={body_type:3,data_id:swatch,variation_id:null};families[swatch]={mItems:[{dataID:A.data_id},{dataID:swatch}]};
setPages('swatch',[{offset:0,total:2,next:null,rows:[resource(swatch),resource(swatch)]}]);
ApexSearchText('swatch');finish();assert.deepEqual(ids(feed),[A.data_id]);assert.strictEqual(feed.RequestItemAt(0),A);
assert.equal(nativeCalls.filter(c=>c.name==='GetCatalogItem').length,1);
assert.equal(nativeCalls.filter(c=>c.name==='GetCatalogColorFamilies').length,1);
ApexSearchText('swatch');finish();assert.equal(nativeCalls.length,2);
''')

    def test_ambiguous_or_wrong_body_native_resources_cannot_make_cards(self):
        self.run_case(r'''
const {feed}=boot([A,B]);nativeItems['31']={body_type:3,data_id:'31'};
families['31']={mItems:[{dataID:A.data_id},{dataID:B.data_id},{dataID:'31'}]};
nativeItems['32']={body_type:29,data_id:'32'};
setPages('bad',[{offset:0,total:2,next:null,rows:[resource('31'),resource('32')]}]);
ApexSearchText('bad');finish();assert.equal(feed.length,0);assert.equal(apexSearch.ready,true);
assert.match(apexSearch.message.text,/No matches in this category/);assert.equal(apexSearch.shown,0);
''')

    def test_loading_empty_and_error_states_are_visible_and_clear_restores_catalog(self):
        self.run_case(r'''
const {feed,panel}=boot([A,B]);setPages('none',[{offset:0,total:0,next:null,rows:[]}]);
ApexSearchText('none');frame();assert.match(apexSearch.message.text,/Searching/);assert.equal(apexSearch.message.visible,true);
finish();assert.equal(feed.length,0);assert.match(apexSearch.message.text,/No matches/);assert.equal(panel.txtNoResults.visible,false);
ApexSearchText('broken');forcedWire=()=>'SEARCHERROR|Close the quoted search value';finish();
assert.equal(apexSearch.ready,false);assert.match(apexSearch.message.text,/Close the quoted search value/);
assert.match(apexSearch.message.text,/Clear search/);assert.equal(feed.length,0);
ApexSearchText('');frame();assert.deepEqual(feed.items,[A,B]);assert.equal(apexSearch.message.visible,false);
assert.equal(panel.txtNoResults.visible,false);assert.equal(apexSearch.error,'');
ApexSearchText('   ');frame();assert.deepEqual(feed.items,[A,B]);assert.equal(apexSearch.text,'');
''')

    def test_new_query_and_new_owner_cannot_publish_an_old_worker_page(self):
        self.run_case(r'''
const {feed,panel}=boot([A,B]);setPages('old',[{offset:0,total:1,next:null,rows:[resource(A.data_id)]}]);
setPages('new',[{offset:0,total:1,next:null,rows:[resource(B.data_id)]}]);
ApexSearchText('old');frame(181);const oldTicket=apexSearch.ticket;waitTickets.add(oldTicket);
ApexSearchText('new');finish();assert.deepEqual(ids(feed),[B.data_id]);assert.notEqual(apexSearch.ticket,oldTicket);
ApexSearchText('old');frame(181);apexFormsSelectedId='native/4';frame(60);
assert.equal(apexSearch.pending,false);assert.equal(apexSearch.ready,false);assert.equal(apexSearch.ticket,'');
assert.deepEqual(ids(feed),[]);assert.match(apexSearch.message.text,/Waiting for this category/);
const fresh=product('9007199254741881');const replacement=new Feed([fresh]);const next=makePanel(replacement);mCurrentPanel=next;
ApexSearchSource({rows:[fresh],feed:replacement,state:mCurrState,selected:[]});frame();
assert.equal(feed.handlers.size,0);assert.equal(replacement.handlers.size,1);
assert.equal(apexSearch.rows[0],fresh);assert.equal(apexSearch.resource_count,0);
''')

    def test_worker_query_preserves_fuzzy_package_author_folder_and_mixed_ea_cc_matches(self):
        self.run_case(r'''
const {feed}=boot([A,B]);const text='lipstik author:"Magic Hand" folder:"Artist Sets" package:hair*';
setPages(text,[{offset:0,total:2,next:null,rows:[resource(A.data_id),resource(B.data_id)]}]);
ApexSearchText(text);finish();assert.equal(submissions[0].text,text);assert.equal(submissions[0].fuzzy,true);
assert.equal(submissions[0].origin,null);assert.equal(submissions[0].body_type,3);assert.deepEqual(feed.items,[A,B]);
allow=p=>p===A;ApexSearchPublish();assert.deepEqual(feed.items,[A]);ApexSearchText('');frame();assert.deepEqual(feed.items,[A]);
const other=product('9007199254741771',29);ApexSearchSource({rows:[A,other],feed,state:mCurrState,selected:[]});
feed.items=[A,other];frame();assert.equal(apexSearch.body_type,null);assert.equal(ApexSearchQuery().body_type,null);
''')

    def test_mismatched_ticket_and_detached_feed_are_refused_before_publishing(self):
        self.run_case(r'''
const {feed,panel}=boot([A,B]);ApexSearchText('wrong');
forcedWire=()=>wire([resource(A.data_id)],1,0,null,'999');finish();
assert.equal(feed.length,0);assert.match(apexSearch.error,/does not match/);ApexSearchText('');frame();
const replacement=new Feed([C]);panel.mcTileList.mGridLayout.GetDataFeed=()=>replacement;
setPages('late',[{offset:0,total:1,next:null,rows:[resource(A.data_id)]}]);ApexSearchText('late');frame(181);
assert.deepEqual(replacement.items,[C]);assert.equal(apexSearch.pending,false);assert.deepEqual(feed.items,[A,B]);
''')

    def test_mixed_categories_skip_unrelated_body_reads_and_keep_both_eligible_types(self):
        self.run_case(r'''
const other=product('9007199254741553',29);const {feed}=boot([A,other]);
setPages('mixed',[{offset:0,total:3,next:null,rows:[resource('811',42),resource(A.data_id),resource(other.data_id,29)]}]);
ApexSearchText('mixed');finish();assert.equal(submissions[0].body_type,null);assert.deepEqual(feed.items,[A,other]);
assert.equal(nativeCalls.length,0);assert.equal(apexSearch.shown,2);
''')

    def test_nonresponsive_worker_has_bounded_wait_and_enter_retries_the_current_query(self):
        self.run_case(r'''
const {feed}=boot([A]);setPages('wait',[{offset:0,total:1,next:null,rows:[resource(A.data_id)]}]);
ApexSearchText('wait');frame(181);waitTickets.add(apexSearch.ticket);finish(305);
assert.equal(feed.length,0);assert.match(apexSearch.message.text,/did not respond/);assert.equal(apexSearch.ready,false);
const event={keyCode:13,preventDefault(){},stopImmediatePropagation(){}};ApexSearchKey(event);finish();
assert.deepEqual(feed.items,[A]);assert.equal(apexSearch.ready,true);assert.equal(apexSearch.error,'');
''')

    def test_empty_native_category_and_disposal_restore_native_label_palette_and_listeners(self):
        self.run_case(r'''
const {feed,panel}=boot([]);assert.equal(panel.txtNoResults.visible,true);assert.equal(panel.txtNoResults.y,262);
setPages('none',[{offset:0,total:0,next:null,rows:[]}]);ApexSearchText('none');finish();
assert.equal(panel.txtNoResults.visible,false);assert.equal(apexSearch.message.visible,true);
ApexSearchText('');frame();assert.equal(panel.txtNoResults.visible,true);assert.equal(panel.txtNoResults.y,262);
const message=apexSearch.message;ApexSearchDispose();assert.equal(apexSearch,null);assert.equal(feed.handlers.size,0);
assert.equal(message.parent,null);assert.equal(panel.txtNoResults.y,210);assert.equal(panel.txtNoResults.visible,true);
assert.equal(panel.mcColorSwatchPanel.y,176);assert.equal(panel.mcTileList.y,210);assert.equal(feed.removes,0);
''')


if __name__ == '__main__':
    unittest.main()
