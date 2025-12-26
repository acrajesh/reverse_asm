"""Assembler reconstructor - generates HLASM-like output from disassembly"""

from typing import List, Optional, Dict, Any
import logging

from .ir import DisassemblyResult, Instruction, BasicBlock, Procedure

logger = logging.getLogger(__name__)


class AssemblerReconstructor:
    """Reconstructs HLASM-like assembly listing from disassembly"""
    
    def __init__(self):
        self.output_lines: List[str] = []
        self.include_annotations = True
        self.include_confidence = True
        
    def reconstruct(self, disasm_result: DisassemblyResult) -> str:
        """Generate reconstructed assembler listing"""
        self.output_lines = []
        
        # Add header
        self._add_header(disasm_result)
        
        # Add metadata section if available
        if disasm_result.metadata:
            self._add_metadata_section(disasm_result.metadata)
        
        # Group instructions by procedure if available
        if disasm_result.cfg.procedures:
            self._add_procedures_section(disasm_result)
        else:
            # Fall back to linear listing
            self._add_linear_listing(disasm_result.instructions)
        
        # Add unknown regions
        if disasm_result.unknown_regions:
            self._add_unknown_regions(disasm_result.unknown_regions)
        
        # Add statistics
        self._add_statistics(disasm_result.statistics)
        
        return "\n".join(self.output_lines)
    
    def _add_header(self, disasm_result: DisassemblyResult):
        """Add listing header"""
        self.output_lines.extend([
            "*" * 80,
            "* z/OS Binary Reverse Engineering - Reconstructed Assembly",
            "* Module: " + (disasm_result.metadata.name or "UNKNOWN"),
            "* Format: " + (disasm_result.metadata.format_type or "unknown"),
            "* Note: This is reconstructed code with synthetic labels",
            "*" * 80,
            ""
        ])
    
    def _add_metadata_section(self, metadata):
        """Add metadata information"""
        self.output_lines.extend([
            "* Metadata:",
            f"*   Entry Point: 0x{metadata.entry_point:08X}" if metadata.entry_point else "*   Entry Point: unknown",
            f"*   AMODE: {metadata.amode}" if metadata.amode else "*   AMODE: unknown",
            f"*   RMODE: {metadata.rmode}" if metadata.rmode else "*   RMODE: unknown",
        ])
        
        if metadata.external_symbols:
            self.output_lines.append("*   External Symbols:")
            for sym in metadata.external_symbols:
                self.output_lines.append(f"*     - {sym}")
        
        self.output_lines.append("")
    
    def _add_procedures_section(self, disasm_result: DisassemblyResult):
        """Add procedures with their instructions"""
        # Build instruction to procedure mapping
        inst_to_proc: Dict[int, str] = {}
        for proc in disasm_result.cfg.procedures.values():
            for block_id in proc.basic_blocks:
                block = disasm_result.cfg.basic_blocks.get(block_id)
                if block:
                    for inst in block.instructions:
                        inst_to_proc[inst.address] = proc.id
        
        # Output procedures
        for proc in sorted(disasm_result.cfg.procedures.values(), key=lambda p: p.entry_address):
            self._add_procedure(proc, disasm_result)
        
        # Output orphan instructions (not in any procedure)
        orphans = []
        for inst in disasm_result.instructions:
            if inst.address not in inst_to_proc:
                orphans.append(inst)
        
        if orphans:
            self.output_lines.extend([
                "",
                "*" * 80,
                "* Orphan Instructions (not in any detected procedure)",
                "*" * 80,
            ])
            self._add_instruction_list(orphans)
    
    def _add_procedure(self, proc: Procedure, disasm_result: DisassemblyResult):
        """Add a single procedure"""
        self.output_lines.extend([
            "",
            "*" * 80,
            f"* Procedure: {proc.name}",
            f"* Entry: 0x{proc.entry_address:08X}",
            f"* Detection: {proc.detection_method} (confidence: {proc.confidence:.2f})",
        ])
        
        if proc.calls_to:
            calls = [disasm_result.cfg.procedures.get(pid).name for pid in proc.calls_to 
                    if pid in disasm_result.cfg.procedures]
            self.output_lines.append(f"* Calls: {', '.join(calls)}")
        
        self.output_lines.extend([
            "*" * 80,
            ""
        ])
        
        # Collect all instructions in this procedure
        proc_instructions = []
        for block_id in proc.basic_blocks:
            block = disasm_result.cfg.basic_blocks.get(block_id)
            if block:
                # Add block comment
                if len(proc.basic_blocks) > 1:
                    self.output_lines.append(f"* Basic Block: {block_id} (type: {block.block_type.value})")
                proc_instructions.extend(block.instructions)
        
        # Sort by address and output
        proc_instructions.sort(key=lambda i: i.address)
        self._add_instruction_list(proc_instructions)
    
    def _add_linear_listing(self, instructions: List[Instruction]):
        """Add linear instruction listing"""
        self.output_lines.extend([
            "",
            "* Instructions (linear listing):",
            ""
        ])
        self._add_instruction_list(instructions)
    
    def _add_instruction_list(self, instructions: List[Instruction]):
        """Add a list of instructions in HLASM format"""
        for inst in instructions:
            line = inst.to_asm_line()
            
            # Add confidence indicator if low
            if self.include_confidence and inst.confidence < 0.8:
                line += f"  [conf: {inst.confidence:.2f}]"
            
            self.output_lines.append(line)
    
    def _add_unknown_regions(self, unknown_regions: List[tuple]):
        """Add unknown/undecodable regions"""
        if not unknown_regions:
            return
            
        self.output_lines.extend([
            "",
            "*" * 80,
            "* Unknown/Undecodable Regions",
            "*" * 80,
        ])
        
        for start, end, data in unknown_regions:
            size = end - start + 1
            self.output_lines.append(f"* Region: 0x{start:08X} - 0x{end:08X} ({size} bytes)")
            
            # Show first few bytes as hex
            hex_preview = data[:16].hex().upper() if len(data) > 0 else ""
            if len(data) > 16:
                hex_preview += "..."
            self.output_lines.append(f"*   Data: {hex_preview}")
        
        self.output_lines.append("")
    
    def _add_statistics(self, stats: Dict[str, Any]):
        """Add statistics section"""
        self.output_lines.extend([
            "",
            "*" * 80,
            "* Statistics",
            "*" * 80,
            f"* Instructions decoded: {stats.get('instruction_count', 0)}",
            f"* Bytes decoded: {stats.get('decoded_bytes', 0)}",
            f"* Unknown bytes: {stats.get('unknown_bytes', 0)}",
            f"* Decode rate: {stats.get('decode_rate', 0):.1%}",
            f"* Branches: {stats.get('branch_count', 0)}",
            f"* Calls: {stats.get('call_count', 0)}",
            f"* Returns: {stats.get('return_count', 0)}",
        ])
        
        if 'top_mnemonics' in stats:
            self.output_lines.append("* Top mnemonics:")
            for mnem, count in stats['top_mnemonics'][:5]:
                self.output_lines.append(f"*   {mnem:6} : {count}")
        
        self.output_lines.append("*" * 80)
