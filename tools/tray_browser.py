"""Read-only native Tray gallery. Source files stay in place; images are lazy.

The public EA protobuf field numbers and native thumbnail envelope are decoded
independently. No household is loaded into the game to browse this library.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
from PIL import Image
import cas_resource_catalog as resources
import tray_library
from save_metadata import fields


def metadata(raw):
    if not 8 <= len(raw) <= tray_library.MAX_FILE:
        raise ValueError('Invalid native Tray metadata size.')
    version, size = struct.unpack_from('<II', raw)
    if not (version == 0 and size == len(raw)-8 or version == 1 and size == len(raw)-4):
        raise ValueError('Unverified native Tray metadata header.')
    result = dict(name='', description='', creator='', type=0, timestamp=0)
    wanted = {2: ('type', 0), 4: ('name', 2), 5: ('description', 2), 7: ('creator', 2), 11: ('timestamp', 0)}
    seen = set()
    for n, wire, value in fields(raw[8:]):
        if n not in wanted: continue
        name, expected = wanted[n]
        if n in seen or wire != expected: raise ValueError('Ambiguous Tray metadata field.')
        seen.add(n)
        if wire == 2:
            value = value.decode('utf-8')
            if len(value) > (8192 if name == 'description' else 256): raise ValueError('Tray text exceeds its bound.')
        result[name] = value
    return result


def thumbnail(raw):
    """Native 24-byte envelope, repeating XOR transport key, genuine JPEG/ALFA.

    Enforce the declared extent instead of silently accepting truncated files.
    Decode the source pixels before resizing gallery cards, including alpha.
    """
    if not 28 <= len(raw) <= tray_library.MAX_FILE: raise ValueError('Invalid Tray image extent.')
    size = struct.unpack_from('<I', raw)[0]
    if not 4 <= size <= len(raw)-24 or len(raw)-24-size > 16: raise ValueError('Tray image payload extent differs.')
    key = bytes.fromhex('4125e6cd47bab21a')
    data = bytes(v ^ key[i % 8] for i, v in enumerate(raw[24:24+size]))
    if not data.startswith(b'\xff\xd8'): raise ValueError('Tray thumbnail is not a native JPEG.')
    end = data.rfind(b'\xff\xd9')
    if end < 2 or len(data)-end-2 > 16: raise ValueError('Tray thumbnail JPEG ending differs.')
    data = data[:end+2]
    with Image.open(io.BytesIO(data)) as image:
        if not 0 < image.width <= 4096 or not 0 < image.height <= 4096: raise ValueError('Tray image dimensions exceed their bound.')
        image.load(); rgba = image.convert('RGBA')
    if data[24:28] == b'ALFA':
        alpha_size = struct.unpack_from('>I', data, 28)[0]
        if not 0 < alpha_size <= len(data)-32: raise ValueError('Tray alpha extent differs.')
        with Image.open(io.BytesIO(data[32:32+alpha_size])) as alpha:
            if alpha.format != 'PNG' or alpha.size != rgba.size: raise ValueError('Tray alpha dimensions differ.')
            alpha.load(); rgba.putalpha(alpha.convert('L'))
    rgba.thumbnail((512,512))
    stream = io.BytesIO(); rgba.save(stream, format='PNG')
    return stream.getvalue(), rgba.width, rgba.height


class Gallery:
    def __init__(self, folder):
        self.folder = Path(folder).absolute()
        resources.no_redirected_ancestors(self.folder)
        self.records = {}; self.items = []
        for name, paths in tray_library.groups(self.folder).items():
            try:
                if len(paths)>256: raise ValueError('Tray group file count exceeds its bound.')
                rows = [(p, resources.signature(p)) for p in paths]
                identity = resources.digest(resources.canonical([[p.name, list(s)] for p,s in rows]))
                meta = metadata(tray_library.read(self.folder/name))
                households = [p for p in paths if p.suffix.lower()=='.householdbinary']
                if len(households)>1: raise ValueError('Tray household group is ambiguous.')
                count = len(tray_library.sims(tray_library.read(households[0]))['sims']) if households else 0
                image_files = sorted([p for p in paths if p.suffix.lower() in ('.hhi','.sgi','.bpi','.rmi')],
                    key=lambda p:(p.suffix.lower()!='.hhi',int(p.name[2:10],16)&15!=3,p.name))
                item = dict(meta, item_id=identity, item=name, file_count=len(paths), sim_count=count,
                    kind='household' if households else 'lot' if any(p.suffix.lower()=='.blueprint' for p in paths) else 'room',
                    modified_ns=max(p.stat().st_mtime_ns for p in paths), status='ready', image_count=len(image_files))
                self.records[identity] = dict(files=rows, household=households[0] if households else None, images=image_files)
            except (OSError,ValueError,UnicodeError) as error:
                identity=resources.digest(name.encode('utf-8'))
                item=dict(item_id=identity,item=name,name=name,description='',creator='',type=0,timestamp=0,
                          kind='unknown',modified_ns=0,status='unavailable',reason=str(error)[:1000],file_count=len(paths),sim_count=0,image_count=0)
            self.items.append(item)
        self.items.sort(key=lambda r:(-r['modified_ns'],r['item']))
        self.expected = resources.digest(resources.canonical(self.items))

    def query(self, request):
        if not isinstance(request,dict) or set(request)!={'text','kind','offset','limit'}:
            raise ValueError('Typed Tray page required.')
        text,kind,offset,limit=(request[k] for k in ('text','kind','offset','limit'))
        if not isinstance(text,str) or len(text)>200 or kind not in ('all','household','lot','room') or type(offset)is not int or not 0<=offset<=100000 or type(limit)is not int or not 1<=limit<=60:
            raise ValueError('Invalid Tray gallery filter/page.')
        words=text.casefold().split()
        selected=[r for r in self.items if (kind=='all' or r['kind']==kind) and all(w in (r['name']+' '+r['creator']+' '+r['description']).casefold() for w in words)]
        rows=selected[offset:offset+limit]
        return dict(ok=True,library_sha256=self.expected,query=request,total=len(selected),offset=offset,
            next_offset=offset+len(rows) if offset+len(rows)<len(selected) else None,items=rows,game_contacted=False,source_files_written=False)

    def _record(self, request, extra=()):
        if not isinstance(request,dict) or set(request)!={'item_id','library_sha256',*extra} or request['library_sha256']!=self.expected:
            raise ValueError('Exact Tray gallery selection required.')
        record=self.records[resources.sha(request['item_id'])]
        if any(resources.signature(p)!=s for p,s in record['files']): raise ValueError('Tray source changed; refresh its gallery snapshot.')
        return record

    def image(self, request):
        record=self._record(request,('image_index',)); n=request['image_index']
        if type(n)is not int or not 0<=n<len(record['images']): raise ValueError('Select an existing native Tray image.')
        raw=tray_library.read(record['images'][n]); png,w,h=thumbnail(raw)
        import base64
        return dict(ok=True,**request,png_base64=base64.b64encode(png).decode('ascii'),sha256=resources.digest(png),width=w,height=h,
                    source_sha256=resources.digest(raw),game_contacted=False,source_files_written=False)

    def inspect(self, request):
        context=request.get('context') if isinstance(request,dict) else None
        record=self._record(request, ('context',) if context is not None else ())
        if record['household'] is None: raise ValueError('This item is a lot or room; choose a household for Sim form preview.')
        path=record['household']; expected=resources.file_hash(path)
        result=tray_library.inspect(path,expected)
        self._record(request, ('context',) if context is not None else ())
        if context is not None:
            if not isinstance(context,dict) or set(context)!={'runtime_pid','history_lane'} or type(context['runtime_pid'])is not int or context['runtime_pid']<=0 or not isinstance(context['history_lane'],str) or len(context['history_lane'])>256:
                raise ValueError('Exact destination runtime/lane context required.')
            result['preview_sims']=[dict(name=s['name'],sim_id=s['sim_id'],forms=tray_library.preview_forms(s,expected,
                dict(pid=context['runtime_pid']),context)) for s in result['sims']]
        if len(resources.canonical(result))>8*1024*1024: raise ValueError('Tray inspection exceeds its transport bound.')
        return dict(result,item_id=request['item_id'],library_sha256=self.expected)
