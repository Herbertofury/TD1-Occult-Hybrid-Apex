"""Run the actual AS publisher against native-feed semantics and cell identities."""
import shutil
import subprocess
import unittest
from test_cas_panel_scheduling import javascript_body


@unittest.skipUnless(shutil.which('node'), 'Node required')
class PublicationTests(unittest.TestCase):
    def test_rebinds_one_card_per_turn_reuses_controls_and_trims_only_surplus(self):
        code = '''
const assert=require('node:assert/strict');var now=0,changes=[],created=0;
var flash={utils:{getTimer:()=>now}};function int(v){return Math.trunc(v)||0;}
var drawer={0:{parent:{},getChildByName:()=>({visible:true})},40:{visible:true}};
function Feed(ids){this.rows=ids.map(data_id=>({data_id}));this.cells=ids.map(()=>++created);}
Object.defineProperty(Feed.prototype,'length',{get(){return this.rows.length;}});
Feed.prototype.ReplaceItemAt=function(i,p){this.rows[i]=p;changes.push('reuse');now++;};
Feed.prototype.AddItem=function(p){this.rows.push(p);this.cells.push(++created);changes.push('add');now+=12;};
Feed.prototype.RemoveItemAt=function(i){this.rows.splice(i,1);this.cells.splice(i,1);changes.push('remove');now+=5;};
for(var g=0;g<4;g++){drawer[47+g*3]=new Feed(['oldA','oldB']);drawer[49+g*3]={PositionCells:()=>{}};}
var originals=[0,1,2,3].map(g=>drawer[47+g*3].cells.slice()),records=[];
var apexPanels={stamp_ticket:'',revision:7,requested:false,key:'',cards_reused:0,cards_added:0,cards_removed:0,
 helpers:{CurrentRemove:{Record:(g,p)=>records.push([g,p.map(x=>x.data_id)])}},
 metrics:{},job_metrics:{phases:{}},host:{LayoutCurrentOutfit:()=>{}},refreshes:0,refresh_max_ms:0,stale:0};
for(var phase of ['feed_publish','position_cells','current_layout']){
 apexPanels.metrics[phase]={calls:0,total_ms:0,max_ms:0,last_ms:0};
 apexPanels.job_metrics.phases[phase]={calls:0,total_ms:0,max_ms:0,last_ms:0};}
var products=[[{data_id:'new1'},{data_id:'new2'}],[{data_id:'new3'}],[],[{data_id:'new4'},{data_id:'new5'},{data_id:'new6'}]];
apexPanels.job={drawer,context:'sim2/alien',phase:'publish',products,publish:0,publish_item:0,revision:7,key:'verified-new-owner',started:0};
function ApexPanelsWork(drawer,context){''' + javascript_body('ApexPanelsWork') + '''}
var turns=0;while(apexPanels.job){var count=changes.length;ApexPanelsWork(drawer,'sim2/alien');assert.ok(changes.length-count<=1);assert.ok(++turns<40);}
assert.equal(apexPanels.cards_reused,5);assert.equal(apexPanels.cards_added,1);assert.equal(apexPanels.cards_removed,3);
assert.equal(apexPanels.refreshes,1);assert.equal(apexPanels.key,'verified-new-owner');assert.equal(records.length,4);
for(var g=0;g<4;g++)assert.deepEqual(drawer[47+g*3].rows,products[g]);
assert.deepEqual(drawer[47].cells,originals[0]);assert.equal(drawer[50].cells[0],originals[1][0]);
assert.deepEqual(drawer[56].cells.slice(0,2),originals[3]);
assert.ok(!changes.includes('clear'));assert.equal(apexPanels.job_metrics.completed,true);
// A new revision invalidates publication before any feed can be rebound.
apexPanels.job={drawer,context:'sim2/alien',phase:'publish',products,publish:0,publish_item:0,revision:6};
var count=changes.length;ApexPanelsWork(drawer,'sim2/alien');assert.equal(changes.length,count);assert.equal(apexPanels.job,null);
assert.equal(apexPanels.requested,true);assert.equal(apexPanels.stale,1);
'''
        result = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
