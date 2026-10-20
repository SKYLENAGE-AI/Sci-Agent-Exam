# Which generated crystal candidates should enter the synthesis queue?

All required sources are mounted under `/home/agent/data/`; do not use external scientific sources.

## Decision context

A thin-film materials laboratory can fund one small experimental campaign for previously unreported
diperiodic crystal structures. Its discovery committee proposes using SLayerGen as the front end and
sending its highest-ranked candidates directly to synthesis whenever they satisfy the model study's
reported structural validity, compositional validity, stability, uniqueness, and novelty criteria. The
committee treats those labels as comparable to the other papers' candidate-quality evidence and assumes
that no composition-level crystal-structure search or separate synthesizability gate is needed.

Determine whether the supplied literature supports that policy. Choose one final decision:

- `approve_direct_synthesis_routing`
- `retain_generator_and_require_staged_validation`
- `reject_generator_for_candidate_discovery`

Apply this decision policy:

- Choose `approve_direct_synthesis_routing` only when the exact direct-routing proposition and every
  scientific component it requires are `supported`.
- Choose `retain_generator_and_require_staged_validation` when direct routing is not supported, but the
  discovery-front-end proposition is `supported` or `mixed` and a staged validation campaign can resolve
  the decision-critical uncertainty.
- Choose `reject_generator_for_candidate_discovery` when direct routing is not supported and the
  discovery-front-end proposition is `unsupported` or `indeterminate`, or when the corpus establishes an
  obstacle that the requested validation campaign cannot resolve.

## Source corpus

Base scientific claims only on the four mounted papers and cite them by source ID.

| Source ID | Paper | Path |
| :-- | :-- | :-- |
| P1 | *SLayerGen: a Crystal Generative Model for all Space and Layer Groups* | `/home/agent/data/2605.08262v1.pdf` |
| P2 | *LeMat-GenBench: A Unified Evaluation Framework for Crystal Generative Models* | `/home/agent/data/2512.04562v2.pdf` |
| P3 | *A Synthesizability-Guided Pipeline for Materials Discovery* | `/home/agent/data/2511.01790v1.pdf` |
| P4 | *Introducing physics-informed generative models for targeting structural novelty in the exploration of chemical space* | `/home/agent/data/2510.23181v2.pdf` |

## Required synthesis

Answer all four questions using cross-source evidence:

1. What scientific quantity does each paper call validity, stability, novelty, or synthesizability,
   and which reported quantities can and cannot be carried across the studies?
2. Which parts of the committee's case survive differences in dimensionality, structural reference,
   energy reference, relaxation or search depth, and experimental endpoint?
3. What does the corpus establish about preserving a generated candidate's structural identity and
   discovery value through downstream validation?
4. What decision follows, which assumptions remain exposed, and what minimum staged gate should
   precede allocation of synthesis resources?

Audit these exact propositions in `answer.json`:

- `DISCOVERY_FRONT_END_VALUE`: the evidence justifies retaining symmetry-aware crystal generation
  as a candidate-proposal front end for the laboratory.
- `SUN_IS_LAB_READINESS`: satisfying the candidate-quality criteria reported with SLayerGen
  establishes that a candidate is ready for experimental synthesis.
- `GENERATED_IDENTITY_IS_DECISION_STABLE`: the generated candidate's stability and novelty labels
  are established to remain valid after composition-level structural search.
- `DIRECT_ROUTING_IS_JUSTIFIED`: the committee's proposed direct-to-synthesis policy is established
  for the laboratory.

Assign exactly one verdict to each proposition:

- `supported`: the corpus affirmatively establishes the exact proposition for the target scope, with
  no material adverse evidence or unresolved transfer gap.
- `mixed`: the corpus supports a material part of the proposition but also contains counterevidence
  or a scope mismatch that prevents unqualified support.
- `unsupported`: the affirmative proposition is contradicted, or a required element lacks evidence
  under the decision's burden of proof.
- `indeterminate`: relevant evidence exists but is genuinely incommensurable or directionally
  unresolved, so neither support nor rejection follows.

For every material transfer into the laboratory policy, assign the first matching evidence status in
this order:

