"""Bounded private receiver lifetime; no disk, game APIs or native authority.

Certificates are emitted only after the receiver's existing durable validation.
Compact retired receipts are diagnostics. They never authorize writes/replay.
"""
from collections import OrderedDict
import threading

_ADMIT = object()

def _hash(value):return type(value) is str and len(value)==64 and all(c in '0123456789abcdef'for c in value)
def _token(value):return type(value) is str and len(value)==32 and all(c in '0123456789abcdef'for c in value)
def _id(value):return type(value)is str and value.isascii()and value.isdecimal()and 0<int(value)<2**64 and str(int(value))==value

class Completion(tuple):
    __slots__=()
    def __new__(cls,admit,key,identity,epoch,journal_sha,plan_sha,scope,generation,native_sha):
        if admit is not _ADMIT:raise ValueError('Only receiver-validated completion can be retained.')
        if(type(key)is not tuple or len(key)!=3 or any(type(v)is not str for v in key)or not _token(key[2])or
           type(identity)is not tuple or len(identity)!=4 or type(identity[0])is not int or not 0<identity[0]<=0xffffffff or
           not all(_id(v)for v in identity[1:])or key[1]!=identity[1]+':'+identity[3]or
           not all(_hash(v)for v in(epoch,journal_sha,plan_sha))):raise ValueError('Completion requires exact primitive owner/receipt identity.')
        if scope is None:
            if generation is not None or native_sha is not None:raise ValueError('Unbound completion cannot carry native scope evidence.')
        elif not _token(scope)or type(generation)is not int or generation<=0 or not _hash(native_sha):raise ValueError('Native completion scope/generation/hash is incomplete.')
        return tuple.__new__(cls,(key,identity,epoch,journal_sha,plan_sha,scope,generation,native_sha))
    key=property(lambda self:self[0]);identity=property(lambda self:self[1]);epoch=property(lambda self:self[2])
    journal_sha=property(lambda self:self[3]);plan_sha=property(lambda self:self[4]);scope=property(lambda self:self[5])
    generation=property(lambda self:self[6]);native_sha=property(lambda self:self[7])

