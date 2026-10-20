# Materials Science Literature Synthesis 02

## Task record

- **Claim:** Materials Science / Crystal structure / Literature Synthesis 02
- **Decision:** Whether a thin-film laboratory should route SLayerGen candidates directly to
  synthesis after they satisfy the generator study's validity, stability, uniqueness, and novelty
  criteria.
- **Scoring:** `0.20` deterministic structured-decision checks and `0.80` source-grounded rubric.
  This is the current repository contract and was confirmed for this task by the project lead; it
  supersedes older onboarding text that described Literature Synthesis as judge-only.
- **Corpus boundary:** The four mounted PDFs are the complete scientific corpus.

## Sources and eligibility

| ID | Source | Date and license | Unique role |
| :-- | :-- | :-- | :-- |
| P1 | Chang et al., *SLayerGen: a Crystal Generative Model for all Space and Layer Groups*, `2605.08262v1.pdf` | 7 May 2026; CC BY 4.0 | Supplies the positive case: explicit layer-group generation, diperiodic datasets, and S.U.N.-style model evaluation. Without P1 there is no candidate generator to assess. |
| P2 | Betala et al., *LeMat-GenBench: A Unified Evaluation Framework for Crystal Generative Models*, `2512.04562v2.pdf` | 4 December 2025; CC BY 4.0 | Shows that stability and novelty depend on the energy/reference protocol and trade against one another. Without P2, benchmark labels look more portable than they are. |
| P3 | Prein et al., *A Synthesizability-Guided Pipeline for Materials Discovery*, `2511.01790v1.pdf` | 3 November 2025; CC BY 4.0 | Supplies the only experimental synthesis endpoint and exposes composition-level labels, selection effects, polymorph outcomes, and database errors. |
| P4 | Vasylenko et al., *Introducing physics-informed generative models for targeting structural novelty in the exploration of chemical space*, `2510.23181v2.pdf` | 27 October 2025; CC BY 4.0 | Demonstrates that composition-level crystal-structure prediction can overturn both stability and novelty assigned to generated structures. |

All four papers satisfy the project recency requirement. The set creates genuine synthesis pressure
because each paper uses a defensible but different endpoint: symmetry-aware generation, benchmark
stability/novelty, predicted or observed synthesizability, and identity after composition-level
potential-energy-surface search.

## Load-bearing source conventions

| Convention | Location | Consequence for the decision |
| :-- | :-- | :-- |
| Diperiodic symmetry is not recovered reliably by superficial 3D tiling because 18 of 80 layer groups do not injectively map to a space group. | P1, Introduction and Section 2 | Directly supports retaining explicit layer-group generation as a discovery front end. |
| P1's data-curation rules are dataset-specific: 200 meV/atom for C2DB/Alex2D, 150 meV/atom for 2DMatPedia, and binding plus sliding stability for BiDB; all four curated datasets also receive the Gamma-point phonon screen. | P1, Section 5, Data processing | These rules define corpus inclusion, not the generated-candidate stability metric. |
| P1 evaluates relaxed generated candidates under a separate metric: non-BiDB candidates require E_hull < 200 meV/atom against MP v2023.02.07 plus Gamma-point phonons; BiDB candidates require lower relaxed bilayer energy than the relaxed constituent monolayers plus Gamma-point phonons; S.U.N. then adds recomputed uniqueness and novelty. | P1, Section 5, Metrics | Prevents silently applying curation thresholds, especially 2DMatPedia's 150 meV/atom cutoff, to generated candidates. |
| P1 calls the data-processing hulls rough guides because those curation filters are loose and omit surface/interface interactions. | P1, Section 5, Data processing | Bounds the curation evidence without mislabeling it as the generated-candidate S.U.N. definition. |
| P2 defines stable as E_hull <= 0 and metastable as 0 < E_hull <= 0.1 eV/atom, and requires a self-consistent MLIP reference hull. | P2, Sections 3.2 and 5.2 | Makes P1 and P2 stability rates non-poolable without protocol harmonization. |
| P2's reference swap changes MatterGen novelty from 83.1% to 70.5% and divides example stability rates by roughly 2-3. | P2, Section 5.4 and Appendix C.4 | Establishes that candidate rankings can move even when the generated structures do not. |
| P3 labels a composition positive if any polymorph is not marked theoretical, and its final score is a rank-average rather than an absolute probability threshold. | P3, Sections 2.1 and 2.2 | Prevents carrying P3's score or success rate to an exact SLayerGen structure. |
| P4's two composition-level searches change the generated structures: LiNb7N8 becomes the known W2C prototype, whereas Rb2Er4O7 becomes a different novel stable framework. | P4, Results, Figure 5 | Refutes the assumption that generated identity, stability, and novelty survive deeper search unchanged. |

## Difficulty and fairness audit

The prompt discloses all output obligations and the decision burden but does not state the source
conventions or the conclusion. A plausible shallow pipeline still produces a coherent answer: it can
accept P1's SUN labels, cite P3's 44% exact-target rate, and recommend direct synthesis. That reading
fails for scientific reasons rather than formatting reasons:

1. P1's positive evidence remains real but is bounded to candidate generation and its own loose,
   dataset-specific diperiodic evaluation.
2. P2 prevents silent pooling of stability/novelty labels across reference databases and energy
   conventions, and does not benchmark SLayerGen.
3. P3's experimental result concerns a separately selected, composition-level pipeline; eight of 24
   attempted samples were uncharacterized, and only seven of the 16 characterized samples matched
   the exact target.
4. P4 directly shows that a generated structure's identity can change during a composition-level
   search, including a novelty reversal to a known prototype.

The final decision is therefore categorical, not tolerance-driven. Omitting any one source weakens a
different link: P1 removes the positive front-end case, P2 removes metric/reference comparability,
P3 removes the laboratory endpoint, and P4 removes the identity-preservation test.

## Golden structured conclusions

- `synthesis_verdict`: `retain_generator_and_require_staged_validation`
- `DISCOVERY_FRONT_END_VALUE`: `supported`
- `SUN_IS_LAB_READINESS`: `unsupported`
- `GENERATED_IDENTITY_IS_DECISION_STABLE`: `unsupported`
- `DIRECT_ROUTING_IS_JUSTIFIED`: `unsupported`
- `P1_LAYER_GROUP_CONTROL`: `directly_supported`
- `P1_SUN_TO_SYNTHESIZABILITY`: `extrapolated`
- `P2_BENCHMARK_RANK_TO_SLAYERGEN`: `extrapolated`
- `P3_SUCCESS_RATE_TO_SLAYERGEN`: `extrapolated`
- `P4_IDENTITY_TRANSFER`: `extrapolated`

The deterministic checker owns the final decision, four closed proposition verdicts, and the five
evidence-status enums under the prompt's first-match precedence. Each transfer enum has weight 2,
while the decision-critical outputs have weights 5-8, so the structured audit is covered without
dominating the scientific decision. The rubric owns the transfer justification, cross-source reasoning,
staged validation logic,
and the scientific meaning of the figure and code.
