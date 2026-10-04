# Metareasoning papers reviewed against the PLN cost-factor experiment

4 October 2026. Method, experimental-evidence, and implementation-readiness review.

## Purpose and scope

This review covers the five papers named in our problem statement and Meta-Reasoner from our earlier reading. It asks what each paper actually selects, how it represents benefit and cost, what its experiments establish, and what would be required to reproduce or adapt it. Methods and experimental sections were inspected in primary sources; relevant supplements, figures, and available implementation paths were checked. Numerical results below are **reported by the authors, not reproduced here**. No new PLN experiments, training, installations, or selector changes were performed.

Our reference is the [PLN problem statement and measured baseline](preliminary-pln-computation-findings.md), with the [remaining evaluation requirements](qualification/09-criteria-review.txt). The pinned reasoner selects a sentence and expands it against the belief buffer. An expansion can generate several results. Implication records are candidates too, so selecting ReadyA or ReadyB does not exclusively choose a complete proof route. The primary outcome is a valid proof obtained by a declared CPU deadline, with late answers counted as misses. Probabilistic accuracy remains a separate, unqualified track.

**Main finding:** these papers provide useful methods for estimating benefit, selecting computations, or deciding when to stop. None of the six supplies a validated predictor of the heterogeneous PLN expansion CPU costs we measured. This is a statement about this reviewed set, not a literature-wide novelty claim. Reproducing a paper's original task and testing a cost factor in PLN are separate experiments.

## 1. Hay et al.: Selecting Computations: Theory and Applications

