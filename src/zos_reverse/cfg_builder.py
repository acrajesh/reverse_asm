"""Control Flow Graph builder for z/OS binary analysis"""

from typing import List, Dict, Set, Optional, Tuple
import logging

from .ir import (
    Instruction, BasicBlock, ControlFlowGraph, BlockType,
    DisassemblyResult, Procedure
)

logger = logging.getLogger(__name__)


class CFGBuilder:
    """Builds control flow graphs from disassembled instructions"""
    
    def __init__(self):
        self.instructions: List[Instruction] = []
        self.instruction_map: Dict[int, Instruction] = {}
        self.leaders: Set[int] = set()
        self.blocks: Dict[str, BasicBlock] = {}
        
    def build_cfg(self, disasm_result: DisassemblyResult) -> ControlFlowGraph:
        """Build complete CFG from disassembly result"""
        self.instructions = disasm_result.instructions
        self.instruction_map = {inst.address: inst for inst in self.instructions}
        
        # Find basic block leaders
        self._find_leaders(disasm_result.cfg.entry_points)
        
        # Create basic blocks
        self._create_basic_blocks()
        
        # Add control flow edges
        unresolved = self._add_control_flow_edges()
        cfg.unresolved_branches.extend(unresolved)
        
        # Assign synthetic labels to branch targets
        self._assign_synthetic_labels()
        
        # Update CFG
        cfg = disasm_result.cfg
        cfg.basic_blocks = self.blocks
        
        # Find unresolved branches
        self._find_unresolved_branches(cfg)
        
        return cfg
    
    def _find_leaders(self, entry_points: List[int]):
        """Find all basic block leaders (first instruction of each block)"""
        # Entry points are leaders
        for ep in entry_points:
            if ep in self.instruction_map:
                self.leaders.add(ep)
        
        # First instruction is a leader if no entry points
        if not self.leaders and self.instructions:
            self.leaders.add(self.instructions[0].address)
        
        # Process all instructions
        for i, inst in enumerate(self.instructions):
            if inst.is_branch:
                # Target of branch is a leader
                if inst.branch_target and inst.branch_target in self.instruction_map:
                    self.leaders.add(inst.branch_target)
                    
                # Instruction after branch is a leader (if not unconditional)
                if not self._is_unconditional_branch(inst) and i + 1 < len(self.instructions):
                    self.leaders.add(self.instructions[i + 1].address)
                    
            elif inst.is_call:
                # Instruction after call is a leader
                if i + 1 < len(self.instructions):
                    self.leaders.add(self.instructions[i + 1].address)
                    
            elif inst.is_return:
                # Instruction after return is a leader (if exists)
                if i + 1 < len(self.instructions):
                    self.leaders.add(self.instructions[i + 1].address)
    
    def _create_basic_blocks(self):
        """Create basic blocks from leaders"""
        sorted_leaders = sorted(self.leaders)
        
        for i, leader in enumerate(sorted_leaders):
            # Determine block end
            if i + 1 < len(sorted_leaders):
                # Block ends before next leader
                end_addr = sorted_leaders[i + 1] - 1
            else:
                # Last block extends to end of instructions
                if self.instructions:
                    end_addr = self.instructions[-1].address + len(self.instructions[-1].raw_bytes) - 1
                else:
                    end_addr = leader
            
            # Collect instructions for this block
            block_instructions = []
            for inst in self.instructions:
                if leader <= inst.address <= end_addr:
                    block_instructions.append(inst)
            
            if not block_instructions:
                continue
            
            # Determine block type
            block_type = self._determine_block_type(block_instructions)
            
            # Create block
            block_id = f"block_{leader:08X}"
            block = BasicBlock(
                id=block_id,
                start_address=leader,
                end_address=block_instructions[-1].address if block_instructions else leader,
                instructions=block_instructions,
                block_type=block_type
            )
            
            self.blocks.append(block)
    
    def _add_control_flow_edges(self):
        """Add edges between basic blocks"""
        unresolved_branches = []
        for block_id, block in enumerate(self.blocks):
            if not block.instructions:
                continue
                
            last_inst = block.instructions[-1]
            
            if last_inst.is_branch:
                # Add edge to branch target
                if last_inst.branch_target:
                    target_block = self._find_block_by_address(last_inst.branch_target)
                    if target_block:
                        block.branch_targets.append(target_block.id)
                        block.successors.add(target_block.id)
                        target_block.predecessors.add(block_id)
                    else:
                        # Unresolved branch target
                        unresolved_branches.append(last_inst.address)
                        last_inst.annotation = "UNRESOLVED_TARGET"
                elif last_inst.is_branch:
                    # Indirect branch without computed target
                    unresolved_branches.append(last_inst.address)
                    last_inst.annotation = "UNRESOLVED_TARGET (indirect)"
                
                # Add fall-through edge if conditional branch
                if not self._is_unconditional_branch(last_inst):
                    next_block = self._find_next_block(block)
                    if next_block:
                        block.fall_through = next_block.id
                        block.successors.add(next_block.id)
                        next_block.predecessors.add(block_id)
                        
            elif last_inst.is_return:
                # No successors for return
                pass
                
            else:
                # Normal fall-through
                next_block = self._find_next_block(block)
                if next_block:
                    block.fall_through = next_block.id
                    block.successors.add(next_block.id)
                    next_block.predecessors.add(block_id)
        
        return unresolved_branches
    
    def _assign_synthetic_labels(self):
        """Assign synthetic labels to branch targets and entry points"""
        label_counter = 1
        
        # Label all blocks that are branch targets
        for block in self.blocks.values():
            if block.predecessors or block.block_type == BlockType.ENTRY:
                # This block is a target
                if block.instructions:
                    first_inst = block.instructions[0]
                    if not first_inst.synthetic_label:
                        # Assign label based on block type
                        if block.block_type == BlockType.ENTRY:
                            first_inst.synthetic_label = "ENTRY"
                        elif block.block_type == BlockType.CALL:
                            first_inst.synthetic_label = f"PROC_{label_counter:03d}"
                            label_counter += 1
                        else:
                            first_inst.synthetic_label = f"L_{label_counter:05d}"
                            label_counter += 1
        
        # Label call targets
        for inst in self.instructions:
            if inst.is_call and inst.branch_target:
                target_inst = self.instruction_map.get(inst.branch_target)
                if target_inst and not target_inst.synthetic_label:
                    target_inst.synthetic_label = f"PROC_{label_counter:03d}"
                    label_counter += 1
    
    def _find_unresolved_branches(self, cfg: ControlFlowGraph):
        """Find branches with unresolved targets"""
        for inst in self.instructions:
            if inst.is_branch and inst.branch_target:
                if inst.branch_target not in self.instruction_map:
                    cfg.unresolved_branches.append(inst.address)
    
    def _determine_block_type(self, instructions: List[Instruction]) -> BlockType:
        """Determine the type of a basic block"""
        if not instructions:
            return BlockType.UNKNOWN
            
        first_inst = instructions[0]
        last_inst = instructions[-1]
        
        # Check if entry block
        if first_inst.synthetic_label == "ENTRY":
            return BlockType.ENTRY
            
        # Check if call block
        if any(inst.is_call for inst in instructions):
            return BlockType.CALL
            
        # Check if return block
        if last_inst.is_return:
            return BlockType.RETURN
            
        # Check if branch block
        if last_inst.is_branch:
            return BlockType.BRANCH
            
        return BlockType.NORMAL
    
    def _is_unconditional_branch(self, inst: Instruction) -> bool:
        """Check if instruction is an unconditional branch"""
        # BC 15,x is unconditional
        if inst.mnemonic == "BC" and inst.operands and inst.operands[0] == "15":
            return True
        # BCR 15,x is unconditional  
        if inst.mnemonic == "BCR" and inst.operands and inst.operands[0] == "15":
            return True
        # B is always unconditional (extended mnemonic for BC 15)
        if inst.mnemonic == "B":
            return True
        # BR is unconditional
        if inst.mnemonic == "BR":
            return True
        return False
    
    def _find_block_by_address(self, address: int) -> Optional[BasicBlock]:
        """Find the basic block containing the given address"""
        for block in self.blocks.values():
            if block.start_address <= address <= block.end_address:
                return block
        return None
    
    def _find_next_block(self, block: BasicBlock) -> Optional[BasicBlock]:
        """Find the next block in address order"""
        next_addr = None
        
        # Find the minimum address greater than this block's end
        for other_block in self.blocks.values():
            if other_block.start_address > block.end_address:
                if next_addr is None or other_block.start_address < next_addr:
                    next_addr = other_block.start_address
        
        if next_addr:
            return self._find_block_by_address(next_addr)
        return None


