; Authored semantic fixture, not a measured performance workload.
; The Python runner loads the pinned lib_pln.metta before this file.
; Strengths are population conditionals; confidence 0.9 is a controlled setting.
; Distinct stamps identify assertions, not proven statistical independence.
(= (STV HighLoad) (stv 0.5 0.9))
(= (STV Hot) (stv 0.5 0.9))
(= (STV Vibrating) (stv 0.5 0.9))
(= (STV Fails) (stv 0.5 0.9))

(= (kb)
   ((Sentence ((Inheritance HighLoad Hot) (stv 0.8 0.9)) (1))
    (Sentence ((Inheritance Hot Fails) (stv 0.9 0.9)) (2))
    (Sentence ((Inheritance HighLoad Vibrating) (stv 0.8 0.9)) (3))
    (Sentence ((Inheritance Vibrating Fails) (stv 0.644 0.9)) (4))))

; Native confidence selection, all native rules, declared fixed step/queue caps.
; These are correctness-run settings, NOT a calibrated CPU budget.
!(println! (STEP1_RESULT (PLN.Query (kb) (Inheritance HighLoad Fails) 100 30 100)))
