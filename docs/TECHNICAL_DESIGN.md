# Technical Design: z/OS Binary → Reconstructed Assembler + Pseudocode

**Document Version:** 1.0  
**Status:** Ready for Implementation  
**Audience:** Developer Agent, Technical Leads, Code Reviewers  
**Derived From:** Architecture Overview v1.0, Design Handoff Notes

---

## 1. Purpose and Scope of Technical Design

### Purpose
This Technical Design translates the Architecture Overview's vision into concrete, implementable design decisions. It removes all ambiguity for implementation while preserving the lean MVP scope.

### Scope
- **In Scope**: All design decisions needed to implement the reverse engineering pipeline from binary artifact to reconstructed outputs
- **Out of Scope**: Mainframe connectivity, AI/ML features, performance optimization beyond basic scalability, UI/visualization

### Document Authority
This Technical Design is derived from and subordinate to the Architecture Overview. All architectural decisions follow from Architecture Overview constraints.

---

## 2. Mapping from Architecture Overview to Technical Design (Traceability Table)

| Architecture Overview Element | Technical Design Section | Key Decisions |
|-------------|-------------|---------------|
| §8: Architecture Overview | §4: Component Design | Concrete interfaces, data contracts |
| §9: Major Components | §4: Component Design | Module boundaries, APIs |
| §10: Data Flow | §6: Control Flow | Pipeline orchestration, stage contracts |
| §12: Quality Attributes | §7,8: Determinism/Error | Concrete determinism rules, error model |
| §15: Risks | §8: Error Handling | Partial success criteria |
| §16: Open Questions | §12: Technical Design Decisions | All OQ items resolved |
| Handoff Note LLD-01 | §12.1 | Normalization via common interface |
| Handoff Note LLD-02 | §12.2 | Linear sweep fallback |
| Handoff Note LLD-03 | §12.3 | MVP classification criteria |
| Handoff Note LLD-04 | §12.4 | Three-level enum confidence |
| Handoff Note LLD-05 | §12.5 | UNRESOLVED markers |
| Handoff Note LLD-06 | §12.6 | Lexicographic ordering |
| Handoff Note LLD-07 | §12.7 | Three-state error model |

---

## 3. Refined System Context and Boundaries

### System Entry Points
1. **CLI Command**: `zos-reverse analyze <input> [options]`
2. **CLI Batch**: `zos-reverse batch <directory> [options]`

### System Exit Points
1. **File Output**: `.asm`, `.pseudo`, `.yaml`/`.json` reports
2. **Exit Codes**: 0 (success), 1 (partial), 2 (failure)
3. **Structured Logs**: JSON to stderr or logfile

### Execution Environment
- **Runtime**: Python 3.9+ (no OS-specific dependencies)
- **Memory Model**: Streaming where possible, max 2GB for single module
- **File System**: Read from input path, write to output directory
- **Concurrency**: Single-threaded per module, parallel batch via process pool

---

## 4. Detailed Component Design

### 4.1 Artifact Ingestor

**Interface:**
```
Input:  binary_path: str, entry_hints: Optional[List[int]]
Output: ArtifactModel
Errors: InvalidFormatError, CorruptedFileError
```

**Internal Structure:**
- `ArtifactModel`: Common abstraction for both load modules and program objects
- `LoadModuleParser`: Handles legacy load module format
- `ProgramObjectParser`: Handles extended program object format
- **Normalization Strategy (LLD-01)**: Both parsers produce unified `ArtifactModel`

**Key Methods:**
- `detect_format()`: Magic bytes/header detection
- `parse_headers()`: Extract ESD/CESD/IDR records
- `extract_sections()`: Return list of `Section` objects
- `get_entry_points()`: Return declared + hinted entry addresses

### 4.2 Disassembler Interface

**Interface:**
```
Input:  bytes: bytes, base_addr: int, length: int
Output: List[Instruction]
Errors: DecodeError (non-fatal, returns Unknown instruction)
```

**Pluggable Implementation:**
- `DisassemblerInterface`: Abstract base
- `NativeDisassembler`: Custom z/Architecture decoder (MVP default)
- `CapstoneWrapper`: Future option for Capstone integration

