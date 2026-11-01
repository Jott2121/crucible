# Related Work — VERIFIED bibliography (web-grounded 2026-07-12; use ONLY these for citations)

> Every title / arXiv id / venue / year below was confirmed against a real source URL by the
> literature-verification agent. Author lists as reported by arXiv/ACM/venue pages. Do NOT cite
> anything not on this list without a fresh lookup. One item (Pynguin exact record) is flagged
> COULD NOT VERIFY and needs one more lookup before it is cited directly.
> Already-verified in the frozen docs/RELATED-WORK.md (do not re-verify): MuTAP, AdverTest,
> Meta ACH, Refute-or-Promote, TestForge, Self-MoA.

## Confirmed (safe to cite)

1a. TestGen-LLM tool paper: "Automated Unit Test Improvement using Large Language Models at Meta"
    Alshahwan, Chheda, Finogenova, Gokkaya, Harman, Harper, Marginean, Sengupta, Wang.
    FSE 2024 (Industry). arXiv:2402.09171 ; DOI 10.1145/3663529.3663839.
    (Also cited in Jeff's frozen AI-Testing-Standard evidence file -- Meta discards AI tests that
    don't add coverage.)
1b. "Assured LLM-Based Software Engineering" (SEPARATE position paper) -- Alshahwan, Harman,
    Harper, Marginean, Sengupta, Wang. InteNSE 2024 workshop (co-located ICSE 2024). arXiv:2402.04380.
1c. "Mutation-Guided LLM-based Test Generation at Meta" -- Foster, Gulati, Harman, Harper, Mao,
    Ritchey, Robert, Sengupta. FSE 2025. arXiv:2501.12862.
    ** CORRECTED 2026-07-12: this Foster paper (2501.12862) IS Meta ACH -- the frozen ledger
    (docs/RELATED-WORK.md line 75) already cites 2501.12862 as "Meta ACH ('Mutation-Guided
    LLM-based Test Generation at Meta,' Foster, Harman, Ritchey et al.)". It is NOT a separate/new
    paper. Cite ONCE as Meta ACH. The original note here (claiming it was distinct from Meta ACH)
    was WRONG and is retracted. The genuinely-separate earlier Meta paper is TestGen-LLM (1a,
    Alshahwan, 2402.09171). **

2.  "LLM Evaluators Recognize and Favor Their Own Generations" -- Panickssery, Bowman, Feng.
    NeurIPS 2024 (Oral). arXiv:2404.13076.
    ** The canonical self-preference-bias cite; anchors the Discussion 5.3 "mechanical oracle
    closes the self-preference channel" bridge. **

3.  "CoverUp: Coverage-Guided LLM-Based Test Generation" (journal: "CoverUp: Effective High
    Coverage Test Generation for Python") -- Pizzorno, Berger. arXiv:2403.16218 ;
    PACMSE / FSE 2025 track, DOI 10.1145/3729398. (Python; coverage-guided.)

4a. "CodaMosa: Escaping Coverage Plateaus in Test Generation with Pre-trained Large Language
    Models" -- Lemieux, Inala, Lahiri, Sen. ICSE 2023.
4b. Pynguin -- Lukasczyk, Fraser (Python search-based test gen tool, commonly cited 2022).
    ** COULD NOT VERIFY exact standalone title/venue/id -- confirmed only via CoverUp/CodaMosa
    references. If cited directly, one more lookup before finalizing. **

5a. TestPilot: "An Empirical Evaluation of Using Large Language Models for Automated Unit Test
    Generation" -- Schäfer, Nadi, Eghbali, Tip. IEEE TSE vol.50 no.1, Jan 2024.
    arXiv:2302.06527 ; DOI 10.1109/TSE.2023.3334955.
5b. HITS: "HITS: High-coverage LLM-based Unit Test Generation via Method Slicing" -- Wang, Liu, Li,
    Jin. ASE 2024. arXiv:2408.11324. (AdverTest's baseline; cite directly rather than second-hand.)
5c. ChatTester: "No More Manual Tests? Evaluating and Improving ChatGPT for Unit Test Generation"
    arXiv:2305.04207.
5d. ChatUniTest (NOTE spelling): "ChatUniTest: A Framework for LLM-Based Test Generation" --
    Chen et al. arXiv:2305.04764. (Distinct from ChatTester.)

6.  "LLMorpheus: Mutation Testing using Large Language Models" -- Tip, Bell, Schäfer.
    arXiv:2404.09952. (LLM-generated mutants; contrast to crucible's rule-based mutmut mutants.)

7.  "Improving Factuality and Reasoning in Language Models through Multiagent Debate" -- Du, Li,
    Torralba, Tenenbaum, Mordatch. arXiv:2305.14325 ; ICML 2024. (Heterogeneous-ensemble context
    for the cross-lineage question, alongside Self-MoA's counter-current.)

## Newly surfaced (not in Fable's list; strong candidates)

A.  "A Comprehensive Study on Large Language Models for Mutation Testing" -- Wang, Chen, Deng, Lin,
    Harman, Papadakis, Zhang. arXiv:2406.09843 ; TOSEM, DOI 10.1145/3805038. (Empirical LLM-mutant
    study on 851 real Java bugs; directly relevant to mutation-to-assess-LLM-tests.)
B.  "Great Models Think Alike and this Undermines AI Oversight" -- arXiv:2502.04313.
    ** HIGH VALUE: LLMs increasingly share errors, which undermines cross-model evaluation/oversight
    -- direct external support for Discussion 5.3's "cross-model comparisons can inherit harness
    asymmetry / mechanical oracles don't immunize cross-model comparison" claim. Strongly consider. **
C.  Dakhel et al. 2024, "Effective test generation using pre-trained Large Language Models and
    mutation testing" -- Information and Software Technology (Elsevier). (The MuTAP line's journal
    work; mutation-guided improvement of LLM Python tests. Cross-check against the MuTAP entry
    already in RELATED-WORK.md so we don't double-cite the same lineage confusingly.)

## CORRECTIONS the verification caught (proof the anti-fabrication pass earned its keep)
- "Foster, Harman et al." was WRONG for TestGen-LLM and Assured LLMSE (first author = Alshahwan on
  both). Foster is first author of a THIRD, distinct paper (1c above). Fable's memory conflated three.
- Spelling confirmed "Panickssery" (not Perez); co-authors Bowman + Feng only.
- "ChatUniTest" not "ChatUnitTest"; and it is distinct from ChatTester.
- Du et al.: arXiv 2023 but peer-reviewed venue is ICML 2024.
