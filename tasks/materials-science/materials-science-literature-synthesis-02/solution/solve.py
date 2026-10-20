"""Deterministic oracle for Materials Science Literature Synthesis 02."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path


SOLUTION_DIR = Path(__file__).resolve().parent
CODE_SOURCE = SOLUTION_DIR / "code" / "build_evidence_chain.py"

ANSWER = {
    "synthesis_verdict": "retain_generator_and_require_staged_validation",
    "subclaim_verdicts": {
        "DISCOVERY_FRONT_END_VALUE": "supported",
        "SUN_IS_LAB_READINESS": "unsupported",
        "GENERATED_IDENTITY_IS_DECISION_STABLE": "unsupported",
        "DIRECT_ROUTING_IS_JUSTIFIED": "unsupported",
    },
    "evidence_statuses": {
        "P1_LAYER_GROUP_CONTROL": "directly_supported",
        "P1_SUN_TO_SYNTHESIZABILITY": "extrapolated",
        "P2_BENCHMARK_RANK_TO_SLAYERGEN": "extrapolated",
        "P3_SUCCESS_RATE_TO_SLAYERGEN": "extrapolated",
        "P4_IDENTITY_TRANSFER": "extrapolated",
    },
}

# Keep the complete scientific evidence chain on the executable oracle path. This
# makes the report-generation method traceable instead of copying an opaque artifact.
REPORT_TEXT = r"""# Evidence review for routing generated diperiodic crystals to synthesis

## Decision and scope

The four papers support **retaining SLayerGen as a discovery front end and requiring staged
validation**. They do not support sending candidates directly to synthesis on the strength of P1's
validity, stability, uniqueness, and novelty labels. That conclusion preserves the strongest positive
evidence in P1: explicit layer-group control addresses a real representational problem for
diperiodic materials. It rejects only the committee's transfer from that model-evaluation endpoint
to experimental readiness.

The apparent disagreement is mainly an endpoint mismatch. P1 evaluates generated structures with
post-relaxation stability, uniqueness, and novelty metrics after training on separately curated,
dataset-specific corpora. P2 shows that benchmark stability and novelty move with the reference set
and energy protocol. P3 predicts and then tests synthesizability, but at composition level and after
additional selection. P4 searches the potential-energy surface at fixed composition and shows that
the stable structure need not be the generated one. No paper observes the full chain for SLayerGen
candidates.

## What each source establishes

### P1: layer-group generation is useful, but SUN is not a lab endpoint

P1 (Introduction and Section 2) identifies a specifically diperiodic representation problem:
superficially tiling a layer along the aperiodic direction is inadequate because **18 of the 80 layer
groups do not injectively map to a space group**. SLayerGen is the first reported model in the paper
that explicitly models all layer groups as well as space groups. This directly supports using it to
propose symmetry-controlled candidates that a 3D-only representation can miss.

P1's model scores have narrower meanings than the committee assumes. Section 5 defines structural
validity by nearest-neighbor distances between 0.5 and 7.5 A and compositional validity by SMACT;
the authors note that roughly **10% of known crystals fail the compositional checker**. Thus even a
validity failure is not identical to physical impossibility, and a validity pass is not evidence of
synthesizability.

P1 Section 5 has two distinct stages. **Data processing** curates the four source datasets before
training: C2DB and Alex2D structures above 200 meV/atom are removed, while 2DMatPedia uses a
150 meV/atom cutoff because it was computed with a different functional. BiDB is curated using
negative bilayer binding energy and interlayer sliding stability instead of a monolayer hull cutoff.
All four datasets are then filtered for Gamma-point phonon stability. P1 calls these curation tolerances looser than
typical bulk-crystal filters and the associated convex hulls **rough guides** because surface and
interfacial interactions were neglected (P1, Section 5, Data processing).

The **Metrics** stage applies a different stability definition to relaxed generated candidates. For
2DMatPedia, C2DB, and Alex2D candidates, stability requires both `E_hull < 200 meV/atom` against
Materials Project v2023.02.07 and dynamically stable Gamma-point phonons. For BiDB candidates,
stability requires both a relaxed bilayer energy below the total energy of its separately relaxed
constituent monolayers and dynamically stable Gamma-point phonons. P1 then recomputes uniqueness
and novelty after relaxation; its S.U.N. structure and template rates count generated candidates that
are stable under the relevant definition and unique and novel under the corresponding matcher. The
150 meV/atom 2DMatPedia curation cutoff therefore is not the generated-candidate stability cutoff
(P1, Section 5, Metrics).

