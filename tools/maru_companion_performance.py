"""Narrow lazy-swatch adapters for the pinned, private donor sources.

Keep the actual donor UI and its handlers. A closed, unhovered card does not
need hundreds of live color-button display objects. The complete original
Decorate body follows the early return and still handles hover/open normally.
No decompiled third-party source is stored in this module.
"""
ROUTES = ('dcc.history.HairSwatches', 'dcc.history.SwatchRepair')
PREFERENCES = 'widgets.CAS.dcc.DCCFavorites'


def preferences(source):
    """Resolve the same live settings map once per lookup, not per legacy key.

    The native getter can cross into the game to resolve the account. Keep the
    shared false override, all fourteen legacy categories and extra types.
    Do not copy the preference values or invent an account identity.
    """
    start = source.index('      public static function Has(')
    end = source.index('      public static function Toggle(', start)
    before = source[start:end]
    anchor = '         var _loc4_:* = UISettings.AccountSettings.GetValue(_loc3_);'
    if before.count(anchor) != 1 or before.count('UISettings.AccountSettings') != 3:
        raise ValueError('Pinned favorite lookup boundary differs')
    after = before.replace('UISettings.AccountSettings', 'settings')
    after = after.replace('         var _loc4_:* = settings.GetValue(_loc3_);',
                          '         var settings:Object = UISettings.AccountSettings;\n'
                          '         var _loc4_:* = settings.GetValue(_loc3_);')
    return source[:start] + after + source[end:]


def inject(name, source):
    if name not in ROUTES:
        raise ValueError('Unreviewed lazy-swatch adapter')
    if name.endswith('HairSwatches'):
        anchor = '         var type:int = Type(int(states[product]));'
        guard = '''         // Apex: populate this card's swatches only while visible.
         if(!over && origin !== cell)
         {
            if(cell.btnVariationStackContainer)
            {
               cell.btnVariationStackContainer.visible = false;
               cell.btnVariationStackContainer.Selected = false;
               if(cell.btnVariationStackContainer.mcArrow)
               {
                  cell.btnVariationStackContainer.mcArrow.alpha = 0;
               }
            }
            return;
         }
'''
    else:
        anchor = '         var feed:SelectableArrayDataFeed = p.GetColorSwatchDataFeed();'
        guard = '''         // Apex: preserve an open grid; defer a closed card's grid.
         if(!over && Base() !== p)
         {
            button.visible = false;
            button.Selected = false;
            if(button.mcArrow)
            {
               button.mcArrow.alpha = 0;
            }
            return;
         }
'''
    if source.count(anchor) != 1 or '// Apex:' in source:
        raise ValueError('Pinned donor lazy-swatch boundary differs: ' + name)
    return source.replace(anchor, guard + anchor)
