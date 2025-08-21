# dsl/parser.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

from lark import Lark, Transformer, v_args, Token
from lark.exceptions import UnexpectedInput

# ---------- IR types ----------
@dataclass
class ObjectIR:
    id: str
    type: str
    attrs: Dict[str, Any]
    loc: Tuple[int, int]  # (line, column) of the ADD_* statement

@dataclass
class PageIR:
    id: str
    attrs: Dict[str, Any]
    loc: Tuple[int, int]

@dataclass
class IR:
    objects: Dict[str, ObjectIR] = field(default_factory=dict)
    series: List[Tuple[List[Any], Tuple[int, int]]] = field(default_factory=list)  # (chain, loc)
    pages: Dict[str, PageIR] = field(default_factory=dict)
    style: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)  # room for version, etc.

# ---------- Load grammar ----------
def _load_grammar() -> str:
    # assumes grammar_ebnf.lark is next to this file
    path = Path(__file__).with_name("grammar_ebnf.lark")
    return path.read_text(encoding="utf-8")

_GRAMMAR = _load_grammar()
# Use LALR for speed; start at "script" per the grammar
_parser = Lark(_GRAMMAR, start="script", parser="lalr", propagate_positions=True)


# ---------- Helpers ----------
def _pairs_to_dict(items: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """Convert list of ('key', value) pairs to dict; later keys override earlier ones."""
    out: Dict[str, Any] = {}
    for k, v in items:
        out[k] = v
    return out

def _merge_front(kvs_main: Dict[str, Any], kvs_extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge optional extra k/vs into the main set (main keys win)."""
    if not kvs_extra:
        return kvs_main
    merged = dict(kvs_extra)
    merged.update(kvs_main)
    return merged


# ---------- Transformer ----------
@v_args(meta=True)  # pass node metadata (line/col) into rule methods
class ToIR(Transformer):
    def __init__(self) -> None:
        super().__init__()
        self.ir = IR()

    # ----- atoms -----
    def ID(self, tok):
        return str(tok)

    def STRING(self, tok):
        # strip surrounding quotes
        return tok[1:-1]

    def NUM(self, tok):
        # lark SIGNED_NUMBER -> string; coerce to float
        return float(tok)

    def KEY(self, tok):
        return str(tok)

    def BOOL(self, tok):
        return True if tok == "true" else False

    def value(self, meta, v):
        # passthrough (STRING | NUM | ID)
        return v[0]

    # key/value pairs from opt_kvs
    @v_args(inline=True)
    def key(self, meta, k):
        return k

    @v_args(inline=True)
    def opt_kvs(self, meta, *pairs):
        # pairs are ('KEY', value)
        return _pairs_to_dict(pairs)

    @v_args(inline=True)
    def pair(self, meta, k, v):
        # Not used unless your grammar defines 'pair'; shown for pattern
        return (k, v)

    # ----- lists and composites -----
    def list_id(self, meta, items):
        return list(items)

    def list_rel(self, meta, items):
        return list(items)

    def list_num(self, meta, items):
        return [float(x) for x in items]

    def seq_params(self, meta, *items):
        # items are alternating keys & values by rule → but our grammar provided explicit named entries, so we get tokens in order.
        # Easiest: build dict by scanning tokens (we'll receive a flat list like ["R1_ohm_per_km", 0.05, "X1_ohm_per_km", 0.4, ...] only if the grammar was different).
        # With current grammar, we will get NUMs in fixed positions; better to return a dict keyed as in the grammar:
        # For portability, we parse children into a dict by peeking at token.text; but Lark already gave us structured order.
        # Simpler: return a dict mapping known keys if present (children come as tokens interleaved with names).
        # However, Lark's default will pass us the values only; so we customize the grammar if needed.
        # To keep it simple, assume grammar passes named fields in order:
        # seq_params: { R1_ohm_per_km=NUM, X1_ohm_per_km=?, ...}
        # We'll reconstruct via meta.children labels not available; fallback: return tuple list.
        # Pragmatic approach: return a dict with positional names; you can refine later.
        vals = [x for x in items]
        keys = ["R1_ohm_per_km", "X1_ohm_per_km", "B1_uS_per_km", "R0_ohm_per_km", "X0_ohm_per_km", "B0_uS_per_km"]
        out = {}
        for i, val in enumerate(vals):
            if val is None:
                continue
            # only map sequentially; skip Nones injected by optionals
            out[keys[i]] = val
        return out

    def tap_obj(self, meta, *items):
        # items: side, range_pct, steps, maybe regulation_mode
        d = {}
        if len(items) >= 1: d["side"] = items[0]
        if len(items) >= 2: d["range_pct"] = items[1]
        if len(items) >= 3: d["steps"] = items[2]
        if len(items) >= 4: d["regulation_mode"] = items[3]
        return d

    def tuning(self, meta, tuned_hz, q_factor):
        return {"tuned_Hz": tuned_hz, "Q_factor": q_factor}

    def routing(self, meta, *items):
        # items will be values (some may be missing because optionals)
        # Return a dict with only provided keys; easier: grammar order must be known
        keys = ["pref", "avoid_crossing", "bus_spacing", "bay_spacing"]
        out = {}
        for k, v in zip(keys, items):
            if v is not None:
                out[k] = v
        return out

    def range(self, meta, a, b):
        return [float(a), float(b)]

    # ----- series items -----
    def OPEN_END(self, meta, _tok=None):
        return {"OPEN_END": True}

    def stub_obj(self, meta, s):
        # s is the inner STRING (already stripped)
        return {"STUB": s}

    # ----- ADD_*: return ("OBJ", TYPE, dict), then add_stmt will insert into table
    def _collect(self, children) -> Dict[str, Any]:
        """
        Pulls all KEY=VALUE pairs present in the rule expansion into a dict.
        We rely on our grammar using explicit 'key=value' tokens plus an optional opt_kvs dict at the end.
        """
        # Children arrive interleaved as literals and parsed values.
        # Our pattern: we used explicit literals like "id=" ID, so the only 'values' here
        # we need are the IDs/NUMs/STRINGs we can reconstruct by position. Rather than positional,
        # we can ask the grammar to emit named pairs; but to keep code short, we build dict by scanning.
        # ==> Best solution: in each add_* method we build dict explicitly (few lines) and then merge opt_kvs.
        return {}

    # For each add_* rule, we build the dict explicitly for the mandatory keys and merge opt_kvs (last child if dict)
    def bus_params(self, meta, *_children):
        # bus_params: "id=" ID "," SP "kv=" NUM
        # The children come as nested structure, need to flatten
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        # Now extract ID and NUM from the flattened items
        id_value = None
        kv_value = None
        
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kv=', ' ']:
                id_value = item
            elif isinstance(item, (int, float)):
                kv_value = item
            elif isinstance(item, Token):
                if item.type == 'ID':
                    id_value = item.value
                elif item.type == 'NUMBER':
                    kv_value = float(item.value)
                elif item.type == 'SP' and item.value.strip():
                    # Skip space tokens
                    continue
        
        return [id_value, kv_value]

    def bay_params(self, meta, *_children):
        # bay_params: "id=" ID "," SP "kind=" BAYKIND "," SP "kv=" NUM "," SP "bus=" ID
        # The children come as nested structure, need to flatten
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        # Extract values in order: ID, BAYKIND, NUM, ID
        id_value = None
        kind_value = None
        kv_value = None
        bus_value = None
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kind=', 'kv=', 'bus=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type in ['ID', 'BAYKIND']:
                    found_values.append(item.value)
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    # Skip space tokens
                    continue
        
        # Assign values based on position (id, kind, kv, bus)
        if len(found_values) >= 4:
            id_value = found_values[0]
            kind_value = found_values[1]
            kv_value = found_values[2]
            bus_value = found_values[3]
        
        return [id_value, kind_value, kv_value, bus_value]

    def coupler_params(self, meta, *_children):
        """Extract id, kv, from_bus, to_bus from coupler parameters"""
        # coupler_params: "id=" ID "," SP "kv=" NUM "," SP "from_bus=" ID "," SP "to_bus=" ID
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kv=', 'from_bus=', 'to_bus=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type == 'ID':
                    found_values.append(item.value)
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    continue
        
        # Order: id, kv, from_bus, to_bus
        if len(found_values) >= 4:
            return [found_values[0], found_values[1], found_values[2], found_values[3]]
        return found_values

    def breaker_params(self, meta, *_children):
        """Extract id, kv, interrupting_kA, type, continuous_A from breaker parameters"""
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kv=', 'interrupting_kA=', 'type=', 'continuous_A=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type in ['ID', 'BREAKER_TYPE']:
                    found_values.append(item.value)
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    continue
        
        # Order: id, kv, interrupting_kA, type, continuous_A
        if len(found_values) >= 5:
            return [found_values[0], found_values[1], found_values[2], found_values[3], found_values[4]]
        return found_values

    def disconnector_params(self, meta, *_children):
        """Extract id, kv, type, continuous_A from disconnector parameters"""
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kv=', 'type=', 'continuous_A=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type in ['ID', 'DISCONNECTOR_TYPE']:
                    found_values.append(item.value)
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    continue
        
        # Order: id, kv, type, continuous_A
        if len(found_values) >= 4:
            return [found_values[0], found_values[1], found_values[2], found_values[3]]
        return found_values

    def transformer_params(self, meta, *_children):
        """Extract id, type, rated_MVA, vector_group, percentZ from transformer parameters"""
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'type=', 'rated_MVA=', 'vector_group=', 'percentZ=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type in ['ID', 'TRANSFORMER_TYPE']:
                    found_values.append(item.value)
                elif item.type == 'STRING':
                    # Remove quotes from string
                    found_values.append(item.value.strip('"\''))
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    continue
        
        # Order: id, type, rated_MVA, vector_group, percentZ
        if len(found_values) >= 5:
            return [found_values[0], found_values[1], found_values[2], found_values[3], found_values[4]]
        return found_values

    def line_params(self, meta, *_children):
        """Extract id, kv, type, length_km, thermal_A from line parameters"""
        all_items = []
        for child in _children:
            if isinstance(child, list):
                all_items.extend(child)
            else:
                all_items.append(child)
        
        found_values = []
        for item in all_items:
            if isinstance(item, str) and item not in ['id=', ',', 'kv=', 'type=', 'length_km=', 'thermal_A=', ' ']:
                found_values.append(item)
            elif isinstance(item, (int, float)):
                found_values.append(item)
            elif isinstance(item, Token):
                if item.type in ['ID', 'LINE_TYPE']:
                    found_values.append(item.value)
                elif item.type == 'NUM':
                    found_values.append(float(item.value))
                elif item.type == 'SP':
                    continue
        
        # Order: id, kv, type, length_km, thermal_A
        if len(found_values) >= 5:
            return [found_values[0], found_values[1], found_values[2], found_values[3], found_values[4]]
        return found_values

    def add_bus(self, meta, *_children):
        # We should receive the result from bus_params
        # Let's look for the bus_params result (which should be [id, kv])
        bus_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                # Look inside the list for the actual bus_params result
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 2 and not isinstance(subchild[0], Token):
                        # This looks like the bus_params result [id, kv]
                        bus_params_result = subchild
                        break
            elif isinstance(child, dict):
                # This could be extra_params
                extra = child
            # Skip tokens like SP
        
        if not bus_params_result:
            raise ValueError(f"add_bus: could not find bus_params result in {_children}")
            
        # Extract values
        id_value, kv_value = bus_params_result
        
        # Build kvs
        kvs = {"id": id_value, "kv": kv_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        
        return ("OBJ", "BUS", kvs, (meta.line, meta.column))

    def add_bay(self, meta, *_children):
        """Create a BAY object from parsed components"""
        bay_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                # Look for the bay_params result [id, kind, kv, bus]
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 4 and not isinstance(subchild[0], Token):
                        bay_params_result = subchild
                        break
            elif isinstance(child, dict):
                # This could be extra_params
                extra = child
            # Skip tokens like SP
        
        if not bay_params_result:
            raise ValueError(f"add_bay: could not find bay_params result in {_children}")
            
        # Extract values
        id_value, kind_value, kv_value, bus_value = bay_params_result
        
        # Build kvs
        kvs = {"id": id_value, "kind": kind_value, "kv": kv_value, "bus": bus_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        
        return ("OBJ", "BAY", kvs, (meta.line, meta.column))

    def add_coupler(self, meta, *_children):
        """Create a COUPLER object from parsed components"""
        coupler_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 4 and not isinstance(subchild[0], Token):
                        coupler_params_result = subchild
                        break
            elif isinstance(child, dict):
                extra = child
        
        if not coupler_params_result:
            raise ValueError(f"add_coupler: could not find coupler_params result in {_children}")
            
        id_value, kv_value, from_bus_value, to_bus_value = coupler_params_result
        kvs = {"id": id_value, "kv": kv_value, "from_bus": from_bus_value, "to_bus": to_bus_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        return ("OBJ", "COUPLER", kvs, (meta.line, meta.column))

    def add_breaker(self, meta, *_children):
        """Create a BREAKER object from parsed components"""
        breaker_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 5 and not isinstance(subchild[0], Token):
                        breaker_params_result = subchild
                        break
            elif isinstance(child, dict):
                extra = child
        
        if not breaker_params_result:
            raise ValueError(f"add_breaker: could not find breaker_params result in {_children}")
            
        id_value, kv_value, interrupting_kA_value, type_value, continuous_A_value = breaker_params_result
        kvs = {"id": id_value, "kv": kv_value, "interrupting_kA": interrupting_kA_value, "type": type_value, "continuous_A": continuous_A_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        return ("OBJ", "BREAKER", kvs, (meta.line, meta.column))

    def add_disconnector(self, meta, *_children):
        """Create a DISCONNECTOR object from parsed components"""
        disconnector_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 4 and not isinstance(subchild[0], Token):
                        disconnector_params_result = subchild
                        break
            elif isinstance(child, dict):
                extra = child
        
        if not disconnector_params_result:
            raise ValueError(f"add_disconnector: could not find disconnector_params result in {_children}")
            
        id_value, kv_value, type_value, continuous_A_value = disconnector_params_result
        kvs = {"id": id_value, "kv": kv_value, "type": type_value, "continuous_A": continuous_A_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        return ("OBJ", "DISCONNECTOR", kvs, (meta.line, meta.column))

    def add_earthing_switch(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "make_kA": c[2]}
        extra = c[3] if len(c) > 3 and isinstance(c[3], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "EARTHING_SWITCH", kvs, (meta.line, meta.column))

    def add_ct(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "ratio": c[2], "class": c[3]}
        idx = 4
        if idx < len(c) and not isinstance(c[idx], dict):
            kvs["burden_VA"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "CT", kvs, (meta.line, meta.column))

    def add_vt(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "type": c[2], "ratio": c[3], "class": c[4]}
        extra = c[5] if len(c) > 5 and isinstance(c[5], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "VT", kvs, (meta.line, meta.column))

    def add_relay_group(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "functions": c[1], "dc_supply": c[2]}
        idx = 3
        if idx < len(c) and not isinstance(c[idx], dict):
            kvs["trip_objects"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "RELAY_GROUP", kvs, (meta.line, meta.column))

    def add_transformer(self, meta, *_children):
        """Create a TRANSFORMER object from parsed components"""
        transformer_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 5 and not isinstance(subchild[0], Token):
                        transformer_params_result = subchild
                        break
            elif isinstance(child, dict):
                extra = child
        
        if not transformer_params_result:
            raise ValueError(f"add_transformer: could not find transformer_params result in {_children}")
            
        id_value, type_value, rated_MVA_value, vector_group_value, percentZ_value = transformer_params_result
        kvs = {"id": id_value, "type": type_value, "rated_MVA": rated_MVA_value, "vector_group": vector_group_value, "percentZ": percentZ_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        return ("OBJ", "TRANSFORMER", kvs, (meta.line, meta.column))

    def add_line(self, meta, *_children):
        """Create a LINE object from parsed components"""
        line_params_result = None
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                for subchild in child:
                    if isinstance(subchild, list) and len(subchild) == 5 and not isinstance(subchild[0], Token):
                        line_params_result = subchild
                        break
            elif isinstance(child, dict):
                extra = child
        
        if not line_params_result:
            raise ValueError(f"add_line: could not find line_params result in {_children}")
            
        id_value, kv_value, type_value, length_km_value, thermal_A_value = line_params_result
        kvs = {"id": id_value, "kv": kv_value, "type": type_value, "length_km": length_km_value, "thermal_A": thermal_A_value}
        if extra:
            kvs = _merge_front(kvs, extra)
        return ("OBJ", "LINE", kvs, (meta.line, meta.column))

    def add_cable(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "length_km": c[2], "thermal_A": c[3], "insulation": c[4]}
        idx = 5
        if idx < len(c) and isinstance(c[idx], dict):
            kvs["seq_params"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "CABLE", kvs, (meta.line, meta.column))

    def add_shunt_cap_bank(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "mvar_total": c[2], "steps": c[3], "connection": c[4]}
        idx = 5
        if idx < len(c) and isinstance(c[idx], dict) and "tuned_Hz" in c[idx]:
            kvs["tuning"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "SHUNT_CAP_BANK", kvs, (meta.line, meta.column))

    def add_shunt_reactor(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "mvar": c[2], "switchable": c[3]}
        extra = c[4] if len(c) > 4 and isinstance(c[4], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "SHUNT_REACTOR", kvs, (meta.line, meta.column))

    def add_series_cap(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "compensation_pct": c[2], "protection": c[3]}
        extra = c[4] if len(c) > 4 and isinstance(c[4], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "SERIES_CAP", kvs, (meta.line, meta.column))

    def add_svc(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "mvar_range": c[2], "control_mode": c[3]}
        idx = 4
        if idx < len(c) and not isinstance(c[idx], dict):
            kvs["response_ms"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "SVC", kvs, (meta.line, meta.column))

    def add_statcom(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "mvar_range": c[2], "control_mode": c[3]}
        idx = 4
        if idx < len(c) and not isinstance(c[idx], dict):
            kvs["response_ms"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "STATCOM", kvs, (meta.line, meta.column))

    def add_surge_arrester(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "mcov_kV": c[2], "class": c[3]}
        extra = c[4] if len(c) > 4 and isinstance(c[4], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "SURGE_ARRESTER", kvs, (meta.line, meta.column))

    def add_line_trap(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "kv": c[1], "carrier_kHz": c[2]}
        extra = c[3] if len(c) > 3 and isinstance(c[3], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "LINE_TRAP", kvs, (meta.line, meta.column))

    def add_station_service_transformer(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "primary_kv": c[1], "secondary_kV": c[2], "kVA": c[3]}
        extra = c[4] if len(c) > 4 and isinstance(c[4], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "STATION_SERVICE_TRANSFORMER", kvs, (meta.line, meta.column))

    def add_dc_system(self, meta, *_c):
        c = [x for x in _c]
        kvs = {"id": c[0], "nominal_V": c[1], "capacity_Ah": c[2], "redundancy": c[3]}
        extra = c[4] if len(c) > 4 and isinstance(c[4], dict) else None
        kvs = _merge_front(kvs, extra)
        return ("OBJ", "DC_SYSTEM", kvs, (meta.line, meta.column))

    # add_stmt receives ("OBJ", type, kvs, loc) from add_* and inserts into table
    def add_stmt(self, meta, *children):
        # The structure might be wrapped in a Tree or other nested structure
        # Let's extract the actual tuple
        item = None
        for child in children:
            if isinstance(child, list):
                # Look through the list for a Tree or tuple
                for subchild in child:
                    if hasattr(subchild, 'children') and subchild.children:
                        # This is a Tree, extract its children
                        for tree_child in subchild.children:
                            if isinstance(tree_child, tuple) and len(tree_child) == 4:
                                item = tree_child
                                break
                    elif isinstance(subchild, tuple) and len(subchild) == 4:
                        item = subchild
                        break
                if item:
                    break
            elif isinstance(child, tuple) and len(child) == 4:
                item = child
                break
        
        if not item or not isinstance(item, tuple) or len(item) != 4:
            raise ValueError(f"add_stmt expected 4-tuple, got {item}")
            
        kind, typ, kvs, loc = item
        oid = kvs.get("id")
        if not oid:
            raise ValueError(f"Missing id in {typ} at line {loc[0]}")
        if oid in self.ir.objects:
            raise ValueError(f"Duplicate id '{oid}' at line {loc[0]}")
        self.ir.objects[oid] = ObjectIR(id=oid, type=typ, attrs=kvs, loc=loc)
        return None

    # CONNECT
    def connect_stmt(self, meta, *_children):
        """Process CONNECT statement with series list"""
        series_list = []
        extra = None
        
        for child in _children:
            if isinstance(child, list):
                # This should be the list of series items
                series_list = child
            elif isinstance(child, dict):
                # This could be extra_params
                extra = child
            # Skip other tokens like SP, LSQB, RSQB
        
        self.ir.series.append((series_list, (meta.line, meta.column)))
        return None

    # PAGE (store as dict by id for later use)
    def page_stmt(self, meta, *_c):
        c = [x for x in _c]
        # id, title, voltage_scope(list), buses(list), bays(list), [routing], [opt_kvs]
        kvs = {"id": c[0], "title": c[1], "voltage_scope": c[2], "buses": c[3], "bays": c[4]}
        idx = 5
        if idx < len(c) and isinstance(c[idx], dict) and ("pref" in c[idx] or "bus_spacing" in c[idx]):
            kvs["routing"] = c[idx]; idx += 1
        extra = c[idx] if idx < len(c) and isinstance(c[idx], dict) else None
        if extra:
            kvs.update(extra)
        pid = kvs["id"]
        self.ir.pages[pid] = PageIR(id=pid, attrs=kvs, loc=(meta.line, meta.column))
        return None

    # STYLE/LABEL/SET_LAYOUT/…: stash as you like (you can ignore in parser and use validator/renderer later)
    def style_stmt(self, meta, *c):
        # Collect provided key/vals by scanning tokens; simplest: treat whole line as extras via opt_kvs in grammar
        # If your grammar returns explicit tokens, build a dict similarly to page_stmt
        return None

    def label_stmt(self, meta, *c):
        return None

    def layout_stmt(self, meta, *c):
        return None

    def validate_stmt(self, meta, *c):
        return None

    def emit_stmt(self, meta, *c):
        return None


# ---------- Public API ----------
class ParseError(Exception):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.line = line
        self.column = column

def parse(text: str) -> IR:
    """
    Parse DSL text into IR. Raises ParseError on syntax problems.
    """
    try:
        tree = _parser.parse(text)
        tx = ToIR()
        tx.transform(tree)
        return tx.ir
    except UnexpectedInput as e:
        # Build a helpful error with line context
        line = getattr(e, 'line', None)
        column = getattr(e, 'column', None)
        # Try to show the offending line
        lines = text.splitlines()
        context = ""
        if line and 1 <= line <= len(lines):
            src_line = lines[line-1]
            caret = " " * (column-1 if column and column > 0 else 0) + "^"
            context = f"\n{src_line}\n{caret}"
        msg = f"Syntax error at line {line}, column {column}.{context}\nExpected one of: {getattr(e, 'expected', [])}"
        raise ParseError(msg, line, column) from None

