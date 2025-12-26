"""Region classifier - identifies code vs data vs unknown regions"""

from typing import List, Tuple
from enum import Enum
import logging

from .ir import Instruction, Confidence

logger = logging.getLogger(__name__)


class RegionType(Enum):
    """Region classification types"""
    CODE = "code"
    DATA = "data"
    UNKNOWN = "unknown"


class Region:
    """Classified region in binary"""
    
    def __init__(self, start_addr: int, end_addr: int, 
                 region_type: RegionType, confidence: Confidence,
                 evidence: str = ""):
        self.start_addr = start_addr
        self.end_addr = end_addr
        self.region_type = region_type
        self.confidence = confidence
        self.evidence = evidence
        self.decode_rate = 0.0
        
    def to_dict(self):
        return {
            "start": f"0x{self.start_addr:08X}",
            "end": f"0x{self.end_addr:08X}",
            "type": self.region_type.value,
            "confidence": self.confidence.value,
            "evidence": self.evidence,
            "decode_rate": self.decode_rate
        }


class RegionClassifier:
    """Classifies binary regions as code, data, or unknown per Technical Design §4.3"""
    
    # MVP thresholds from Technical Design §12.3
    CODE_THRESHOLD = 0.70    # >70% decode success = CODE
    DATA_THRESHOLD = 0.30    # <30% decode success = DATA
    # 30-70% = UNKNOWN
    
    def __init__(self):
        self.regions: List[Region] = []
        
    def classify(self, sections: List[Tuple[int, int, bytes]], 
                 instructions: List[Instruction]) -> List[Region]:
        """
        Classify sections based on instruction decode success rate
        
        Per Technical Design §12.3: MVP success = correctly classify direct branch targets
        """
        self.regions = []
        
        # Build instruction address map for quick lookup
        inst_map = {inst.address: inst for inst in instructions}
        
        for start_addr, end_addr, data in sections:
            region = self._classify_section(start_addr, end_addr, data, inst_map)
            self.regions.append(region)
            
        # Post-process: check for constant pool patterns
        self._detect_constant_pools()
        
        return self.regions
    
    def _classify_section(self, start_addr: int, end_addr: int, 
                          data: bytes, inst_map: dict) -> Region:
        """Classify a single section based on decode rate"""
        
        section_size = end_addr - start_addr + 1
        decoded_bytes = 0
        valid_instructions = 0
        total_instructions = 0
        
        # Count successfully decoded instructions in this section
        for addr in range(start_addr, end_addr + 1):
            if addr in inst_map:
                inst = inst_map[addr]
                total_instructions += 1
                if inst.mnemonic != "UNKNOWN":
                    valid_instructions += 1
                    decoded_bytes += len(inst.raw_bytes)
        
        # Calculate decode rate
        decode_rate = decoded_bytes / section_size if section_size > 0 else 0.0
        
        # Classify based on thresholds
        if decode_rate > self.CODE_THRESHOLD:
            region_type = RegionType.CODE
            confidence = Confidence.HIGH
            evidence = f"decode_rate={decode_rate:.2f} > {self.CODE_THRESHOLD}"
        elif decode_rate < self.DATA_THRESHOLD:
            region_type = RegionType.DATA
            confidence = Confidence.MEDIUM
            evidence = f"decode_rate={decode_rate:.2f} < {self.DATA_THRESHOLD}"
        else:
            region_type = RegionType.UNKNOWN
            confidence = Confidence.LOW
            evidence = f"decode_rate={decode_rate:.2f} in uncertain range"
        
        region = Region(start_addr, end_addr, region_type, confidence, evidence)
        region.decode_rate = decode_rate
        
        logger.info(f"Classified region 0x{start_addr:08X}-0x{end_addr:08X} as {region_type.value} "
                   f"(decode_rate={decode_rate:.2f}, confidence={confidence.value})")
        
        return region
    
    def _detect_constant_pools(self):
        """Detect constant pool patterns and reclassify if needed"""
        
        for region in self.regions:
            if region.region_type == RegionType.UNKNOWN:
                # Check for constant pool indicators:
                # - Repeated addresses (pointers)
                # - Alignment patterns
                # - Near code regions
                
                # Simple heuristic: if unknown region is small and between code regions, 
                # likely a constant pool
                region_size = region.end_addr - region.start_addr + 1
                if region_size < 256:  # Small region
                    # Check if surrounded by code
                    has_code_before = any(
                        r.region_type == RegionType.CODE and r.end_addr < region.start_addr
                        for r in self.regions
                    )
                    has_code_after = any(
                        r.region_type == RegionType.CODE and r.start_addr > region.end_addr
                        for r in self.regions
                    )
                    
                    if has_code_before and has_code_after:
                        # Likely a constant pool
                        region.region_type = RegionType.DATA
                        region.confidence = Confidence.MEDIUM
                        region.evidence = "constant_pool_pattern (between code regions)"
                        logger.info(f"Reclassified region 0x{region.start_addr:08X} as constant pool")
    
    def get_code_regions(self) -> List[Region]:
        """Get all regions classified as CODE"""
        return [r for r in self.regions if r.region_type == RegionType.CODE]
    
    def get_data_regions(self) -> List[Region]:
        """Get all regions classified as DATA"""
        return [r for r in self.regions if r.region_type == RegionType.DATA]
    
    def get_unknown_regions(self) -> List[Region]:
        """Get all regions classified as UNKNOWN"""
        return [r for r in self.regions if r.region_type == RegionType.UNKNOWN]
    
    def get_statistics(self) -> dict:
        """Get classification statistics"""
        total_bytes = sum(r.end_addr - r.start_addr + 1 for r in self.regions)
        code_bytes = sum(r.end_addr - r.start_addr + 1 for r in self.regions 
                        if r.region_type == RegionType.CODE)
        data_bytes = sum(r.end_addr - r.start_addr + 1 for r in self.regions
                        if r.region_type == RegionType.DATA)
        unknown_bytes = sum(r.end_addr - r.start_addr + 1 for r in self.regions
                           if r.region_type == RegionType.UNKNOWN)
        
        return {
            "total_regions": len(self.regions),
            "code_regions": len(self.get_code_regions()),
            "data_regions": len(self.get_data_regions()),
            "unknown_regions": len(self.get_unknown_regions()),
            "total_bytes": total_bytes,
            "code_bytes": code_bytes,
            "data_bytes": data_bytes,
            "unknown_bytes": unknown_bytes,
            "code_percentage": (code_bytes / total_bytes * 100) if total_bytes > 0 else 0,
            "data_percentage": (data_bytes / total_bytes * 100) if total_bytes > 0 else 0,
            "unknown_percentage": (unknown_bytes / total_bytes * 100) if total_bytes > 0 else 0
        }