class ProcedureDetector:
    """Detects procedure boundaries using heuristics"""
    
    def __init__(self):
        self.procedures: Dict[str, Procedure] = {}
        self.proc_counter = 1
        
    def detect_procedures(self, cfg: ControlFlowGraph) -> Dict[str, Procedure]:
        """Detect procedures in the CFG"""
        # Method 1: Entry points are procedures
        for entry_point in cfg.entry_points:
            self._create_procedure_from_entry(entry_point, cfg)
        
        # Method 2: Targets of BALR/BASR are procedures
        self._detect_call_targets(cfg)
        
        # Method 3: Prologue pattern detection
        self._detect_prologues(cfg)
        
        # Build call graph
        self._build_call_graph(cfg)
        
        cfg.procedures = self.procedures
        return self.procedures
    
    def _create_procedure_from_entry(self, entry_addr: int, cfg: ControlFlowGraph):
        """Create a procedure from an entry point"""
        block = self._find_block_by_address(entry_addr, cfg)
        if not block:
            return
            
        proc_id = f"proc_{self.proc_counter:04d}"
        self.proc_counter += 1
        
        proc = Procedure(
            id=proc_id,
            name=f"ENTRY_{entry_addr:08X}",
            entry_address=entry_addr,
            detection_method="entry_point",
            confidence=0.95
        )
        
        # Find all blocks in this procedure (simplified - just connected blocks)
        visited = set()
        self._collect_procedure_blocks(block, proc, cfg, visited)
        
        self.procedures[proc_id] = proc
    
    def _detect_call_targets(self, cfg: ControlFlowGraph):
        """Detect procedures from call instructions"""
        for block in cfg.basic_blocks.values():
            for inst in block.instructions:
                if inst.is_call and inst.branch_target:
                    # Check if target is already in a procedure
                    if not self._address_in_procedures(inst.branch_target):
                        target_block = self._find_block_by_address(inst.branch_target, cfg)
                        if target_block:
                            proc_id = f"proc_{self.proc_counter:04d}"
                            self.proc_counter += 1
                            
                            proc = Procedure(
                                id=proc_id,
                                name=f"SUB_{inst.branch_target:08X}",
                                entry_address=inst.branch_target,
                                detection_method="call_target",
                                confidence=0.85
                            )
                            
                            visited = set()
                            self._collect_procedure_blocks(target_block, proc, cfg, visited)
                            self.procedures[proc_id] = proc
    
    def _detect_prologues(self, cfg: ControlFlowGraph):
        """Detect procedures by prologue patterns"""
        for block in cfg.basic_blocks.values():
            if block.instructions and not self._address_in_procedures(block.start_address):
                first_inst = block.instructions[0]
                
                # Common prologue: STM 14,12,12(13) - save registers
                if first_inst.mnemonic == "STM" and first_inst.operands:
                    if len(first_inst.operands) >= 2 and first_inst.operands[0] == "14":
                        proc_id = f"proc_{self.proc_counter:04d}"
                        self.proc_counter += 1
                        
                        proc = Procedure(
                            id=proc_id,
                            name=f"FUNC_{block.start_address:08X}",
                            entry_address=block.start_address,
                            detection_method="prologue_pattern",
                            confidence=0.75
                        )
                        
                        visited = set()
                        self._collect_procedure_blocks(block, proc, cfg, visited)
                        self.procedures[proc_id] = proc
    
    def _collect_procedure_blocks(self, start_block: BasicBlock, proc: Procedure, 
                                 cfg: ControlFlowGraph, visited: Set[str]):
        """Collect all blocks belonging to a procedure"""
        if start_block.id in visited:
            return
            
        visited.add(start_block.id)
        proc.basic_blocks.append(start_block.id)
        
        # Check for return instruction
        if start_block.instructions:
            last_inst = start_block.instructions[-1]
            if last_inst.is_return:
                proc.exit_addresses.append(last_inst.address)
        
        # Follow successors (but not call targets)
        for succ_id in start_block.successors:
            if succ_id not in visited:
                succ_block = cfg.basic_blocks.get(succ_id)
                if succ_block and not self._is_call_edge(start_block, succ_block):
                    self._collect_procedure_blocks(succ_block, proc, cfg, visited)
    
    def _build_call_graph(self, cfg: ControlFlowGraph):
        """Build call relationships between procedures"""
        for proc in self.procedures.values():
            for block_id in proc.basic_blocks:
                block = cfg.basic_blocks.get(block_id)
                if block:
                    for inst in block.instructions:
                        if inst.is_call and inst.branch_target:
                            # Find target procedure
                            target_proc = self._find_procedure_by_address(inst.branch_target)
                            if target_proc:
                                proc.calls_to.add(target_proc.id)
                                target_proc.called_by.add(proc.id)
                                
                                # Update CFG call graph
                                if proc.id not in cfg.call_graph:
                                    cfg.call_graph[proc.id] = set()
                                cfg.call_graph[proc.id].add(target_proc.id)
    
    def _find_block_by_address(self, address: int, cfg: ControlFlowGraph) -> Optional[BasicBlock]:
        """Find block containing address"""
        for block in cfg.basic_blocks.values():
            if block.start_address <= address <= block.end_address:
                return block
        return None
    
    def _address_in_procedures(self, address: int) -> bool:
        """Check if address is already in a procedure"""
        for proc in self.procedures.values():
            if proc.entry_address == address:
                return True
        return False
    
    def _find_procedure_by_address(self, address: int) -> Optional[Procedure]:
        """Find procedure by entry address"""
        for proc in self.procedures.values():
            if proc.entry_address == address:
                return proc
        return None
    
    def _is_call_edge(self, from_block: BasicBlock, to_block: BasicBlock) -> bool:
        """Check if edge is a call edge"""
        if from_block.instructions:
            last_inst = from_block.instructions[-1]
            if last_inst.is_call and last_inst.branch_target == to_block.start_address:
                return True
        return False
