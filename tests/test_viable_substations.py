#!/usr/bin/env python3
"""
Test suite for minimum viable DSL - tests building different types of substations
using only the supported commands: ADD_BUS, ADD_BAY, ADD_COUPLER, ADD_BREAKER, 
ADD_DISCONNECTOR, ADD_TRANSFORMER, ADD_LINE, CONNECT, APPEND_TO_BAY, VALIDATE, EMIT_SPEC
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dsl.parser import parse, ParseError


class TestViableSubstations(unittest.TestCase):
    """Test building different viable substations with minimum DSL"""

    def test_simple_transmission_substation(self):
        """Test a basic 138kV transmission substation with one line bay"""
        dsl = """
# Simple 138kV Transmission Substation
ADD_BUS id=main-138, kv=138
ADD_BAY id=line-bay-1, kind=LINE, kv=138, bus=main-138
ADD_BREAKER id=line-brk-1, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_DISCONNECTOR id=line-iso-1, kv=138, type=CENTER_BREAK, continuous_A=2000
ADD_LINE id=transmission-line-1, kv=138, type=OHL, length_km=50, thermal_A=1500

CONNECT series=[main-138, line-iso-1, line-brk-1, transmission-line-1]
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-brk-1
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-iso-1

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify basic structure
        self.assertEqual(len(result.objects), 5)
        self.assertEqual(len(result.series), 1)
        
        # Check objects exist
        self.assertIn('main-138', result.objects)
        self.assertIn('line-bay-1', result.objects)
        self.assertIn('line-brk-1', result.objects)
        self.assertIn('line-iso-1', result.objects)
        self.assertIn('transmission-line-1', result.objects)
        
        # Verify object types
        self.assertEqual(result.objects['main-138'].type, 'BUS')
        self.assertEqual(result.objects['line-bay-1'].type, 'BAY')
        self.assertEqual(result.objects['line-brk-1'].type, 'BREAKER')
        self.assertEqual(result.objects['line-iso-1'].type, 'DISCONNECTOR')
        self.assertEqual(result.objects['transmission-line-1'].type, 'LINE')

    def test_distribution_substation(self):
        """Test a distribution substation with transformer"""
        dsl = """
# 138kV/13.8kV Distribution Substation
ADD_BUS id=hv-bus-138, kv=138
ADD_BUS id=lv-bus-13p8, kv=13.8

ADD_BAY id=source-bay, kind=LINE, kv=138, bus=hv-bus-138
ADD_BAY id=transformer-bay, kind=TRANSFORMER, kv=138, bus=hv-bus-138
ADD_BAY id=feeder-bay-1, kind=FEEDER, kv=13.8, bus=lv-bus-13p8

ADD_BREAKER id=source-brk, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_BREAKER id=tx-hv-brk, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_BREAKER id=feeder-brk-1, kv=13.8, interrupting_kA=25, type=VACUUM, continuous_A=1200

ADD_DISCONNECTOR id=source-iso, kv=138, type=CENTER_BREAK, continuous_A=2000
ADD_DISCONNECTOR id=tx-hv-iso, kv=138, type=CENTER_BREAK, continuous_A=2000

ADD_TRANSFORMER id=main-tx-1, type=TWO_WINDING, rated_MVA=50, vector_group="Dy11", percentZ=8.5

ADD_LINE id=source-line, kv=138, type=OHL, length_km=25, thermal_A=1800
ADD_LINE id=feeder-line-1, kv=13.8, type=UGC, length_km=5, thermal_A=800

# High voltage side connections
CONNECT series=[source-line, source-iso, source-brk, hv-bus-138]
CONNECT series=[hv-bus-138, tx-hv-iso, tx-hv-brk, main-tx-1]

# Low voltage side connection
CONNECT series=[main-tx-1, lv-bus-13p8, feeder-brk-1, feeder-line-1]

# Bay assignments
APPEND_TO_BAY bay_id=source-bay, object_id=source-brk
APPEND_TO_BAY bay_id=source-bay, object_id=source-iso
APPEND_TO_BAY bay_id=transformer-bay, object_id=tx-hv-brk
APPEND_TO_BAY bay_id=transformer-bay, object_id=tx-hv-iso
APPEND_TO_BAY bay_id=feeder-bay-1, object_id=feeder-brk-1

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify comprehensive structure
        self.assertEqual(len(result.objects), 13)
        self.assertEqual(len(result.series), 3)
        
        # Check transformer exists and has correct properties
        tx = result.objects['main-tx-1']
        self.assertEqual(tx.type, 'TRANSFORMER')
        self.assertEqual(tx.attrs['rated_MVA'], 50)
        self.assertEqual(tx.attrs['vector_group'], 'Dy11')
        self.assertEqual(tx.attrs['percentZ'], 8.5)

    def test_switching_station(self):
        """Test a switching station with bus coupler"""
        dsl = """