Those operational metrics support P1's within-study comparisons, but P1 does not test experimental
synthesis. Transferring its S.U.N. label to laboratory readiness is therefore an extrapolation. The
positive proposition that survives is candidate-proposal value, not direct synthesis eligibility.

### P2: stability and novelty are protocol-relative

P2 (Sections 3.2 and 5.2) uses a different stability convention. It calls a relaxed structure stable
when E_hull <= 0 and metastable when 0 < E_hull <= 0.1 eV/atom. It constructs a hull from a
self-consistent machine-learned interatomic-potential evaluation of both candidates and the
LeMat-Bulk reference. P2 warns that mixing MLIP candidate energies with a DFT reference hull is
inconsistent because the systematic offset can change labels.

The choice of structural reference also changes novelty. Replacing MP-20 with LeMat-Bulk lowers
MatterGen's novelty from **83.1% to 70.5%**. P2 reports example stability rates divided by about
two to three: PLaID++ falls from 31.0% to 12.4%, and DiffCSP from 7.2% to 2.3% (P2, Section
5.4 and Appendix C.4). These are not small numerical perturbations. They show that a candidate set
can look substantially more novel and stable under a narrower reference.

P2 also rejects a one-dimensional leaderboard. Under LeMat-Bulk, MatterGen has the highest
novelty at 70.5% but only a 2.0% stable rate, whereas PLaID++ has much lower novelty at
24.2% but a 12.4% stable rate. A different failure surface appears for Crystal-GFN: it reaches
the largest site diversity (32.06) and size diversity (0.32) among evaluated generators, yet has
only 51.7% validity and 0.0% stability. These concrete reversals show why no single ranking can
stand in for the laboratory's endpoint (P2, Tables 1-2 and Section 4.2).

This paper does not benchmark SLayerGen and focuses on triperiodic bulk-model outputs. Therefore
its exact rankings cannot be assigned to SLayerGen. Its methodological result still carries across:
the committee may not treat labels from different energy/reference protocols as interchangeable.

### P3: experimental evidence is valuable but does not validate SLayerGen SUN

P3 defines synthesizability as the probability that a compound can be prepared with available
methods, but its training label is composition-level. A composition is positive if **any polymorph**
has a Materials Project entry not flagged theoretical; it is negative only when all polymorphs are
flagged theoretical (P3, Section 2.1). The final ensemble converts composition and structure model
probabilities to ranks and uses a **rank-average**; candidates are ranked rather than passed through
one portable probability threshold (P3, Section 2.1, Usage in Screening).

The experimental cohort is also selected after the model score. From roughly 500 candidates, a
web-searching language model and expert review remove apparently known formulas and chemically
implausible oxidation states before a final list is formed (P3, Section 2.2). Consequently, the lab
outcome measures the whole screening and human-selection pipeline, not the synthesizability score
alone.

P3 originally attempted 24 targets. Eight completed furnace processing but bonded to their
crucibles and were not available for XRD, so the paper treats them as in progress. Among the 16
characterized samples, the exact target was synthesized seven times (44%), another predicted or
known polymorph formed twice (12%), and the target failed seven times (44%) (P3, Section 3 and
Appendix A.3). Of the nine target-or-polymorph outcomes, three were nearly identical to structures
already present and three more had similar ICSD structures that Materials Project had mislabeled as
theoretical. This makes the reported novelty endpoint database-sensitive as well.

P3's Figure 2 supplies an important direction of evidence: a simple <=50 meV/atom hull heuristic
has precision 0.534, below the composition/structure ensemble's 0.764. Low energy alone is not a
good synthesis gate. But neither the 44% exact-target rate nor the learned score directly transfers to
SLayerGen's untested diperiodic candidates, so that transfer is `extrapolated`.

### P4: deeper structural search can reverse candidate identity