- `directly_supported`: a supplied study measures the complete named proposition for the named
  subject and outcome in the target scope.
- `cross_source_inferred`: no single study measures the complete proposition, but the supplied
  results jointly establish every link without changing the model, dimensionality, reference set,
  energy convention, structural-search stage, or experimental endpoint.
- `extrapolated`: the corpus supplies a directionally relevant mechanism or analogue and no direct
  contradiction, but applying it to the complete proposition requires at least one of those changes.
- `unsupported`: the complete proposition is directly contradicted or the corpus supplies no
  directionally relevant mechanism or analogue from which to extrapolate it.

Record the evidence status of these five source-to-policy audits in `answer.json`:

- `P1_LAYER_GROUP_CONTROL`: what P1 establishes about the relationship between requested
  layer-group conditioning and realized candidate symmetry under its own evaluation.
- `P1_SUN_TO_SYNTHESIZABILITY`: whether P1's candidate-quality result establishes readiness for
  experimental synthesis in the target laboratory.
- `P2_BENCHMARK_RANK_TO_SLAYERGEN`: whether P2's reported benchmark rankings transfer to
  SLayerGen's diperiodic candidates in the laboratory's target scope.
- `P3_SUCCESS_RATE_TO_SLAYERGEN`: whether P3's experimental outcome predicts exact-phase synthesis
  yield for SLayerGen candidates selected under P1's candidate-quality result.
- `P4_IDENTITY_TRANSFER`: whether P4's downstream structural-search findings transfer to actual
  SLayerGen candidates in the laboratory's target scope.

State each source's scope, the risk if a transfer fails, and the validation needed. Distinguish genuine
contradiction from differences caused by dimensionality, reference databases, stability thresholds,
structural matching, model coverage, or experimental selection.

## Deliverables

Create all of the following under `/home/agent/results/`:

| Path | Required scientific content |
| :-- | :-- |
| `/home/agent/results/report.md` | Source-by-source evidence, cross-source synthesis, proposition verdicts, assumption audit, final decision, and minimum staged validation gate |
| `/home/agent/results/answer.json` | Final decision, four proposition verdicts, and five evidence-status labels |
| `/home/agent/results/code/build_evidence_chain.py` | Executable code that builds the evidence figure from a structured, editable source-evidence representation |
| `/home/agent/results/figures/candidate_evidence_chain.png` | A synthesis figure showing how P1-P4 bear on symmetry validity, energetic stability, structural identity or novelty, synthesizability, and direct laboratory routing |

`answer.json` must have exactly this structure:

```json
{
  "synthesis_verdict": "approve_direct_synthesis_routing|retain_generator_and_require_staged_validation|reject_generator_for_candidate_discovery",
  "subclaim_verdicts": {
    "DISCOVERY_FRONT_END_VALUE": "supported|mixed|unsupported|indeterminate",
    "SUN_IS_LAB_READINESS": "supported|mixed|unsupported|indeterminate",
    "GENERATED_IDENTITY_IS_DECISION_STABLE": "supported|mixed|unsupported|indeterminate",
    "DIRECT_ROUTING_IS_JUSTIFIED": "supported|mixed|unsupported|indeterminate"
  },
  "evidence_statuses": {
    "P1_LAYER_GROUP_CONTROL": "directly_supported|cross_source_inferred|extrapolated|unsupported",
    "P1_SUN_TO_SYNTHESIZABILITY": "directly_supported|cross_source_inferred|extrapolated|unsupported",
    "P2_BENCHMARK_RANK_TO_SLAYERGEN": "directly_supported|cross_source_inferred|extrapolated|unsupported",
    "P3_SUCCESS_RATE_TO_SLAYERGEN": "directly_supported|cross_source_inferred|extrapolated|unsupported",
    "P4_IDENTITY_TRANSFER": "directly_supported|cross_source_inferred|extrapolated|unsupported"
  }
}
```

The evidence-chain figure may use any visual design, but the four source identities, five decision
axes, direction of evidence, and whether an axis was not tested must be determinable from the image.
The report must explain the figure's scientific meaning and remain consistent with `answer.json`.