# 230kV Switching Station with Bus Coupler
ADD_BUS id=bus-a-230, kv=230
ADD_BUS id=bus-b-230, kv=230

ADD_BAY id=line-bay-1, kind=LINE, kv=230, bus=bus-a-230
ADD_BAY id=line-bay-2, kind=LINE, kv=230, bus=bus-b-230
ADD_BAY id=coupler-bay, kind=COUPLER, kv=230, bus=bus-a-230

ADD_BREAKER id=line-1-brk, kv=230, interrupting_kA=63, type=SF6, continuous_A=3000
ADD_BREAKER id=line-2-brk, kv=230, interrupting_kA=63, type=SF6, continuous_A=3000
ADD_BREAKER id=coupler-brk, kv=230, interrupting_kA=63, type=SF6, continuous_A=3000

ADD_DISCONNECTOR id=line-1-iso-a, kv=230, type=DOUBLE_BREAK, continuous_A=3000
ADD_DISCONNECTOR id=line-1-iso-b, kv=230, type=DOUBLE_BREAK, continuous_A=3000
ADD_DISCONNECTOR id=line-2-iso-a, kv=230, type=DOUBLE_BREAK, continuous_A=3000
ADD_DISCONNECTOR id=line-2-iso-b, kv=230, type=DOUBLE_BREAK, continuous_A=3000

ADD_COUPLER id=bus-coupler, kv=230, from_bus=bus-a-230, to_bus=bus-b-230

ADD_LINE id=tx-line-1, kv=230, type=OHL, length_km=100, thermal_A=2500
ADD_LINE id=tx-line-2, kv=230, type=OHL, length_km=75, thermal_A=2500

# Line 1 connections (Bus A)
CONNECT series=[tx-line-1, line-1-iso-a, line-1-brk, line-1-iso-b, bus-a-230]

# Line 2 connections (Bus B)
CONNECT series=[tx-line-2, line-2-iso-a, line-2-brk, line-2-iso-b, bus-b-230]

# Bus coupler connection
CONNECT series=[bus-a-230, bus-coupler, coupler-brk, bus-b-230]

# Bay assignments
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-1-brk
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-1-iso-a
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-1-iso-b
APPEND_TO_BAY bay_id=line-bay-2, object_id=line-2-brk
APPEND_TO_BAY bay_id=line-bay-2, object_id=line-2-iso-a
APPEND_TO_BAY bay_id=line-bay-2, object_id=line-2-iso-b
APPEND_TO_BAY bay_id=coupler-bay, object_id=coupler-brk

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify switching station structure
        self.assertEqual(len(result.objects), 15)
        self.assertEqual(len(result.series), 3)
        
        # Check bus coupler
        coupler = result.objects['bus-coupler']
        self.assertEqual(coupler.type, 'COUPLER')
        self.assertEqual(coupler.attrs['from_bus'], 'bus-a-230')
        self.assertEqual(coupler.attrs['to_bus'], 'bus-b-230')

    def test_industrial_substation(self):
        """Test an industrial substation with multiple feeders"""
        dsl = """
# Industrial Plant 138kV/4.16kV Substation
ADD_BUS id=incoming-138, kv=138
ADD_BUS id=plant-4p16, kv=4.16

ADD_BAY id=incoming-bay, kind=LINE, kv=138, bus=incoming-138
ADD_BAY id=main-tx-bay, kind=TRANSFORMER, kv=138, bus=incoming-138
ADD_BAY id=motor-feeder-1, kind=FEEDER, kv=4.16, bus=plant-4p16
ADD_BAY id=motor-feeder-2, kind=FEEDER, kv=4.16, bus=plant-4p16
ADD_BAY id=lighting-feeder, kind=FEEDER, kv=4.16, bus=plant-4p16

# Incoming line equipment
ADD_BREAKER id=incoming-brk, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_DISCONNECTOR id=incoming-iso, kv=138, type=CENTER_BREAK, continuous_A=2000

# Transformer equipment
ADD_BREAKER id=tx-hv-brk, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_TRANSFORMER id=plant-tx, type=TWO_WINDING, rated_MVA=20, vector_group="Dy1", percentZ=6.5

# Low voltage feeders
ADD_BREAKER id=motor-1-brk, kv=4.16, interrupting_kA=15, type=VACUUM, continuous_A=800
ADD_BREAKER id=motor-2-brk, kv=4.16, interrupting_kA=15, type=VACUUM, continuous_A=800
ADD_BREAKER id=lighting-brk, kv=4.16, interrupting_kA=15, type=VACUUM, continuous_A=400

# External connections
ADD_LINE id=utility-line, kv=138, type=OHL, length_km=15, thermal_A=1500
ADD_LINE id=motor-cable-1, kv=4.16, type=UGC, length_km=0.5, thermal_A=600
ADD_LINE id=motor-cable-2, kv=4.16, type=UGC, length_km=0.3, thermal_A=600
ADD_LINE id=lighting-cable, kv=4.16, type=UGC, length_km=0.2, thermal_A=300

# High voltage side
CONNECT series=[utility-line, incoming-iso, incoming-brk, incoming-138]
CONNECT series=[incoming-138, tx-hv-brk, plant-tx]

# Low voltage side
CONNECT series=[plant-tx, plant-4p16, motor-1-brk, motor-cable-1]
CONNECT series=[plant-4p16, motor-2-brk, motor-cable-2]
CONNECT series=[plant-4p16, lighting-brk, lighting-cable]

# Bay assignments
APPEND_TO_BAY bay_id=incoming-bay, object_id=incoming-brk
APPEND_TO_BAY bay_id=incoming-bay, object_id=incoming-iso
APPEND_TO_BAY bay_id=main-tx-bay, object_id=tx-hv-brk
APPEND_TO_BAY bay_id=motor-feeder-1, object_id=motor-1-brk
APPEND_TO_BAY bay_id=motor-feeder-2, object_id=motor-2-brk
APPEND_TO_BAY bay_id=lighting-feeder, object_id=lighting-brk

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify industrial substation
        self.assertEqual(len(result.objects), 18)
        self.assertEqual(len(result.series), 5)
        
        # Check low voltage equipment exists
        self.assertTrue(any(obj.attrs.get('kv') == 4.16 for obj in result.objects.values()))

    def test_minimal_substation(self):
        """Test the absolute minimum viable substation"""
        dsl = """
