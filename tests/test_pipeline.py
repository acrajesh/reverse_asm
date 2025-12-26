"""Tests for the reverse engineering pipeline"""

import pytest
from pathlib import Path
import tempfile
import struct

from zos_reverse.pipeline import ReverseEngineeringPipeline
from zos_reverse.ingestion import BinaryIngestor
from zos_reverse.disassembler import NativeDecoder
from zos_reverse.ir import InstructionFormat


class TestPipeline:
    """Test the complete pipeline"""
    
    def test_native_decoder(self):
        """Test native decoder with known instructions"""
        decoder = NativeDecoder()
        
        # Test BALR 14,15 (common entry)
        data = bytes([0x05, 0xEF])
        inst = decoder.decode_instruction(data, 0, 0x1000)
        assert inst is not None
        assert inst.mnemonic == "BALR"
        assert inst.operands == ["14", "15"]
        assert inst.is_call == True
        
        # Test STM 14,12,12(13) - save registers
        data = bytes([0x90, 0xEC, 0xD0, 0x0C])
        inst = decoder.decode_instruction(data, 0, 0x1000)
        assert inst is not None
        assert inst.mnemonic == "STM"
        
        # Test BC 15,x - unconditional branch
        data = bytes([0x47, 0xF0, 0x10, 0x00])
        inst = decoder.decode_instruction(data, 0, 0x1000)
        assert inst is not None
        assert inst.mnemonic == "BC"
        assert inst.is_branch == True
    
    def test_synthetic_binary(self, tmp_path):
        """Test with a synthetic z/OS-like binary"""
        # Create synthetic binary with simple program structure
        # Entry: BALR 14,15 (establish base)
        # STM 14,12,12(13) (save registers)
        # LA 1,data_area (load address)
        # L 2,0(1) (load from address)
        # A 2,=F'1' (add 1)
        # ST 2,0(1) (store back)
        # LM 14,12,12(13) (restore registers)
        # BCR 15,14 (return)
        
        program = bytearray()
        
        # BALR 14,15
        program.extend([0x05, 0xEF])
        
        # STM 14,12,12(13)
        program.extend([0x90, 0xEC, 0xD0, 0x0C])
        
        # LA 1,X'100'
        program.extend([0x41, 0x10, 0x01, 0x00])
        
        # L 2,0(1)
        program.extend([0x58, 0x20, 0x10, 0x00])
        
        # A 2,X'200'
        program.extend([0x5A, 0x20, 0x02, 0x00])
        
        # ST 2,0(1)
        program.extend([0x50, 0x20, 0x10, 0x00])
        
        # LM 14,12,12(13)
        program.extend([0x98, 0xEC, 0xD0, 0x0C])
        
        # BCR 15,14 (BR 14)
        program.extend([0x07, 0xFE])
        
        # Write to file
        test_file = tmp_path / "test_program.bin"
        test_file.write_bytes(bytes(program))
        
        # Process with pipeline
        pipeline = ReverseEngineeringPipeline()
        result = pipeline.process_file(test_file)
        
        assert result is not None
        assert len(result.instructions) == 8
        assert result.statistics['decode_rate'] == 1.0
        assert len(result.cfg.basic_blocks) >= 1
        
        # Validate the result
        validation = pipeline.validate_result(result)
        assert validation['is_valid'] == True
    
    def test_ingestion_format_detection(self, tmp_path):
        """Test binary format detection"""
        ingestor = BinaryIngestor()
        
        # Test with load module pattern
        load_module = bytearray([0x47, 0xF0])  # BC 15,x pattern
        load_module.extend([0x10, 0x00] * 50)
        
        test_file = tmp_path / "load_module.bin"
        test_file.write_bytes(bytes(load_module))
        
        assert ingestor.load_file(test_file)
        assert ingestor.metadata.format_type in ['load_module', 'unknown']
        
    def test_cfg_builder(self):
        """Test CFG construction with branches"""
        from zos_reverse.disassembler import Disassembler
        from zos_reverse.cfg_builder import CFGBuilder
        
        # Create program with conditional branch
        program = bytearray()
        
        # Entry block
        program.extend([0x05, 0xEF])  # BALR 14,15
        program.extend([0x55, 0x20, 0x30, 0x00])  # CL 2,X'300'
        program.extend([0x47, 0x80, 0x00, 0x14])  # BC 8,X'14' (branch if equal)
        
        # Fall-through block
        program.extend([0x41, 0x10, 0x01, 0x00])  # LA 1,X'100'
        program.extend([0x47, 0xF0, 0x00, 0x1C])  # BC 15,X'1C' (unconditional)
        
        # Branch target block (offset 0x14)
        program.extend([0x41, 0x10, 0x02, 0x00])  # LA 1,X'200'
        
        # Common exit (offset 0x1C)
        program.extend([0x07, 0xFE])  # BCR 15,14 (return)
        
        # Disassemble
        disassembler = Disassembler()
        disasm_result = disassembler.disassemble(bytes(program))
        
        # Build CFG
        cfg_builder = CFGBuilder()
        cfg = cfg_builder.build_cfg(disasm_result)
        
        # Should have multiple basic blocks
        assert len(cfg.basic_blocks) >= 3
        
        # Check for branch edges
        has_branch_edge = False
        for block in cfg.basic_blocks.values():
            if block.branch_targets:
                has_branch_edge = True
                break
        assert has_branch_edge


class TestReporting:
    """Test report generation"""
    
    def test_report_formats(self, tmp_path):
        """Test different output formats"""
        from zos_reverse.reporter import ReportWriter
        from zos_reverse.ir import DisassemblyResult, ModuleMetadata, ControlFlowGraph
        
        # Create minimal result
        metadata = ModuleMetadata(name="TEST", format_type="load_module")
        cfg = ControlFlowGraph(module_name="TEST", entry_points=[0])
        result = DisassemblyResult(
            metadata=metadata,
            instructions=[],
            cfg=cfg,
            unknown_regions=[],
            statistics={'instruction_count': 0, 'decode_rate': 0}
        )
        
        # Generate reports
        writer = ReportWriter(tmp_path)
        files = writer.write_reports(result, formats=['text', 'yaml', 'json'])
        
        assert 'text' in files
        assert 'yaml' in files
        assert 'json' in files
        
        # Check files exist
        for fmt, path in files.items():
            assert path.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