**Primary evidence.** [UAI 2012 paper, §§2–6](https://arxiv.org/pdf/1207.5879).

- **Problem/unit:** choose which alternative action to sample before making one final decision. The metalevel state records observations; stopping selects the largest posterior expected utility. A computation incurs a specified fixed cost.
- **Method:** myopic selection evaluates one more computation; blinkered selection permits continued sampling of one independent alternative, using backward induction. Other variants use distribution-free value-of-information bounds. These estimate decision improvement, not hardware duration.
- **Experiments:** Figure 2 uses 25 Bernoulli alternatives and 1,000 trials, comparing blinkered, myopic, ESPb and UCB1 variants. Figure 3 uses 10,000 trials, comparing VOI/VOI+ with UCB1 at fixed sample budgets; every method spends the budget. Reported regret improves for the proposed variants.
- **Additional result/limit:** the modified Pachi experiment reports up to 64% wins against UCT in 9×9 Go at 10,000 simulations per move, over 1,000 repetitions. That result combines root selection, stopping and reuse of saved budgets; it is not a CPU-cost ablation. Independence restricts blinkered decomposition. See Definitions 3/6, Theorem 16, Figures 2–5.

**Mapping to our PLN task — our assessment.** The useful distinction is between selecting work to improve a final answer and collecting rewards from every intermediate operation. Our pending sentences are computational actions; they are not independent alternative answers with separate Bernoulli reward distributions. Shared beliefs, evidence, and selectable rules couple their consequences. PLN confidence is not automatically a Bayesian posterior over search success. A prerequisite expansion may have no immediate answer reward, yet enable a later proof; a purely one-step benefit estimate can miss that value.

**Reproduction and solo feasibility.** A small Python sampling reproduction appears tractable, but runtime has not been measured. Freeze Figure 3's task, initialization, tie-breaking, budget grid and regret metric before running it. A CPU measurement added to that task would be an extension. A full Go reproduction is considerably larger and unnecessary to understand the selection mechanism. An exact original reproduction package was not verified; this does not establish that none exists. No PLN mapping follows automatically from reproducing the sampling result.

## 2. Callaway et al.: Learning to Select Computations (BMPS)

**Primary evidence.** [2018 v3 paper, §§2–5 and supplement](https://cocosci.princeton.edu/papers/callawayLearningToSelect.pdf).

- **Problem/unit:** select information-gathering computations and stopping decisions in binary choice, Bernoulli option selection, and reward-revealing tree planning.
- **Method:** Bayesian policy search fits a convex mixture of immediate, perfect-information and relevant-subset information values, minus a separately weighted cost term. Features require a belief/update/utility model. Studied computations have common assumed cost `λ`, not learned CPU duration.
- **Experiments:** option selection uses 2–5 alternatives, horizon 25, ten optimization iterations of 1,000 episodes, candidate reevaluation, and 2,000 evaluation episodes per setting. Return is 0.6535 versus optimal 0.6596 and blinkered 0.6559. Baselines also include meta-greedy, full deliberation, and DQN. Aggregate planning return is 98.4% of optimal over evaluated height-2/3 cases.
- **Overhead/limits:** the hypothetical tornado study measures approximately 1–3 ms selection overhead against simulations assumed to take hours. Supplementary scenarios include losses when metareasoning is too expensive relative to selected computations. Locations: Eq. 5; §§4.2–5; supplement.

**Mapping — our assessment.** Three different problems must remain separate: estimating the next expansion's CPU, estimating its eventual proof contribution, and optimizing a policy using those estimates. Our harness supplies executable transitions and proof checks, but not a justified distribution over unperformed computations or a cheap perfect-information feature. Saved future proofs cannot become online features. The millisecond overhead scale is especially consequential beside our microsecond expansions and millisecond first answers; the paper's favorable timing regime cannot establish feasibility here.

**Reproduction and solo feasibility.** A small original-task reproduction is plausible, with model and features supplied by the task. A faithful PLN adaptation is more demanding than fitting a few policy weights: it also needs defensible features, task diversity, outcome definitions and charged feature acquisition. Our repeated runs of nine KBs do not establish sufficient training diversity. An exact release matching the 2018 experiments was not verified. The [later author repository](https://github.com/fredcallaway/optimal-fixations-simple-choice) identified in earlier notes concerns another study and must not be relabeled as the 2018 release.

**Protocol correction:** §4.2.2's five-candidate reevaluation mentions 5,000 additional episodes; the aggregate count is not explicit. Earlier notes asserting `5 × 5,000` were too definite.

## 3. Budd, Lacerda and Hawes: Stop! Planner Time

**Primary evidence.** [AAAI 2024 paper, pp. 20053–20060](https://ojs.aaai.org/index.php/AAAI/article/view/29983/31725), with the [official Oxford supplement](https://ora.ox.ac.uk/objects/uuid%3A71b8f60e-519f-4f5f-b8bb-ae18a67469e7/files/s1j92g945t).

- **Problem/unit:** execute an anytime planner's current policy or continue planning with a selected heuristic setting. A proper default policy makes incomplete plans executable.
- **Method:** DQN maps planner features and problem context to actions. Performance profiles are implicit in learned action values, rather than a separate CPU predictor. Continued planning incurs an instance-fixed thinking price; terminal execution cost is sampled through Monte Carlo.
- **Experiments:** Deep Sea Treasure and racetrack use twenty metasteps covering 10,000 and 100,000 state visits, respectively. Training uses hundreds of thousands of experience steps, eight seeds, separate validation and 1,000 held-out problems. Comparators include MidBound, PolicyEval, and feature/context/tuning ablations.
- **Results/limits:** the reported advantage is significant at 0.01 except against NoFeatures in racetrack; feature information helps little there. PolicyEval's added assessment cost can cause premature execution. The experimental resource unit is state visits, not CPU. Figures 3–5 show variability without tabulated exact means. State abstraction may fail the Markov assumption; no general online-planning result is demonstrated.

**Implementation evidence.** Supplement pp. 9–11 specify C++ planning/simulation, Stable-Baselines3 1.8.0, ten parallel environments, normalized planner/context observations and hardware with 16 vCPUs and a T4. PolicyEval overhead is converted from measured runtime ratios into thinking-cost units. Exact training duration, seed lists and a separate DQN inference-time measurement were not located. No official runnable package or checkpoints were verified in this bounded search. The reported machine is not a demonstrated minimum requirement.

**Mapping — our assessment.** Learning eventual outcomes could address delayed usefulness, but changing the action menu from planner settings to pending PLN sentences is a new adaptation. The baseline has no always-valid fallback answer before a proof exists, so its stopping objective differs. Planner value bounds must not be replaced by PLN confidence without justification. Running a rich learned policy against native confidence would change several factors at once and would not isolate cost information.

**Reproduction and solo feasibility.** This is a larger reproduction than a small sampling task: it needs the planning domains, planner, training protocol and costly comparison policies. Our existing traces are insufficient evidence that a DQN will generalize. A reduced run could test execution, but not reproduce the published comparison. Its most immediate lesson for our protocol is to measure whether acquiring better selection information costs more than it saves.

## 4. Vlasselaer et al.: Anytime Inference with TP-Compilation

**Primary evidence.** [IJCAI 2015 paper, §§3–5](https://starai.cs.ucla.edu/papers/VlasselaerIJCAI15.pdf), especially §4.2, Table 1 and Figures 4–5; result tables were visually checked.

- **Problem/unit:** update one atom's explanation formula in a probabilistic logic program; weighted model counting provides probability bounds.
- **Method:** the selector combines bound improvement, relative decision-diagram growth and query depth. It computes candidate updates to score them; this is not a learned runtime predictor. Scoring itself performs compilation work.
- **Experiments:** exact inference compares SDD/d-DNNF pipelines on Smokers and Alzheimer networks. Anytime comparisons include WPMS and MC-SAT on Genes/WebKB. Budgets are five minutes for simplified models and fifteen for original models, excluding relevant grounding.
- **Results:** on 500 simplified Genes queries, TP-Compilation gives 419 bounds of width below 0.01 versus WPMS's 308. On original Genes, WPMS gives no informative answer for all 500; TP-Compilation gives 30 almost-exact, 207 tight and 263 loose bounds. These are bound categories, not proof-success rates. Incremental reuse helps the partitioned Smokers case but not the highly connected Alzheimer case.
- **Limits:** guarantees depend on ProbLog's distribution semantics; structural growth is not measured CPU. The paper points to a ProbLog implementation.

**Mapping — our assessment.** This is a close conceptual comparator because it prioritizes symbolic work using both progress and resource-related structure. However, our truth values do not inherit its guaranteed probability bounds, and one accepted proof is not the same objective as tightening a probability interval. Candidate evaluation that performs most of the candidate's work could be particularly expensive in our setting. Counts of matches or outputs may explain cost, but they must not replace timing or be obtained for free by executing future work.

**Reproduction and solo feasibility.** The [ProbLog project](https://github.com/ML-KULeuven/problog) is accessible, but a paper-matched implementation revision, datasets and complete experiment scripts were not verified here. Reproduction needs those dependencies and the original probability semantics. A PLN structural-cost/relevance heuristic would be an explicitly labeled adaptation, not reproduction of the bound guarantees. It is worth assessing as an inexpensive comparator before a complex learner; no specific heuristic has been selected.

## 5. Geisweiller: PLN for Inference Control

**Primary evidence.** [AITP 2025 paper, all three pages](https://aitp-conference.org/2025/abstract/AITP_2025_paper_2.pdf).

- **Problem/unit:** guide theorem proving by estimating whether a conjecture is provable. Candidate proof paths can be compared through their required subgoals.
- **Method:** a relation `Θ(theory, proof, proposition)` represents proof validity. PLN reasons over existential proof queries, including induction/abduction from examples, and compares joint provability of prerequisites. The proposed score concerns viability, not measured execution time or deadline success.
- **Evidence:** §3 gives an A/B path example and links an early prototype. The paper contains no quantitative matched-CPU benchmark, speedup table, or measured training budget. There is consequently no published numerical improvement here for us to reproduce.
- **Limit:** probability that a proof exists is different from probability that a particular search process finds one within its remaining CPU budget.

**Implementation evidence.** The [linked experiment directory](https://github.com/trueagi-io/chaining/tree/main/experimental/pln-inf-ctl) describes random and PLN-based query-viability experiments using Metamath propositional calculus. Its [prototype source](https://github.com/trueagi-io/chaining/blob/main/experimental/pln-inf-ctl/pln-inf-ctl.metta) is available. Repository inspection is evidence of a prototype, not of successful execution in our pinned PeTTa/SWI setup; runtime compatibility and complete experimental reproducibility remain unverified.

**Mapping — our assessment.** This is directly relevant prior Hyperon work and prevents us from claiming that proof usefulness has never been considered. But our synthetic tasks already have authored witnesses: predicting theorem existence is not sufficient to predict remaining search cost. Its chainer/proof representation is also not automatically our Sentence-queue expansion interface. We could investigate a shared viability signal before testing its incremental combination with cost, but using different benefit guidance in only one arm would confound our question.

**Reproduction and solo feasibility.** The bounded first objective would be compatibility and correctness validation of the existing prototype, not reproduction of a reported speedup. Building a performance benchmark and supplying a diverse proof corpus are additional work. Their feasibility cannot be inferred merely from the presence of runnable-looking MeTTa files.

## 6. Sui et al.: Meta-Reasoner — secondary comparison

**Primary evidence.** [arXiv:2502.19918v6](https://arxiv.org/pdf/2502.19918v6), §§3.1–3.3 and Appendices B/C/E/F.

- **Problem/unit:** choose high-level guidance such as continuation, restart or backtracking between LLM reasoning steps.
- **Method:** contextual bandits use progress-report embeddings; rewards combine judged correctness/adherence and a step-count penalty. The default judge is Gemini-2.5-Flash; embeddings use text-embedding-3-small. The penalty is not measured heterogeneous CPU. Training examples include 50 Game-of-24 problems and 30 each from TheoremQA/SciBench.
- **Results:** Table 13 reports GPT-4o-mini Game-of-24 accuracy/time of 89%/43.8 s versus 82%/42.9 s for direct strategy selection; TheoremQA gives 84.13%/18.60 s versus 80.74%/18.17 s. Table 11 reports Game-of-24 accuracy dropping from 89.0±1.2% to 84.2±1.6% when the cost coefficient rises from 0.1 to 0.5.
- **Limits:** judged progress differs from verified proof progress. The comparison's small latency difference does not establish negligible total metareasoning overhead or isolate the value of CPU-cost information. Reward definitions in Appendices B and F require reconciliation before reproduction.

**Implementation evidence.** The paper-linked repository's inspected [inference entry point](https://raw.githubusercontent.com/Y-Sui/Meta-reasoner/main/inference.py) invokes [a meta-reasoner class](https://raw.githubusercontent.com/Y-Sui/Meta-reasoner/main/src/meta_reasoner.py) that summarizes reasoning and requests guidance. That inspected path does not contain the v6 bandit state/update or embedding mechanism. This is a version-correspondence issue, not a claim that the paper's results are invalid or that no matching code exists elsewhere. A paper-matched commit was not established; the inspected links refer to mutable `main`.

**Mapping and solo feasibility — our assessment.** LLM strategy prompts are a different control unit from native sentence expansion. Our independent proof checker does not provide cheap labels for partial usefulness. Adding a judge, embeddings, and adaptive strategies only to the cost-enabled condition would confound the comparison. Sharing or separately ablating them could isolate the factor, but their information quality and overhead would still need validation. Reproduction also requires resolving code/version differences and model/API access. This is a less direct first implementation target for the present symbolic question.

## A relevant extension discovered during this review

[Consul et al., Improving Human Decision-making by Discovering Efficient Strategies for Hierarchical Planning (2022)](https://link.springer.com/article/10.1007/s42113-022-00128-3), “Low-level Policy Search,” Eq. 7, revises BMPS's cost feature to charge the observations assumed by its benefit features. The authors identify bias toward shared nodes when benefits presume multiple computations but cost represents only one. It still uses specified observation prices, not measured PLN CPU. [Author-linked code](https://github.com/RationalityEnhancement/SSD_Hierarchical) was identified but not audited or run.

Only the directly relevant method extension was checked, not the complete experimental study. It is a follow-up lead, not a seventh completed reproduction audit. For our project, the implication is to make the benefit horizon and the cost horizon consistent: crediting a future proof while charging only its first prerequisite can misrank work. It does not select hierarchical control as our architecture.

## What this comparison changes for our study

The following are our conclusions from the paper review and local evidence, not additional author-reported results.

| Decision we need to make | What is now clear | What remains unresolved |
|---|---|---|
| Predict cost or predict usefulness? | They are different targets; a useful computation may be expensive. | The permitted pre-expansion observations and the cheapest adequate cost model. |
| What should be optimized? | Our first endpoint is verified completion by a deadline, with actual CPU and failures retained. | Whether any later objective should trade probability quality against computation instead. |
| What does the data support? | Existing traces support timing and correctness checks. | Diverse training tasks, labels for unchosen alternatives, and structural held-out evaluation. |
| What establishes the value of cost information? | The same selector with the factor disabled/enabled, common candidates, proof rules and stopping behavior. | The exact factor and its treatment of uncertain cost predictions. |
| Which overhead counts? | All online feature extraction, prediction, selection, crossings and observation. | Whether any method can be inexpensive enough at this workload's scale. |
| What could falsify the hoped-for benefit? | No gain over cheap controls, losses after overhead, or delayed necessary reasoning. | Validated task families exposing those conditions. |

Several practical consequences follow:

1. **An accurate CPU estimate alone does not establish improved inference control.** We must test whether using it changes outcomes after acquisition overhead is charged; well-supported neutral or negative findings remain valid research results. Failure of an expensive estimator need not show that cost information is useless.
2. **A full metareasoning policy can obscure the causal question.** Adding relevance, new representations, learned benefit estimates and stopping simultaneously would require additional ablations. We should not attribute their combined effect to cost.
3. **Timing scale is a constraint, not an inconvenience to hide.** Our accepted expansion gaps are tens to hundreds of microseconds and first answers take milliseconds. A selector can consume the potential saving. Any longer tasks must be justified independently, with short cases retained as overhead controls.
4. **Neither more confidence nor more generated atoms is automatically progress.** Completion labels must come from the agreed proof criterion. Probability-accuracy claims require a separate reference model.
5. **Our cooperative deadline is not strict equal resource consumption.** Preserve the current overshoot accounting or explicitly define a common revised execution boundary before comparing methods.

## Implementation readiness and next review point

No paper can yet be designated a direct, validated replacement for our selector. For a bounded Python reproduction, Hay's sampling comparison is a relatively small candidate; BMPS adds a useful learning/feature study. Those are feasibility judgments, not measured runtime promises. TP-Compilation and PLN viability guidance are particularly important when designing strong symbolic comparators. Planner Time and Meta-Reasoner broaden the assessment of delayed benefit and overhead, with larger interface and data requirements.

Before coding a PLN adaptation, freeze one concrete method-to-PLN mapping: the computation unit, input observations available before execution, target being predicted, selection change, cost-disabled control, shared deadline semantics, workload split and accounting boundary. If original-paper reproduction is desired, separately identify its figure/table, version, task, metrics and protocol. A reduced smoke run must not be presented as reproduction of a complete published result.

Known source ambiguities to retain: BMPS's aggregate candidate-reevaluation episode count; a planning test statistic/p-value pairing that should be checked before reuse; Hay's inconsistent Go sample-budget prose/figure labeling; Planner Time supplement Algorithm 2's printed `argmax` within a cost-minimization formulation; and Meta-Reasoner's reward/version differences. These are reproduction questions, not established software defects. We do not silently resolve them in favor of a desired result.

The review supports continuing the research question. It does not establish that adding computation-cost information improves PLN, that learning is necessary, or that every original paper must be reproduced before a controlled PLN experiment. The next decision is the precise comparison to implement, after review of this document.
