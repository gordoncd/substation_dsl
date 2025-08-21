# Simple 138kV Substation Example
# This demonstrates basic equipment and connections using minimum viable DSL

# Main 138kV bus
ADD_BUS id=main-138, kv=138

# Line bay equipment
ADD_BAY id=line-bay-1, kind=LINE, kv=138, bus=main-138
ADD_BREAKER id=line-brk-1, kv=138, interrupting_kA=40, type=SF6, continuous_A=2000
ADD_DISCONNECTOR id=line-iso-1, kv=138, type=CENTER_BREAK, continuous_A=2000

# Transmission line
ADD_LINE id=tx-line-1, kv=138, type=OHL, length_km=75, thermal_A=1200

# Connection topology
CONNECT series=[main-138, line-iso-1, line-brk-1, tx-line-1]

# Add equipment to bay
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-brk-1
APPEND_TO_BAY bay_id=line-bay-1, object_id=line-iso-1

# Validate and emit
VALIDATE
EMIT_SPEC
