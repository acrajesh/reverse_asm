# z/OS Binary Reverse Engineering Tool

An offline, evidence-first reverse engineering tool for z/OS load modules and program objects.

It reconstructs:

- **Reconstructed assembler** (HLASM-style listing with synthetic labels)
- **Human-readable pseudocode** (structured control flow with explicit unknowns)

This project is designed to replace manual binary reading with repeatable automation, while preserving traceability back to the original bytes.

## Features

- **Evidence-preserving disassembly**
- **Control-flow recovery** (basic blocks + CFG edges for direct branches)
- **Procedure inference** (entry points, call targets, prologue heuristics)
- **Reconstructed assembly listing**
  - Address
  - Instruction bytes (hex)
  - Decoded mnemonic + operands
  - Synthetic labels for discovered targets
  - Explicit unresolved/unknown annotations
- **Pseudocode generation**
  - `IF / ELSE / LOOP / CALL / RETURN` where inferable
  - Explicit `UNKNOWN` where not inferable
  - Evidence links back to address ranges
- **Deterministic reporting** (text + YAML/JSON)

## Evidence & Explainability Guarantees

- **No silent gaps**: undecodable bytes and ambiguous regions are explicitly emitted as unknowns.
- **Evidence-first output**: assembly lines are anchored to instruction addresses and original bytes.
- **Determinism**: repeated runs on the same input yield the same outputs (including batch ordering).

### Confidence

Confidence is represented as:

- `high`: direct evidence (e.g., decoded instruction)
- `medium`: pattern-based inference
- `low`: heuristic guess / uncertain region

## Installation

```bash
pip install -e .
```

Notes:

- **Python**: requires Python `>= 3.9`.
- The console entrypoint `zos-reverse` may install outside your `PATH` depending on your environment.

## Usage

### Single File Analysis
```bash
python3 -m zos_reverse.cli analyze input.bin -o ./output
```

If `zos-reverse` is on your `PATH`:

```bash
zos-reverse analyze input.bin -o ./output
```

### Batch Processing
```bash
python3 -m zos_reverse.cli batch ./loadlib_exports -o ./analysis -p "*"
```

### Select Output Formats
```bash
python3 -m zos_reverse.cli analyze input.bin -o ./output \
  -f text -f yaml -f json -f asm -f pseudocode
```

### Tool Information

```bash
python3 -m zos_reverse.cli info
```

## Output Formats

For an input `input.bin` the tool writes (depending on `-f/--format`):

- **`input_report.txt`**: human-readable summary
- **`input_analysis.yaml`**: metadata, CFG, procedures, unresolved branches
- **`input_analysis.json`**: JSON equivalent (includes an instruction sample)
- **`input.asm`**: reconstructed assembly listing
- **`input_pseudocode.txt`**: pseudocode with evidence links

The CLI returns an exit code based on decode rate:

- `0`: success (decode rate > 0.8)
- `1`: partial success (0.2 <= decode rate <= 0.8)
- `2`: failure (decode rate < 0.2)

## What This Tool Does NOT Do

- Connect to z/OS or extract artifacts from loadlibs/PDSE (inputs are **files**)
- Recover original source code or assembler listings
- Guarantee semantic completeness
- Convert to Java/C# (foundation only)
- Provide a GUI

## Architecture

The tool follows a modular pipeline architecture:

1. **Artifact Ingestor**: Load and identify binary format
2. **Disassembler Interface**: Pluggable decoder with IR emission
3. **Region Classifier**: Best-effort code vs data vs unknown
4. **CFG Builder**: Basic block construction and branch resolution
5. **Procedure Heuristics**: Call/return pattern detection
6. **Assembler Reconstructor**: HLASM-like output generation
7. **Pseudocode Generator**: Structured code from CFG
8. **Report Writer**: Multi-format output generation

## Project Status

This repository is a practical foundation for z/OS reverse engineering automation. It is intentionally conservative:

- prioritizes traceability and determinism
- prefers explicit unknowns over invented semantics

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
