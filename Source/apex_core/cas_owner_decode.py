"""Decode a detached native DTO into the existing appearance-only codec.

The installed protobuf descriptor supplies values/defaults. No SimInfo is
created, loaded or changed. Complete native DTO bytes remain separate evidence;
nonappearance construction defaults must never replace gameplay Sim data.
"""
import hashlib
import math
import re
from . import form_appearance as appearance

ALIASES = {'facial_attributes':'facial_attr', '__outfits__':'outfits'}
INTEGER_TYPES = (3,4,5,6,7,13,14,15,16,17,18)


def layout(fields):
    """Retain field representations only; no old appearance values are replayed."""
    appearance.payload(fields)
    if '__outfits__' not in fields:raise ValueError('An owner layout requires its captured outfit field.')
    result={}
    for name,row in fields.items():
        kind=row['kind'];value=row['value']
        if kind=='value' and type(value) in (str,int,float):result[name]=appearance.encode(type(value)())
        elif kind=='bytes':result[name]=appearance.encode(b'')
        elif kind=='protobuf':result[name]=appearance.encode(('protobuf',b''))
        elif kind=='mapping' and name=='parts_custom_tattoos':result[name]=appearance.encode({})
        else:raise ValueError('Unsupported native appearance representation: '+name)
    return result


def from_message(message, template):
    if getattr(getattr(message,'DESCRIPTOR',None),'full_name',None) != 'EA.Sims4.Persistence.SimData':
        raise ValueError('Decode only the installed detached native SimData message.')
    appearance.payload(template)
    if '__outfits__' not in template:
        raise ValueError('A native owner requires the complete captured outfit field set.')
    descriptors=message.DESCRIPTOR.fields_by_name
    result={}
    for name,prior in template.items():
        native=ALIASES.get(name,name);field=descriptors.get(native)
        if field is None:
            raise ValueError('Native owner descriptor lost an existing appearance field: '+name)
        value=getattr(message,native)
        if name=='parts_custom_tattoos':
            if field.type!=11 or field.label!=3 or prior['kind']!='mapping':
                raise ValueError('Native tattoo storage differs from the captured wrapper mapping.')
            mapping={}
            for tattoo in value:
                body,texture=tattoo.body_type,tattoo.texture_id
                if (type(body) is not int or type(texture) is not int or
                        not 0<=body<2**32 or not 0<=texture<2**64 or body in mapping):
                    raise ValueError('Native tattoo body keys are duplicated or outside their ranges.')
                mapping[body]=texture
            result[name]=appearance.encode(mapping)
            continue
        if field.label==3:
            raise ValueError('Unexpected repeated appearance field; no partial owner decoded.')
        kind=prior['kind']
        if field.type in (11,12):
            raw=value.SerializeToString() if field.type==11 else bytes(value)
            if kind not in ('bytes','protobuf'):
                raise ValueError('Native appearance bytes differ from their wrapper representation.')
            result[name]=appearance.encode(('protobuf',raw) if kind=='protobuf' else raw)
        elif field.type==9 and kind=='value' and isinstance(prior['value'],str) and isinstance(value,str):
            result[name]=appearance.encode(value)
        elif field.type in INTEGER_TYPES and kind=='value' and type(prior['value']) is int:
            unsigned=field.type in (4,6,7,13)
            bits=64 if field.type in (3,4,6,16,18) else 32
            if type(value) is not int or not (0<=value<2**bits if unsigned else -(2**(bits-1))<=value<2**(bits-1)):
                raise ValueError('Native appearance integer is outside its declared range.')
            result[name]=appearance.encode(int(value))
        elif (field.type in (1,2) and kind=='value' and type(prior['value']) in (int,float) and
                type(value) in (int,float) and math.isfinite(value)):
            result[name]=appearance.encode(float(value))
        else:
            raise ValueError('Native appearance field has an unsupported wrapper representation: '+name)
    # Validate every field together. This is not whole-Sim restore authority.
    appearance.payload(result)
    return result


def read(raw, sim_id, template):
    if (not isinstance(raw,bytes) or not 0<len(raw)<=512*1024 or not isinstance(sim_id,str) or
            re.fullmatch('[1-9][0-9]{0,19}',sim_id) is None or int(sim_id)>=2**64):
        raise ValueError('Decode exact bounded bytes for one existing uint64 Sim identity.')
    from protocolbuffers import FileSerialization_pb2
    message=FileSerialization_pb2.SimData();message.ParseFromString(raw)
    if str(message.sim_id)!=sim_id:
        raise ValueError('Native owner DTO belongs to another Sim; no appearance decoded.')
    fields=from_message(message,template)
    return dict(fields=fields,native_bytes=raw,native_sha256=hashlib.sha256(raw).hexdigest(),
                appearance_written=False,whole_sim_restore_authorized=False,
                unknown_native_bytes_preserved_separately=True,production_ready=False)
