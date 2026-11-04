"""Post-retainer cell-role adapter; proprietary donor sources remain private.

Compile temporary reference classes solely to obtain one pure helper, IsCurrent
and a cross-class receiver probe. The Java pass retains every unrelated byte,
including the incoming Main, height and prior Draw diagnostic markers.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DONOR_SHA256 = 'c97afa8f0362a0452b359074769b9c99174444dd211927d08972091db3391969'
PRIVATE_SOURCE_PINS = {
    'CurrentOutfitUI': 'cf661133c41f4cb976aa050098dc60923bda457d7bab0dc41e1651573367d260',
    'OutfitCategory': 'b85fb4c0ac1316ac6c1d82dfa15386cf6bd0197cc508739ce15be49311f3c7cd',
}
HELPER_METHOD = '''      public static function ApexCellRole(cell:Object) : int
      {
         var r:Object = HistoryHost.dccHistoryRuntimeDrawer;
         if(!r || !cell || !r[0] || !r[0].parent)
         {
            return 0;
         }
         var root:Object = r[0];
         var p:Object = cell;
         var role:int = 0;
         var depth:int = 0;
         while(p && depth < 256)
         {
            if(p === root)
            {
               return r === HistoryHost.dccHistoryRuntimeDrawer ? role : 0;
            }
            if(p === r[40])
            {
               role = 3;
            }
            else if(role == 0)
            {
               if(p === r[2])
               {
                  role = 1;
               }
               else if(p === r[25])
               {
                  role = 2;
               }
            }
            p = p.parent;
            depth++;
         }
         return 0;
      }
'''
IS_CURRENT_METHOD = '''      public static function IsCurrent(cell:Object) : Boolean
      {
         return ApexCellRole(cell) == 3;
      }
'''
PROBE_METHOD = '''      public static function ApexRoleCallProbe(cell:Object) : int
      {
         return dcc.history.CurrentOutfitUI.ApexCellRole(cell);
      }
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def method_extent(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return start, end


def append_method(source, method):
    at = source.rfind('\n   }')
    if at < 0:
        raise ValueError('Pinned donor class closing boundary differs.')
    return source[:at] + '\n' + method + source[at:]


def inject_current(source):
    if 'function ApexCellRole(' in source:
        raise ValueError('Structural role helper already exists.')
    start, end = method_extent(source, '      public static function IsCurrent(')
    return append_method(source[:start] + IS_CURRENT_METHOD + source[end:], HELPER_METHOD)


def inject_probe(source):
    if 'function ApexRoleCallProbe(' in source:
        raise ValueError('Structural role compiler probe already exists.')
    return append_method(source, PROBE_METHOD)


def run(args, log):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=180)
    Path(log).write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError('Structural role build failed: ' + (result.stdout + result.stderr)[-1800:])


def adapt(donor_swf, baseline_swf, source_root, ffdec, work):
    """Return retained ABC bytes and a separate, honest post-adapter contract.

    baseline_swf is the already-retained complete SWF, not a compiler output.
    Its Main hash is dynamic: the original Draw/trace projection authenticates
    the selected code, and whole-ABC rollback proves all incoming Main methods
    and unselected structures survive. The base contract remains historical;
    this contract explicitly declares the later IsCurrent native-code change.
    """
    donor_swf, source_root, ffdec, work = map(Path, (donor_swf, source_root, ffdec, work))
    if digest(donor_swf.read_bytes()) != DONOR_SHA256:
        raise ValueError('Structural roles require the authenticated donor SWF.')
    work.mkdir(parents=True, exist_ok=True)
    baseline_path = work / 'retained-baseline.swf'
    baseline_path.write_bytes(baseline_swf)
    for name, transform in [('CurrentOutfitUI', inject_current), ('OutfitCategory', inject_probe)]:
        source = (source_root / 'dcc/history' / (name + '.as')).read_text(encoding='utf-8')
        if digest(source.encode('utf-8')) != PRIVATE_SOURCE_PINS[name]:
            raise ValueError('Pinned private structural-role source differs: ' + name)
        (work / (name + '.as')).write_text(transform(source), encoding='utf-8')
    first, compiled = work / 'helper-compiled.swf', work / 'probe-compiled.swf'
    run([ffdec, '-importAssets', 'yes,local', '-replace', baseline_path, first,
         'dcc.history.CurrentOutfitUI', work / 'CurrentOutfitUI.as'], work / 'helper-compile.log')
    run([ffdec, '-importAssets', 'yes,local', '-replace', first, compiled,
         'dcc.history.OutfitCategory', work / 'OutfitCategory.as'], work / 'probe-compile.log')
    classes = work / 'classes'
    classes.mkdir(exist_ok=True)
    jar = ffdec.with_name('ffdec.jar')
    java_source = ROOT / 'tools/CasStructuralRolesPatch.java'
    run(['javac', '-cp', jar, '-d', classes, java_source], work / 'javac.log')
    retained, report = work / 'retained.abc', work / 'contract.json'
    run(['java', '-cp', str(jar) + os.pathsep + str(classes), 'CasStructuralRolesPatch',
         donor_swf, baseline_path, compiled, retained, report], work / 'transplant.log')
    contract = json.loads(report.read_text(encoding='utf-8'))
    data = retained.read_bytes()
    if (contract.get('ok') is not True or contract.get('abc_sha256') != digest(data) or
            contract.get('baseline_swf_sha256') != digest(baseline_swf) or
            contract.get('additional_native_changes_after_base') != ['dcc.history.CurrentOutfitUI.IsCurrent'] or
            contract.get('serialized_whole_abc_rollback_projection') is not True or
            contract.get('compiled_cross_class_receiver_abi') is not True or
            contract.get('main_and_height_preserved') is not True or
            contract.get('edited_baseline_methods') != 2 or contract.get('appended_helpers') != 1):
        raise ValueError('Structural role post-adapter contract differs.')
    contract['source_sha256'] = {
        'tools/CasStructuralRolesPatch.java': digest(java_source.read_bytes()),
        'tools/cas_structural_roles.py': digest(Path(__file__).read_bytes()),
    }
    contract['private_source_sha256'] = PRIVATE_SOURCE_PINS.copy()
    return data, contract


def chain_contract(base, post, final_swf):
    """Bind the historical retainer proof to this final ABC and honest counts."""
    from cas_ui_build import tags, unpack
    required = ('explicit_jump_switch_exception_fixtures', 'compiled_helper_control_flow_oracle',
                'compiled_cross_class_receiver_abi', 'serialized_whole_abc_rollback_projection',
                'main_and_height_preserved', 'unowned_corruption_rejected',
                'draw_replaces_existing_trace_adapter', 'base_contract_requires_post_adapter_chain')
    if (post.get('ok') is not True or any(post.get(key) is not True for key in required) or
            post.get('base_donor_body_count') != base.get('native_method_count') or
            post.get('edited_baseline_methods') != 2 or post.get('appended_helpers') != 1 or
            post.get('additional_native_changes_after_base') != ['dcc.history.CurrentOutfitUI.IsCurrent'] or
            post.get('unchanged_baseline_bodies') != post.get('baseline_body_count', 0) - 2 or
            not isinstance(base.get('unchanged_native_methods'), int) or base['unchanged_native_methods'] < 1):
        raise ValueError('Structural role contract cannot chain to the base native proof.')
    abc = [t[3] for t in tags(unpack(final_swf)[1]) if t[0] == 82]
    if len(abc) != 1 or digest(abc[0][abc[0].index(b'\0', 4) + 1:]) != post.get('abc_sha256'):
        raise ValueError('Final SWF does not contain the structurally verified ABC.')
    result = dict(post)
    result['base_contract_sha256'] = digest(json.dumps(base, sort_keys=True, separators=(',', ':')).encode())
    result['additional_changed_original_native_bodies'] = 1
    result['edited_existing_adapter_bodies'] = 1
    result['unchanged_original_native_bodies_after_chain'] = base['unchanged_native_methods'] - 1
    result['final_swf_sha256'] = digest(final_swf)
    return result