**Instruction Model:**
```
Instruction:
  address: int
  raw_bytes: bytes
  mnemonic: str
  operands: List[Operand]
  length: int (2/4/6)
  is_valid: bool
```

### 4.3 Region Classifier

**Interface:**
```
Input:  sections: List[Section], instructions: List[Instruction]
Output: List[Region]
Errors: None (best-effort classification)
```

**Classification Rules (LLD-03: MVP Criteria):**
- **Code**: Contains valid instructions with >70% decode success
- **Data**: <30% decode success or constant pool patterns
- **Unknown**: Everything else or low confidence

**Region Model:**
```
Region:
  type: Enum[CODE, DATA, UNKNOWN]
  start_addr: int
  end_addr: int
  confidence: Enum[HIGH, MEDIUM, LOW]
  evidence: str (reason for classification)
```

### 4.4 CFG Builder

**Interface:**
```
Input:  code_regions: List[Region], instructions: List[Instruction]
Output: ControlFlowGraph
Errors: None (best-effort CFG)
```

**Basic Block Identification:**
- Leaders: targets of branches, instruction after branch, first instruction
- Terminators: branch, return, halt instructions

**Edge Types:**
- `FALLTHROUGH`: Sequential flow
- `BRANCH_TAKEN`: Conditional branch taken
- `BRANCH_NOT_TAKEN`: Conditional branch not taken
- `UNCONDITIONAL`: Unconditional jump
- `UNRESOLVED`: Indirect branch (LLD-05)

**CFG Model:**
```
ControlFlowGraph:
  blocks: Dict[int, BasicBlock]
  edges: List[Edge]
  entry_points: List[int]
  unresolved_targets: List[int]  # For indirect branches
```

### 4.5 Procedure Detector

**Interface:**
```
Input:  cfg: ControlFlowGraph, instructions: List[Instruction]
Output: List[Procedure], CallGraph
Errors: None (best-effort detection)
```

**Detection Patterns:**
- Standard linkage: `STM R14,R12,12(R13)` entry
- Call pattern: `BALR`/`BASR` instructions
- Return pattern: `BR R14`
- LE prologue/epilogue signatures

**Procedure Model:**
```
Procedure:
  id: str (e.g., "PROC_001000")
  entry_addr: int
  exit_addrs: List[int]
  blocks: List[int]  # Basic block IDs
  confidence: Enum[HIGH, MEDIUM, LOW]
  linkage_type: str (e.g., "STANDARD", "LE", "UNKNOWN")
```

### 4.6 Assembler Reconstructor

**Interface:**
```
Input:  procedures: List[Procedure], instructions: List[Instruction], evidence: EvidenceMap
Output: str (HLASM-formatted text)
Errors: None (always produces output)
```

**Label Generation:**
- Procedures: `PROC_<hex_addr>` (e.g., `PROC_001000`)
- Locations: `LOC_<hex_addr>` (e.g., `LOC_001010`)
- Data: `DATA_<hex_addr>`
- Unresolved: `UNRESOLVED_TARGET` (LLD-05)

**Output Format:**
```asm
* [Address: hex] [Bytes: hex] [Confidence: level]
LABEL    MNEMONIC  OPERANDS        | Evidence/Comment
```

### 4.7 Pseudocode Generator

**Interface:**
```
Input:  cfg: ControlFlowGraph, procedures: List[Procedure]
Output: str (structured pseudocode)
Errors: None (always produces output)
```

**Pattern Matching:**
- If-then-else: Conditional branch patterns
- While loops: Back-edge detection
- For loops: Counter patterns (when detectable)
- Switch: Branch table patterns

**Unresolved Handling (LLD-05):**
```pseudo
// Indirect branch - target unknown
goto UNRESOLVED_TARGET  // @0x001234: computed jump
```

### 4.8 Report Writer

**Interface:**
```
Input:  all_artifacts: AnalysisResult
Output: Dict[str, Any] (serializable to YAML/JSON)
Errors: None (always produces output)
```

**Report Structure:**
```yaml
metadata:
  tool_version: str
  input_hash: str (SHA-256)
  timestamp: str (ISO 8601)
  
analysis:
  procedures: List[ProcedureReport]
  cfg: CFGReport
  call_graph: CallGraphReport
  statistics: StatsReport
  
evidence_index: List[EvidenceEntry]
```

