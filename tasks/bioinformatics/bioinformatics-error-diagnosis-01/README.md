# Bioinformatics — Error Diagnosis 01

Offline deterministic diagnosis of a silent target-mirroring eligibility regression in a
paper-grounded individual-ligand-novelty affinity benchmark replay.

- Primary source: Mattsson and Walters (2026), bioRxiv v1,
  `10.64898/2026.06.29.735309`
- Task type: Error Diagnosis
- Domain: Bioinformatics (`SCI-01`)
- Runtime: Python 3.11 with pandas, NumPy, SciPy, and RDKit
- Programmatic / qualitative grading: 0.65 / 0.35

## Source and construction record

The sole scientific source is Mattsson and Walters, *Identifying and Addressing Systematic Data
Leakage in Protein-Ligand Affinity Benchmarks*, bioRxiv v1, posted June 30, 2026, DOI
`10.64898/2026.06.29.735309`, licensed CC-BY 4.0. The mounted PDF SHA-256 is
`5fab564cc3280fc061eee71531015a096989ea656e7ca0beedc983ff2add864d`.

The software fixture is an offline fork of `https://github.com/bamattsson/ntab` at upstream commit
`ca9019a9b9f1ffaf7727834f716bfa347247802f` under the MIT license. Its activity records,
assay-document chronology, target-pair identities, and 2048-bit fingerprint catalog are
deterministic synthetic fixtures. They are not redistributed ChEMBL data and do not support claims
about chemical prevalence or prospective model performance.

The paper is the sole method authority. Section 4 supplies the same-document, paired-pChEMBL,
target-identity, and activity-correlation target-mirroring screen. Section 7, Figure 4, and Appendix
D supply individual-compound novelty based on earliest catalog publication and Morgan/Tanimoto
similarity. Both contributions are necessary: ligand novelty does not adjudicate target-side
mirroring, while target similarity does not establish ligand novelty. The task-specific exclusion
of mirror-incident otherwise qualifying assays is fixture policy, not a claim that the paper
prescribes a production filter.

## Reviewer notes

### Symptom summary

The broken replay exits successfully, its retained tests stay green, and the coarse release
receipt matches raw coverage. Yet its target-mirroring audit loses same-document comparisons even
though the mounted fixture contains multi-assay documents. Ligand-novel assays consequently reach
retention without their independent target-side leakage evidence.

### Expected diagnostic path and root cause

A source-grounded diagnosis must keep the two scientific axes distinct. Individual novelty is a
compound-to-reference calculation. Target mirroring is a canonical same-document assay-pair
calculation using the intersection of compounds with equality-relation, reported pChEMBL in both
assays; the pair then faces the paper's shared-count, strict target-identity, and R-squared
criteria. Pair construction is independent of novelty, base assay eligibility, and retained
representatives.

The earliest defect is in eligibility construction: the broken replay asks for same-document pair
evidence only after the working assay population has already been reduced to document
representatives. At most one assay remains per document, so the scientific pair object is erased
before it can be audited. The resulting empty or incomplete pair evidence is internally tidy but
scientifically non-diagnostic. The injected regression is confined to population orchestration in
`src/ntab_preprocess/offline_replay.py`; the pair calculations in
`src/ntab_preprocess/target_mirroring.py` are already correct.

### Minimal patch and expected diagnosis

The minimal repair constructs the complete raw same-document pair audit independently, maps
policy-active target-mirroring incidence back to otherwise qualifying assays, and allows the
existing representative rule to operate on final eligibility. It changes no novelty membership,
fingerprint, Tanimoto value, paired pChEMBL value, sequence identity, threshold, base assay rule,
tie rule, performance estimator, or schema. The correct receipt is `data_alignment /
eligibility_construction / eligibility_only / optimistic / true`.

`optimistic` refers to performance aggregation: every finite split mean changed by the repair is
higher in the broken replay, with at least one such split. It does not imply that every retained
membership change has the same direction.

### Controlled alternatives

The strongest decoy treats an individually ligand-novel retained assay as leakage-safe because no
target-mirroring partner survives in the reduced representation. It fails because Section 4's
evidence unit is the same-document assay pair, not a property inferred from the selected assay
alone. A ligand-novel assay can remain incident to a strongly correlated, sufficiently supported
pair whose targets lie below the strict sequence-identity boundary.

Other isolated alternatives are independently testable:

- assay-average novelty may alter compound and assay eligibility but must not alter the raw pair
  audit;
- counting raw shared identifiers instead of paired reported pChEMBL can falsely satisfy the
  minimum support;
- accepting target identity exactly `0.90` violates the strict boundary;
- comparing Pearson `r` directly with the `0.60` R-squared boundary changes the correlation test;
- pooling across documents or broadcasting one target-pair result discards campaign-local paired
  evidence; and
- prediction completeness affects performance only, not mirroring evidence or eligibility.

### Verification and trajectory expectations

The programmatic grader should execute the submitted project and verify fixture immutability,
complete compound and assay-pair row domains, pair-status precedence, incident-assay mapping,
base-versus-final eligibility, all secondary artifacts, stale-derivative rejection, and held-out
behavior under row permutation, opaque relabeling, deeper documents, missing target identity,
exact thresholds, duplicate rows, undefined correlation, and no-effect controls. The qualitative
grader owns source grounding, localization, independent-axis reasoning, controlled alternatives,
optimistic aggregate interpretation, evidence units, and claim limits.

### Common failure modes

Invalid approaches include hard-coding fixture identifiers, modifying mounted inputs, weakening
tests, auditing only retained representatives, using novelty as a safety override, restricting pair
evidence to novelty-tier rows, counting unpaired or missing pChEMBL, using inclusive identity,
comparing `r` with an R-squared threshold, pooling across documents, changing the target-identity
table, or regenerating only headline summaries.

### Scientific impact and limits

The bug allows target-mirrored evidence to enter a nominally ligand-novel evaluation population
and can make aggregate performance look more optimistic. The synthetic fixture establishes only
the joint-screen software failure. It cannot establish target-mirroring prevalence, real-compound
novelty, prospective affinity performance, causal binding mechanisms, or the validity of other
benchmarks.
