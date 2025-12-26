# MVP Alignment Report: Code vs Architecture Overview/Technical Design

**Date:** 2024-12-26  
**Purpose:** Map existing implementation to Architecture Overview and Technical Design documents and identify required changes

---

## Component Mapping Analysis

### ✅ KEEP: Components Aligned with Design

| Component | File | Architecture Section | Technical Design Section | Status |
|-----------|------|-------------|-------------|--------|
| Artifact Ingestor | `ingestion.py` | §9.1 | §4.1 | **KEEP** - Normalizes load modules/program objects |
| Disassembler | `disassembler.py` | §9.2 | §4.2 | **KEEP** - Has pluggable interface |
| CFG Builder | `cfg_builder.py` | §9.4 | §4.4 | **KEEP** - Core logic correct |
| Procedure Detector | `cfg_builder.py` | §9.5 | §4.5 | **KEEP** - Detection patterns present |
| Assembler Reconstructor | `reconstructor.py` | §9.6 | §4.6 | **KEEP** - Base structure correct |
| Pseudocode Generator | `pseudocode.py` | §9.7 | §4.7 | **KEEP** - Pattern matching present |
| Report Writer | `reporter.py` | §9.8 | §4.8 | **KEEP** - Multi-format output works |
| Pipeline | `pipeline.py` | §10 | §6 | **KEEP** - Orchestration correct |
| CLI | `cli.py` | §11 | §9.1 | **KEEP** - Interface matches spec |

### ⚠️ FIX: Critical Misalignments

| Issue | Current | Required (Technical Design) | Impact |
|-------|---------|----------------|--------|
| **Missing Region Classifier** | Not implemented | §4.3: Code/Data/Unknown classifier | Cannot properly classify regions |
| **Confidence Model** | Float (0.0-1.0) | §12.4: Enum (HIGH/MEDIUM/LOW) | Wrong confidence representation |
| **Error Model** | Binary success/fail | §12.7: Three-state (SUCCESS/PARTIAL/FAILURE) | Cannot handle partial success |
| **UNRESOLVED Markers** | Not explicit | §12.5: `UNRESOLVED_TARGET` markers | Unresolved branches not marked |
| **Deterministic Ordering** | Not guaranteed | §12.6: Lexicographic ordering | Non-reproducible batch results |
| **Evidence Preservation** | Partial | §5.2: Full chain preservation | Traceability broken |

### 🔧 SIMPLIFY: Over-Engineered Elements

| Element | Current Complexity | Simplification |
|---------|-------------------|----------------|
| External Decoder | Subprocess architecture | Remove for MVP (keep interface) |
| Rich UI Progress | Complex progress bars | Basic progress messages |
| Validation Scoring | Complex metrics | Simple decode rate check |

---

## Priority Action Items

### Phase 1: Critical Fixes (HIGH PRIORITY)

1. **Add Region Classifier Component**
   - Create `classifier.py` implementing Technical Design §4.3
   - 70% decode threshold for CODE
   - 30% threshold for DATA
   - Everything else is UNKNOWN

2. **Fix Confidence Model**
   - Replace float confidence with Enum
   - Update all components to use HIGH/MEDIUM/LOW
   - Map existing float values to enum

3. **Implement Three-State Error Model**
   - Add partial success handling
   - Exit codes: 0 (SUCCESS), 1 (PARTIAL), 2 (FAILURE)
   - >80% decoded = SUCCESS
   - 20-80% = PARTIAL
   - <20% = FAILURE

4. **Add UNRESOLVED Markers**
   - Mark indirect branches as `UNRESOLVED_TARGET`
   - Show in assembler output
   - Show in pseudocode output

### Phase 2: Evidence & Determinism (MEDIUM PRIORITY)

5. **Evidence Preservation**
   - Add evidence tracking to each transformation
   - Ensure address→bytes mapping throughout
   - Add evidence index to reports

6. **Deterministic Ordering**
   - Sort files lexicographically in batch mode
   - Sort procedures by address
   - Fixed field order in reports

### Phase 3: Cleanup (LOW PRIORITY)

7. **Remove Over-Scoped Code**
   - Remove external decoder subprocess logic (keep interface)
   - Simplify progress reporting
   - Remove unused validation metrics

---

## Files to Modify

### New Files Required
- `/src/zos_reverse/classifier.py` - Region classifier implementation

### Files Requiring Major Changes
- `/src/zos_reverse/ir.py` - Change confidence to enum
- `/src/zos_reverse/pipeline.py` - Add classifier stage, fix error model
- `/src/zos_reverse/cli.py` - Fix exit codes

### Files Requiring Minor Changes
- `/src/zos_reverse/cfg_builder.py` - Add UNRESOLVED markers
- `/src/zos_reverse/reconstructor.py` - Show UNRESOLVED_TARGET
- `/src/zos_reverse/pseudocode.py` - Show UNRESOLVED_TARGET
- `/src/zos_reverse/reporter.py` - Add evidence index

---

## Success Criteria

Per Development Guide §124:
> "If the tool can take a directory of already-extracted binaries and reliably produce reconstructed assembler and pseudocode—clearly marked, traceable, and deterministic—the MVP is successful."

Current State: **70% Complete**
- ✅ Takes directory of binaries
- ✅ Produces reconstructed assembler
- ✅ Produces pseudocode
- ⚠️ Not clearly marking unknowns
- ⚠️ Not fully traceable
- ⚠️ Not deterministic in batch mode

After Fixes: **100% MVP Complete**
