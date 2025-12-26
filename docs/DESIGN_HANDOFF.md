lld_handoff:
  document:
    title: "Design Handoff Notes"
    project: "z/OS Binary → Reconstructed Assembler + Pseudocode"
    from: "Technical Review (Architecture Overview)"
    to: "Technical Design Creator"
    purpose: "Highlight specific clarifications needed at Technical Design stage"
    scope: "Obvious gaps only; no redesign, no overengineering"

  context:
    provided_inputs:
      - "Architecture Overview document"
      - "Architecture Design Agent prompt"
    review_summary:
      assessment: "Architecture Overview is architecturally sound, MVP-appropriate, and internally consistent"
      intent: "Notes below are clarifications, not defects"

  items_to_clarify_in_technical_design:
    - id: LLD-01
      topic: "Load Module vs Program Object normalization"
      observation: >
        Architecture Overview accepts both load modules and program objects as inputs but does not
        explicitly state whether they are normalized into a single internal abstraction
        or handled via format-specific paths.
      technical_design_action: >
        Explicitly state the normalization strategy to avoid implicit branching
        or inconsistent handling downstream.

    - id: LLD-02
      topic: "Entry point discovery fallback"
      observation: >
        Architecture Overview allows for entry point discovery via metadata or optional user hints,
        but does not define behavior when neither is available.
      technical_design_action: >
        Define a deterministic fallback strategy (e.g., multi-root CFG or
        linear sweep start points).

    - id: LLD-03
      topic: "Code vs data classification success criteria"
      observation: >
        Architecture Overview defines a region classifier but does not bound what 'good enough'
        means for MVP-level correctness.
      technical_design_action: >
        State minimal acceptance criteria suitable for MVP
        (e.g., correctness for direct branch targets only).

    - id: LLD-04
      topic: "Confidence scoring semantics"
      observation: >
        Confidence scoring is required but unconstrained in scale or representation.
      technical_design_action: >
        Choose and document a simple, explainable confidence model
        appropriate for MVP; avoid probabilistic or ML-based scoring.

    - id: LLD-05
      topic: "Unresolved indirect branch representation"
      observation: >
        Architecture Overview avoids guessing indirect branch targets but does not specify
        how unresolved branches appear in outputs.
      technical_design_action: >
        Define explicit markers in reconstructed assembler and pseudocode
        (e.g., UNRESOLVED_JUMP, UNKNOWN_TARGET).

    - id: LLD-06
      topic: "Deterministic ordering in batch/portfolio mode"
      observation: >
        Architecture Overview requires determinism and supports batch processing but does not
        state ordering guarantees.
      technical_design_action: >
        Define deterministic ordering rules for module processing,
        procedure listings, and report/index generation.

    - id: LLD-07
      topic: "Error vs partial-success semantics"
      observation: >
        Architecture Overview mentions graceful degradation but does not distinguish between
        hard failure, partial success, and success-with-warnings.
      technical_design_action: >
        Define a simple error/state model and corresponding exit-code behavior.

  explicitly_out_of_scope_for_technical_design:
    - "Advanced data-flow or register liveness analysis"
    - "Deep LE-conformance modeling"
    - "Performance optimization beyond basic scalability"
    - "AI/ML-based inference or naming"
    - "UI or visualization layers"
    - "Mainframe-side extraction tooling"

  summary_for_technical_design_agent:
    guidance:
      - "Proceed with Technical Design based on Architecture Overview as-is; no architectural redesign needed."
      - "Focus on making implicit assumptions explicit."
      - "Preserve lean MVP posture."
      - "Do not introduce features not justified by Architecture Overview."
