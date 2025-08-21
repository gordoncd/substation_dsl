# Complex 500kV/230kV/138kV transmission substation
ADD_BUS id=ehv-main-500, kv=500
ADD_BUS id=ehv-transfer-500, kv=500
ADD_BUS id=hv-main-230, kv=230
ADD_BUS id=hv-transfer-230, kv=230
ADD_BUS id=mv-bus-138, kv=138

# Multiple voltage level bays with different functions
ADD_BAY id=tx-line-bay-1, kind=LINE, kv=500, bus=ehv-main-500
ADD_BAY id=tx-line-bay-2, kind=LINE, kv=500, bus=ehv-transfer-500
ADD_BAY id=auto-tx-bay-1, kind=TRANSFORMER, kv=500, bus=ehv-main-500
ADD_BAY id=step-down-bay-1, kind=TRANSFORMER, kv=230, bus=hv-main-230
ADD_BAY id=distribution-bay-1, kind=FEEDER, kv=138, bus=mv-bus-138

# High-voltage switching equipment with precise specifications
ADD_BREAKER id=line-brk-500-1, kv=500, interrupting_kA=63, type=SF6, continuous_A=4000
ADD_BREAKER id=line-brk-500-2, kv=500, interrupting_kA=63, type=SF6, continuous_A=4000
ADD_BREAKER id=auto-tx-brk-1, kv=500, interrupting_kA=50, type=SF6, continuous_A=3000
ADD_BREAKER id=step-down-brk-1, kv=230, interrupting_kA=40, type=SF6, continuous_A=2500

# Isolation and grounding equipment
ADD_DISCONNECTOR id=line-iso-500-1, kv=500, type=DOUBLE_BREAK, continuous_A=4000
ADD_DISCONNECTOR id=line-iso-500-2, kv=500, type=DOUBLE_BREAK, continuous_A=4000
ADD_DISCONNECTOR id=tx-iso-500-1, kv=500, type=CENTER_BREAK, continuous_A=3000

# Power transformation equipment
ADD_TRANSFORMER id=auto-tx-500-230, type=AUTO, rated_MVA=300, vector_group="YNa0d11", percentZ=12.5
ADD_TRANSFORMER id=step-down-230-138, type=TWO_WINDING, rated_MVA=150, vector_group="YNd11", percentZ=8.7

# Transmission lines with thermal ratings
ADD_LINE id=tx-line-500-1, kv=500, type=OHL, length_km=127, thermal_A=3500
ADD_LINE id=tx-line-500-2, kv=500, type=OHL, length_km=89, thermal_A=3500
ADD_LINE id=distribution-line-138, kv=138, type=UGC, length_km=25, thermal_A=1800

# Bus coupling for reliability
ADD_COUPLER id=ehv-bus-coupler, kv=500, from_bus=ehv-main-500, to_bus=ehv-transfer-500
ADD_COUPLER id=hv-bus-coupler, kv=230, from_bus=hv-main-230, to_bus=hv-transfer-230

# Complex connection topology
CONNECT series=[tx-line-500-1, line-iso-500-1, line-brk-500-1, ehv-main-500]
CONNECT series=[tx-line-500-2, line-iso-500-2, line-brk-500-2, ehv-transfer-500]
CONNECT series=[ehv-main-500, ehv-bus-coupler, ehv-transfer-500]
CONNECT series=[ehv-main-500, tx-iso-500-1, auto-tx-brk-1, auto-tx-500-230, hv-main-230]
CONNECT series=[hv-main-230, step-down-brk-1, step-down-230-138, mv-bus-138]
CONNECT series=[mv-bus-138, distribution-line-138]

# Bay organization for operational control
APPEND_TO_BAY bay_id=tx-line-bay-1, object_id=line-brk-500-1
APPEND_TO_BAY bay_id=tx-line-bay-1, object_id=line-iso-500-1
APPEND_TO_BAY bay_id=tx-line-bay-2, object_id=line-brk-500-2
APPEND_TO_BAY bay_id=tx-line-bay-2, object_id=line-iso-500-2
APPEND_TO_BAY bay_id=auto-tx-bay-1, object_id=auto-tx-brk-1
APPEND_TO_BAY bay_id=auto-tx-bay-1, object_id=tx-iso-500-1
APPEND_TO_BAY bay_id=step-down-bay-1, object_id=step-down-brk-1

VALIDATE
EMIT_SPEC