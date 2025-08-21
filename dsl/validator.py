from .ir_types import IR

class DSLValidationError(Exception):
    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code

def _kv_of(ir: IR, obj_id: str) -> float | None:
    o = ir.objects.get(obj_id)
    if not o:
        return None
    # keys differ by type; for buses use attrs['kv']; for devices use attrs['kv']
    return o.attrs.get("kv")

def validate(ir: IR) -> None:
    # 1) ID uniqueness
    if len(set(ir.objects.keys())) != len(ir.objects):
        raise DSLValidationError("E.ID.DUP", "Duplicate object ids found.")

    # 2) CONNECT chains non-empty; allow OPEN_END/STUB at edges only
    for chain in ir.series:
        if not chain:
            raise DSLValidationError("E.CONNECT.EMPTY", "Empty CONNECT series.")
        for i, itm in enumerate(chain):
            if isinstance(itm, dict):  # OPEN_END/STUB
                if i not in (0, len(chain)-1):
                    raise DSLValidationError("E.CONNECT.ENDPOINT",
                        "OPEN_END/STUB allowed only at start or end of series.")
        # 3) Voltage sanity: adjacent real objects should have same kv unless one is a transformer or bus bridge
        for a, b in zip(chain, chain[1:]):
            if isinstance(a, dict) or isinstance(b, dict):  # skip endpoints
                continue
            oa, ob = ir.objects.get(a), ir.objects.get(b)
            if not oa or not ob:  # one may be a BUS id not added yet (should be added though)
                continue
            if {"TRANSFORMER","BUS"} & {oa.type, ob.type}:
                continue  # handled by higher-level checks
            kva, kvb = oa.attrs.get("kv"), ob.attrs.get("kv")
            if kva is not None and kvb is not None and abs(kva-kvb) > 0.15*max(kva, kvb):
                raise DSLValidationError("E.VOLT.MISMATCH",
                    f"Voltage mismatch between {a}({kva}) and {b}({kvb}).")

    # 4) Breakers should appear in at least one series
    breakers = {oid for oid, o in ir.objects.items() if o.type == "BREAKER"}
    in_series = {oid for chain in ir.series for oid in chain if isinstance(oid, str)}
    for brk in breakers:
        if brk not in in_series:
            raise DSLValidationError("E.PROT.BRK_UNUSED", f"Breaker {brk} is not connected.")

    # Add other rules as you need (bus existence, coupler buses differ, etc.)
