# z/OS Binary Reverse Engineering Tool - Lean MVP

A minimal viable product (MVP) tool that reverse engineers z/OS load modules or program objects into reconstructed assembler-like code and human-readable pseudocode.

## Features

- **Binary Ingestion**: Accept z/OS load modules and program objects as binary files
- **Disassembly**: Decode z/Architecture instructions with evidence mapping
- **Control Flow Recovery**: Build CFG with basic blocks and branch resolution
- **Procedure Inference**: Detect call/return patterns with confidence scoring
- **Assembler Reconstruction**: Generate HLASM-like listings with synthetic labels
- **Pseudocode Generation**: Structured pseudocode with evidence links
- **Deterministic Reporting**: YAML/JSON output for downstream tooling

## Installation

```bash
pip install -e .
```

## Usage

### Single File Analysis
```bash
zos-reverse analyze input.bin --output-dir ./output
```

### Batch Processing
```bash
zos-reverse batch ./loadlib_exports --output-dir ./analysis
```

### Generate Reports
```bash
zos-reverse analyze input.bin --format yaml --include-cfg --include-callgraph
```

## Output Formats

- **Reconstructed Assembler**: HLASM-style with synthetic labels
- **Pseudocode**: Structured control flow with confidence scores
- **YAML/JSON**: Machine-readable CFG and call graphs
- **Text Reports**: Human-readable analysis summaries

## Architecture

The tool follows a modular pipeline architecture:

1. **Artifact Ingestor**: Load and identify binary format
2. **Disassembler Interface**: Pluggable decoder with IR emission
3. **CFG Builder**: Basic block construction and branch resolution
4. **Procedure Heuristics**: Call/return pattern detection
5. **Assembler Reconstructor**: HLASM-like output generation
6. **Pseudocode Generator**: Structured code from CFG
7. **Report Writer**: Multi-format output generation

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
```

## License

MIT
