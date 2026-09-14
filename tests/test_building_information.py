"""Building-card prose boundaries and live selection survival/invalidation."""
from copy import deepcopy
import struct
import unittest
from test_surface import surface_session
from test_colony import definition,building
from openreunion.core import GameError
from openreunion.dos.building_information import building_description,building_lines,statistics
from openreunion.dos.surface_screen import SurfaceView


class BuildingInformationTests(unittest.TestCase):
    def test_description_records_do_not_leak_into_next_building(self):
        lines=[f'Building {i//6+1}' if i%6==0 else f'Line {i}' for i in range(150)]+['']*6
        self.assertEqual(building_description(lines,25),{'title':'Building 25','description':'Line 145 Line 146 Line 147 Line 148 Line 149'})
        self.assertEqual(building_lines(lines,1),lines[:6])
        for invalid in (lines[:149],lines+[''],lines[:150]+['extra record']):
            with self.assertRaises(GameError):building_lines(invalid,25)
        for identity in (0,26,True):
            with self.assertRaises(GameError):building_lines(lines,identity)

    def test_mine_abundance_differs_from_generator_condition_output(self):
        mine=definition(4,category=2,workers=12,power=100,output=10);mine['price']=123
        raw=[0]*65;row=building(4)
        self.assertEqual(dict(statistics(mine,raw))[1],'Production : mine')
        self.assertEqual(dict(statistics(mine,raw,row))[1],'Production : NONE')
        raw[59]=255
        self.assertEqual(dict(statistics(mine,raw,row))[1],'Production : 25 t/ptp')
        generator=definition(6,category=1,workers=12,output=117);generator['price']=999
        row[7]=87;row[13]=63
        self.assertEqual(dict(statistics(generator,raw,row))[1],'Production : 63 kwh')
        self.assertEqual(dict(statistics(generator,raw,row))[3],'Working    : 63%')

    def test_unsigned_live_assignments_and_inactive_values(self):
        item=definition(2,category=3,workers=100,power=250);item['price']=999
        row=building(2);row[9:13]=struct.pack('<HH',65535,32768)
        self.assertEqual(dict(statistics(item,[0]*65,row)),{0:'Status     : Active',1:'Workers    : 65535/100',2:'Energy     : 32768 kwh',3:'Working    : 100%'})
        row[8]=0
        self.assertEqual(dict(statistics(item,[0]*65,row)),{0:'Status     : Passive',1:'Workers    : 0/100',2:'Energy     : 0 kwh',3:'Working    : 0%'})

    def test_information_survives_live_updates_but_closes_on_replaced_row(self):
        session=surface_session();row=building(2);row[4:6]=[2,3];session.state['buildings']=[row]
        view=SurfaceView(selected=2,mode='info',inspected=0);view.sync(session.state,session.catalog)
        session.state=deepcopy(session.state);session.state['buildings'][0][6:14]=[0,99,0,0,0,0,0,0]
        view.sync(session.state,session.catalog)
        self.assertEqual((view.mode,view.inspected),('info',0))
        self.assertTrue(all(t[2]==('surface_close_info',) for t in view.targets()))
        session.state['buildings'][0][4]=3;view.sync(session.state,session.catalog)
        self.assertEqual((view.mode,view.inspected,view.inspected_identity),('inspect',None,None))

    def test_compacted_building_indices_cannot_inspect_another_structure(self):
        session=surface_session();session.state['buildings']=[building(2),building(3),building(4)]
        view=SurfaceView(selected=3,mode='info',inspected=1);view.sync(session.state,session.catalog)
        session.state['buildings'].pop(0);view.sync(session.state,session.catalog)
        self.assertEqual((view.mode,view.inspected),('inspect',None))


if __name__=='__main__':unittest.main()
