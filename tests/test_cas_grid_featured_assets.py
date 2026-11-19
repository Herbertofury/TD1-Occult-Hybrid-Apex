"""Additional native asset cases; not part of the intermediate source freeze."""
import unittest
import test_cas_grid_featured as fixture

class FeaturedAssetTests(unittest.TestCase):
    case = fixture.FeaturedTests.case
    def test_native_pack_art_and_primary_thumbnail_keep_their_original_targets(self):
        self.case('''SharedIcons.SIZE_32=32;SharedIcons.GetPackIcon=(pack,size)=>'pack:'+pack+':'+size;
const g=makeFeatured();for(const item of g.mGridData.items)item.product.packId=7;
g.hooks.construct=c=>{c.mcPackIcon.LoadImage=function(resource){this.resourceId=resource;};};
g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');
for(const c of g.mCells){if(!c.item)continue;assert.equal(c.mcPackIcon.visible,true);assert.equal(c.mcPackIcon.resourceId,'pack:7:32');
 assert.ok(c.mcImage.resourceId.includes(c.item.outfit.data_id));}''')

    def test_confirmed_featured_thumbnail_failure_keeps_native_requested_resource_evidence(self):
        self.case('''const g=makeFeatured();g.failPrimary=true;g.ApexGridBegin(featureRequest(g));assert.equal(bounded(g).phase,'done');
const status=g.ApexGridStatus();assert.ok(status.thumbnail_failures.length>0);
for(const failure of status.thumbnail_failures){assert.equal(failure.ea_warning,true);assert.ok(failure.requested_resource_preview.startsWith('l_'));}
assert.ok(g.mCells.filter(c=>c.item).every(c=>c.mcImage.resourceId===SharedIcons.ICON_WARNING));''')

if __name__ == '__main__':
    unittest.main()
