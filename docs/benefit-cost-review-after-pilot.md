# Benefit and cost after the negative PLN pilot

4 October 2026. Focused primary-source recheck and adaptation assessment. No new experiments, model fitting or selector changes.

## What needs explaining

The [completed comparison](selection-budget-comparison.md) found higher median first-answer CPU under the frozen immediate-cost tie-breaker on all 21 cases. The overhead-only control also slowed native selection. In the canonical width-4 trace, the cost-informed policy first selected five goal-producing implications whose premises were absent; it reached the first proof after 13 expansions rather than four.

This was a test of predicted immediate expansion cost within confidence ties. It was not an implementation of the papers' benefit estimates or full metareasoning policies. It neither refutes their methods nor establishes that an adaptation will work.

## What the papers actually supply

The following summarizes the relevant mechanisms, not a new reproduction audit. Broader experimental results and unresolved code/version questions remain in the [earlier paper review](metareasoning-papers-pln-review.md). Requirements and PLN implications in the last column are our assessment.

| Primary source and location | How benefit enters | Requirements and transfer limit |
| --- | --- | --- |
| [Hay et al., Selecting Computations](https://arxiv.org/pdf/1207.5879), Definitions 3, 6 and 14–16 | Final decision utility minus computation charges. Myopic evaluation considers one computation; blinkered evaluation permits further sampling of the same independent alternative. | The Bayesian treatment needs an outcome/utility model. Its independence assumptions do not automatically hold for PLN expansions sharing a belief buffer. A prerequisite's usefulness can appear only after further work. |
| [Callaway et al., BMPS](https://cocosci.princeton.edu/papers/callawayLearningToSelect.pdf), §§2–3, Eq. 5 | Combines immediate information value, perfect-information value and relevant-subset information value; subtracts a weighted cost term. Bayesian optimization fits policy weights. | Requires beliefs, updates, utilities and relevance definitions from which these features can be calculated. Fitting CPU duration alone supplies none of those benefit features. |
| [Budd et al., Stop! Planner Time](https://ojs.aaai.org/index.php/AAAI/article/view/29983/31725), Algorithm 1 and experimental setup | DQN learns action values from planning charges and terminal policy-execution cost. Decisions are whether to execute or continue planning with a heuristic setting. | Uses generated problem distributions, planner/context features and experience: 300,000/600,000 training steps in its two domains. Evaluation budgets are planner state visits. This does not establish a PLN sample requirement or CPU-saving guarantee. |
| [Vlasselaer et al., TP-Compilation](https://starai.cs.ucla.edu/papers/VlasselaerIJCAI15.pdf), §4.2 | Scores probability-bound improvement against relative decision-diagram growth, adjusted by query depth. | Requires ProbLog explanation formulas and weighted model counting. Candidate scoring itself performs compilation. Its probability guarantees and cost proxy cannot be substituted for PLN truth values and measured CPU. |
| [Geisweiller, PLN for Inference Control](https://aitp-conference.org/2025/abstract/AITP_2025_paper_2.pdf), §§2–3 | Estimates conjecture provability from evidence and compares joint provability of prerequisite subgoals. | Needs the proof/theory representation and supporting examples or relations. Existence of a proof is different from finding it before a CPU deadline. This short paper supplies no measured-CPU performance comparison. |
| [Sui et al., Meta-Reasoner v6](https://arxiv.org/pdf/2502.19918v6), §3.3 | Contextual bandit feedback combines judged reasoning progress with a reasoning-step penalty. | Needs progress representations, feedback and a strategy action set. Judged text progress is not an independently verified PLN derivation; a step penalty is not heterogeneous CPU cost. The earlier review's implementation/version mismatch remains unresolved. |
| [Consul et al., hierarchical planning](https://link.springer.com/article/10.1007/s42113-022-00128-3), Low-level Policy Search, Eqs. 6–7 | Modifies BMPS's cost feature to account for the observations assumed by its benefit features. | Warns against crediting a sequence's benefit while pricing only one computation. This is a relevant method extension, not a completed audit of that entire study or a reason to select a hierarchical architecture. |

## A consequential BMPS distinction

Equation 5 uses

```text
estimated value = w1·VOI1 + w2·VPI + w3·VPI_subset − w4·cost
```

Its studied computations have equal specified cost λ (§2.1). **Our algebraic inference:** at a fixed state and fixed weights, both the global VPI term and this equal cost term cancel when comparing two computational actions. They can still affect whether to stop. Ranking computations by unequal measured CPU would therefore be an adaptation, not a replication of that experimental setting. The paper's cost term is not a trained hardware-duration predictor. [BMPS, §§2.1–3](https://cocosci.princeton.edu/papers/callawayLearningToSelect.pdf).

## Translate benefit before selecting an algorithm

For our existing endpoint, useful work contributes to obtaining a verified proof before the CPU deadline. This is our task-specific interpretation, not a paper-provided PLN value function. Several distinctions are necessary:

1. **Immediate output is not the whole benefit.** `ReadyA` produces a certificate rather than Goal, but that certificate enables a later Goal derivation. A reward that recognizes only an immediately completed Goal misses this prerequisite. Conversely, merely generating many atoms can reward distracting work.
2. **Relevance, applicability and eventual usefulness differ.** `Certificate -> Goal` is query-relevant but cannot fire without its certificate. A matching premise can make work applicable without making it necessary or novel. Duplicate conclusions and alternative proofs complicate usefulness labels.
3. **The reasoning action remains one selected sentence.** We cannot assume that selecting ReadyA commits PLN to an exclusive A route. Implications can be selected, and all branches share BB. Any multi-step benefit estimate must specify the subsequent selection behavior it assumes.
4. **The objective and units must match.** A hard-deadline proof-success objective is not automatically equivalent to utility minus a freely chosen CPU penalty. Subtracting nanoseconds from a probability requires a declared conversion or a different constrained formulation. Credit for a future proof must also account for the computation needed after its first prerequisite.
5. **Available information must be explicit.** Current KB, query, queue and already observed results may be inputs. Saved future traces and completed proofs can support offline evaluation, but cannot be free online features. Inspecting rules, building indexes and simulating candidates all cost computation; lookup-based does not mean free.

## What our existing data can support

The [development collection](cost-data-collection.md) supplied 941 qualified cost-fitting rows across 56 states from 15 cases. Those targets are expansion CPU, not eventual proof benefit. The 6,048 comparison runs repeat 21 cases under three fixed policies and eight budgets; they are not 6,048 diverse training problems. They characterize timing, selected trajectories and verified outcomes.

Membership in one captured proof is not a complete benefit label: another expansion might enable an alternative proof, and unchosen continuation sequences were not exhaustively evaluated. These records do not yet establish that a learned benefit model or DQN will generalize. A structural heuristic need not require training labels, but its usefulness and online overhead would still need evaluation. The papers do not establish a minimum dataset or GPU requirement for our setting.

The six formerly held-out cases remain legitimate held-out evidence for the frozen Step 5 model. Their outcomes have now informed our reasoning. If they influence the next method, they become known diagnostics for that method; a new generalization claim needs a fresh reserved evaluation set.

## Review boundary

Before choosing an architecture, agree on a precise **benefit definition, permissible pre-expansion inputs, continuation horizon and data source**. Then check that a proposed benefit signal can distinguish missing-prerequisite goal rules, useful prerequisite work, duplicates and genuinely necessary expensive work without consulting future answers. No such signal has been selected or validated here.

For a later causal comparison, benefit guidance must be shared between the cost-disabled and cost-enabled conditions. Retain an overhead-only control and native reference, common proof/stopping rules, and total CPU accounting. A cheap applicability or relevance improvement could explain gains by itself; those gains must not be attributed to cost information. Fixing cost-estimation overhead alone may also matter and should not be conflated with better benefit estimates.

This review supports a concrete next discussion: **what evidence available before an expansion can indicate that it enables a verified answer soon, at an affordable evaluation cost?** It does not select a neural model, promise an improvement, or draft the final project proposal.

Suggested commit message: `Document benefit-cost requirements after the negative PLN pilot`
