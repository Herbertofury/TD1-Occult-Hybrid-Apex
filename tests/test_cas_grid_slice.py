from pathlib import Path
import sys,importlib.util,subprocess,unittest,json
ROOT=Path(__file__).resolve().parents[1];PROJECT=next(p for p in (ROOT,*ROOT.parents) if (p/'tools/cas_grid_progress.py').is_file());sys.path[:0]=[str(ROOT/'tools'),str(PROJECT/'tests'),str(PROJECT/'tools')]
import cas_grid_slice as stage,cas_grid_progress as previous,test_cas_grid_presentation as p

class LogicalTests(unittest.TestCase):
 def case(self,code,fixed=True):
  original=p.stage
  try:
   p.stage=stage if fixed else previous;result=subprocess.run(['node','-'],input=p.NATIVE_MOCK+p.javascript()+p.BOOT+SETUP+code,text=True,capture_output=True,timeout=15);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  finally:p.stage=original
 def test_actual_180_retained_60_target_surplus_positions_are_performed_not_128_unaccounted_noops(self):
  self.case("seek('position',60);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations+1);assert.equal(after.index,61);assert.equal(after.counts.position,before.counts.position+1);assert.equal(time-start,6);",False)
 def test_exact_171_ms_hypothesis_is_not_reproduced_by_180_to_60_alone(self):
  self.case("seek('position',178);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations+1);assert.equal(after.index,179);assert.equal(time-start,6);",False)
 def test_old_expired_capacity_transition_performs_an_extra_atom_after_deadline(self):
  self.case("seek('capacity',0);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations+1);assert.equal(after.phase,'position');assert.equal(after.index,1);assert.equal(time-start,8);",False)
 def test_fixed_expired_capacity_yields_after_one_real_logical_transition(self):
  self.case("seek('capacity',0);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations);assert.equal(after.phase,'position');assert.equal(after.index,0);assert.equal(time-start,6);const next=g.ApexGridStep(64,getTimer()+1);assert.equal(next.index,1);assert.equal(next.operations,before.operations+1);")
 def test_old_position_tail_transition_crosses_deadline_into_first_bind(self):
  self.case("seek('position',180);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations+1);assert.equal(after.phase,'selection');assert.ok(Math.abs(time-start-16.1)<.000001);",False)
 def test_fixed_position_tail_transition_yields_without_data_or_draw(self):
  self.case("seek('position',180);slow();const before=g.ApexGridStatus(),start=time;const after=g.ApexGridStep(64,getTimer()+1);assert.equal(after.operations,before.operations);assert.equal(after.phase,'bind');assert.equal(after.counts.data,before.counts.data);assert.equal(after.counts.draw,before.counts.draw);assert.equal(time-start,6);")
 def test_first_slow_selection_atom_still_progresses_and_converges_without_partial_publish(self):
  self.case("seek('selection',0);slow();const before=g.ApexGridStatus(),first=g.ApexGridStep(64,getTimer()+1);assert.equal(first.operations,before.operations+1);assert.equal(first.phase,'bind');assert.equal(first.index,1);let after;for(let i=0;i<1200;i++){after=g.ApexGridStep(64,getTimer()+1);if(after.phase==='done')break;}assert.equal(after.phase,'done');assert.equal(after.error,null);assert.equal(after.publishes,3);")
 def test_owner_revision_reentry_invalid_budget_and_array_guards_remain(self):
  self.case("seek('position',178);g.lease.active=false;const before=g.calls.length;const s=g.ApexGridStep(64,getTimer()+1);assert.equal(s.phase,'cancelled');assert.equal(g.calls.length,before);assert.equal(s.reason,'context');")
 def test_no_deadline_keeps_original_operation_budget(self):
  self.case("seek('capacity',0);const before=g.ApexGridStatus();const after=g.ApexGridStep(4,0);assert.equal(after.operations-before.operations,4);assert.equal(after.phase,'position');assert.equal(after.index,4);")
SETUP="""
const g=new NativeGrid(1000,0);
function small(y){return request(g,12,{width:21.4,height:29.4,scale:.2,viewHeight:450,scrollY:y});}
g.ApexGridBegin(small(0));assert.equal(bounded(g).phase,'done');g.ApexGridBegin(small(1));assert.equal(bounded(g).phase,'done');
assert.equal(g.mCells.length,180);assert.equal(g.apexGridState.presentation.spareCells.length,180);
g.ApexGridBegin(request(g,6,{width:107,height:147,scale:1,viewHeight:1213.7,scrollY:0}));
function seek(phase,index){for(let i=0;i<2000;i++){const s=g.ApexGridStatus();if(s.phase===phase&&s.index===index)break;g.ApexGridStep(1,0);}const s=g.ApexGridStatus();assert.equal(s.phase,phase);assert.equal(s.index,index);assert.equal(s.target,60);assert.equal(g.ApexGridCells.length,180);}
function slow(){const validate=g.apexGridState.validate;g.apexGridState.validate=o=>{time+=2;return validate(o);};}
"""
if __name__=='__main__':unittest.main()
