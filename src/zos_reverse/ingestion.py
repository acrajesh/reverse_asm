"""Binary artifact ingestion for z/OS load modules and program objects"""

import struct
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
import logging

from .ir import ModuleMetadata

logger = logging.getLogger(__name__)


class ArtifactFormat:
    """Format detection constants for z/OS binary artifacts"""
    LOAD_MODULE_MAGIC = b'\x00\x01'  # Classic load module indicator
    PROGRAM_OBJECT_MAGIC = b'\x00\x03'  # Binder-produced program object
    PDS_HEADER_SIZE = 20  # PDS directory entry size
    
    # Common z/OS record formats
    RECFM_F = 0x80   # Fixed
    RECFM_V = 0x40   # Variable
    RECFM_U = 0xC0   # Undefined
    

@dataclass
class LoadModuleHeader:
    """Classic load module header structure"""
    text_length: int
    origin: int
    entry_point: int
    attributes: int
    amode: int = 31
    rmode: str = "ANY"


@dataclass 
class ProgramObjectHeader:
    """Program object (binder) header structure"""
    version: int
    flags: int
    text_size: int
    entry_offset: int
    external_count: int
    section_count: int


class BinaryIngestor:
    """Ingests and identifies z/OS binary artifacts"""
    
    def __init__(self):
        self.data: bytes = b''
        self.metadata = ModuleMetadata()
        self.code_start = 0
        self.code_end = 0
        
    def load_file(self, file_path: Path) -> bool:
        """Load binary file and detect format"""
        try:
            with open(file_path, 'rb') as f:
                self.data = f.read()
                
            if len(self.data) < 8:
                logger.warning(f"File too small: {len(self.data)} bytes")
                return False
                
            self.metadata.name = file_path.stem
            self._detect_format()
            return True
            
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return False
    
    def _detect_format(self):
        """Detect whether artifact is load module or program object"""
        # Check for program object magic
        if len(self.data) >= 4 and self.data[0:2] == ArtifactFormat.PROGRAM_OBJECT_MAGIC:
            self.metadata.format_type = "program_object"
            self._parse_program_object()
        # Check for load module patterns
        elif self._looks_like_load_module():
            self.metadata.format_type = "load_module"
            self._parse_load_module()
        else:
            # Default to load module with heuristics
            self.metadata.format_type = "unknown"
            self._apply_heuristics()
            
    def _looks_like_load_module(self) -> bool:
        """Heuristic check for load module format"""
        # Check for common load module patterns:
        # - Starts with machine code (x'47F0' for branch)
        # - Has CSECT-like structure
        # - Contains valid z/Architecture opcodes
        
        if len(self.data) < 2:
            return False
            
        # Common entry point instructions
        entry_patterns = [
            b'\x47\xF0',  # BC 15,x (unconditional branch)
            b'\x90\xEC',  # STM 14,12,x (save registers)
            b'\x18\x0F',  # LR 0,15 (load register)
            b'\x05\xC0',  # BALR 12,0 (establish base)
        ]
        
        for pattern in entry_patterns:
            if self.data.startswith(pattern):
                return True
        
        return False
    
    def _parse_load_module(self):
        """Parse classic load module structure"""
        # Load modules typically have:
        # - Optional PDS directory info (if extracted with directory)
        # - Text (executable code)
        # - Possible RLD (relocation) data
        # - Possible ESD (external symbol) data
        
        offset = 0
        
        # Check for PDS directory entry
        if self._has_pds_header():
            offset = ArtifactFormat.PDS_HEADER_SIZE
            self._extract_pds_info(self.data[:offset])
        
        # The rest is assumed to be text (code)
        self.code_start = offset
        self.code_end = len(self.data)
        
        # Try to find entry point (usually at start of text)
        if self.code_start < len(self.data):
            self.metadata.entry_point = self.code_start
            
        # Extract AMODE/RMODE from attributes if available
        self._extract_attributes()
    
    def _parse_program_object(self):
        """Parse binder-produced program object"""
        # Program objects have more structured format
        # with sections, attributes, and external symbols
        
        if len(self.data) < 32:
            logger.warning("Program object too small for header")
            return
            
        # Parse basic header (simplified)
        header = ProgramObjectHeader(
            version=struct.unpack('>H', self.data[2:4])[0],
            flags=struct.unpack('>H', self.data[4:6])[0],
            text_size=struct.unpack('>I', self.data[8:12])[0],
            entry_offset=struct.unpack('>I', self.data[12:16])[0],
            external_count=struct.unpack('>H', self.data[16:18])[0],
            section_count=struct.unpack('>H', self.data[18:20])[0]
        )
        
        self.code_start = 32  # After header
        self.code_end = min(self.code_start + header.text_size, len(self.data))
        self.metadata.entry_point = header.entry_offset
        
        # Extract sections and externals if present
        self._extract_sections(header)
        
    def _apply_heuristics(self):
        """Apply heuristics when format is unknown"""
        # Assume entire file is code
        self.code_start = 0
        self.code_end = len(self.data)
        
        # Look for likely entry point
        entry_candidates = []
        
        # Search for common entry point patterns
        for i in range(0, min(256, len(self.data) - 2), 2):
            opcode = self.data[i:i+2]
            # STM 14,12,x is common entry
            if opcode == b'\x90\xEC':
                entry_candidates.append(i)
            # BALR/BASR for base establishment
            elif opcode[0] in [0x05, 0x0D]:
                entry_candidates.append(i)
        
        if entry_candidates:
            self.metadata.entry_point = entry_candidates[0]
        else:
            self.metadata.entry_point = 0
            
    def _has_pds_header(self) -> bool:
        """Check if data starts with PDS directory entry"""
        if len(self.data) < ArtifactFormat.PDS_HEADER_SIZE:
            return False
            
        # PDS entries have specific patterns
        # Check for member name (8 bytes EBCDIC)
        name_bytes = self.data[0:8]
        
        # Simple check: should be printable EBCDIC or spaces
        for byte in name_bytes:
            if byte != 0x40 and not (0xC1 <= byte <= 0xE9):  # EBCDIC letters
                return False
        return True
    
    def _extract_pds_info(self, header: bytes):
        """Extract info from PDS directory entry"""
        # Member name (8 bytes EBCDIC)
        name_ebcdic = header[0:8]
        self.metadata.attributes['pds_member'] = self._ebcdic_to_ascii(name_ebcdic)
        
    def _extract_attributes(self):
        """Extract AMODE/RMODE attributes"""
        # These are often encoded in specific bytes or instructions
        # Default to AMODE 31, RMODE ANY for modern programs
        self.metadata.amode = 31
        self.metadata.rmode = "ANY"
        
    def _extract_sections(self, header: ProgramObjectHeader):
        """Extract section information from program object"""
        offset = 32
        
        # Parse external symbols
        for _ in range(header.external_count):
            if offset + 16 > len(self.data):
                break
            symbol_name = self.data[offset:offset+8]
            self.metadata.external_symbols.append(
                self._ebcdic_to_ascii(symbol_name).strip()
            )
            offset += 16
            
        # Parse sections
        for _ in range(header.section_count):
            if offset + 20 > len(self.data):
                break
            section_info = {
                'offset': struct.unpack('>I', self.data[offset:offset+4])[0],
                'size': struct.unpack('>I', self.data[offset+4:offset+8])[0],
                'type': 'text'  # Simplified
            }
            self.metadata.csect_info.append(section_info)
            offset += 20
    
    def _ebcdic_to_ascii(self, ebcdic_bytes: bytes) -> str:
        """Convert EBCDIC to ASCII (simplified)"""
        # Simplified EBCDIC to ASCII conversion
        # Full conversion would use proper codec
        result = []
        for byte in ebcdic_bytes:
            if byte == 0x40:  # EBCDIC space
                result.append(' ')
            elif 0xC1 <= byte <= 0xC9:  # A-I
                result.append(chr(ord('A') + byte - 0xC1))
            elif 0xD1 <= byte <= 0xD9:  # J-R
                result.append(chr(ord('J') + byte - 0xD1))
            elif 0xE2 <= byte <= 0xE9:  # S-Z
                result.append(chr(ord('S') + byte - 0xE2))
            elif 0xF0 <= byte <= 0xF9:  # 0-9
                result.append(chr(ord('0') + byte - 0xF0))
            else:
                result.append('.')
        return ''.join(result)
    
    def get_code_bytes(self) -> bytes:
        """Get the code/text portion of the artifact"""
        return self.data[self.code_start:self.code_end]
    
    def get_metadata(self) -> ModuleMetadata:
        """Get extracted metadata"""
        return self.metadata
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        return {
            'total_size': len(self.data),
            'code_size': self.code_end - self.code_start,
            'format': self.metadata.format_type,
            'has_externals': len(self.metadata.external_symbols) > 0,
            'section_count': len(self.metadata.csect_info)
        }