---

## 5. Internal Data Models and Contracts (Conceptual, Not Code)

### 5.1 Core Data Pipeline Contract

Each pipeline stage consumes and produces well-defined data structures:

| Stage | Input Contract | Output Contract |
|-------|----------------|-----------------|
| Ingestion | File path + hints | ArtifactModel |
| Disassembly | ArtifactModel | InstructionStream |
| Classification | InstructionStream | RegionMap |
| CFG Building | RegionMap + InstructionStream | ControlFlowGraph |
| Procedure Detection | ControlFlowGraph | ProcedureList + CallGraph |
| Rendering | ProcedureList + CFG + Instructions | Output files |

### 5.2 Evidence Preservation Contract

Every transformation must preserve:
- `source_addr`: Original address in binary
- `source_bytes`: Original byte sequence
- `transform_reason`: Why this interpretation was made
- `confidence`: Certainty level of interpretation

### 5.3 Confidence Model (LLD-04: Simple Enum)

```
Confidence: Enum
  HIGH = "high"      # Direct evidence, no inference
  MEDIUM = "medium"  # Pattern-based inference
  LOW = "low"        # Heuristic guess
```

**Assignment Rules:**
- HIGH: Direct instruction decode, explicit metadata
- MEDIUM: Pattern matching, common conventions
- LOW: Statistical heuristics, fallback methods

---

## 6. Control Flow and Processing Logic

### 6.1 Main Pipeline Flow

```
1. Parse CLI arguments → Configuration
2. For each input file (deterministic order):
   a. Ingest artifact → ArtifactModel
   b. Disassemble all sections → InstructionStream
   c. Classify regions → RegionMap
   d. Build CFG from code regions → ControlFlowGraph
   e. Detect procedures → ProcedureList
   f. Render outputs → Files
   g. Generate report → YAML/JSON
3. Generate portfolio index (if batch mode)
4. Exit with appropriate code
```

### 6.2 Entry Point Resolution (LLD-02: Fallback Strategy)

```
1. Check for explicit entry points in artifact metadata
2. If none found, check user-provided hints
3. If still none, fallback to linear sweep:
   - Start CFG from beginning of each code region
   - Mark confidence as LOW
   - Log warning about missing entry point
```

### 6.3 Pipeline State Machine

```
States: INIT → INGESTING → DISASSEMBLING → ANALYZING → RENDERING → COMPLETE
Errors: Any state can transition to ERROR or PARTIAL_SUCCESS
```

---

## 7. Determinism and Ordering Rules

### 7.1 Deterministic Guarantees

| Operation | Determinism Rule |
|-----------|------------------|
| File processing order | Lexicographic sort by filename |
| Section processing | By address, ascending |
| Instruction decode | Sequential, no parallelism within module |
| Label generation | Based on address (hex format) |
| Report field order | Fixed schema, alphabetic for dynamic keys |
| Hash computation | SHA-256 of input bytes only |

### 7.2 Batch Processing Order (LLD-06)

```
1. List all files in input directory
2. Filter by extension (.bin, .obj, .lmod)
3. Sort lexicographically by full path
4. Process sequentially (parallel via process pool OK)
5. Portfolio index lists modules in same order
```

### 7.3 Non-Deterministic Elements (Documented)

