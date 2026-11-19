import copy
import hashlib
import unittest
from apex_core import cas_named_return,form_appearance as appearance,lifestate_forms,lifestates
from apex_core.cas_owner_payload import owner_id


class NamedReturnTests(unittest.TestCase):
    def fixture(self):
        variants={'HUMAN':('primary',),'ALIEN':('alien','disguise'),'VAMPIRE':('base','dark'),
            'MERMAID':('human','mermaid'),'WITCH':('primary','human'),
            'WEREWOLF':('beast','human','human_cc'),'FAIRY':('primary','alternate')}
        variants.update({name:spec['variants'] for name,spec in lifestates.SPECIAL.items()})
        forms={};owners=[];native={}
        def fields(value):
            return dict(physique=appearance.encode(value),genetic_data=appearance.encode(b'unknown genetic fields\x00\xff'),
                pelt_layers=appearance.encode(b'pelt'),__outfits__=appearance.encode(('protobuf',b'\xa0\x06\x01')))
        def row(oid,kind,value):
            raw=(oid+'-opaque-future-native-fields').encode()
            return dict(owner_id=oid,native_kind=kind,fields=fields(value),native_hex=raw.hex(),
                sha256=hashlib.sha256(raw).hexdigest(),linked_targets=[],revision=2)
        for state,names in variants.items():
            for variant in names:
                identity=state.lower()+'_'+variant;kind=lifestates.NATIVE.get(state,1)
                if variant in ('human','base','disguise','real'):kind=1
                original=fields('old-'+identity)
                forms[identity]=dict(id=identity,lifestate=state,label=identity,base_form=kind,
                    fields=original,appearance_sha256=appearance.fingerprint(original)['appearance_sha256'])
                owners.append(row(owner_id(state,identity),lifestate_forms.visual_form(forms[identity]),'edit-'+identity))
        # Additional user-created variants are not limited to the defaults.
        original=copy.deepcopy(forms['ghost_ghost']);original.update(id='ghost_user_variant',label='My ghost')
        forms[original['id']]=original;owners.append(row('ghost/ghost_user_variant',1,'edit-user-variant'))
        for kind in lifestates.NATIVE.values():
            owners.append(row('native/'+str(kind),kind,'native-'+str(kind)));native[str(kind)]=fields('native-'+str(kind))
        record=dict(lifestate_forms=dict(schema=1,forms=forms,active={'1':'ghost_ghost'}),other={'untouched':[1,2,3]})
        returned=dict(ok=True,source='receiver-native-owner-return',appearance_written=False,owners=owners)
        return record,returned,native

    def decisions(self,returned,action='accept-returned'):
        return [dict(owner_id=row['owner_id'],action=action) for row in returned['owners'] if not row['owner_id'].startswith(('native/','active/'))]

    def test_human_werewolf_rendering_returns_to_its_own_gameplay_lane_without_merging(self):
        record,returned,native=self.fixture()
        document,_=cas_named_return.prepare(record,returned,native,self.decisions(returned))
        human=document['forms']['werewolf_human_cc'];beast=document['forms']['werewolf_beast']
        self.assertEqual((human['base_form'],beast['base_form']),(32,32))
        self.assertNotEqual(human['fields'],beast['fields'])
        changes=cas_named_return.changes(record,returned)
        human_change=next(r for r in changes if r['owner_id']=='werewolf/werewolf_human_cc')
        self.assertEqual((human_change['native_kind'],human_change['gameplay_form']),(1,32))
        next(r for r in returned['owners'] if r['owner_id']=='werewolf/werewolf_human_cc')['native_kind']=32
        with self.assertRaisesRegex(ValueError,'rendering owner'):
            cas_named_return.prepare(record,returned,native,self.decisions(returned))

    def test_every_native_special_alternate_and_extra_form_keeps_its_own_fields(self):
        record,returned,native=self.fixture();before=copy.deepcopy(record)
        document,archive=cas_named_return.prepare(record,returned,native,self.decisions(returned))
        self.assertEqual(len(document['forms']),32)
        for identity,row in document['forms'].items():
            self.assertEqual(row['fields']['physique']['value'],'edit-user-variant' if identity=='ghost_user_variant' else 'edit-'+identity)
        self.assertEqual(document['active'],{});self.assertEqual(record,before);self.assertEqual(archive,returned)
        archive['owners'][0]['native_hex']='00';self.assertNotEqual(archive,returned)
        document['forms']['ghost_ghost']['fields']['genetic_data']['value']='changed'
        self.assertEqual(record,before)

    def test_incomplete_or_changed_owner_never_returns_a_partial_metadata_document(self):
        for damage in ('missing','duplicate','kind','field','raw','extra'):
            with self.subTest(damage=damage):
                record,returned,native=self.fixture();before=copy.deepcopy(record)
                if damage=='missing':returned['owners'].pop(0)
                elif damage=='duplicate':returned['owners'].append(copy.deepcopy(returned['owners'][0]))
                elif damage=='kind':returned['owners'][0]['native_kind']=64
                elif damage=='field':del returned['owners'][0]['fields']['genetic_data']
                elif damage=='raw':returned['owners'][0]['native_hex']='00'
                else:
                    extra=copy.deepcopy(returned['owners'][0]);extra['owner_id']='ghost/uncaptured';returned['owners'].append(extra)
                with self.assertRaises(ValueError):cas_named_return.prepare(record,returned,native,self.decisions(returned))
                self.assertEqual(record,before)

    def test_cancel_and_mixed_named_choices_do_not_accept_other_variants(self):
        record,returned,native=self.fixture();before=copy.deepcopy(record)
        with self.assertRaisesRegex(ValueError,'explicit disposition'):cas_named_return.prepare(record,returned,native,None)
        choices=self.decisions(returned,'restore-original')
        choices[0]['action']='accept-returned'
        document,_=cas_named_return.prepare(record,returned,native,choices)
        accepted=choices[0]['owner_id'].split('/')[1]
        for identity,row in document['forms'].items():
            if identity!=accepted:self.assertEqual(row,before['lifestate_forms']['forms'][identity])
        self.assertEqual(record,before)


if __name__=='__main__':unittest.main()