P4's generated candidates pass a multistage plausibility/novelty screen and lie within 50
meV/atom of the convex hull before two compositions are taken into global crystal-structure
prediction (P4, Results and Figure 5). The subsequent search changes both examples materially.

For LiNb7N8, the initially unstable generated structure transforms into the **known W2C(hP3)
prototype** and becomes stable. For Rb2Er4O7, the initially unstable generated structure becomes a
**different, previously unreported stable framework** absent from the ICSD prototypes. The DFT
energy reductions are 214 and 158 meV/atom, respectively. P4 concludes that full global
optimization remains essential because it can overturn both stability and novelty. Its FUSE search stops
after 1,500 structures have been generated since the current minimum was located; the two searches
generated 2,189 and 2,852 structures. This finite stopping rule is why the reported CSP minimum is
heuristic rather than guaranteed (P4, Figure 5 and Methods).

These two cases do not estimate a population frequency for SLayerGen. They directly establish the
mechanism that the committee proposes to skip: composition-level search can change which
structure is stable and whether its framework is novel. The claim that a generated candidate's
identity is already decision-stable is therefore unsupported.

## Cross-source synthesis

### Metric compatibility

The four papers' terms cannot be pooled into a single candidate score.

| Quantity | What is measured | Decision-safe transfer |
| :-- | :-- | :-- |
| P1 validity | Geometric nearest-neighbor bounds and SMACT composition check | Supports basic screenability within P1; not physical realization. |
| P1 stability/S.U.N. | After relaxation: non-BiDB candidates require E_hull < 200 meV/atom against MP v2023.02.07 plus Gamma phonons; BiDB candidates require lower bilayer energy than the relaxed monolayers plus Gamma phonons; S.U.N. adds recomputed uniqueness and novelty | Supports within-protocol ranking; not lab readiness. |
| P2 stability/novelty | Self-consistent MLIP hull with stable/metastable thresholds and a large structural reference | Supplies a comparability requirement; exact rates do not transfer to SLayerGen. |
| P3 synthesizability | Composition/structure rank ensemble plus downstream selection and experiment | Supplies an experimentally relevant gate; its success rate does not transfer to SLayerGen. |
| P4 post-CSP identity | Lowest structures found by heuristic global search at two generated compositions | Directly shows that identity and labels may change; not a population success rate. |

There is therefore no genuine contradiction between P1's positive generation results and P3's
partial experimental success. P1 asks whether the model can generate and score candidates under a
diperiodic benchmark. P3 asks whether a separately screened set of compositions forms in a
particular laboratory workflow. P2 and P4 identify what must happen between those endpoints.

### Proposition audit

`DISCOVERY_FRONT_END_VALUE` is **supported**. P1 directly establishes explicit layer-group
control and competitive generation, while P4 treats generation as a useful way to seed unexplored
compositions before CSP. Neither adverse paper establishes that the generator has no discovery
value.

`SUN_IS_LAB_READINESS` is **unsupported**. P1's loose, dataset-specific proxy criteria do not
measure synthesis; P2 shows labels are reference-sensitive; P3 shows low-energy screening is a
weaker proxy than a dedicated pipeline and still does not always recover the target; and P4 shows
the generated structure can change.

`GENERATED_IDENTITY_IS_DECISION_STABLE` is **unsupported**. P4's two searches directly
produce a known-prototype reversal in one case and a different novel stable framework in the other.
P3's polymorph outcomes and mislabeled database entries reinforce the risk.

`DIRECT_ROUTING_IS_JUSTIFIED` is **unsupported**. The exact SLayerGen-to-lab chain is not
tested, and multiple required links have adverse or missing evidence.

## Assumption and transfer audit

