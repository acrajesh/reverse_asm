developer_handoff:
  document:
    title: "Development Guide – z/OS Binary Reverse Engineering MVP"
    audience: "Developer Agent / Implementation Team"
    purpose: >
      Provide consolidated intent, constraints, and guardrails for implementing
      the MVP reverse-engineering tool based on the Architecture Overview and Technical Design.
      This document exists to prevent scope drift and misinterpretation.

  authoritative_sources:
    primary:
      - "Architecture Overview (ARCHITECTURE_OVERVIEW.md)"
      - "Technical Design (TECHNICAL_DESIGN.md)"
    supporting:
      - "Design Handoff Notes (YAML)"
    precedence_rule:
      - "If there is any ambiguity, Architecture Overview intent overrides Technical Design mechanics."
      - "This handoff document clarifies intent; it does not introduce new requirements."

  core_intent_lock:
    what_we_are_building: >
      An offline tool that takes already-extracted z/OS load modules or program objects
      from a local path or VM-accessible path and reverse engineers them into:
        (1) reconstructed assembler-like code
        (2) human-readable pseudocode.
    what_we_are_not_building:
      - "Mainframe connectivity or artifact extraction"
      - "Object-to-object or source-to-source transformation"
      - "Perfect source reconstruction"
      - "A general-purpose disassembler product"
      - "A UI or visualization platform"

  execution_model:
    input_model:
      - "Artifacts already exist as files on local machine or VM"
      - "Tool is invoked with a file path or folder path"
      - "Artifacts are processed one by one or in batch"
    invocation_example_conceptual: >
      tool --input /path/to/artifacts --output /path/to/reports
    non_assumptions:
      - "Do not assume access to z/OS"
      - "Do not assume availability of assembler source or listings"

  mvp_success_definition:
    success_means:
      - "Given a binary artifact, the tool produces reconstructed assembler output"
      - "The tool produces pseudocode derived from control flow"
      - "All outputs are traceable back to binary evidence (addresses/bytes)"
      - "Unknown or unresolved logic is explicitly marked, not guessed"
    success_does_not_require:
      - "Complete instruction coverage"
      - "Accurate macro recovery"
      - "Full data-flow or register liveness analysis"
      - "High semantic fidelity in all cases"

  critical_guardrail_decoder_scope:
    intent_statement: >
      The primary value of the MVP is reverse engineering and structure recovery,
      not instruction decoding research.
    decoder_guidance:
      - "Instruction decoding is a means to an end, not the end itself."
      - "Decoder may be native, library-based, or external."
      - "Decoder must be treated as replaceable and imperfect."
    explicit_warning:
      - "Do not let decoder completeness dominate MVP scope or timeline."
      - "Delegating decoding is acceptable if it enables faster delivery of reverse-engineering logic."

  alignment_with_technical_design:
    accepted_technical_design_decisions:
      - "Offline-only operation"
      - "Evidence-first outputs"
      - "Explicit UNKNOWN / UNRESOLVED markers"
      - "Deterministic processing and ordering"
      - "Simple confidence scoring model"
    technical_design_items_to_treat_as_heuristics:
      - "Code vs data classification thresholds"
      - "Decode success percentage cutoffs"
      - "Procedure detection confidence levels"
    guidance: >
      These values are starting heuristics, not correctness contracts.
      They may be adjusted without violating design intent.

  minimum_acceptable_behavior:
    when_decoding_is_partial:
      - "Still emit reconstructed assembler for decoded regions"
      - "Still build partial CFG where possible"
      - "Mark undecoded regions explicitly"
      - "Do not fail the entire artifact unless decoding is impossible"
    when_procedure_detection_fails:
      - "Emit flat CFG-based pseudocode"
      - "Do not suppress output due to weak structure recovery"

  error_and_result_expectations:
    hard_failure:
      - "Unreadable artifact"
      - "Zero instruction decode"
    partial_success:
      - "Some decoded instructions"
      - "Incomplete CFG or procedure recovery"
    success_with_warnings:
      - "Full pipeline executed with unresolved constructs"
    principle: >
      Partial output is always preferred over no output.

  scope_discipline:
    do_not_add:
      - "AI/ML inference"
      - "Deep LE semantic modeling"
      - "Cross-module linking"
      - "Performance optimizations beyond basic scalability"
    rationale: >
      These are future enhancements and explicitly not required for MVP success.

  developer_expectations:
    mindset:
      - "Implement the design, do not reinterpret it"
      - "Prefer clarity and traceability over cleverness"
      - "Explicitly mark uncertainty"
    validation_focus:
      - "Does output map back to binary evidence?"
      - "Is behavior deterministic?"
      - "Does tool still produce value on imperfect input?"

  final_lock_statement: >
    If the tool can take a directory of already-extracted binaries and reliably
    produce reconstructed assembler and pseudocode—clearly marked, traceable,
    and deterministic—the MVP is successful.