- Process pool scheduling (doesn't affect output)
- Timestamp in reports (explicitly marked as variable)
- Temp file names (not exposed in output)

---

## 8. Error Handling and Partial-Success Model

### 8.1 Error Model (LLD-07: Three States)

| State | Exit Code | Condition | Report Flag |
|-------|-----------|-----------|-------------|
| SUCCESS | 0 | All stages complete, >80% code decoded | `status: success` |
| PARTIAL | 1 | Some stages complete, 20-80% decoded | `status: partial` |
| FAILURE | 2 | Critical error, <20% decoded or I/O fail | `status: failure` |

### 8.2 Error Propagation Rules

- **File I/O Errors**: Immediate FAILURE
- **Decode Errors**: Accumulate, mark as unknown, continue
- **Classification Errors**: Use UNKNOWN region, continue
- **CFG Build Errors**: Partial CFG acceptable, continue
- **Procedure Detection Errors**: Empty procedure list acceptable, continue

### 8.3 Warning Categories

| Category | Handling |
|----------|----------|
| Missing entry point | Log warning, use fallback, continue |
| Invalid instruction | Mark as unknown, continue |
| Unreachable code | Note in report, include in output |
| Overlapping regions | Flag in report, process both |

---

## 9. Configuration and Invocation Model

### 9.1 CLI Interface

```bash
# Single file analysis
zos-reverse analyze <input_file> \
  --output-dir <dir> \
  --entry-point <addr> \
  --format [yaml|json] \
  --confidence-min [high|medium|low] \
  --verbose

# Batch analysis
zos-reverse batch <input_dir> \
  --output-dir <dir> \
  --pattern "*.lmod" \
  --parallel <n> \
  --index-name "portfolio.yaml"
```

### 9.2 Configuration Priority

1. CLI arguments (highest)
2. Config file (if `--config` specified)
3. Environment variables (`ZOS_REVERSE_*`)
4. Defaults (lowest)

### 9.3 Configuration Schema

```yaml
analysis:
  confidence_min: medium  # Minimum confidence to include
  decode_unknown: true    # Attempt to decode uncertain regions
  entry_points: []        # List of addresses
  
output:
  format: yaml           # yaml or json
  include_evidence: true # Include evidence index
  include_hex: true      # Include hex bytes in assembler
  
logging:
  level: INFO            # DEBUG, INFO, WARNING, ERROR
  file: null             # Log file path or null for stderr
```

---

## 10. Output Structure and File Contracts

### 10.1 File Naming Convention (Resolved OQ3)

```
<module_name>.<extension>
Where:
  module_name = input filename without extension
  extension = .asm | .pseudo | .yaml | .json

Example:
  Input: PAYROLL.lmod
  Outputs: PAYROLL.asm, PAYROLL.pseudo, PAYROLL.yaml
```

### 10.2 Directory Structure

```
output_dir/
├── modules/
│   ├── MODULE1.asm
│   ├── MODULE1.pseudo
│   └── MODULE1.yaml
├── portfolio_index.yaml  # Batch mode only
└── analysis.log          # If file logging enabled
```

### 10.3 Output Content Contracts

**Assembler Output (.asm):**
- HLASM-compatible syntax
- UTF-8 encoding
- Line length max 80 chars (traditional)
- Comments with evidence on each line

**Pseudocode Output (.pseudo):**
- C-like syntax by default (Resolved OQ5)
- UTF-8 encoding
- Indentation: 4 spaces
- Evidence in comments

**Report Output (.yaml/.json):**
- Valid YAML 1.2 / JSON
- Schema version field
- All addresses in hex string format
- Confidence as string enum

---

## 11. Logging and Observability Design

### 11.1 Log Format

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "module": "disassembler",
  "message": "Decoded 1000 instructions",
  "context": {
    "file": "input.lmod",
    "stage": "disassembly",
    "progress": 0.5
  }
}
```

### 11.2 Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Instruction-level decode details |
| INFO | Stage entry/exit, counts |
| WARNING | Fallbacks used, unknown regions |
| ERROR | Failures requiring user attention |

### 11.3 Metrics (Logged at INFO)

- Instructions decoded/failed
- Procedures detected
- Confidence distribution
- Processing time per stage
- Memory usage (peak)

---

## 12. Technical Design Decisions Closed from Handoff Notes

### 12.1 Load Module vs Program Object Normalization (LLD-01)

**Decision**: Normalize through common `ArtifactModel` interface
- Both formats parsed to same internal representation
- Format-specific details preserved in `metadata` field
- Downstream components only see `ArtifactModel`

### 12.2 Entry Point Discovery Fallback (LLD-02)

**Decision**: Linear sweep from code region starts
- When no entry point available, treat each code region start as potential entry
- Build multi-root CFG
- Mark all such roots with confidence=LOW
- Log WARNING about missing entry point

### 12.3 Code vs Data Classification Criteria (LLD-03)

**Decision**: MVP success = correctly classify direct branch targets
- If instruction decode rate >70% in region → CODE
- If decode rate <30% → DATA
- Otherwise → UNKNOWN
- Constant pool detection via pattern (repeated addresses, alignment)

### 12.4 Confidence Scoring Model (LLD-04)

**Decision**: Three-level enum (HIGH, MEDIUM, LOW)
- HIGH: Direct evidence, no inference required
- MEDIUM: Standard pattern matching
- LOW: Heuristic or fallback method
- No probabilistic scores, no ML

### 12.5 Unresolved Indirect Branch Representation (LLD-05)

**Decision**: Explicit `UNRESOLVED` markers
- Assembler: `BR UNRESOLVED_TARGET  ; Indirect jump`
- Pseudocode: `goto UNRESOLVED_TARGET  // computed target`
- CFG: Edge with type=UNRESOLVED, target=null
- Report: List of unresolved addresses

