"""Portable AST contracts for unchanged receiver/storage/owner guards."""
from pathlib import Path
import ast
import hashlib
import json

CONTRACTS=Path(__file__).resolve().parent/'fixtures/receiver_guard_contracts.json'


def semantic(value):
    """Normalize only AST representation changes, never executable operands."""
    if isinstance(value,ast.AST):
        name=type(value).__name__
        if name=='Index':return semantic(value.value)
        if name in ('Constant','Num','Str','Bytes','NameConstant'):
            literal=getattr(value,'value',getattr(value,'n',getattr(value,'s',None)))
            kind=type(literal).__name__
            if isinstance(literal,bytes):literal={'bytes_hex':literal.hex()}
            return ['literal',kind,literal]
        fields=[]
        for key,item in ast.iter_fields(value):
            if key in ('type_params','posonlyargs') and item==[]:continue # Empty syntax fields added after Python3.7.
            if key=='type_comment' and item is None:continue
            fields.append([key,semantic(item)])
        return [name,fields]
    if isinstance(value,list):return [semantic(item)for item in value]
    return value


def digest(node):
    return hashlib.sha256(json.dumps(semantic(node),sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def module_members(path):
    tree=ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    return {node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}


def assert_contract(testcase,module,key):
    document=json.loads(CONTRACTS.read_text(encoding='utf-8'))
    actual=module_members(module.__file__)
    for name,expected in document['unchanged_guards'][key].items():
        testcase.assertIn(name,actual)
        testcase.assertEqual(digest(actual[name]),expected,key+'.'+name)


def legacy_hair_helper(namespace):
    """Historical warm-index policy for the actual old-vs-new callback proof."""
    document=json.loads(CONTRACTS.read_text(encoding='utf-8'))
    source=document['legacy_hair_policy_enabled_source']
    code=ast.parse(source);function=code.body[0]
    if function.name!='hair_policy_enabled' or digest(function)!=document['legacy_hair_policy_enabled_digest']:
        raise AssertionError('Historical hair policy fixture differs from its reviewed contract.')
    target={};exec(compile(code,'reviewed-historical-hair-helper','exec'),namespace,target)
    return target['hair_policy_enabled']
