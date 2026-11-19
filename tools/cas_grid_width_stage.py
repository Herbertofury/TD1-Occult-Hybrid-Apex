"""Private width-only view transfer; exact EOF/authority predecessor."""
from pathlib import Path
import cas_grid_eof as previous,cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexTxnRequest','ApexGridNativeGuard','ApexGridNeedsWork','ApexGridMetrics',
          'ApexGridBegin','ApexGridBeginFrame','ApexGridDeltaRestore')
MAIN_REPLACED=('ApexCatalogGridRequest',)
MAIN_ADDED=()
ADDED=('ApexGridWidthWake','ApexGridWidthCounters','ApexGridWidthCurrent','ApexGridWidthTry')

def helpers():
 s=previous.helpers()
 s=pool.edit_method(s,'ApexGridNativeGuard',[
  ('         if(kind=="position" || kind=="reset" || kind=="profile") {',
   '         if(kind=="position" && ApexGridWidthWake(j))return true;\n         if(kind=="position" || kind=="reset" || kind=="profile") {')])
 s=pool.edit_method(s,'ApexGridNeedsWork',[
  ('         return s.bootstrap || j.phase!="done"',
   '         return s.widthWake!=null || s.bootstrap || j.phase!="done"')])
 s=pool.edit_method(s,'ApexTxnRequest',[
  ('         if(j.desired!=null && j.desired.signature==signature){j.coalesced++;return;}\n         r.signature=signature;',
   '         r.signature=signature;\n         if(ApexGridWidthTry(j,r) || ApexGridAuthorityProbe() || j.cancelled) {j.coalesced++;return;}\n         if(j.desired!=null && j.desired.signature==signature){j.coalesced++;return;}')])
 s=pool.edit_method(s,'ApexGridMetrics',[
  ('         result.row_delta_last_error=',
   '         result.width_only_commits=int(s.widthOnlyCommits);result.width_only_pending=s.widthWake!=null;\n         result.width_only_refusal=s.widthOnlyRefusal==null ? "" : String(s.widthOnlyRefusal).substr(0,160);\n         result.row_delta_last_error=')])
 s=s.replace('public final function ApexGridBeginFrame','public function ApexGridBeginFrame')
 for name,ret in (('ApexGridBegin','return ApexGridAuthorityStatus();'),('ApexGridBeginFrame','return;')):
  s=pool.edit_method(s,name,[('               ApexTxnRequest(apexGridState.job,request);',
   '               ApexTxnRequest(apexGridState.job,request);\n               if(ApexGridAuthorityProbe())'+ret)])
 s=s.replace('public function ApexGridBeginFrame','public final function ApexGridBeginFrame')
 s=pool.edit_method(s,'ApexGridDeltaRestore',[
  ('private function ApexGridDeltaRestore(d:Object) : void {', '''private function ApexGridDeltaRestore(d:Object) : void {
         if(d!=null && d.widthTransfer===true) {
            if(ApexGridAuthorityProbe())return;
            if(!ApexGridAuthorityCurrent(d) || !ApexGridAuthorityBank(d)) {ApexGridAuthorityLose(d,"width-cancel-custody-changed");return;}
            if(apexGridState===d.state && d.state.delta===d) {
               d.state.delta=null;if(d.state.widthWake===d.wake)d.state.widthWake=null;
               if(apexGridAuthority===d.authority)apexGridAuthority=null;
            }
            return;
         }''')])
 return s+'\n'+(ROOT/'Source/CASUi/catalog_grid_width_methods.as').read_text()


def extend_main(source):
 a,b=pool.method_extent(source,'ApexCatalogGridRequest')
 old=source[a:b];needle='intrinsicGeometryContract:nativeCardContract,'
 if old.count(needle)!=2:raise ValueError('Exact authenticated Main width capability issuer missing')
 expected=old.replace(needle,needle+'viewWidthTransferContract:nativeCardContract,')
 reviewed=(ROOT/'Source/CASUi/catalog_grid_width_main_request.as').read_text().strip()
 if expected.strip()!=reviewed:raise ValueError('Exact reviewed Main width request differs')
 return source[:a]+reviewed+source[b:]