ADD_BUS id=simple-bus, kv=69
ADD_LINE id=simple-line, kv=69, type=OHL, length_km=10, thermal_A=1000
CONNECT series=[simple-bus, simple-line]
VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        self.assertEqual(len(result.objects), 2)
        self.assertEqual(len(result.series), 1)
        self.assertIn('simple-bus', result.objects)
        self.assertIn('simple-line', result.objects)

    def test_equipment_types_coverage(self):
        """Test all supported equipment types and parameters"""
        dsl = """
# Test all equipment types with different parameters

# Different bus voltages
ADD_BUS id=bus-765, kv=765
ADD_BUS id=bus-345, kv=345
ADD_BUS id=bus-138, kv=138
ADD_BUS id=bus-69, kv=69
ADD_BUS id=bus-25, kv=25
ADD_BUS id=bus-13p8, kv=13.8
ADD_BUS id=bus-4p16, kv=4.16

# Different bay types
ADD_BAY id=line-bay, kind=LINE, kv=138, bus=bus-138
ADD_BAY id=tx-bay, kind=TRANSFORMER, kv=138, bus=bus-138
ADD_BAY id=feeder-bay, kind=FEEDER, kv=13.8, bus=bus-13p8
ADD_BAY id=shunt-bay, kind=SHUNT, kv=138, bus=bus-138
ADD_BAY id=coupler-bay, kind=COUPLER, kv=138, bus=bus-138
ADD_BAY id=gen-bay, kind=GENERATOR, kv=25, bus=bus-25

# Different breaker types and ratings
ADD_BREAKER id=sf6-brk, kv=345, interrupting_kA=63, type=SF6, continuous_A=4000
ADD_BREAKER id=vacuum-brk, kv=25, interrupting_kA=31.5, type=VACUUM, continuous_A=1200
ADD_BREAKER id=oil-brk, kv=138, interrupting_kA=40, type=OIL, continuous_A=2000
ADD_BREAKER id=airblast-brk, kv=765, interrupting_kA=100, type=AIRBLAST, continuous_A=5000

# Different disconnector types
ADD_DISCONNECTOR id=center-break, kv=138, type=CENTER_BREAK, continuous_A=2000
ADD_DISCONNECTOR id=double-break, kv=345, type=DOUBLE_BREAK, continuous_A=4000
ADD_DISCONNECTOR id=pantograph, kv=765, type=PANTOGRAPH, continuous_A=5000
ADD_DISCONNECTOR id=earth-switch, kv=138, type=EARTH_SWITCH_COMBINED, continuous_A=2000

# Different transformer types
ADD_TRANSFORMER id=two-winding, type=TWO_WINDING, rated_MVA=100, vector_group="Dy11", percentZ=12.5
ADD_TRANSFORMER id=auto-tx, type=AUTO, rated_MVA=500, vector_group="YNa0", percentZ=8.0
ADD_TRANSFORMER id=three-winding, type=THREE_WINDING, rated_MVA=300, vector_group="YNynd11", percentZ=15.0
ADD_TRANSFORMER id=grounding-tx, type=GROUNDING, rated_MVA=25, vector_group="Zn", percentZ=5.0

# Different line types
ADD_LINE id=overhead-line, kv=345, type=OHL, length_km=150, thermal_A=3000
ADD_LINE id=underground-cable, kv=138, type=UGC, length_km=8, thermal_A=1500

# Bus coupler
ADD_COUPLER id=bus-tie, kv=138, from_bus=bus-138, to_bus=bus-69

# Sample connections
CONNECT series=[bus-345, sf6-brk, overhead-line]
CONNECT series=[bus-138, center-break, oil-brk, two-winding]

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify all equipment types are created
        equipment_types = {obj.type for obj in result.objects.values()}
        expected_types = {'BUS', 'BAY', 'BREAKER', 'DISCONNECTOR', 'TRANSFORMER', 'LINE', 'COUPLER'}
        self.assertEqual(equipment_types, expected_types)
        
        # Check we have variety in parameters
        kv_levels = {obj.attrs.get('kv') for obj in result.objects.values() if 'kv' in obj.attrs}
        self.assertGreaterEqual(len(kv_levels), 5)  # Multiple voltage levels

    def test_error_handling(self):
        """Test that invalid DSL produces appropriate errors"""
        
        # Missing required parameter
        with self.assertRaises(ParseError):
            parse("ADD_BUS id=bad-bus")  # Missing kv
        
        # Invalid enum value
        with self.assertRaises(ParseError):
            parse("ADD_BREAKER id=bad-brk, kv=138, interrupting_kA=40, type=INVALID_TYPE, continuous_A=2000")
            
        # Invalid syntax
        with self.assertRaises(ParseError):
            parse("ADD_BUS id=bad-bus kv=138")  # Missing comma

    def test_complex_connections(self):
        """Test complex series connections with multiple paths"""
        dsl = """
