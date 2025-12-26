"""Disassembler interface with pluggable decoder for z/Architecture instructions"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import struct
import logging

from .ir import Instruction, InstructionFormat, DisassemblyResult, ModuleMetadata, ControlFlowGraph, Confidence

logger = logging.getLogger(__name__)


class DecoderInterface(ABC):
    """Abstract interface for instruction decoders"""
    
    @abstractmethod
    def decode_instruction(self, data: bytes, offset: int, address: int) -> Optional[Instruction]:
        """Decode a single instruction at the given offset"""
        pass
    
    @abstractmethod
    def get_instruction_length(self, opcode: int) -> int:
        """Get the length of an instruction based on its opcode"""
        pass


class NativeDecoder(DecoderInterface):
    """Native Python decoder for z/Architecture instructions"""
    
    # Instruction length table based on first byte of opcode
    OPCODE_LENGTHS = {
        # 2-byte instructions (RR format)
        0x00: 2, 0x01: 2, 0x02: 2, 0x03: 2, 0x04: 2, 0x05: 2, 0x06: 2, 0x07: 2,
        0x08: 2, 0x09: 2, 0x0A: 2, 0x0B: 2, 0x0C: 2, 0x0D: 2, 0x0E: 2, 0x0F: 2,
        0x10: 2, 0x11: 2, 0x12: 2, 0x13: 2, 0x14: 2, 0x15: 2, 0x16: 2, 0x17: 2,
        0x18: 2, 0x19: 2, 0x1A: 2, 0x1B: 2, 0x1C: 2, 0x1D: 2, 0x1E: 2, 0x1F: 2,
        
        # 4-byte instructions (RX, RS, SI formats)
        0x40: 4, 0x41: 4, 0x42: 4, 0x43: 4, 0x44: 4, 0x45: 4, 0x46: 4, 0x47: 4,
        0x48: 4, 0x49: 4, 0x4A: 4, 0x4B: 4, 0x4C: 4, 0x4D: 4, 0x4E: 4, 0x4F: 4,
        0x50: 4, 0x51: 4, 0x54: 4, 0x55: 4, 0x56: 4, 0x57: 4, 0x58: 4, 0x59: 4,
        0x5A: 4, 0x5B: 4, 0x5C: 4, 0x5D: 4, 0x5E: 4, 0x5F: 4,
        
        # 4-byte instructions continued
        0x86: 4, 0x87: 4, 0x88: 4, 0x89: 4, 0x8A: 4, 0x8B: 4, 0x8C: 4, 0x8D: 4,
        0x8E: 4, 0x8F: 4, 0x90: 4, 0x91: 4, 0x92: 4, 0x94: 4, 0x95: 4, 0x96: 4,
        0x97: 4, 0x98: 4, 0x99: 4, 0x9A: 4, 0x9B: 4,
        
        # 6-byte instructions (SS format)
        0xD0: 6, 0xD1: 6, 0xD2: 6, 0xD3: 6, 0xD4: 6, 0xD5: 6, 0xD6: 6, 0xD7: 6,
        0xD9: 6, 0xDA: 6, 0xDB: 6, 0xDC: 6, 0xDD: 6, 0xDE: 6, 0xDF: 6,
        0xF0: 6, 0xF1: 6, 0xF2: 6, 0xF3: 6, 0xF8: 6, 0xF9: 6, 0xFA: 6, 0xFB: 6,
        0xFC: 6, 0xFD: 6,
        
        # Extended opcodes (prefix determines length)
        0xA5: 4, 0xA7: 4, 0xB2: 4, 0xB3: 4, 0xB9: 4,  # Extended formats
        0xC0: 6, 0xC2: 6, 0xC4: 6, 0xC6: 6, 0xC8: 6,  # RIL formats
        0xE3: 6, 0xE5: 4, 0xEB: 6, 0xEC: 6, 0xED: 6,  # Extended formats
    }
    
    # Common instruction mnemonics
    MNEMONICS = {
        0x05: "BALR", 0x0D: "BASR", 0x07: "BCR", 0x47: "BC",
        0x18: "LR", 0x58: "L", 0x50: "ST", 0x90: "STM", 0x98: "LM",
        0x41: "LA", 0x1A: "AR", 0x5A: "A", 0x1B: "SR", 0x5B: "S",
        0x12: "LTR", 0x55: "CL", 0x95: "CLI", 0x15: "CLR",
        0x19: "CR", 0x59: "C", 0x89: "SLL", 0x88: "SRL",
        0x13: "LCR", 0x11: "LNR", 0x10: "LPR", 0x14: "NR",
        0x16: "OR", 0x17: "XR", 0x54: "N", 0x56: "O", 0x57: "X",
        0x96: "OI", 0x94: "NI", 0x97: "XI", 0x92: "MVI",
        0x43: "IC", 0x42: "STC", 0x44: "EX", 0x45: "BAL",
        0x46: "BCT", 0x8E: "SRDA", 0x8C: "SRDL", 0x8D: "SLDA",
        0x86: "BXH", 0x87: "BXLE", 0xD2: "MVC", 0xD5: "CLC",
        0xDC: "TR", 0xDD: "TRT", 0xD1: "MVN", 0xD3: "MVZ",
        0xF1: "MVO", 0xF2: "PACK", 0xF3: "UNPK", 0xD7: "XC",
        0xD6: "OC", 0xD4: "NC", 0xD9: "MVCK", 0xDA: "MVCP",
        0xDB: "MVCS", 0xDE: "ED", 0xDF: "EDMK", 0xFA: "AP",
        0xFB: "SP", 0xF8: "ZAP", 0xF9: "CP", 0xFC: "MP", 0xFD: "DP",
    }
    
    def decode_instruction(self, data: bytes, offset: int, address: int) -> Optional[Instruction]:
        """Decode a single instruction"""
        if offset >= len(data):
            return None
            
        opcode = data[offset]
        length = self.get_instruction_length(opcode)
        
        if offset + length > len(data):
            # Not enough bytes for complete instruction
            return None
            
        inst_bytes = data[offset:offset + length]
        hex_str = inst_bytes.hex().upper()
        
        # Get mnemonic and decode operands
        mnemonic, operands, fmt = self._decode_instruction_details(inst_bytes)
        
        # Determine instruction type
        is_branch = mnemonic in ["BC", "BCR", "BAL", "BALR", "BASR", "BAS", "BXH", "BXLE", "BCT", "BCTR"]
        is_call = mnemonic in ["BALR", "BASR", "BAL", "BAS"]
        is_return = (mnemonic == "BCR" and operands and operands[0] == "15") or \
                   (mnemonic == "BR" and operands and operands[0] == "14")
        
        # Calculate branch target if applicable
        branch_target = None
        if is_branch and length >= 4:
            branch_target = self._calculate_branch_target(inst_bytes, address, fmt)
        
        return Instruction(
            address=address,
            raw_bytes=inst_bytes,
            hex_bytes=hex_str,
            mnemonic=mnemonic,
            operands=operands,
            format=fmt,
            is_branch=is_branch,
            is_call=is_call,
            is_return=is_return,
            branch_target=branch_target,
            confidence=Confidence.HIGH if mnemonic != "UNKNOWN" else Confidence.LOW
        )
    
    def get_instruction_length(self, opcode: int) -> int:
        """Get instruction length based on opcode"""
        # Check for extended opcodes
        if opcode in [0xB2, 0xB3, 0xB9]:
            return 4  # RRE format
        elif opcode in [0xE3, 0xEB, 0xEC, 0xED]:
            return 6  # RXY, RSY formats
        elif opcode in [0xC0, 0xC2, 0xC4, 0xC6, 0xC8]:
            return 6  # RIL format
            
        # Use lookup table
        return self.OPCODE_LENGTHS.get(opcode, 2)  # Default to 2
    
    def _decode_instruction_details(self, inst_bytes: bytes) -> Tuple[str, List[str], InstructionFormat]:
        """Decode instruction mnemonic and operands"""
        opcode = inst_bytes[0]
        length = len(inst_bytes)
        
        # Get mnemonic
        mnemonic = self.MNEMONICS.get(opcode, "UNKNOWN")
        operands = []
        fmt = InstructionFormat.UNKNOWN
        
        if length == 2:
            # RR format: opcode(1) R1R2(1)
            fmt = InstructionFormat.RR
            if len(inst_bytes) >= 2:
                r1 = (inst_bytes[1] >> 4) & 0xF
                r2 = inst_bytes[1] & 0xF
                operands = [str(r1), str(r2)]
                
        elif length == 4:
            # Could be RX, RS, or SI format
            if opcode >= 0x90 and opcode <= 0x9B:
                # SI format: opcode(1) I2(1) B1D1(2)
                fmt = InstructionFormat.SI
                i2 = inst_bytes[1]
                b1 = (inst_bytes[2] >> 4) & 0xF
                d1 = ((inst_bytes[2] & 0xF) << 8) | inst_bytes[3]
                operands = [f"X'{i2:02X}'", f"{d1}({b1})"]
            elif opcode in [0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F]:
                # RS format: opcode(1) R1R3(1) B2D2(2)
                fmt = InstructionFormat.RS
                r1 = (inst_bytes[1] >> 4) & 0xF
                r3 = inst_bytes[1] & 0xF
                b2 = (inst_bytes[2] >> 4) & 0xF
                d2 = ((inst_bytes[2] & 0xF) << 8) | inst_bytes[3]
                operands = [str(r1), str(r3), f"{d2}({b2})"]
            else:
                # RX format: opcode(1) R1X2(1) B2D2(2)
                fmt = InstructionFormat.RX
                r1 = (inst_bytes[1] >> 4) & 0xF
                x2 = inst_bytes[1] & 0xF
                b2 = (inst_bytes[2] >> 4) & 0xF
                d2 = ((inst_bytes[2] & 0xF) << 8) | inst_bytes[3]
                if x2 != 0:
                    operands = [str(r1), f"{d2}({x2},{b2})"]
                else:
                    operands = [str(r1), f"{d2}({b2})"]
                    
        elif length == 6:
            # SS format or extended format
            if opcode >= 0xD0 and opcode <= 0xDF:
                # SS format: opcode(1) L(1) B1D1(2) B2D2(2)
                fmt = InstructionFormat.SS
                ll = inst_bytes[1]
                b1 = (inst_bytes[2] >> 4) & 0xF
                d1 = ((inst_bytes[2] & 0xF) << 8) | inst_bytes[3]
                b2 = (inst_bytes[4] >> 4) & 0xF
                d2 = ((inst_bytes[4] & 0xF) << 8) | inst_bytes[5]
                operands = [f"{d1}({ll},{b1})", f"{d2}({b2})"]
            elif opcode in [0xC0, 0xC2, 0xC4, 0xC6, 0xC8]:
                # RIL format: opcode(2) R1(1) I2(4)
                fmt = InstructionFormat.RIL
                r1 = (inst_bytes[1] >> 4) & 0xF
                i2 = struct.unpack('>I', inst_bytes[2:6])[0]
                operands = [str(r1), f"X'{i2:08X}'"]
                
        return mnemonic, operands, fmt
    
    def _calculate_branch_target(self, inst_bytes: bytes, address: int, fmt: InstructionFormat) -> Optional[int]:
        """Calculate branch target address"""
        if fmt == InstructionFormat.RX and len(inst_bytes) >= 4:
            # RX format branch (e.g., BC)
            b2 = (inst_bytes[2] >> 4) & 0xF
            d2 = ((inst_bytes[2] & 0xF) << 8) | inst_bytes[3]
            if b2 == 0:
                # Absolute address
                return d2
            # Else it's base-displacement, cannot resolve without register values
            
        elif fmt == InstructionFormat.RIL and len(inst_bytes) >= 6:
            # RIL format with relative addressing
            offset = struct.unpack('>i', inst_bytes[2:6])[0]
            return address + (offset * 2)  # Halfword addressing
            
        return None


# ExternalDecoder removed for MVP - interface preserved for future extension


class Disassembler:
    """Main disassembler that uses pluggable decoders"""
    
    def __init__(self, decoder: Optional[DecoderInterface] = None):
        self.decoder = decoder or NativeDecoder()
        self.instructions: List[Instruction] = []
        self.unknown_regions: List[Tuple[int, int, bytes]] = []
        
    def disassemble(self, data: bytes, base_address: int = 0, metadata: Optional[ModuleMetadata] = None) -> DisassemblyResult:
        """Disassemble binary data into instructions"""
        self.instructions = []
        self.unknown_regions = []
        
        offset = 0
        current_address = base_address
        unknown_start = None
        unknown_bytes = b''
        
        while offset < len(data):
            # Try to decode instruction
            inst = self.decoder.decode_instruction(data, offset, current_address)
            
            if inst:
                # Successfully decoded
                if unknown_start is not None:
                    # Save previous unknown region
                    self.unknown_regions.append((unknown_start, current_address - 1, unknown_bytes))
                    unknown_start = None
                    unknown_bytes = b''
                    
                self.instructions.append(inst)
                offset += len(inst.raw_bytes)
                current_address += len(inst.raw_bytes)
            else:
                # Failed to decode - mark as unknown
                if unknown_start is None:
                    unknown_start = current_address
                    
                unknown_bytes += data[offset:offset + 1]
                offset += 1
                current_address += 1
        
        # Handle any remaining unknown region
        if unknown_start is not None:
            self.unknown_regions.append((unknown_start, current_address - 1, unknown_bytes))
        
        # Create CFG (will be populated by CFG builder)
        cfg = ControlFlowGraph(
            module_name=metadata.name if metadata else "unknown",
            entry_points=[metadata.entry_point] if metadata and metadata.entry_point else [base_address]
        )
        
        # Generate statistics
        stats = self._generate_statistics()
        
        return DisassemblyResult(
            metadata=metadata or ModuleMetadata(),
            instructions=self.instructions,
            cfg=cfg,
            unknown_regions=self.unknown_regions,
            statistics=stats
        )
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """Generate disassembly statistics"""
        total_bytes = sum(len(inst.raw_bytes) for inst in self.instructions)
        unknown_bytes = sum(end - start + 1 for start, end, _ in self.unknown_regions)
        
        mnemonic_counts = {}
        for inst in self.instructions:
            mnemonic_counts[inst.mnemonic] = mnemonic_counts.get(inst.mnemonic, 0) + 1
            
        return {
            'instruction_count': len(self.instructions),
            'decoded_bytes': total_bytes,
            'unknown_bytes': unknown_bytes,
            'decode_rate': total_bytes / (total_bytes + unknown_bytes) if (total_bytes + unknown_bytes) > 0 else 0,
            'branch_count': sum(1 for inst in self.instructions if inst.is_branch),
            'call_count': sum(1 for inst in self.instructions if inst.is_call),
            'return_count': sum(1 for inst in self.instructions if inst.is_return),
            'top_mnemonics': sorted(mnemonic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        }
