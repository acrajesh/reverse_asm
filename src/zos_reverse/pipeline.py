"""Main processing pipeline for z/OS binary reverse engineering"""

from pathlib import Path
from typing import Optional, Callable, Dict, Any
import logging
import time

from .ingestion import BinaryIngestor
from .disassembler import Disassembler, NativeDecoder, ExternalDecoder
from .cfg_builder import CFGBuilder, ProcedureDetector
from .ir import DisassemblyResult

logger = logging.getLogger(__name__)


class ReverseEngineeringPipeline:
    """Main pipeline coordinating all reverse engineering components"""
    
    def __init__(self, decoder_type: str = 'native'):
        """
        Initialize pipeline with specified decoder
        
        Args:
            decoder_type: 'native' or 'external'
        """
        self.decoder_type = decoder_type
        self._init_decoder()
        
    def _init_decoder(self):
        """Initialize the appropriate decoder"""
        if self.decoder_type == 'external':
            self.decoder = ExternalDecoder()
        else:
            self.decoder = NativeDecoder()
    
    def process_file(self, file_path: Path, 
                    progress_callback: Optional[Callable[[str], None]] = None) -> Optional[DisassemblyResult]:
        """
        Process a single binary file through the complete pipeline
        
        Args:
            file_path: Path to the binary file
            progress_callback: Optional callback for progress updates
            
        Returns:
            DisassemblyResult or None if processing failed
        """
        try:
            start_time = time.time()
            
            # Step 1: Binary Ingestion
            if progress_callback:
                progress_callback("Ingesting binary...")
            
            ingestor = BinaryIngestor()
            if not ingestor.load_file(file_path):
                logger.error(f"Failed to load file: {file_path}")
                return None
            
            metadata = ingestor.get_metadata()
            code_bytes = ingestor.get_code_bytes()
            ingestion_stats = ingestor.get_statistics()
            
            logger.info(f"Loaded {metadata.format_type} module: {metadata.name}")
            logger.info(f"Code size: {ingestion_stats['code_size']} bytes")
            
            # Step 2: Disassembly
            if progress_callback:
                progress_callback("Disassembling code...")
            
            disassembler = Disassembler(decoder=self.decoder)
            disasm_result = disassembler.disassemble(
                code_bytes,
                base_address=ingestor.code_start,
                metadata=metadata
            )
            
            logger.info(f"Disassembled {len(disasm_result.instructions)} instructions")
            logger.info(f"Decode rate: {disasm_result.statistics.get('decode_rate', 0):.1%}")
            
            # Step 3: CFG Construction
            if progress_callback:
                progress_callback("Building control flow graph...")
            
            cfg_builder = CFGBuilder()
            cfg = cfg_builder.build_cfg(disasm_result)
            
            logger.info(f"Built CFG with {len(cfg.basic_blocks)} basic blocks")
            
            # Step 4: Procedure Detection
            if progress_callback:
                progress_callback("Detecting procedures...")
            
            proc_detector = ProcedureDetector()
            procedures = proc_detector.detect_procedures(cfg)
            
            logger.info(f"Detected {len(procedures)} procedures")
            
            # Add timing statistics
            elapsed_time = time.time() - start_time
            disasm_result.statistics['processing_time'] = elapsed_time
            disasm_result.statistics['file_path'] = str(file_path)
            
            # Add warnings for low decode rate
            if disasm_result.statistics.get('decode_rate', 1.0) < 0.5:
                disasm_result.warnings.append(
                    f"Low decode rate ({disasm_result.statistics['decode_rate']:.1%}) - "
                    "file may not be a valid z/OS binary or may use unsupported instructions"
                )
            
            # Add warnings for unresolved branches
            if len(cfg.unresolved_branches) > 10:
                disasm_result.warnings.append(
                    f"High number of unresolved branches ({len(cfg.unresolved_branches)}) - "
                    "control flow analysis may be incomplete"
                )
            
            if progress_callback:
                progress_callback("Analysis complete")
            
            return disasm_result
            
        except Exception as e:
            logger.exception(f"Pipeline failed for {file_path}: {e}")
            return None
    
    def validate_result(self, result: DisassemblyResult) -> Dict[str, Any]:
        """
        Validate and score the analysis result
        
        Args:
            result: DisassemblyResult to validate
            
        Returns:
            Validation metrics and scores
        """
        validation = {
            'is_valid': True,
            'scores': {},
            'issues': []
        }
        
        # Check decode rate
        decode_rate = result.statistics.get('decode_rate', 0)
        validation['scores']['decode_rate'] = decode_rate
        if decode_rate < 0.3:
            validation['issues'].append('Very low decode rate - likely not valid z/OS code')
            validation['is_valid'] = False
        elif decode_rate < 0.7:
            validation['issues'].append('Low decode rate - some regions may be data or use unknown instructions')
        
        # Check CFG connectivity
        cfg = result.cfg
        if cfg.basic_blocks:
            # Calculate reachability from entry points
            reachable = self._calculate_reachability(cfg)
            reachability_rate = len(reachable) / len(cfg.basic_blocks)
            validation['scores']['reachability'] = reachability_rate
            
            if reachability_rate < 0.5:
                validation['issues'].append('Low CFG reachability - many orphan blocks detected')
        
        # Check procedure detection
        if cfg.procedures:
            avg_confidence = sum(p.confidence for p in cfg.procedures.values()) / len(cfg.procedures)
            validation['scores']['procedure_confidence'] = avg_confidence
            
            if avg_confidence < 0.5:
                validation['issues'].append('Low confidence in detected procedures')
        
        # Check for common patterns
        stats = result.statistics
        if 'top_mnemonics' in stats:
            top_mnems = [m for m, _ in stats['top_mnemonics'][:5]]
            # Should see common z/Architecture instructions
            expected_mnems = ['L', 'ST', 'LA', 'BC', 'LR']
            found_expected = any(m in expected_mnems for m in top_mnems)
            if not found_expected:
                validation['issues'].append('Unexpected instruction distribution')
        
        return validation
    
    def _calculate_reachability(self, cfg) -> set:
        """Calculate set of reachable blocks from entry points"""
        reachable = set()
        to_visit = []
        
        # Start from entry points
        for entry in cfg.entry_points:
            for block_id, block in cfg.basic_blocks.items():
                if block.start_address <= entry <= block.end_address:
                    to_visit.append(block_id)
                    break
        
        # BFS to find all reachable blocks
        while to_visit:
            block_id = to_visit.pop(0)
            if block_id in reachable:
                continue
                
            reachable.add(block_id)
            block = cfg.basic_blocks.get(block_id)
            if block:
                for succ_id in block.successors:
                    if succ_id not in reachable:
                        to_visit.append(succ_id)
        
        return reachable
