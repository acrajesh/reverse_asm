"""Intermediate Representation (IR) schemas for z/OS reverse engineering"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from enum import Enum
import json


class Confidence(Enum):
    """Confidence levels per Technical Design §12.4"""
    HIGH = "high"        # Direct evidence, no inference
    MEDIUM = "medium"    # Pattern-based inference
    LOW = "low"          # Heuristic guess


class InstructionFormat(Enum):
    """z/Architecture instruction formats"""
    RR = "RR"      # Register-Register
    RX = "RX"      # Register-Index
    RS = "RS"      # Register-Storage
    SI = "SI"      # Storage-Immediate
    SS = "SS"      # Storage-Storage
    RRE = "RRE"    # Register-Register Extended
    RXE = "RXE"    # Register-Index Extended
    RXY = "RXY"    # Register-Index Extended (20-bit displacement)
    RSY = "RSY"    # Register-Storage Extended (20-bit displacement)
    RIL = "RIL"    # Register-Immediate Long
    RIE = "RIE"    # Register-Immediate Extended
    SSE = "SSE"    # Storage-Storage Extended
    UNKNOWN = "UNKNOWN"


class BlockType(Enum):
    """Basic block types"""
    ENTRY = "entry"
    NORMAL = "normal"
    CALL = "call"
    RETURN = "return"
    BRANCH = "branch"
    UNKNOWN = "unknown"


@dataclass
class Instruction:
    """Single disassembled instruction with evidence mapping"""
    address: int
    raw_bytes: bytes
    hex_bytes: str
    mnemonic: str
    operands: List[str]
    format: InstructionFormat = InstructionFormat.UNKNOWN
    synthetic_label: Optional[str] = None
    is_branch: bool = False
    is_call: bool = False
    is_return: bool = False
    branch_target: Optional[int] = None
    annotation: Optional[str] = None
    confidence: Confidence = Confidence.HIGH
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": f"0x{self.address:08X}",
            "bytes": self.hex_bytes,
            "mnemonic": self.mnemonic,
            "operands": self.operands,
            "format": self.format.value,
            "label": self.synthetic_label,
            "branch_target": f"0x{self.branch_target:08X}" if self.branch_target else None,
            "annotation": self.annotation,
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else self.confidence
        }
    
    def to_asm_line(self) -> str:
        """Generate HLASM-like assembly line"""
        label_str = f"{self.synthetic_label:8}" if self.synthetic_label else " " * 8
        operands_str = ",".join(self.operands) if self.operands else ""
        addr_str = f"{self.address:08X}"
        bytes_str = self.hex_bytes[:16].ljust(16)
        
        line = f"{addr_str} {bytes_str} {label_str} {self.mnemonic:6} {operands_str}"
        if self.annotation:
            line += f"  * {self.annotation}"
        return line


@dataclass
class BasicBlock:
    """Basic block in the control flow graph"""
    id: str
    start_address: int
    end_address: int
    instructions: List[Instruction] = field(default_factory=list)
    block_type: BlockType = BlockType.NORMAL
    predecessors: Set[str] = field(default_factory=set)
    successors: Set[str] = field(default_factory=set)
    fall_through: Optional[str] = None
    branch_targets: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.HIGH
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "start": f"0x{self.start_address:08X}",
            "end": f"0x{self.end_address:08X}",
            "type": self.block_type.value,
            "instructions": len(self.instructions),
            "predecessors": list(self.predecessors),
            "successors": list(self.successors),
            "fall_through": self.fall_through,
            "branch_targets": self.branch_targets,
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else self.confidence
        }


@dataclass
class Procedure:
    """Inferred procedure/function"""
    id: str
    name: str
    entry_address: int
    exit_addresses: List[int] = field(default_factory=list)
    basic_blocks: List[str] = field(default_factory=list)
    calls_to: Set[str] = field(default_factory=set)
    called_by: Set[str] = field(default_factory=set)
    confidence: Confidence = Confidence.MEDIUM
    detection_method: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entry": f"0x{self.entry_address:08X}",
            "exits": [f"0x{addr:08X}" for addr in self.exit_addresses],
            "blocks": self.basic_blocks,
            "calls_to": list(self.calls_to),
            "called_by": list(self.called_by),
            "confidence": self.confidence.value,
            "detection": self.detection_method
        }


@dataclass
class ControlFlowGraph:
    """Control flow graph for a module"""
    module_name: str
    entry_points: List[int]
    basic_blocks: Dict[str, BasicBlock] = field(default_factory=dict)
    procedures: Dict[str, Procedure] = field(default_factory=dict)
    call_graph: Dict[str, Set[str]] = field(default_factory=dict)
    unresolved_branches: List[int] = field(default_factory=list)
    data_regions: List[tuple[int, int]] = field(default_factory=list)
    
    def add_block(self, block: BasicBlock):
        self.basic_blocks[block.id] = block
    
    def add_edge(self, from_id: str, to_id: str):
        if from_id in self.basic_blocks and to_id in self.basic_blocks:
            self.basic_blocks[from_id].successors.add(to_id)
            self.basic_blocks[to_id].predecessors.add(from_id)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module_name,
            "entry_points": [f"0x{ep:08X}" for ep in self.entry_points],
            "blocks": {bid: b.to_dict() for bid, b in self.basic_blocks.items()},
            "procedures": {pid: p.to_dict() for pid, p in self.procedures.items()},
            "call_graph": {k: list(v) for k, v in self.call_graph.items()},
            "unresolved": [f"0x{addr:08X}" for addr in self.unresolved_branches],
            "data_regions": [[f"0x{s:08X}", f"0x{e:08X}"] for s, e in self.data_regions]
        }


@dataclass
class ModuleMetadata:
    """Metadata extracted from load module or program object"""
    name: Optional[str] = None
    format_type: str = "unknown"  # "load_module" or "program_object"
    entry_point: Optional[int] = None
    external_symbols: List[str] = field(default_factory=list)
    csect_info: List[Dict[str, Any]] = field(default_factory=list)
    amode: Optional[int] = None  # 24, 31, or 64
    rmode: Optional[str] = None  # "24" or "ANY"
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "format": self.format_type,
            "entry_point": f"0x{self.entry_point:08X}" if self.entry_point else None,
            "externals": self.external_symbols,
            "csects": self.csect_info,
            "amode": self.amode,
            "rmode": self.rmode,
            "attributes": self.attributes
        }


@dataclass
class DisassemblyResult:
    """Complete disassembly result for a module"""
    metadata: ModuleMetadata
    instructions: List[Instruction]
    cfg: ControlFlowGraph
    unknown_regions: List[tuple[int, int, bytes]]  # start, end, raw_bytes
    warnings: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "instruction_count": len(self.instructions),
            "cfg": self.cfg.to_dict(),
            "unknown_regions": [
                {"start": f"0x{s:08X}", "end": f"0x{e:08X}", "size": e - s}
                for s, e, _ in self.unknown_regions
            ],
            "warnings": self.warnings,
            "statistics": self.statistics
        }
