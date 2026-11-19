"""Exercise the actual search layout methods without querying or changing CAS."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'Source/CASUi/catalog_search_methods.as'


def javascript_function(name, parameters=''):
    part = SOURCE.read_text(encoding='utf-8').split('private function ' + name + '(', 1)[1]
    part = re.split(r'\n      private function ', part, maxsplit=1)[0]
    body = part.split('{', 1)[1].rsplit('}', 1)[0]
    body = re.sub(r'\b(var\s+\w+)\s*:\s*[\w.]+', r'\1', body)
    body = re.sub(r'\s+as\s+flash\.[\w.]+', '', body)
    return 'function ' + name + '(' + parameters + '){' + body + '}\n'


@unittest.skipUnless(shutil.which('node'), 'Node is required for the AS layout harness')
class SearchLayoutTests(unittest.TestCase):
    def run_case(self, case):
        script = '''
const assert=require('node:assert/strict');
class Sprite{
    constructor(){this.x=0;this.y=0;this.width=0;this.height=0;this.parent=null;this.visible=true;
        this.graphics={clear(){},lineStyle(){},beginFill(){},drawRoundRect(){},drawRect(){},endFill(){}};this.children=[];}
    addChild(child){this.children.push(child);child.parent=this;return child;}
    removeChild(child){this.children.splice(this.children.indexOf(child),1);child.parent=null;}
    addEventListener(){}
}
class TextField extends Sprite{}
var flash={display:{Sprite},text:{TextField,TextFieldType:{INPUT:'input'},TextFormat:class{constructor(font,size,color){Object.assign(this,{font,size,color});}}},
    events:{Event:{CHANGE:'change'},KeyboardEvent:{KEY_DOWN:'keyDown'},FocusEvent:{FOCUS_IN:'focusIn',FOCUS_OUT:'focusOut'},MouseEvent:{CLICK:'click'}}};
var apexSearch={root:null,geometry:null,bubble:null,list:null,width:-1,text:'',suggestions:null,suggestion_signature:''};
function ApexFormsText(parent,text,x,y,width,size,color){const field=new TextField();Object.assign(field,{text,x,y,width,size,color});return parent.addChild(field);}
function ApexSearchChanged(){}function ApexSearchKey(){}function ApexSearchFocus(){}function ApexSearchClear(){}function ApexSearchLabels(){}
function palette(y){const value=new Sprite();Object.assign(value,{y,mouseEnabled:true,mouseChildren:true,selectedColor:'native-color',nativeCallback:{}});return value;}
function panel(bubbleY=146,listY=210,paletteY=176){
    const value=new Sprite();value.mcFilterPane=new Sprite();value.addChild(value.mcFilterPane);
    const bubble=new Sprite();Object.assign(bubble,{x:20,y:bubbleY,mcBackground:{width:565}});
    value.mcFilterPane.mcFilterBubble=value.mcFilterPane.addChild(bubble);
    value.mcTileList=value.addChild(new Sprite());Object.assign(value.mcTileList,{y:listY,height:1120});
    value.mcColorSwatchPanel=value.addChild(palette(paletteY));return value;
}
function nativeState(value){return {visible:value.visible,mouseEnabled:value.mouseEnabled,mouseChildren:value.mouseChildren,
    selectedColor:value.selectedColor,nativeCallback:value.nativeCallback};}
''' + javascript_function('ApexSearchRestore') + javascript_function('ApexSearchAttach', 'panel') + case
        result = subprocess.run(['node', '-e', script], capture_output=True,
                                text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_repeated_attach_and_restore_keep_one_row_and_preserve_palette_input(self):
        self.run_case('''
const p=panel(),swatches=p.mcColorSwatchPanel,state=nativeState(swatches);
for(let i=0;i<25;i++)ApexSearchAttach(p);
assert.equal(swatches.y,228);assert.equal(p.mcFilterPane.mcFilterBubble.y,198);assert.equal(p.mcTileList.y,262);
assert.equal(p.mcTileList.height,1068);assert.equal(apexSearch.root.y,172);
assert.equal(apexSearch.input.width,485);assert.equal(apexSearch.placeholder.width,485);assert.deepEqual(nativeState(swatches),state);
p.mcFilterPane.mcFilterBubble.mcBackground.width=300;ApexSearchAttach(p);
assert.equal(apexSearch.placeholder.width,220);assert.equal(apexSearch.input.width,220);
ApexSearchRestore();assert.equal(swatches.y,176);assert.equal(p.mcFilterPane.mcFilterBubble.y,146);
assert.equal(p.mcTileList.y,210);assert.equal(p.mcTileList.height,1120);assert.deepEqual(nativeState(swatches),state);
assert.equal(apexSearch.root,null);ApexSearchRestore();assert.equal(swatches.y,176);
''')

    def test_native_relayout_is_rebased_without_accumulating_an_offset(self):
        self.run_case('''
const p=panel();ApexSearchAttach(p);
p.mcColorSwatchPanel.y=190;p.mcFilterPane.mcFilterBubble.y=160;p.mcTileList.y=230;p.mcTileList.height=1080;
for(let i=0;i<25;i++)ApexSearchAttach(p);
assert.equal(p.mcColorSwatchPanel.y,242);assert.equal(p.mcFilterPane.mcFilterBubble.y,212);
assert.equal(p.mcTileList.y,282);assert.equal(p.mcTileList.height,1028);
ApexSearchRestore();assert.equal(p.mcColorSwatchPanel.y,190);assert.equal(p.mcFilterPane.mcFilterBubble.y,160);
assert.equal(p.mcTileList.y,230);assert.equal(p.mcTileList.height,1080);
''')

    def test_panel_and_palette_replacement_restore_only_owned_positions(self):
        self.run_case('''
const first=panel(),second=panel(100,200,150);ApexSearchAttach(first);ApexSearchAttach(second);
assert.equal(first.mcColorSwatchPanel.y,176);assert.equal(first.mcFilterPane.mcFilterBubble.y,146);
assert.equal(first.mcTileList.y,210);assert.equal(second.mcColorSwatchPanel.y,202);
const old=second.mcColorSwatchPanel;second.removeChild(old);second.mcColorSwatchPanel=second.addChild(palette(300));
ApexSearchAttach(second);assert.equal(old.y,150);assert.equal(second.mcColorSwatchPanel.y,352);
second.mcColorSwatchPanel.y=777;ApexSearchRestore();assert.equal(second.mcColorSwatchPanel.y,777);
''')

    def test_hidden_absent_and_removed_native_palettes_keep_native_visibility(self):
        self.run_case('''
const p=panel();p.mcColorSwatchPanel.visible=false;p.mcColorSwatchPanel.mouseEnabled=false;
const original=p.mcColorSwatchPanel,state=nativeState(original);ApexSearchAttach(p);
assert.equal(original.y,228);assert.deepEqual(nativeState(original),state);
delete p.mcColorSwatchPanel;ApexSearchAttach(p);assert.equal(original.y,176);
assert.deepEqual(nativeState(original),state);ApexSearchRestore();
const noPalette=panel();delete noPalette.mcColorSwatchPanel;ApexSearchAttach(noPalette);ApexSearchRestore();
assert.equal('mcColorSwatchPanel' in noPalette,false);
''')


if __name__ == '__main__':
    unittest.main()
