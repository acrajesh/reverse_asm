# z/OS Binary Reverse Engineering Tool - Quick Start Guide

## Installation

```bash
# Install the tool in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Quick Usage Examples

### 1. Generate Sample Binaries for Testing

```bash
python examples/create_sample_binary.py
```

This creates sample z/OS-like binaries in the `samples/` directory.

### 2. Analyze a Single Binary

```bash
# Basic analysis with default outputs (text, YAML, ASM, pseudocode)
zos-reverse analyze samples/simple.bin -o output/

# Specify output formats
zos-reverse analyze samples/branching.bin -o output/ -f yaml -f asm -f pseudocode

# Use external decoder (when available)
zos-reverse analyze input.bin --decoder external
```

### 3. Batch Process Multiple Files

```bash
# Process all .bin files in a directory
zos-reverse batch samples/ -o batch_output/ -p "*.bin"

# Limit number of files
zos-reverse batch loadlib_exports/ --max-files 10
```

### 4. View Tool Capabilities

```bash
zos-reverse info
```

## Output Files

For each analyzed binary, the tool generates:

- **`<name>_report.txt`** - Human-readable analysis report
- **`<name>_analysis.yaml`** - Machine-readable YAML with CFG and metadata
- **`<name>_analysis.json`** - JSON format for integration with other tools
- **`<name>.asm`** - Reconstructed HLASM-like assembly listing
- **`<name>_pseudocode.txt`** - Structured pseudocode representation

## Key Features Demonstrated

### Evidence-First Design
Every output line maps to specific instruction addresses and bytes:
```
00001000 05EF             ENTRY    BALR   14,15
00001002 90ECD00C                  STM    14,12,12(13)  * Save registers
```

### Confidence Scoring
Inferred constructs include confidence scores:
```
PROCEDURE SUB_00001020()  // [0x00001020-0x00001020] (conf: 0.75)
// Detection: prologue_pattern
```

### Explicit Unknowns
Undecodable regions are marked:
```
* Unknown/Undecodable Regions
* Region: 0x00001100 - 0x0000110F (16 bytes)
*   Data: 00112233445566778899AABBCCDDEEFF
```

## Architecture Overview

```
Binary File → Ingestion → Disassembly → CFG Building → Procedure Detection
                ↓             ↓              ↓              ↓
            Metadata    Instructions   Basic Blocks   Call Graph
                              ↓
                    Report Generation
                         ↓    ↓    ↓
                      Text  YAML  Pseudocode
```

## Validation Approach

The tool includes validation without requiring source:
- Synthetic binary generation for known patterns
- CFG sanity checks (reachability, fall-through correctness)
- Decode rate metrics
- Instruction distribution analysis

## Python API Usage

```python
from pathlib import Path
from zos_reverse.pipeline import ReverseEngineeringPipeline
from zos_reverse.reporter import ReportWriter

# Process a binary
pipeline = ReverseEngineeringPipeline()
result = pipeline.process_file(Path("input.bin"))

# Generate reports
writer = ReportWriter(Path("output/"))
files = writer.write_reports(result, formats=['yaml', 'asm', 'pseudocode'])

# Access analysis results
print(f"Decoded {len(result.instructions)} instructions")
print(f"Found {len(result.cfg.procedures)} procedures")
print(f"Decode rate: {result.statistics['decode_rate']:.1%}")
```

## Extending the Tool

### Adding New Instruction Decoders
Implement the `DecoderInterface` in `disassembler.py`:
```python
class CustomDecoder(DecoderInterface):
    def decode_instruction(self, data, offset, address):
        # Your decoding logic
        pass
```

### Custom Heuristics
Add pattern detection in `cfg_builder.py`:
```python
def _detect_custom_pattern(self, cfg):
    # Your heuristic logic
    pass
```

## Limitations (MVP Scope)

- No direct mainframe connectivity
- No perfect source recovery
- Limited to common z/Architecture instructions
- External decoder interface defined but not fully implemented
- No GUI/visualization (command-line only)

## Future Enhancements

- Language Environment (LE) conformance detection
- Advanced data flow analysis
- Macro semantics reconstruction
- Java/COBOL transformation pipelines
- Web-based visualization interface
