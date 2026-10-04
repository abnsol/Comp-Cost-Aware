# Proposed classification of pre-expansion usefulness

Review specification, 4 October 2026. No signal implementation, new native experiment, fitted benefit model or selection policy is introduced here. This follows the [information audit](benefit-cost-review-after-pilot.md) and preserves the [negative cost-only result](selection-budget-comparison.md).

## Classification, not a probability or ranking

The purpose is to describe what a pending expansion could contribute using current information. A structural connection to Goal is a possible route, not a probability of completing a verified proof before the deadline. We have not selected a score, weighting scheme, learner or pruning rule.

Start with the already qualified, closed ground modus-ponens workload family. Consider a candidate's possible MP pairs in both orientations, with the evidence-disjointness guard. Distinguish the candidate sentence from the potential consequences of expanding it. An implication can participate as a rule or as the antecedent of another implication, as it does in the necessary-work family.

For each candidate, the proposed description records:

1. **Applicable MP support:** whether a matching premise/rule pair exists now. This is narrower than applicability under all PLN rules.
2. **Potential contribution to the query:** whether a possible consequence is Goal itself, lies on an implication chain leading to Goal, or has no such known connection. Use the query and current symbolic structure, not names such as `path_a`, evidence-ID conventions or the authored proof.
3. **Current support status:** whether that consequence is absent, already represented, or has unresolved informational value. An absent intermediate on a query-connected chain is a candidate prerequisite contribution. Its absence does not establish that every proof requires it.
4. **Coverage/uncertainty:** whether this analysis covers the active rule profile. Unsupported rule forms or potentially changing dependencies must be marked unknown, not certified irrelevant.

A reverse dependency analysis over current ground implications is one way to describe query connection for this restricted family. No implementation or online cost for that analysis has been established. Merely reaching the query syntactically does not verify evidence compatibility, truth values, queue survival or future selection order along the entire chain.

## Concrete distinctions supported by saved executions

| State and work | Saved observation | Proposed interpretation |
| --- | --- | --- |
| Original A/B initial state: select ReadyA | Produces CertA; CertA -> Goal is already in BB | Applicable work that supplies a missing intermediate with a known route to Goal. It does not itself complete Goal. |
| Original A/B initial state: select CertA -> Goal | Produces no new belief because CertA is absent | Query-connected but not currently applicable through this MP pair. |
| Original A/B state after ReadyA: select CertA -> Goal while it remains pending | The native trace produces Goal when this rule is selected later | Potential direct Goal work once its premise is present. Full answer acceptance still requires the agreed truth-value and proof checks. |
| Necessary-work width 4: select required R or L = (R -> C) | Each produces C plus four terminal side facts | Mixed output: it contains useful prerequisite work despite unavoidable distracting outputs. Do not classify the whole expansion as irrelevant. |
| Same initial state: select R -> SideFact0 | Produces only SideFact0 | Applicable and productive, but its output has no route to Goal in this qualified closed family. New output alone is insufficient. |
| Same initial state: select Idle | Produces no new belief | No applicable MP contribution or query support in this fixture. |
| Original A/B state after ReadyA: later select ReadyA -> CertA | Produces no new retained belief in the saved execution | A repeated consequence in this state. This observation does not establish a general same-term pruning rule. |

Evidence: [native A/B states](../results/selection/step-05/run001/audits/n004-canonical_ids/N/states.json), [native A/B trace](../results/selection/step-05/run001/audits/n004-canonical_ids/N/audit.stdout.txt), [necessary-work initial state](../results/selection/step-02/run001/necessary-w004-canonical_ids/initial-state.json), and [saved all-candidate expansion outputs](../results/selection/step-02/run001/necessary-w004-canonical_ids/initial-expansion-outputs.json). The latter outputs were previously compared against native one-step executions; [qualification evidence and scope](selection-workload-qualification.md) establish why the side terms cannot prove Goal in these exact fixtures. Only existing files were read for this review.

These observed outputs are offline reference evidence, not permissible free inputs to an online selector. The prospective signal must derive its description from the state before expansion. It cannot look up this output table during evaluation.

## Important limits

**Do not erase expensive useful work.** The required R/L expansions also perform side work. Describing their useful consequence does not allow us to skip their other native inference operations or omit their CPU cost.

**Do not count branches as independent value.** Four possible certificates are not automatically four times as valuable as one. Alternatives may establish the same Goal, share prerequisites or duplicate existing evidence.

**Do not equate an existing term with a useless result.** New evidence or a changed truth value can matter. The current cost feature `same_term_disjoint` counts possible same-term evidence interactions; it does not certify that every consequence of a candidate is redundant. Predicting complete record novelty requires additional work and validation. A conservative first description should retain an “already represented / value unresolved” flag rather than discard the candidate.

**Do not silently change confidence priority or the queue.** Classification does not authorize selecting a lower-confidence candidate, reinserting a consumed rule, pruning tasks, or changing stopping behavior. In C's saved trace, a goal implication can be in BB but absent from PQT; a useful classifier must distinguish those roles. Whether a future policy remains restricted to confidence ties is a separate experimental decision.

**Do not assume acquisition is inexpensive.** Existing MP counts scan BB per eligible candidate. Dependency construction, evidence checks and any index maintenance must be charged. Evaluating all candidate expansions to obtain exact descriptions would perform substantial reasoning before selection and cannot be treated as free prediction.

## Next bounded step for review

Validate a proposed signal implementation against saved development states and deliberately specified edge cases before changing selection. It should recognize absent versus present prerequisites, mixed useful/side output, irrelevant productive work, and uncertainty about repeated terms. Renaming symbols or permuting input order should not change its structural assessment of the same candidate/state. Changes to active rule coverage should produce an explicit limitation rather than an unjustified relevance claim.

That would be a signal-correctness and acquisition-cost check, not evidence of better PLN decisions. Only after reviewing those results should we define a selection rule and a matched cost-disabled/cost-enabled comparison. Fresh reserved evaluation cases remain necessary if the next method is designed using the formerly held-out Step 5 results.

Suggested commit message: `Specify state-based usefulness distinctions for PLN review`
