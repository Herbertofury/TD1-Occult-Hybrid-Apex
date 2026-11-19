"""Exact full-publication logical bank; native/row guards remain unchanged."""
from pathlib import Path
import cas_grid_position as previous,cas_grid_pool as pool
ROOT=Path(__file__).resolve().parents[1]
REPLACED=('ApexGridPresentationPublish',)
ADDED=('ApexGridCommitLogicalBank',)

def helpers():
 source=previous.stage.helpers()
 source=pool.edit_method(source,'ApexGridPresentationPublish',[
  ('            ApexGridSpareAfterPublish();','            ApexGridCommitLogicalBank(j);\n            ApexGridSpareAfterPublish();')])
 return source+'\n'+(ROOT/'Source/CASUi/catalog_logical_bank_methods.as').read_text()
