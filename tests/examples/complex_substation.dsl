# Complex Multi-Voltage Substation Example
# Demonstrates advanced features using minimum viable DSL

# 230kV System
ADD_BUS id=main-230, kv=230
ADD_BUS id=xfer-230, kv=230

# 138kV System  
ADD_BUS id=main-138, kv=138
ADD_BUS id=xfer-138, kv=138

# 13.8kV Distribution
ADD_BUS id=dist-13p8, kv=13.8

# 230kV Line Bay
ADD_BAY id=line-230-1, kind=LINE, kv=230, bus=main-230
ADD_BREAKER id=brk-230-1, kv=230, interrupting_kA=63, type=SF6, continuous_A=3000
ADD_DISCONNECTOR id=iso-230-1a, kv=230, type=PANTOGRAPH, continuous_A=3000
ADD_DISCONNECTOR id=iso-230-1b, kv=230, type=PANTOGRAPH, continuous_A=3000
ADD_LINE id=line-230-east, kv=230, type=OHL, length_km=125, thermal_A=2400

# Main Transformer
ADD_BAY id=xfmr-main, kind=TRANSFORMER, kv=230, bus=main-230
ADD_BREAKER id=brk-xfmr-230, kv=230, interrupting_kA=63, type=SF6, continuous_A=3000
ADD_BREAKER id=brk-xfmr-138, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_TRANSFORMER id=main-xfmr, type=AUTO, rated_MVA=300, vector_group="YNa0", percentZ=12.5

# Distribution Transformer
ADD_BAY id=xfmr-dist, kind=TRANSFORMER, kv=138, bus=main-138
ADD_BREAKER id=brk-dist-138, kv=138, interrupting_kA=40, type=SF6, continuous_A=1200
ADD_BREAKER id=brk-dist-13p8, kv=13.8, interrupting_kA=25, type=VACUUM, continuous_A=800
ADD_TRANSFORMER id=dist-xfmr, type=TWO_WINDING, rated_MVA=25, vector_group="Dy1", percentZ=8.5

# Bus Couplers
ADD_COUPLER id=coupler-230, kv=230, from_bus=main-230, to_bus=xfer-230
ADD_COUPLER id=coupler-138, kv=138, from_bus=main-138, to_bus=xfer-138

# Connection Topology
CONNECT series=[main-230, iso-230-1a, brk-230-1, iso-230-1b, line-230-east]
CONNECT series=[main-230, brk-xfmr-230, main-xfmr, brk-xfmr-138, main-138]
CONNECT series=[main-138, brk-dist-138, dist-xfmr, brk-dist-13p8, dist-13p8]

# Assign equipment to bays
APPEND_TO_BAY bay_id=line-230-1, object_id=brk-230-1
APPEND_TO_BAY bay_id=line-230-1, object_id=iso-230-1a
APPEND_TO_BAY bay_id=line-230-1, object_id=iso-230-1b
APPEND_TO_BAY bay_id=xfmr-main, object_id=brk-xfmr-230
APPEND_TO_BAY bay_id=xfmr-main, object_id=main-xfmr
APPEND_TO_BAY bay_id=xfmr-dist, object_id=brk-dist-138
APPEND_TO_BAY bay_id=xfmr-dist, object_id=dist-xfmr

# Validate and emit
VALIDATE
EMIT_SPEC