# Complex substation with multiple connection paths
ADD_BUS id=main-230, kv=230
ADD_BUS id=transfer-230, kv=230
ADD_BUS id=dist-69, kv=69

ADD_BREAKER id=line-1-brk, kv=230, interrupting_kA=50, type=SF6, continuous_A=3000
ADD_BREAKER id=line-2-brk, kv=230, interrupting_kA=50, type=SF6, continuous_A=3000
ADD_BREAKER id=tx-hv-brk, kv=230, interrupting_kA=50, type=SF6, continuous_A=3000
ADD_BREAKER id=dist-brk, kv=69, interrupting_kA=25, type=VACUUM, continuous_A=1500

ADD_DISCONNECTOR id=line-1-iso, kv=230, type=DOUBLE_BREAK, continuous_A=3000
ADD_DISCONNECTOR id=line-2-iso, kv=230, type=DOUBLE_BREAK, continuous_A=3000

ADD_TRANSFORMER id=step-down-tx, type=TWO_WINDING, rated_MVA=75, vector_group="YNd11", percentZ=10.2

ADD_LINE id=transmission-1, kv=230, type=OHL, length_km=80, thermal_A=2800
ADD_LINE id=transmission-2, kv=230, type=OHL, length_km=60, thermal_A=2800
ADD_LINE id=distribution-1, kv=69, type=OHL, length_km=20, thermal_A=1200

ADD_COUPLER id=bus-tie, kv=230, from_bus=main-230, to_bus=transfer-230

# Multiple series connections creating a networked topology
CONNECT series=[transmission-1, line-1-iso, line-1-brk, main-230]
CONNECT series=[transmission-2, line-2-iso, line-2-brk, transfer-230]
CONNECT series=[main-230, bus-tie, transfer-230]
CONNECT series=[main-230, tx-hv-brk, step-down-tx, dist-69]
CONNECT series=[dist-69, dist-brk, distribution-1]

VALIDATE
EMIT_SPEC
        """
        result = parse(dsl)
        
        # Verify complex connections
        self.assertEqual(len(result.objects), 14)
        self.assertEqual(len(result.series), 5)  # 5 different series connections


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
