; a small artificial knowledge base, then asking: “Among machines under high load, what proportion fail?”

; Authored semantic fixture, not a measured performance workload.
; The Python runner loads the pinned lib_pln.metta before this file.
; Strengths are population conditionals; confidence 0.9 is a controlled setting.
; Distinct stamps identify assertions, not proven statistical independence.

; frequency of each condition
; among all machine how often do this conditions be seen
(= (STV HighLoad) (stv 0.5 0.9))
(= (STV Hot) (stv 0.5 0.9))
(= (STV Vibrating) (stv 0.5 0.9))
(= (STV Fails) (stv 0.5 0.9))

;evaluate kb get 4 expressions
;the statement, its truth value, and its evidence stamp.
; evidence stamp PLN can track its use in later derivations.
; among first this percent next 
(= (kb)
   ((Sentence ((Inheritance HighLoad Hot) (stv 0.8 0.9)) (1))
    (Sentence ((Inheritance Hot Fails) (stv 0.9 0.9)) (2))
    (Sentence ((Inheritance HighLoad Vibrating) (stv 0.8 0.9)) (3))
    (Sentence ((Inheritance Vibrating Fails) (stv 0.644 0.9)) (4))))

; Native confidence selection, all native rules, declared fixed step/queue caps.
; These are correctness-run settings, NOT a calibrated CPU budget.

; the high-load–failure answer directly. PLN must derive candidates from the available statements.
!(println! (STEP1_RESULT (PLN.Query (kb) (Inheritance HighLoad Fails) 100 30 100)))
