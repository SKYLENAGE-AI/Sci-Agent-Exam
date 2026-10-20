# Task record: Versioned-result DFT catalytic interpretation

- Domain: SCI-03 (Chemistry)
- Task type: Result Interpretation
- Created: 2026-07-21

## Source

| Field | Value |
| --- | --- |
| Title | Catalytic hydrogenation of acetone to isopropyl alcohol with CAl3MgH2- containing planar tetracoordinate carbon |
| Authors | Abdul Hamid Malhan and Krishnan Thirumoorthy |
| Identifier / URL | https://doi.org/10.3389/fchem.2025.1750798 |
| Publication date | 2026-01-13 |
| License | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Role | Primary method and result source for the proposed two-step DFT pathway and the catalytic claim being interpreted |
| Unique insight | The paper supplies the local stationary-point evidence, separately referenced reaction segments, product-complex regeneration argument, and the boundary between a proposed mechanism and demonstrated catalysis |
| Necessity | Without the paper, an agent can calculate conditional Eyring rates but cannot faithfully assess what the authors validated, how they argued for regeneration, or the experimental status of the catalyst |

## Eligibility

The article was received on 2025-11-20, accepted on 2025-12-29, and published
on 2026-01-13, after the primary-source cutoff. Frontiers publishes it under
CC BY 4.0. It is a peer-reviewed original-research article in theoretical and
computational chemistry and is directly relevant to interpreting mechanistic
and catalytic claims from quantum-chemical results.

The originally bootstrapped `s41524-025-01886-x.pdf` was not used because its
CC BY-NC-ND 4.0 license is outside the project's allowed CC0/CC BY source set.
It was replaced before any task content was derived.

## Construction

The reported-result CSV files transcribe numerical results from Figure 3,
Table 1, Table 2, Figure 5, and the accompanying Results and Discussion. They
preserve the paper's segment-specific reference zeros rather than inventing an
inter-segment offset. `artifact_registry.csv` adds explicit version,
provenance, review-state, and claim-authority metadata. The
`screening_summary.csv` fixture is a clearly registered, synthetic
prepublication preview: it uses the reported TS2 segment barrier as a putative
cycle span and therefore produces a plausible but non-authoritative TOF and
verdict. It is not represented as a result from the article.

`calculation_settings.json` pins the exact constants for deterministic Eyring
calculations and labels the +/-2 kcal/mol exercise as a sensitivity scenario
rather than an uncertainty estimate.

The task deliberately starts from reported stationary points and observables;
it does not ask the agent to repeat DFT. Its load-bearing chain is
authoritative-record selection, preservation of source reference semantics,
bounded calculation, cycle/TOF eligibility, and the compound claim verdict.
The preview remains internally tidy so numerical self-consistency alone cannot
substitute for provenance and reference-state fidelity.

## Reviewer notes

### Study framing

The study proposes CAl3MgH2- as a potential gas-phase acetone-hydrogenation
catalyst. The interpretation target is evidence sufficiency: whether the
reported computations support local elementary steps, a closed catalytic
cycle, and practically meaningful turnover at 298.15 K.

### Artifact inventory

- `artifact_registry.csv` distinguishes the final reported segment data from
  the superseded derived preview; IDs and paths are treated as data rather than
  hardcoded conventions.
- `reported_energetics.csv` carries the two local Gibbs profiles, the
  uncatalyzed comparison barrier, electronic-energy cross-checks, and IRC
  adjacency labels.
- `natural_charges.csv` and `bond_metrics.csv` carry the mechanistic evidence
  for hydride transfer and heterolytic H2 cleavage.
- The PDF supplies the calculation hierarchy, interpretation of IRC and
  charge evidence, product-complex regeneration argument, and explicit lack
  of a demonstrated synthetic route.
- `calculation_settings.json` makes the supporting rate and sensitivity
  calculations deterministic.
- `screening_summary.csv` supplies the tempting closed-cycle/TOF alternative
  whose provenance and derivation must be evaluated rather than accepted from
  clean-looking fields.

### Key calculations and expected values

At 298.15 K with kappa = 1, the local Eyring rates are approximately
4.92e7 s^-1 for TS1 and 9.28e-4 s^-1 for TS2. Their segment-rate ratio is
about 5.29e10.
Perturbing the TS2 barrier by -2 and +2 kcal/mol gives approximately
2.71e-2 and 3.17e-5 s^-1. The reported 52.23 kcal/mol barrier reduction maps
to an Eyring factor of about 1.93e38. The absolute electronic-energy method
differences are 0.69 kcal/mol for TS1 and 0.03 kcal/mol for TS2.

### Evidence interpretation

The first-order saddle points, IRC connections, bond changes, and charge
separation support the local proposed pathway and heterolytic H2 cleavage.
The near identity of the catalyst fragment in product complex D supports
structural recovery inside that optimized complex. These results do not by
themselves establish a turnover frequency. A and C are separate reference
zeros, so no common-reference energy span follows from the supplied profile.
Product release, the inter-segment standard-state connection, competing
paths, catalyst speciation, and a microkinetic model are absent.

The Eyring rate for TS2 is therefore a conditional local rate, not a TOF. The
large acceleration relative to the uncatalyzed path establishes that the
modeled route lowers a particular barrier, but not that an isolable catalyst
will operate at that rate.

### Alternatives, limitations, and follow-up

Product-complex stabilization, including the source-reported hydrogen bond,
could aid formation while hindering product release. The bare gas-phase anion
lacks counterion, solvation, aggregation, and decomposition treatment. The
article also states that effective laboratory synthesis methods for stable
ptC species are lacking.

The decisive computational follow-up is a single-standard-state free-energy
cycle including association and release, followed by energy-span or
microkinetic analysis with alternative pathways and uncertainty. The decisive
experimental follow-up is synthesis/characterization under a defined
counterion/environment and measurement of rate, selectivity, and catalyst
recovery.

### Expected controlled decision

The authoritative artifact ID is `segment-report-2026-01`. Both
`cycle_energy_span_status` and `turnover_frequency_status` are
`not_identifiable`, and the screening summary is `non_authoritative`.
`claim_verdict` is `partially_supported`: the local mechanism and catalyst-
fragment recovery are supported, while catalytic viability and turnover under
the stated conditions are not established.
