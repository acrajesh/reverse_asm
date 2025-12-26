"""Pseudocode generator - converts CFG to structured pseudocode"""

from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from .ir import ControlFlowGraph, BasicBlock, Instruction, Procedure, BlockType, Confidence

logger = logging.getLogger(__name__)


@dataclass
class PseudocodeStatement:
    """Single pseudocode statement with evidence mapping"""
    text: str
    indent_level: int
    address_range: Tuple[int, int]
    confidence: float
    statement_type: str  # 'sequence', 'if', 'else', 'loop', 'call', 'return', 'unknown'
    
    def to_string(self) -> str:
        """Convert to indented string with evidence"""
        indent = "  " * self.indent_level
        addr_str = f"[0x{self.address_range[0]:08X}-0x{self.address_range[1]:08X}]"
        conf_str = f"(conf: {self.confidence})" if isinstance(self.confidence, float) and self.confidence < 0.8 else ""
        return f"{indent}{self.text}  // {addr_str} {conf_str}".rstrip()


class PseudocodeGenerator:
    """Generates structured pseudocode from CFG"""
    
    def __init__(self):
        self.statements: List[PseudocodeStatement] = []
        self.visited_blocks: Set[str] = set()
        self.loop_headers: Set[str] = set()
        self.indent_level = 0
        
    def generate(self, cfg: ControlFlowGraph) -> str:
        """Generate complete pseudocode for the module"""
        self.statements = []
        
        # Add module header
        self._add_header(cfg)
        
        # Generate pseudocode for each procedure
        if cfg.procedures:
            for proc in sorted(cfg.procedures.values(), key=lambda p: p.entry_address):
                self._generate_procedure(proc, cfg)
        else:
            # No procedures detected, generate for entry points
            for entry_point in cfg.entry_points:
                block = self._find_block_by_address(entry_point, cfg)
                if block:
                    self._add_statement("// Main entry point", 'sequence', 
                                      (entry_point, entry_point), 1.0)
                    self.visited_blocks.clear()
                    self._generate_block_sequence(block, cfg, 0)
        
        # Convert statements to string
        return "\n".join(stmt.to_string() for stmt in self.statements)
    
    def _add_header(self, cfg: ControlFlowGraph):
        """Add pseudocode header"""
        self._add_statement(f"// Module: {cfg.module_name}", 'sequence', (0, 0), 1.0)
        self._add_statement("// Pseudocode generated from binary analysis", 'sequence', (0, 0), 1.0)
        self._add_statement("// Note: Control flow inferred from branch patterns", 'sequence', (0, 0), 1.0)
        self._add_statement("", 'sequence', (0, 0), 1.0)
    
    def _generate_procedure(self, proc: Procedure, cfg: ControlFlowGraph):
        """Generate pseudocode for a procedure"""
        self._add_statement("", 'sequence', (0, 0), 1.0)
        conf_val = self._confidence_to_float(proc.confidence)
        self._add_statement(f"PROCEDURE {proc.name}()", 'sequence',
                          (proc.entry_address, proc.entry_address), conf_val)
        self._add_statement(f"// Detection: {proc.detection_method}", 'sequence',
                          (proc.entry_address, proc.entry_address), conf_val)
        
        # Find entry block
        entry_block = None
        for block_id in proc.basic_blocks:
            block = cfg.basic_blocks.get(block_id)
            if block and block.start_address <= proc.entry_address <= block.end_address:
                entry_block = block
                break
        
        if entry_block:
            self.visited_blocks.clear()
            self.loop_headers = self._find_loop_headers(proc, cfg)
            self._generate_block_sequence(entry_block, cfg, 1)
        else:
            self._add_statement("  // Unable to find entry block", 'unknown',
                              (proc.entry_address, proc.entry_address), 0.3)
        
        self._add_statement("END PROCEDURE", 'sequence',
                          (proc.entry_address, proc.entry_address), self._confidence_to_float(proc.confidence))
    
    def _generate_block_sequence(self, block: BasicBlock, cfg: ControlFlowGraph, indent: int):
        """Generate pseudocode for a sequence of blocks"""
        if block.id in self.visited_blocks:
            # Already visited - might be a loop back-edge
            if block.id in self.loop_headers:
                self._add_statement("CONTINUE to loop_start", 'loop',
                                  (block.start_address, block.end_address), 0.7)
            return
        
        self.visited_blocks.add(block.id)
        
        # Check if this is a loop header
        if block.id in self.loop_headers:
            self._generate_loop(block, cfg, indent)
            return
        
        # Generate statements for instructions in block
        self._generate_block_statements(block, indent)
        
        # Handle control flow at end of block
        if block.instructions:
            last_inst = block.instructions[-1]
            
            if last_inst.is_return:
                self._add_statement("RETURN", 'return',
                                  (last_inst.address, last_inst.address), 0.9)
                
            elif last_inst.is_call:
                target_name = self._get_call_target_name(last_inst, cfg)
                self._add_statement(f"CALL {target_name}", 'call',
                                  (last_inst.address, last_inst.address), 0.85)
                # Continue with fall-through
                if block.fall_through:
                    next_block = cfg.basic_blocks.get(block.fall_through)
                    if next_block:
                        self._generate_block_sequence(next_block, cfg, indent)
                        
            elif last_inst.is_branch:
                self._generate_branch_structure(block, cfg, indent)
                
            else:
                # Normal fall-through
                if block.fall_through:
                    next_block = cfg.basic_blocks.get(block.fall_through)
                    if next_block:
                        self._generate_block_sequence(next_block, cfg, indent)
    
    def _generate_block_statements(self, block: BasicBlock, indent: int):
        """Generate statements for instructions in a block"""
        for inst in block.instructions:
            # Skip control flow instructions (handled separately)
            if inst.is_branch or inst.is_call or inst.is_return:
                continue
                
            # Generate statement based on instruction
            stmt = self._instruction_to_statement(inst)
            self._add_statement(stmt, 'sequence',
                              (inst.address, inst.address), self._confidence_to_float(inst.confidence), indent)
    
    def _generate_branch_structure(self, block: BasicBlock, cfg: ControlFlowGraph, indent: int):
        """Generate if/else structure for conditional branch"""
        if not block.instructions:
            return
            
        last_inst = block.instructions[-1]
        
        # Check if unconditional branch
        if self._is_unconditional_branch(last_inst):
            if block.branch_targets:
                target_id = block.branch_targets[0]
                target_block = cfg.basic_blocks.get(target_id)
                if target_block:
                    self._add_statement("GOTO", 'sequence',
                                      (last_inst.address, last_inst.address), 0.8)
                    self._generate_block_sequence(target_block, cfg, indent)
        else:
            # Conditional branch - generate if/else
            condition = self._get_branch_condition(last_inst)
            
            self._add_statement(f"IF {condition} THEN", 'if',
                              (last_inst.address, last_inst.address), 0.75, indent)
            
            # True branch (branch target)
            if block.branch_targets:
                target_id = block.branch_targets[0]
                target_block = cfg.basic_blocks.get(target_id)
                if target_block:
                    self._generate_block_sequence(target_block, cfg, indent + 1)
            
            # False branch (fall-through)
            if block.fall_through:
                self._add_statement("ELSE", 'else',
                                  (last_inst.address, last_inst.address), 0.75, indent)
                fall_block = cfg.basic_blocks.get(block.fall_through)
                if fall_block:
                    self._generate_block_sequence(fall_block, cfg, indent + 1)
            
            self._add_statement("END IF", 'if',
                              (last_inst.address, last_inst.address), 0.75, indent)
    
    def _generate_loop(self, header_block: BasicBlock, cfg: ControlFlowGraph, indent: int):
        """Generate loop structure"""
        self._add_statement("LOOP loop_start:", 'loop',
                          (header_block.start_address, header_block.end_address), 0.7, indent)
        
        # Generate loop body
        self._generate_block_statements(header_block, indent + 1)
        
        # Follow successors within loop
        for succ_id in header_block.successors:
            if succ_id != header_block.id:  # Avoid immediate self-loop
                succ_block = cfg.basic_blocks.get(succ_id)
                if succ_block and succ_block.id not in self.visited_blocks:
                    self._generate_block_sequence(succ_block, cfg, indent + 1)
        
        self._add_statement("END LOOP", 'loop',
                          (header_block.start_address, header_block.end_address), 0.7, indent)
    
    def _instruction_to_statement(self, inst: Instruction) -> str:
        """Convert instruction to pseudocode statement"""
        mnemonic = inst.mnemonic
        operands = inst.operands
        
        # Load/Store operations
        if mnemonic in ["L", "LR", "LH", "LG"]:
            if len(operands) >= 2:
                return f"R{operands[0]} = LOAD({operands[1]})"
            return f"LOAD {', '.join(operands)}"
            
        elif mnemonic in ["ST", "STH", "STG", "STM"]:
            if len(operands) >= 2:
                return f"STORE R{operands[0]} to {operands[1]}"
            return f"STORE {', '.join(operands)}"
            
        # Arithmetic operations
        elif mnemonic in ["A", "AR", "AH", "AG"]:
            if len(operands) >= 2:
                return f"R{operands[0]} = R{operands[0]} + {operands[1]}"
            return f"ADD {', '.join(operands)}"
            
        elif mnemonic in ["S", "SR", "SH", "SG"]:
            if len(operands) >= 2:
                return f"R{operands[0]} = R{operands[0]} - {operands[1]}"
            return f"SUB {', '.join(operands)}"
            
        elif mnemonic in ["M", "MR", "MH", "MSG"]:
            if len(operands) >= 2:
                return f"R{operands[0]} = R{operands[0]} * {operands[1]}"
            return f"MUL {', '.join(operands)}"
            
        # Comparison operations
        elif mnemonic in ["C", "CR", "CH", "CG", "CL", "CLR"]:
            if len(operands) >= 2:
                return f"COMPARE R{operands[0]} with {operands[1]}"
            return f"COMPARE {', '.join(operands)}"
            
        # Move operations
        elif mnemonic == "MVC":
            if len(operands) >= 2:
                return f"MOVE {operands[1]} to {operands[0]}"
            return f"MOVE {', '.join(operands)}"
            
        # LA - Load Address
        elif mnemonic == "LA":
            if len(operands) >= 2:
                return f"R{operands[0]} = ADDRESS_OF({operands[1]})"
            return f"LOAD_ADDRESS {', '.join(operands)}"
            
        # Unknown or complex instruction
        else:
            if inst.confidence == Confidence.LOW:
                return f"UNKNOWN: {inst.hex_bytes}"
            return f"{mnemonic} {', '.join(operands)}"
    
    def _get_branch_condition(self, inst: Instruction) -> str:
        """Get human-readable branch condition"""
        if inst.mnemonic in ["BC", "BCR"]:
            if inst.operands and len(inst.operands) > 0:
                mask = inst.operands[0]
                # Common condition codes
                conditions = {
                    "15": "always",
                    "8": "equal",
                    "7": "not_equal", 
                    "6": "not_equal",
                    "4": "less_than",
                    "2": "greater_than",
                    "11": "less_or_equal",
                    "13": "greater_or_equal",
                    "1": "overflow",
                    "14": "no_overflow"
                }
                return conditions.get(mask, f"condition_mask_{mask}")
        elif inst.mnemonic == "BZ":
            return "zero"
        elif inst.mnemonic == "BNZ":
            return "not_zero"
        elif inst.mnemonic == "BP":
            return "positive"
        elif inst.mnemonic == "BM":
            return "negative"
        
        return "condition"
    
    def _get_call_target_name(self, inst: Instruction, cfg: ControlFlowGraph) -> str:
        """Get name of call target"""
        if inst.branch_target:
            # Look for procedure at target
            for proc in cfg.procedures.values():
                if proc.entry_address == inst.branch_target:
                    return proc.name
            return f"SUB_{inst.branch_target:08X}"
        
        # Register indirect call
        if inst.operands and len(inst.operands) > 0:
            return f"[R{inst.operands[0]}]"
        
        return "UNKNOWN"
    
    def _is_unconditional_branch(self, inst: Instruction) -> bool:
        """Check if instruction is unconditional branch"""
        if inst.mnemonic == "BC" and inst.operands and inst.operands[0] == "15":
            return True
        if inst.mnemonic == "BCR" and inst.operands and inst.operands[0] == "15":
            return True
        if inst.mnemonic in ["B", "BR"]:
            return True
        return False
    
    def _find_loop_headers(self, proc: Procedure, cfg: ControlFlowGraph) -> Set[str]:
        """Find potential loop headers using back edges"""
        loop_headers = set()
        
        for block_id in proc.basic_blocks:
            block = cfg.basic_blocks.get(block_id)
            if block:
                # Check if any successor is a predecessor (back edge)
                for succ_id in block.successors:
                    if succ_id in proc.basic_blocks:
                        succ_block = cfg.basic_blocks.get(succ_id)
                        if succ_block and succ_block.start_address <= block.start_address:
                            # This is a back edge
                            loop_headers.add(succ_id)
        
        return loop_headers
    
    def _find_block_by_address(self, address: int, cfg: ControlFlowGraph) -> Optional[BasicBlock]:
        """Find block containing address"""
        for block in cfg.basic_blocks.values():
            if block.start_address <= address <= block.end_address:
                return block
        return None
    
    def _confidence_to_float(self, confidence) -> float:
        """Convert Confidence enum to float value"""
        if isinstance(confidence, Confidence):
            if confidence == Confidence.HIGH:
                return 0.95
            elif confidence == Confidence.MEDIUM:
                return 0.75
            else:  # LOW
                return 0.3
        return confidence if isinstance(confidence, float) else 0.5
    
    def _add_statement(self, text: str, stmt_type: str, addr_range: Tuple[int, int],
                      confidence: float, indent: Optional[int] = None):
        """Add a pseudocode statement"""
        if indent is None:
            indent = self.indent_level
            
        self.statements.append(PseudocodeStatement(
            text=text,
            indent_level=indent,
            address_range=addr_range,
            confidence=confidence,
            statement_type=stmt_type
        ))
