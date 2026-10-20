# Diagnosis of the joint novelty and target-mirroring replay

## Source conventions and observed symptom

The release receipt verifies raw split, document, assay, and activity-row coverage. It cannot show
whether same-document target-mirroring evidence was constructed before eligibility and retention
were summarized. The broken replay therefore reports a matching receipt and plausible
ligand-novel performance even though its pair audit omits the comparisons needed to evaluate the
independent target axis.

Mattsson and Walters (2026, Section 4) define target-mirroring evidence on pairs of assays from the
same paper. A qualifying pair has at least ten compounds with reported pChEMBL in both assays,
overall target-sequence identity strictly below `0.90`, and paired activity R-squared at least
`0.60`. These commitments fix the document-local assay-pair unit, paired-value support population,
strict identity boundary, and squared-correlation statistic. Overall rather than local identity
separates distinct targets, while strong squared agreement on reported values in both assays marks
unexpectedly transferable campaign-level outcomes: evidence of benchmark leakage risk, not a
binding mechanism or target-causality claim.

The paper's ligand axis is separate. Section 7 and Figure 4 use each compound's maximum 2048-bit,
radius-2 Morgan-fingerprint Tanimoto similarity, with exact matches at `1.00`. The source-document
year assigns assay splits, whereas Appendix D compares each new compound with compounds whose
earliest ChEMBL publication predates the novelty cutoff. Thus an
assay can be composed of compounds in the configured individual-ligand novelty tier and still be
incident to a target-mirroring assay pair. Neither axis is a substitute for the other.

The supplied replay adds one explicit policy: in validation and test, an otherwise qualifying
assay incident to a target-mirroring pair has final status `target_mirroring_excluded`. That
integration rule is a task configuration, not a claim that Mattsson and Walters prescribe this
production exclusion.

## Earliest defect and minimal repair

The compound novelty table, base assay qualification, target-identity values, paired-value
calculation, document tie rule, and performance estimators are individually correct. The earliest
defect is the evidence population used for eligibility construction. The broken replay builds the
target-mirroring audit from a working table already reduced to one representative per document.
Within the policy-active validation/test splits, that representation cannot contain a pair of
distinct assays from the same document. The policy-active audit therefore becomes empty by
construction, its incident-pair counts become zero, and mirror-incident assays evade the configured
final exclusion. Unaffected train rows retain their ordinary pair domain: in the public replay the
broken audit contains three train-control pairs but no policy-active pair, whereas the complete
repaired domain contains twenty pairs.

The minimal repair constructs the complete canonical same-document pair audit from the mounted
source-valid assay evidence, independent of compound novelty, base eligibility, and document
representation. It then maps policy-active target-mirroring incidence to otherwise qualifying
assays and leaves the existing representative selection and performance code unchanged. This is a
`data_alignment` error at `eligibility_construction`, repaired within `eligibility_only`.
Conditioning pair construction on one of those downstream states changes the evidence estimand:
whether upstream evidence exists then depends on the decision that evidence is supposed to inform,
so a qualifying pair can be converted into apparent absence before eligibility is evaluated.

The failure cascade is:

`policy-active document-representative rows substituted for the same-document pair domain ->
policy-active target-mirroring pairs erased -> incident assays receive zero mirror count -> final eligibility is falsely
qualifying -> mirrored assays reach retention and performance -> finite split mean R-squared is
optimistic while raw release coverage still matches`.

## Controlled alternatives

The strongest decoy treats a retained assay's individual-ligand novelty as sufficient evidence of
leakage safety. It is attractive because the compound table and novelty-conditioned assay counts
are correct. It fails on an orthogonal observation: a ligand-novel assay remains incident to a
same-document pair with sufficient paired pChEMBL support, target identity below `0.90`, and
R-squared above `0.60`. The assay is novel on the ligand axis and target-mirrored on the target
axis at the same time.

The repaired evidence includes two test mirror pairs with `(n_shared, identity, R2)` equal to
`(14, 0.62, 0.91)` and `(12, 0.58, 0.79)`, plus one validation pair at
`(12, 0.71, 0.84)`. Each clears all three criteria with stable margins; none depends on rounding,
an exact boundary, or a microscopic rank edge. The compounds in all three mirror witnesses are in
the configured individual-ligand novelty tier, so target mirroring is not an alias for failed
ligand novelty.

An assay-average novelty counterfactual changes only the ligand axis. It may change tier-local
assay counts or base eligibility, but the complete raw pair audit must remain invariant because
pair evidence is defined independently of novelty. If that intervention changes pair rows, the
implementation has incorrectly coupled the axes. This is a logically derived discriminator from
the submitted population boundaries, not a claim that the golden procedure executed a second
novelty replay.

A second one-factor counterfactual changes only shared-support membership: a raw-overlap
alternative counts ligand identifiers present in both assays even when one side has an inequality
relation or missing pChEMBL. Assay/document identities, targets, ligand-novelty rows, identity
values, and thresholds remain invariant. That intervention can raise support above ten without ten
paired reported values, so the source-defined paired-pChEMBL population rejects it.