class ReceiverLifetime:
    def __init__(self,captured,active,capacity=256,completed_limit=256):
        if captured or active:raise ValueError('A new registry cannot adopt unindexed receiver objects.')
        self.captured,self.active=captured,active;self.capacity=capacity;self.completed_limit=completed_limit
        self.owner=None;self.current={};self.ready={};self.finished=OrderedDict()
    def bind_owner(self,owner):
        # The Source caller first verifies backend._APEX_GAME_THREAD_IDENT.
        # Module import and a first untrusted request grant no thread authority.
        if type(owner)is not int or owner!=threading.current_thread().ident:raise ValueError('Explicit current canonical owner required.')
        if len(self.current)!=len(self.captured):raise ValueError('Receiver index changed; no ownership transfer.')
        if self.owner!=owner:
            if self.captured or self.active or self.current or self.ready:raise ValueError('Cannot transfer retained receiver ownership.')
            self.owner=owner
    def _owner(self):
        if threading.current_thread().ident!=self.owner:raise ValueError('Receiver lifetime belongs to its original canonical thread.')
        if len(self.current)!=len(self.captured):raise ValueError('Receiver ownership index differs; no scan or fallback adoption.')
    def lookup(self,path,key,require_active=False):
        self._owner();owner=(str(path),key);cache=self.current.get(owner)
        if cache is None or cache[:2]!=owner or cache not in self.captured:raise ValueError('Exact indexed receiver capability unavailable.')
        captured=self.captured[cache]
        if require_active and cache not in self.active:raise ValueError('Exact observed receiver capability unavailable.')
        return cache,captured
    def _eligible(self,key):
        retained=self.ready.get(key)
        if retained is None:raise ValueError('Receiver has no validated terminal certificate.')
        captured,active,certificate=retained
        if(self.captured.get(key)is not captured or self.active.get(key)is not active or
           self.current.get(key[:2])!=key or getattr(active,'state',None)!='completed'or
           getattr(active,'journal_sha256',None)!=certificate.journal_sha or
           captured.get('prepare_async_inflight')is not None):raise ValueError('Receiver remains active, changed or in flight; state retained.')
        return certificate
    def preflight(self,path,key):
        self._owner();owner=(str(path),key);old=self.current.get(owner)
        if old is not None:
            certificate=self._eligible(old)
            if certificate.scope is not None:raise ValueError('A scoped completed receiver still requires its exact native retirement ACK.')
        elif len(self.captured)>=self.capacity:raise ValueError('CAS checkpoint receiver capacity reached; no original discarded.')
        return owner,old,self.captured.get(old)if old is not None else None
    def install(self,reservation,token,captured):
        self._owner();owner,old,held=reservation
        if(not _token(token)or type(captured)is not dict or self.current.get(owner)!=old or
           (old is not None and self.captured.get(old)is not held)):raise ValueError('Receiver admission reservation changed.')
        cache=owner+(token,)
        if cache in self.captured or cache in self.finished:raise ValueError('A receiver token cannot be reused.')
        if old is not None:
            certificate=self._eligible(old)
            if certificate.scope is not None:raise ValueError('Scoped receiver was not retired.')
            self._remove(old,certificate)
        elif len(self.captured)>=self.capacity:raise ValueError('Receiver capacity changed; no retained capability evicted.')
        self.captured[cache]=captured;self.current[owner]=cache;return cache
    def certify(self,key,captured,active,identity,epoch,journal_sha,plan_sha,scope=None,generation=None,native_sha=None):
        self._owner()
        if(self.captured.get(key)is not captured or self.active.get(key)is not active or self.current.get(key[:2])!=key or
           getattr(active,'state',None)!='completed'or captured.get('prepare_async_inflight')is not None or
           getattr(active,'journal_sha256',None)!=journal_sha):raise ValueError('Only the exact completed non-running receiver can be certified.')
        required=captured.get('native_return_required',False)
        if type(required)is not bool or required!=(scope is not None):raise ValueError('Completion cannot change its captured native-return requirement.')
        certificate=Completion(_ADMIT,key,identity,epoch,journal_sha,plan_sha,scope,generation,native_sha)
        old=self.ready.get(key)
        if old is not None and (old[0]is not captured or old[1]is not active or old[2]!=certificate):raise ValueError('Terminal receiver certificate changed.')
        self.ready[key]=(captured,active,certificate);return certificate
    def _remove(self,key,certificate):
        self.captured.pop(key);self.active.pop(key);self.ready.pop(key);self.current.pop(key[:2]);self.finished[key]=certificate
        while len(self.finished)>self.completed_limit:self.finished.popitem(last=False)
    def retire_unbound(self,key):
        self._owner();certificate=self._eligible(key)
        if certificate.scope is not None:raise ValueError('Native scoped receiver cannot be retired as unbound.')
        self._remove(key,certificate);return dict(retired=1,retained=0,appearance_written=False,native_replay_authorized=False)
    def retire_scope(self,path,scope,receipt):
        self._owner()
        if(type(scope)is not dict or type(receipt)is not dict or receipt.get('ok')is not True or
           receipt.get('pid')!=scope.get('pid')or receipt.get('scope_id')!=scope.get('scope_id')or
           receipt.get('armed')is not True or receipt.get('selection_enabled')is not False):raise ValueError('Verified native retirement receipt required.')
        epochs=scope.get('epochs');completions=scope.get('completions');identity=scope.get('load_identity');rows=receipt.get('members')
        if(not isinstance(epochs,dict)or not epochs or not isinstance(completions,dict)or set(epochs)!=set(completions)or
           not isinstance(identity,dict)or not _id(identity.get('save_guid'))or not _id(identity.get('household_id'))or
           not isinstance(rows,list)or len(rows)!=len(epochs)or any(type(r)is not dict for r in rows)or
           {r.get('sim_id')for r in rows}!=set(epochs)or any(type(r.get('imported_mask'))is not int or r['imported_mask']!=0 for r in rows)):raise ValueError('Complete exact native retirement roster required.')
        selected=[]
        for sid,epoch in epochs.items():
            key,_=self.lookup(path,identity['save_guid']+':'+sid);certificate=self._eligible(key);completion=completions[sid]
            if(certificate.identity!=(scope['pid'],identity['save_guid'],identity['household_id'],sid)or certificate.epoch!=epoch or
               certificate.scope!=scope['scope_id']or type(completion)is not dict or completion.get('epoch')!=epoch or
               certificate.generation!=completion.get('generation')or certificate.native_sha!=completion.get('native_return_sha256')):raise ValueError('Retirement belongs to another receiver epoch/scope/generation.')
            selected.append((key,certificate))
        # Validate every member first. A refused member never drops earlier ones.
        for key,certificate in selected:self._remove(key,certificate)
        return dict(retired=len(selected),retained=0,appearance_written=False,native_replay_authorized=False)
    def pin_prepare(self,key,captured,request_id):
        self._owner()
        if self.captured.get(key)is not captured or not _token(request_id)or captured.get('prepare_async_inflight')is not None:raise ValueError('Async receiver already running or replaced.')
        captured['prepare_async_inflight']=request_id
    def finish_prepare(self,key,captured,request_id):
        self._owner()
        if self.captured.get(key)is not captured or captured.get('prepare_async_inflight')!=request_id:raise ValueError('Async receiver completion belongs to another original UUID.')
        captured['prepare_async_inflight']=None
    def diagnostic_receipt(self,key):
        self._owner();certificate=self.finished.get(key)
        return None if certificate is None else dict(transaction_id=key[2],identity=certificate.identity,epoch=certificate.epoch,journal_sha256=certificate.journal_sha,plan_sha256=certificate.plan_sha,scope_id=certificate.scope,generation=certificate.generation,historical=True,appearance_replay_authorized=False)
