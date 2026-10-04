; Qualification KB. Preload the full pinned lib_pln.metta.
; Generated input only; no native run or cost measurement is implied.
(= (kb)
 ((Sentence ((Ready unit0 route_a) (stv 1.0 0.9)) (1))
  (Sentence ((Implication (Certificate unit0 path_b_001) (CanOperate unit0)) (stv 1.0 0.9)) (6))
  (Sentence ((Ready unit0 route_b) (stv 1.0 0.9)) (2))
  (Sentence ((Implication (Ready unit0 route_a) (Certificate unit0 path_a)) (stv 1.0 0.9)) (3))
  (Sentence ((Implication (Certificate unit0 path_a) (CanOperate unit0)) (stv 1.0 0.9)) (4))
  (Sentence ((Implication (Ready unit0 route_b) (Certificate unit0 path_b_001)) (stv 1.0 0.9)) (5))))

!(println! (QUALIFICATION_RESULT (PLN.Query (kb) (CanOperate unit0) 100 4097 4097)))