### 12.6 Deterministic Ordering (LLD-06)

**Decision**: Lexicographic ordering everywhere
- Files processed in sorted path order
- Procedures listed by address (ascending)
- Report fields in fixed order
- Portfolio index maintains input order

### 12.7 Error vs Partial Success (LLD-07)

**Decision**: Three-state model with clear thresholds
- SUCCESS (exit 0): >80% code decoded
- PARTIAL (exit 1): 20-80% decoded
- FAILURE (exit 2): <20% decoded or I/O error
- Status field in all reports

---

## 13. Assumptions, Constraints, and Invariants

### 13.1 Assumptions
- Input files fit in available disk space
- Single module fits in 2GB RAM
- User has write permission to output directory
- Python 3.9+ available

### 13.2 Constraints
- No network access during analysis
- No modification of input files
- Output must be text-based (no binary formats)
- Must handle corrupted files gracefully

### 13.3 Invariants
- Evidence chain never broken
- Every byte accounted for (code, data, or unknown)
- Same input → same output (determinism)
- Unknown is explicit, never silent

---

## 14. Implementation Guidance (Non-Code)

### 14.1 Module Organization

```
src/
├── artifact_ingestor/
│   ├── __init__.py
│   ├── parser.py
│   └── model.py
├── disassembler/
│   ├── __init__.py
│   ├── interface.py
│   └── native.py
├── analyzer/
│   ├── __init__.py
│   ├── classifier.py
│   ├── cfg_builder.py
│   └── procedure_detector.py
├── renderer/
│   ├── __init__.py
│   ├── assembler.py
│   └── pseudocode.py
├── reporter/
│   ├── __init__.py
│   └── writer.py
├── cli/
│   └── main.py
└── common/
    ├── models.py
    ├── errors.py
    └── logging.py
```

### 14.2 Testing Strategy

- Unit tests for each component
- Integration tests for pipeline
- Regression tests with known binaries
- Property-based tests for determinism
- Fuzzing for robustness

### 14.3 Implementation Priority

1. **Phase 1**: Core pipeline (ingest → disassemble → basic output)
2. **Phase 2**: CFG and procedure detection
3. **Phase 3**: Pseudocode generation
4. **Phase 4**: Batch processing and portfolio index

---

## 15. Open Items Deferred to Developer Agent

| ID | Item | Guidance |
|----|------|----------|
| DEV-01 | Disassembler implementation choice | Start with native, prepare interface for Capstone |
| DEV-02 | Parallel processing library | Use multiprocessing.Pool for batch mode |
| DEV-03 | YAML library selection | Use PyYAML or ruamel.yaml |
| DEV-04 | Progress indication mechanism | Use tqdm for CLI progress bars |
| DEV-05 | Instruction pattern library format | JSON or Python dict, make it extensible |
| DEV-06 | Test data management | Store test binaries in tests/fixtures/ |
| DEV-07 | Performance profiling approach | Use cProfile, optimize only if needed |
| DEV-08 | Documentation generation | Use Sphinx for API docs |

### Final Implementation Notes

- Start with minimal viable pipeline
- Add features incrementally
- Maintain determinism at each step
- Test with real z/OS binaries early
- Keep evidence chain as top priority

---

*End of Low-Level Design Document*
