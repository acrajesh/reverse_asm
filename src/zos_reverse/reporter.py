"""Report writer - generates text, YAML, and JSON output formats"""

import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from .ir import DisassemblyResult
from .reconstructor import AssemblerReconstructor
from .pseudocode import PseudocodeGenerator

logger = logging.getLogger(__name__)


class ReportWriter:
    """Generates reports in multiple formats"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def write_reports(self, disasm_result: DisassemblyResult, 
                     base_name: Optional[str] = None,
                     formats: Optional[list] = None) -> Dict[str, Path]:
        """Write reports in specified formats"""
        if not base_name:
            base_name = disasm_result.metadata.name or "output"
            
        if not formats:
            formats = ['text', 'yaml', 'json']
        
        output_files = {}
        
        if 'text' in formats:
            output_files['text'] = self._write_text_report(disasm_result, base_name)
            
        if 'yaml' in formats:
            output_files['yaml'] = self._write_yaml_report(disasm_result, base_name)
            
        if 'json' in formats:
            output_files['json'] = self._write_json_report(disasm_result, base_name)
            
        if 'asm' in formats:
            output_files['asm'] = self._write_asm_listing(disasm_result, base_name)
            
        if 'pseudocode' in formats:
            output_files['pseudocode'] = self._write_pseudocode(disasm_result, base_name)
            
        return output_files
    
    def _write_text_report(self, disasm_result: DisassemblyResult, base_name: str) -> Path:
        """Write human-readable text report"""
        output_file = self.output_dir / f"{base_name}_report.txt"
        
        with open(output_file, 'w') as f:
            # Header
            f.write("=" * 80 + "\n")
            f.write("z/OS BINARY REVERSE ENGINEERING REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            # Timestamp
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            
            # Module information
            f.write("MODULE INFORMATION\n")
            f.write("-" * 40 + "\n")
            metadata = disasm_result.metadata
            f.write(f"Name: {metadata.name or 'Unknown'}\n")
            f.write(f"Format: {metadata.format_type}\n")
            f.write(f"Entry Point: 0x{metadata.entry_point:08X}\n" if metadata.entry_point else "Entry Point: Unknown\n")
            f.write(f"AMODE: {metadata.amode}\n" if metadata.amode else "")
            f.write(f"RMODE: {metadata.rmode}\n" if metadata.rmode else "")
            
            if metadata.external_symbols:
                f.write("\nExternal Symbols:\n")
                for sym in metadata.external_symbols:
                    f.write(f"  - {sym}\n")
            f.write("\n")
            
            # Disassembly statistics
            f.write("DISASSEMBLY STATISTICS\n")
            f.write("-" * 40 + "\n")
            stats = disasm_result.statistics
            f.write(f"Instructions decoded: {stats.get('instruction_count', 0)}\n")
            f.write(f"Bytes decoded: {stats.get('decoded_bytes', 0)}\n")
            f.write(f"Unknown bytes: {stats.get('unknown_bytes', 0)}\n")
            f.write(f"Decode rate: {stats.get('decode_rate', 0):.1%}\n")
            f.write(f"Branch instructions: {stats.get('branch_count', 0)}\n")
            f.write(f"Call instructions: {stats.get('call_count', 0)}\n")
            f.write(f"Return instructions: {stats.get('return_count', 0)}\n")
            f.write("\n")
            
            # Control flow analysis
            f.write("CONTROL FLOW ANALYSIS\n")
            f.write("-" * 40 + "\n")
            cfg = disasm_result.cfg
            f.write(f"Basic blocks: {len(cfg.basic_blocks)}\n")
            f.write(f"Procedures detected: {len(cfg.procedures)}\n")
            f.write(f"Unresolved branches: {len(cfg.unresolved_branches)}\n")
            
            if cfg.procedures:
                f.write("\nDetected Procedures:\n")
                for proc in sorted(cfg.procedures.values(), key=lambda p: p.entry_address):
                    f.write(f"  - {proc.name} @ 0x{proc.entry_address:08X}")
                    f.write(f" (confidence: {proc.confidence.value}, method: {proc.detection_method})\n")
                    if proc.calls_to:
                        called_names = [cfg.procedures[pid].name for pid in proc.calls_to if pid in cfg.procedures]
                        f.write(f"    Calls: {', '.join(called_names)}\n")
            f.write("\n")
            
            # Call graph
            if cfg.call_graph:
                f.write("CALL GRAPH\n")
                f.write("-" * 40 + "\n")
                for caller, callees in cfg.call_graph.items():
                    caller_name = cfg.procedures[caller].name if caller in cfg.procedures else caller
                    f.write(f"{caller_name}:\n")
                    for callee in callees:
                        callee_name = cfg.procedures[callee].name if callee in cfg.procedures else callee
                        f.write(f"  -> {callee_name}\n")
                f.write("\n")
            
            # Unknown regions
            if disasm_result.unknown_regions:
                f.write("UNKNOWN REGIONS\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total regions: {len(disasm_result.unknown_regions)}\n")
                total_unknown = sum(end - start + 1 for start, end, _ in disasm_result.unknown_regions)
                f.write(f"Total bytes: {total_unknown}\n")
                f.write("\nRegions:\n")
                for start, end, _ in disasm_result.unknown_regions[:10]:  # First 10
                    f.write(f"  0x{start:08X} - 0x{end:08X} ({end - start + 1} bytes)\n")
                if len(disasm_result.unknown_regions) > 10:
                    f.write(f"  ... and {len(disasm_result.unknown_regions) - 10} more\n")
                f.write("\n")
            
            # Warnings
            if disasm_result.warnings:
                f.write("WARNINGS\n")
                f.write("-" * 40 + "\n")
                for warning in disasm_result.warnings:
                    f.write(f"  - {warning}\n")
                f.write("\n")
            
            # Top mnemonics
            if 'top_mnemonics' in stats:
                f.write("TOP INSTRUCTION MNEMONICS\n")
                f.write("-" * 40 + "\n")
                for mnem, count in stats['top_mnemonics']:
                    f.write(f"  {mnem:10} : {count:5} occurrences\n")
        
        logger.info(f"Text report written to {output_file}")
        return output_file
    
    def _write_yaml_report(self, disasm_result: DisassemblyResult, base_name: str) -> Path:
        """Write YAML format report"""
        output_file = self.output_dir / f"{base_name}_analysis.yaml"
        
        data = {
            'metadata': disasm_result.metadata.to_dict(),
            'statistics': disasm_result.statistics,
            'cfg': disasm_result.cfg.to_dict(),
            'unknown_regions': [
                {'start': f'0x{s:08X}', 'end': f'0x{e:08X}', 'size': e - s + 1}
                for s, e, _ in disasm_result.unknown_regions
            ],
            'warnings': disasm_result.warnings,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(output_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"YAML report written to {output_file}")
        return output_file
    
    def _write_json_report(self, disasm_result: DisassemblyResult, base_name: str) -> Path:
        """Write JSON format report"""
        output_file = self.output_dir / f"{base_name}_analysis.json"
        
        data = {
            'metadata': disasm_result.metadata.to_dict(),
            'statistics': disasm_result.statistics,
            'cfg': disasm_result.cfg.to_dict(),
            'instructions': [inst.to_dict() for inst in disasm_result.instructions[:1000]],  # Limit for size
            'unknown_regions': [
                {'start': f'0x{s:08X}', 'end': f'0x{e:08X}', 'size': e - s + 1}
                for s, e, _ in disasm_result.unknown_regions
            ],
            'warnings': disasm_result.warnings,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"JSON report written to {output_file}")
        return output_file
    
    def _write_asm_listing(self, disasm_result: DisassemblyResult, base_name: str) -> Path:
        """Write reconstructed assembly listing"""
        output_file = self.output_dir / f"{base_name}.asm"
        
        reconstructor = AssemblerReconstructor()
        asm_text = reconstructor.reconstruct(disasm_result)
        
        with open(output_file, 'w') as f:
            f.write(asm_text)
        
        logger.info(f"Assembly listing written to {output_file}")
        return output_file
    
    def _write_pseudocode(self, disasm_result: DisassemblyResult, base_name: str) -> Path:
        """Write pseudocode representation"""
        output_file = self.output_dir / f"{base_name}_pseudocode.txt"
        
        generator = PseudocodeGenerator()
        pseudocode = generator.generate(disasm_result.cfg)
        
        with open(output_file, 'w') as f:
            f.write(pseudocode)
        
        logger.info(f"Pseudocode written to {output_file}")
        return output_file
    
    def write_portfolio_index(self, results: Dict[str, DisassemblyResult]) -> Path:
        """Write index file for batch processing results"""
        index_file = self.output_dir / "portfolio_index.yaml"
        
        index_data = {
            'modules': [],
            'total_modules': len(results),
            'timestamp': datetime.now().isoformat()
        }
        
        total_instructions = 0
        total_procedures = 0
        total_unknown_bytes = 0
        
        for name, result in results.items():
            module_info = {
                'name': name,
                'format': result.metadata.format_type,
                'instructions': result.statistics.get('instruction_count', 0),
                'procedures': len(result.cfg.procedures),
                'decode_rate': result.statistics.get('decode_rate', 0),
                'entry_point': f"0x{result.metadata.entry_point:08X}" if result.metadata.entry_point else None
            }
            index_data['modules'].append(module_info)
            
            total_instructions += result.statistics.get('instruction_count', 0)
            total_procedures += len(result.cfg.procedures)
            total_unknown_bytes += result.statistics.get('unknown_bytes', 0)
        
        index_data['summary'] = {
            'total_instructions': total_instructions,
            'total_procedures': total_procedures,
            'total_unknown_bytes': total_unknown_bytes,
            'average_decode_rate': sum(m['decode_rate'] for m in index_data['modules']) / len(results) if results else 0
        }
        
        with open(index_file, 'w') as f:
            yaml.dump(index_data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Portfolio index written to {index_file}")
        return index_file