| ID | Transfer | Status | Scope and failure risk | Validation needed |
| :-- | :-- | :-- | :-- | :-- |
| `P1_LAYER_GROUP_CONTROL` | SLayerGen controls all 80 layer groups under P1's evaluation | `directly_supported` | P1 implements and evaluates the named model property; failure would remove the main reason to retain the generator. | Reconfirm requested layer group after relaxation for each candidate. |
| `P1_SUN_TO_SYNTHESIZABILITY` | A P1 S.U.N.-qualified SLayerGen candidate is ready for experimental synthesis | `extrapolated` | The model study does not perform synthesis and calls its hulls rough guides. If false, scarce experiments are spent on proxy-passing but inaccessible structures. | Dedicated synthesizability screen plus a small prospective campaign. |
| `P2_BENCHMARK_RANK_TO_SLAYERGEN` | P2's bulk-generator rankings also rank SLayerGen's diperiodic candidates | `extrapolated` | P2 omits SLayerGen and uses bulk-model outputs and its own reference protocol. If treated as direct, the wrong model or threshold may be selected. | Re-evaluate SLayerGen candidates under one self-consistent energy and structural-reference protocol. |
| `P3_SUCCESS_RATE_TO_SLAYERGEN` | P3's 44% exact-target rate predicts SLayerGen exact-phase yield after P1-only selection | `extrapolated` | P3 uses different candidates, composition labels, extra machine/expert selection, and bulk solid-state experiments. | Prospective SLayerGen-specific pilot with all attempted samples in the denominator. |
| `P4_IDENTITY_TRANSFER` | P4's observed risk that CSP changes identity, stability, or novelty also applies to actual SLayerGen candidates | `extrapolated` | P4 directly observes the mechanism in two triperiodic PIGEN cases, but neither case is a SLayerGen diperiodic candidate. Treating the frequency or outcome as portable would overstate the evidence. | Composition-level CSP with identity matching on the actual SLayerGen candidates before synthesis. |

## Minimum staged validation gate

The committee should keep SLayerGen as the proposal engine but require a fixed sequence before lab
allocation:

1. **Representation and relaxation gate.** Confirm layer-group assignment, nearest-neighbor
   plausibility, composition, and symmetry after relaxation rather than only at generation.
2. **Comparable energy gate.** Recompute candidate and competing-phase energies with one stated
   DFT/MLIP protocol and one comprehensive reference. Report distance to the hull under that
   protocol; do not mix P1 and P2 rates.
3. **Composition-level structure search.** Seed a global CSP search with the generated structure and
   alternative starts. Compare the lowest structures found with the generated candidate and report
   whether stability, layer symmetry, and prototype identity survive. A heuristic search limitation
   remains explicit.
4. **Novelty and synthesizability gate.** Re-run structure matching against an updated reference,
   score composition and relaxed structure for synthesizability, and perform literature/database
   review. A known polymorph at the composition is not evidence that the exact generated structure
   is accessible.
5. **Prospective pilot.** Synthesize only a small preregistered set that passes all prior gates. Count
   every attempted target, report crucible losses separately, and use XRD/Rietveld analysis to
   distinguish the exact predicted phase from another polymorph or a known prototype.

No single gate is allowed to compensate for failure of another. In particular, a favorable P1
S.U.N. label cannot offset loss of identity after CSP or absence of an experimentally relevant
synthesizability case.

## Evidence-chain figure

`candidate_evidence_chain.png` shows the four source rows against five decision axes. P1 supports
symmetry-aware generation and provides scoped energetic/identity evidence but does not test
synthesizability or direct routing. P2 cautions that energetic and novelty rankings depend on the
reference protocol. P3 supports the need for an explicit synthesizability stage while cautioning on
identity and direct routing. P4 supplies the strongest caution on structural identity and direct
routing after deeper search. Cells marked "not tested" prevent absent evidence from being read as
negative evidence.

## Conclusion

The evidence supports a bounded use of SLayerGen, not the committee's shortcut. The generator can
expand symmetry-controlled candidate space, but the papers do not establish that its reported SUN
criteria preserve a candidate's identity or predict laboratory realization. The final decision is
`retain_generator_and_require_staged_validation`.
"""


def _load_figure_module():
    spec = importlib.util.spec_from_file_location("build_evidence_chain", CODE_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load evidence-chain module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    output_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/agent/results")
    code_dir = output_dir / "code"
    figure_dir = output_dir / "figures"
    code_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "answer.json").write_text(
        json.dumps(ANSWER, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(REPORT_TEXT, encoding="utf-8")
    shutil.copyfile(CODE_SOURCE, code_dir / CODE_SOURCE.name)

    module = _load_figure_module()
    module.build_figure(figure_dir / "candidate_evidence_chain.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
