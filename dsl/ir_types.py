from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class Object:
    id: str
    type: str
    attrs: Dict[str, Any] = field(default_factory=dict)

@dataclass
class IR:
    objects: Dict[str, Object] = field(default_factory=dict)
    series: List[List[str]] = field(default_factory=list)  # CONNECT chains (IDs + OPEN/STUB tokens)
    pages: List[Dict[str, Any]] = field(default_factory=list)
    style: Dict[str, Any] = field(default_factory=dict)
