# SENTINEL Research Discovery Report

**19 Nov 2026 · @Moksh**

---

## 1. Final topic and verdict

**Verdict: MODIFY, then run a small kill-test before committing.** I cannot certify
that any topic is "never used"; I can name the narrowest gap that I did not find
filled in the sources I read, and tell you how to falsify it cheaply.

**Recommended topic:** Telemetry-sufficiency auditing of provenance-based attack
reconstruction: for each reconstructed attacker link, is it still justified when a
given log source is withheld, and which source would settle it?

Three claims, each testable:

- **H1.** Reconstruction links that look correct on full telemetry are often
  unsupported once one source is withheld, and the loss depends on which source,
  not on how many.
- **H2.** Two source sets with equal ATT&CK technique coverage can differ sharply
  in how many links stay justified ("coverage is not sufficiency").
- **H3.** A cheap sufficiency flag predicts which links break under ablation better
  than the reconstructor's own confidence score.

**Biggest new finding this session:** ATLASv2 only has event-level labels for
Windows Security Auditing logs. Other sources (Sysmon, Firefox, DNS, Carbon Black)
are unlabeled at event level; attacker-process labels come from a separate REAPr set
I could not open. So ground truth must be process-level, and any claim about "link
correctness" inherits that coarseness.

**Why only MODIFY and not proceed outright:** SynthChain (source ablations, link
status) and HunterAgent (abstention under budget) overlap closely. If the kill-test
shows H3 does no better than baseline confidence, abandon this topic.

**What I did not verify:** CrossHound's method (abstract only), REAPr labels,
ATLASv2 license, current journal quartiles.

---

## 2. Tools used and limits

- **Used:** web search and page fetches (HunterAgent, SynthChain, DiagChain, the
  STRICT audit, OpTC README, ATLASv2 paper), plus a sandbox network test.
- **Partially read:** HunterAgent (about 300k of 367k characters), SynthChain
  (about 100k of 150k), DiagChain (100k of 414k), STRICT (100k of 141k).
  CrossHound, PIDSMaker and SecTracer: abstracts or summaries only.
- **Not possible here:** the sandbox reaches only PyPI. Bitbucket, arXiv, Zenodo
  and Hugging Face are blocked, so no dataset was downloaded and no experiment has
  been run. Nothing in this report is an experimental result.
- **Needed from you:** download ATLASv2 (and optionally OpTC) on your own machine,
  and either run the code I write there or upload a small sample.

---

## 3. Closest prior work and novelty matrix

No single paper I read does link-level sufficiency labels plus telemetry-source
recommendation plus a predictive flag, but four come close. Overlap judged from
what I read, not from full texts.

| Work | What it does | Overlap with topic | Read |
| --- | --- | --- | --- |
| HunterAgent (arXiv:2605.29269) | Agentic investigation that abstains under a cost budget | Abstention, partial evidence | Most of text |
| SynthChain | Link status and log-source ablations, planning guidelines | Highest: ablation plus link status | About two thirds |
| DiagChain (arXiv:2608.03591) | Diagnostic metrics for reconstruction chains | Metrics only | 100k of 414k chars |
| STRICT audit (arXiv:2609.33532) | Shows inflated evaluation in provenance detection | Evaluation hygiene to adopt | 100k of 141k chars |
| CrossHound (TIFS 2026) | Multi-source correlation | Multi-source use, not sufficiency | Abstract only |
| PIDSMaker (KDD'26), SecTracer | Framework / network provenance with probabilistic RCA | Infrastructure, not sufficiency | Summaries |
| CTID Telemetry Confidence, DeTT&CT | Rank telemetry by ATT&CK coverage | The baseline H2 attacks | Prior knowledge |
| Reiter 1987; de Kleer and Williams 1987 | Consistency-based diagnosis, next-measurement selection | Theory foundation; makes the idea "applied", not new | Prior knowledge |

**Honest novelty claim:** applying consistency-based sufficiency to provenance
links, measured against coverage baselines on a public benchmark. That is an
empirical and framing contribution, not a new theorem. A hostile reviewer will call
it incremental over SynthChain unless H3 holds. Before drafting, search once more
for 2026 work on "missing log", "evidence sufficiency" and "counterfactual
telemetry" provenance.

---

## 4. Five candidates, ranked

Scored on novelty risk, feasibility for one undergraduate with no cluster, and how
testable the claim is.

| Rank | Candidate | Strongest argument against |
| --- | --- | --- |
| 1 | Telemetry-sufficiency audit of reconstructed links (recommended) | SynthChain already ablates sources; only H3 separates you |
| 2 | Validity audit of investigation-oriented evaluation (alerting vs investigation utility) | STRICT already audits detection; needs OpTC-scale data you may not have |
| 3 | Process-level label noise in ATLASv2/OpTC and its effect on reported PIDS scores | Mostly an analysis note; a weaker journal fit |
| 4 | Coverage versus pairwise distinguishability of ATT&CK hypotheses (original SENTINEL) | Needs a paired incident benchmark that does not exist |
| 5 | Adversary-aware sequential telemetry acquisition under deadlines | Heavy theory; crowded with sensor-selection literature |

**Why #1 wins:** it is the only one that is cheap to falsify on one public dataset,
produces a clear negative result if wrong, and reuses open reconstructors so you do
not build a detector from scratch. #2 is the fallback if the kill-test fails, since
it reuses the same data and tooling.

---

## 5. Data, design, kill criteria and next steps

**Data.** ATLASv2 on Bitbucket, about 154 GB, ten scenarios, two Windows 7 VMs.
Event-level labels exist only for Windows Security Auditing logs (paper). All attacks
share steps, so generalization claims must stay narrow. License is not stated in the
paper: check the repo before any redistribution. OpTC (about 1 TB, imperfect ground
truth) is a stretch goal. LANL lacks process provenance and is unsuitable.

**Design.**

1. Define claims as attacker-process-to-process links, truth from Security Auditing
   labels plus REAPr process labels.
2. Run one open reconstructor (for example one PIDSMaker model) on every non-empty
   subset of the five main sources: 31 configurations.
3. For each link, record whether it survives each subset; compute a sufficiency flag
   by consistency-based rules.
4. Compare the flag to reconstructor confidence (H3) and to ATT&CK coverage ranking
   (H2). Use leave-one-scenario-out splits and report intervals over scenarios, not
   over events.

**Pre-registered kill criteria (abandon if any holds):**

- **F1.** Fewer than 20% of links change status across subsets.
- **F2.** Coverage ranking predicts survival as well as the sufficiency flag.
- **F3.** The flag does not beat reconstructor confidence on held-out scenarios.
- **F4.** Process-level labels are too noisy to score links reliably.

**Likely reviewer objections.** Incremental over SynthChain; only 10 correlated
scenarios; coarse labels; Windows 7 is dated; sufficiency is not correctness. Answer
with the kill-test, narrow claims and open code.

**Roadmap.**

1. **You:** download ATLASv2 Security Auditing and Sysmon logs for two scenarios,
   plus REAPr labels, and check the license.
2. **Me:** write the pipeline, tests and research log; you run it and send results.
3. Decide go or abandon from F1 to F4. Only then draft the paper.
4. Verify journal quartiles on Scimago for the year of submission before naming any
   journal. No Q1 outcome can be promised, and nothing is submitted without your
   explicit approval.
