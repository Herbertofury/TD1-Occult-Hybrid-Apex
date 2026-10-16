"""Read-only slider/preset provenance, conflicts and hotspot bindings.

Format references: CmarNYC-Tools/TS4MorphMaker HOTC.cs and SMOD.cs; historical
hotspot layouts: s4ptacle/Sims4Tools HotSpotControl.cs. Resource
identities and decompressed hashes describe competing definitions, never guessed
game load order. No resource or Sim exports; output is bounded metadata only.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import struct
from cas_resource_catalog import Package, canonical, digest, no_redirected_ancestors, tgi
from source_manifest import write_json, sha256

SMOD, HOTC, SCULPT, PRESET = 0xC5F6763E, 0x8B18FF6E, 0x9D1AB874, 0xEAA32ADD
TYPES = {SMOD: 'modifier', HOTC: 'hotspot', SCULPT: 'sculpt', PRESET: 'preset'}
MAX_PACKAGES, MAX_ROWS = 20000, 200000


class Reader:
    def __init__(self, raw):
        if not isinstance(raw, bytes) or len(raw) > 1024 * 1024:
            raise ValueError('Slider metadata exceeds its byte bound.')
        self.raw, self.pos = raw, 0
    def read(self, fmt):
        size = struct.calcsize('<' + fmt)
        if self.pos + size > len(self.raw): raise ValueError('Truncated slider metadata.')
        out = struct.unpack_from('<' + fmt, self.raw, self.pos); self.pos += size
        return out[0] if len(out) == 1 else out
    def finish(self):
        if self.pos != len(self.raw): raise ValueError('Unparsed slider metadata bytes.')


def hotspot(raw):
    r = Reader(raw); version, age_frame = r.read('II')
    if version not in (11, 12, 13, 14, 15): raise ValueError('Unsupported hotspot version.')
    species = r.read('I') if version >= 14 else None
    occult = r.read('I') if version >= 15 else None
    level, color, cursor = r.read('BBB'); region = r.read('I')
    subregion = r.read('I') if version >= 14 else None
    gender = r.read('B') if version >= 14 else None
    texture, unknown, count = r.read('Q'), r.read('I'), r.read('B')
    views = []
    for ordinal in range(count):
        angle, flip = r.read('BB'); scale_x, scale_y = r.read('ff')
        if flip not in (0, 1) or not all(math.isfinite(v) for v in (scale_x, scale_y)):
            raise ValueError('Invalid hotspot view metadata.')
        ids = r.read('QQQQ')
        views.append(dict(index=ordinal, angle=angle, flip=bool(flip), scale_x=scale_x, scale_y=scale_y,
                          directions={name: str(value) for name, value in zip(('left','right','up','down'), ids)}))
    r.finish()
    return dict(version=version, age_frame=age_frame, species=species, occult=occult,
                level=level, color_id=color, cursor=cursor, region=region, subregion=subregion,
                gender_restriction=gender, texture_reference=str(texture), views=views)


def sim_modifier(raw):
    r = Reader(raw); context, public, external, delay, objects = r.read('IIIII')
    if context != 3 or objects != 1 or max(public, external, delay) > 1024:
        raise ValueError('Unsupported modifier resource context.')
    def resource():
        instance, kind, group = r.read('QII'); return tgi((kind, group, instance))
    keys = [resource() for _ in range(public + external + delay)]
    offset, extent = r.read('II')
    if offset != r.pos or offset + extent != len(raw):
        raise ValueError('Modifier object extent differs.')
    version, age_gender, region = r.read('III')
    if version not in (0x70, 0x80, 0x90): raise ValueError('Unsupported modifier object version.')
    subregion = r.read('I') if version >= 0x90 else None
    link_tag = r.read('I'); bone, shape, normal = resource(), resource(), resource()
    count = r.read('I')
    if count > 16384: raise ValueError('Modifier bone entry count exceeds its bound.')
    bones = []
    for _ in range(count):
        bone_hash, multiplier = r.read('If')
        if not math.isfinite(multiplier): raise ValueError('Nonfinite modifier bone multiplier.')
        bones.append(dict(bone_hash=bone_hash, multiplier=multiplier))
    r.finish()
    return dict(version=version, age_gender=age_gender, region=region, subregion=subregion,
                link_tag=link_tag, referenced_resources=keys + [bone, shape, normal], bones=bones,
                native_bounds_verified=False)


def classify(providers):
    # EA plus CC at one TGI is an intentional/default override candidate. Two
    # differing CC definitions are a conflict; neither is called the winner.
    mods = [p for p in providers if p['origin'] == 'mod']
    if len({p['resource_sha256'] for p in mods}) > 1: return 'conflicting-mod-definitions'
    if len(mods) > 1: return 'identical-mod-definitions'
    if mods and any(p['origin'] == 'ea' and p['resource_sha256'] != mods[0]['resource_sha256'] for p in providers):
        return 'ea-override-candidate'
    if len(providers) > 1:
        return 'identical-definitions' if len({p['resource_sha256'] for p in providers}) == 1 else 'competing-ea-definitions'
    return 'unique-definition'


def build(sources):
    if not 0 < len(sources) <= MAX_PACKAGES: raise ValueError('Package inventory bound exceeded.')
    resources, packages, seen, total = defaultdict(list), [], set(), 0
    for path, origin in sources:
        no_redirected_ancestors(path); path = Path(path).resolve(strict=True)
        if str(path).casefold() in seen: raise ValueError('Duplicate source package.')
        seen.add(str(path).casefold()); package = Package(path, origin)
        wanted = [key for key in package.entries if key[0] in TYPES]
        if not wanted: continue
        payloads = package.read_many(wanted)
        packages.append(dict(path=str(path), sha256=package.source_sha256, origin=origin))
        for key, raw in sorted(payloads.items()):
            row = dict(package_name=path.name, package_path=str(path), package_sha256=package.source_sha256,
                       resource_sha256=digest(raw), origin=origin, metadata_status='unparsed')
            try:
                if key[0] == HOTC: row['metadata'] = hotspot(raw)
                elif key[0] == SMOD: row['metadata'] = sim_modifier(raw)
                else: row['metadata'] = {}
                row['metadata_status'] = 'parsed' if key[0] in (HOTC, SMOD) else 'identity-only'
            except (ValueError, struct.error) as error:
                row['reason'] = str(error)
            resources[key].append(row)
            total += 1
            if total > MAX_ROWS: raise ValueError('Resource row bound exceeded.')
    rows, bindings = [], defaultdict(list)
    for key, providers in sorted(resources.items()):
        ident = tgi(key)
        rows.append(dict(resource_tgi=ident, instance=str(key[2]), kind=TYPES[key[0]], providers=providers,
                         conflict=classify(providers), effective_load_source_verified=False,
                         independently_addressable=key[0] == SMOD and key[2] != 0,
                         unusable_zero_identifier=key[2] == 0, native_bounds_verified=False))
        if key[0] == HOTC:
            for provider in providers:
                if provider['metadata_status'] != 'parsed': continue
                meta = provider['metadata']
                for view in meta['views']:
                    for direction, modifier in view['directions'].items():
                        if modifier != '0': bindings[modifier].append(dict(hotspot_tgi=ident,
                            package_name=provider['package_name'], region=meta['region'], subregion=meta['subregion'],
                            age_frame=meta['age_frame'], occult=meta['occult'], angle=view['angle'], direction=direction,
                            hotspot_conflict=classify(providers)))
    for row in rows:
        if row['kind'] == 'modifier': row['hotspot_bindings'] = bindings.get(row['instance'], [])
    return dict(schema=1, operation='read-only-slider-resource-catalog', resources=rows, packages=packages,
                game_contacted=False, source_files_written=False, bounds_verified=False,
                conflicting_resources=sum(r['conflict']=='conflicting-mod-definitions' for r in rows),
                duplicate_resources=sum(r['conflict']=='identical-mod-definitions' for r in rows),
                parsing_failures=sum(p['metadata_status']=='unparsed' for r in rows for p in r['providers']))


class Catalog:
    def __init__(self, path, expected):
        self.path = Path(path); no_redirected_ancestors(self.path)
        if self.path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('Slider catalog SHA/size differs.')
        raw = self.path.read_bytes()
        if len(raw) > 64 * 1024 * 1024 or digest(raw) != expected:
            raise ValueError('Slider catalog SHA/size differs.')
        data = json.loads(raw.decode('utf-8'))
        if data.get('schema') != 1 or data.get('operation') != 'read-only-slider-resource-catalog':
            raise ValueError('Unsupported slider catalog.')
        self.data, self.expected = data, expected
    def query(self, request):
        if not isinstance(request, dict) or set(request) != {'search','offset','limit','kind','conflicts_only'}:
            raise ValueError('Exact slider catalog query required.')
        if (not isinstance(request['search'], str) or len(request['search']) > 200 or
                type(request['offset']) is not int or request['offset'] < 0 or
                type(request['limit']) is not int or not 1 <= request['limit'] <= 100 or
                request['kind'] not in ('modifier','hotspot','preset','sculpt','all') or
                type(request['conflicts_only']) is not bool): raise ValueError('Invalid slider query bounds.')
        text = request['search'].casefold()
        rows = [row for row in self.data['resources'] if
                (request['kind']=='all' or request['kind']==row['kind']) and
                (not request['conflicts_only'] or row['conflict'] in ('conflicting-mod-definitions','identical-mod-definitions')) and
                (not text or text in canonical(row).decode('utf-8').casefold())]
        return dict(ok=True, catalog_sha256=self.expected, items=rows[request['offset']:request['offset']+request['limit']],
                    total=len(rows), offset=request['offset'], limit=request['limit'],
                    game_contacted=False, source_files_written=False, effective_load_source_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mods-root', required=True, type=Path)
    parser.add_argument('--game-root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    no_redirected_ancestors(args.output)
    if args.output.exists(): raise ValueError('Use a fresh external metadata file.')
    roots = [(args.mods_root, 'mod')]
    if args.game_root: roots += [(args.game_root,'ea')]
    for root, _ in roots:
        no_redirected_ancestors(root)
        if root.resolve() == args.output.resolve() or root.resolve() in args.output.resolve().parents:
            raise ValueError('Metadata output must stay outside all source folders.')
    sources = [(path, origin) for root, origin in roots for path in sorted(root.rglob('*.package'))]
    result = build(sources); write_json(args.output, result)
    print(json.dumps(dict(ok=True, resources=len(result['resources']), packages=len(result['packages']),
                         conflicts=result['conflicting_resources'], duplicates=result['duplicate_resources'],
                         parsing_failures=result['parsing_failures'], sha256=sha256(args.output))))


if __name__ == '__main__': main()