A separate boundary control changes only the identity comparison from strict to inclusive at
exactly `0.90`; pair membership, shared support, correlation, and every other threshold remain
invariant. Under the hypothetical inclusive comparator, an exactly-`0.90` row passes the identity
stage and proceeds to the later correlation disposition; under the configured strict comparator
it is `target_identity_not_below_threshold`. Every non-status pair field is unchanged. This is a
logical consequence of the submitted comparator and status precedence, not an executed auxiliary
replay. Likewise, substituting Pearson `r` for
R-squared changes only the statistic tested and cannot be compared directly with the `0.60`
R-squared threshold. These isolated controls do not rely on a compound multi-factor intervention.

Thus the one-factor alternatives have explicit evidence routes: assay-average novelty changes only
ligand-tier membership while pair identities and paired statistics remain fixed; raw shared-ID
support changes only the support population while assay/document identities, targets, novelty,
identity, and thresholds remain fixed; and inclusive identity changes only boundary disposition
while shared support, correlation, and non-status pair fields remain fixed. The named final tables
and patched analysis functions make each invariant and discriminating consequence directly
checkable without relying on an execution-history claim.

Pooling across documents or broadcasting one target-pair disposition also fails. Section 4's
correlation is campaign-local paired evidence: the same targets may occur in another document with
different compounds and a different correlation. Prediction missingness is downstream again; it
may change complete performance pairs but not compound novelty, raw target-mirroring evidence, or
eligibility. Missing experimental pChEMBL is instead excluded without imputation from base-assay
eligibility and paired-pChEMBL support; neither kind of missingness is treated as zero.

## Artifact reconciliation and validation

The repaired `compound_novelty.tsv` remains unchanged because the repair does not alter the ligand axis.
Its validation/test rows preserve earliest-catalog references, maximum Tanimoto, strict tier
membership, deterministic nearest-reference ties, and query self-membership; train remains the
no-effect control.

The repaired `assay_pair_audit.tsv` covers every canonical unordered pair of distinct assays in
each document, including rejected, undefined, target-mirroring, train-control, and no-effect rows.
Every row is traceable to paired equality-relation finite pChEMBL after agreeing-duplicate
collapse, one unordered sequence-identity lookup, and the declared status precedence. Assay-average
novelty and prediction completeness are outside this table's declared inputs, so changing either
would leave this raw pair-evidence table invariant.

The assay inventory separates base eligibility from mirror incidence and final eligibility. Only
otherwise qualifying validation/test assays incident to policy-active target-mirroring pairs gain
`target_mirroring_excluded`; unrelated base-ineligible assays keep their original failure reason,
and train has no exclusion. One repaired `target_mirroring` row is incident only to two
base-ineligible assays: it remains load-bearing pair, document, and split evidence while producing
no eligibility, retention, or performance change. Document and split audits then reconcile pair counts, distinct excluded
assays, final qualifying membership, retained representatives, and membership digests without
double-counting an assay incident to multiple pairs. The three repaired mirror pairs make four
distinct otherwise qualifying validation/test assays final-ineligible: two in test and two in
validation.

Pair-to-assay incidence is the necessary bridge from the paper's pair-level evidence object to the
fixture's assay-level conditional policy; without that bridge a numerically correct pair table is
scientifically decorative. A qualifying pair incident only to already base-ineligible assays remains
valid upstream evidence and a downstream no-effect control. Non-mirroring, missing-identity,
undefined-correlation, rejected-boundary, no-op, and unchanged rows are likewise retained at their
own evidence layers rather than being discarded because they do not alter final eligibility.

Relational identity supplies the generalization mechanism: grouping and joins use declared split,
document, assay, standard-type, and ligand keys; target identity uses an unordered target-pair key;
and the audit uses a canonical unordered assay-pair key. Row position, endpoint orientation,
opaque identifier spelling, and a fixed rank therefore cannot define any scientific unit.

All retained-assay performance rows, split summaries, and the release receipt are freshly
regenerated for the mounted fixture. The submitted implementation derives groups, joins, and
canonical pairs from relational keys rather than row position, identifier spelling, or fixed
ranks; its handling of document depth, multiple incidence, declared boundaries, missing identity,
undefined correlation, agreeing duplicates, repeated target pairs, and no-op exclusions is
inspectable in those code paths. These are implementation-level generalization properties, not a
claim that the golden procedure executed and preserved a separate transformed-fixture suite.

## Interpretation and limits

`optimistic` describes the aggregate comparison: at least one finite split `mean_r2` changes, and
the broken value is higher for every changed finite split. It does not require retained membership
to change only in one direction. Pearson `r` and R-squared in `assay_performance.tsv` are computed
within retained assays from complete experimental-prediction pairs; `mean_r2` is the unweighted
mean across retained assays with defined R-squared. Test changes from broken `0.97970243` to
repaired `0.79036721`, and validation from `0.33872270` to `0.22218218`; train remains
`0.91334516`. Test retains five assays in both replays but changes its membership digest, while
validation changes from six retained assays to five. Counts alone therefore cannot substitute for
identifier-complete evidence. Across the complete membership sets there are two broken-only and
one repaired-only assays, confirming that performance direction and membership direction are
distinct commitments.

The repair establishes that a ligand-novel evaluation population can still contain target-mirrored
assay evidence when a joint replay destroys the source-defined pair unit. The inputs are synthetic
interface fixtures, not real molecules or redistributed ChEMBL records. This replay cannot
establish target-mirroring prevalence, chemical novelty in real data, prospective affinity
performance, a causal protein-ligand mechanism, or the validity of other benchmarks.
