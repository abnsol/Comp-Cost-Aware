; Qualification KB. Preload the full pinned lib_pln.metta.
; Generated input only; no native run or cost measurement is implied.
(= (kb)
 ((Sentence ((Ready unit0 route_b) (stv 1.0 0.9)) (2))
  (Sentence ((Ready unit0 route_a) (stv 1.0 0.9)) (1))
  (Sentence ((Implication (Ready unit0 route_a) (Certificate unit0 path_a)) (stv 1.0 0.9)) (3))
  (Sentence ((Implication (Certificate unit0 path_a) (CanOperate unit0)) (stv 1.0 0.9)) (4))
  (Sentence ((Implication (Ready unit0 route_b) (Certificate unit0 path_b_001)) (stv 1.0 0.9)) (5))
  (Sentence ((Implication (Certificate unit0 path_b_001) (CanOperate unit0)) (stv 1.0 0.9)) (6))
  (Sentence ((Implication (Ready unit0 route_b) (Certificate unit0 path_b_002)) (stv 1.0 0.9)) (7))
  (Sentence ((Implication (Certificate unit0 path_b_002) (CanOperate unit0)) (stv 1.0 0.9)) (8))
  (Sentence ((Implication (Ready unit0 route_b) (Certificate unit0 path_b_003)) (stv 1.0 0.9)) (9))
  (Sentence ((Implication (Certificate unit0 path_b_003) (CanOperate unit0)) (stv 1.0 0.9)) (10))
  (Sentence ((Implication (Ready unit0 route_b) (Certificate unit0 path_b_004)) (stv 1.0 0.9)) (11))
  (Sentence ((Implication (Certificate unit0 path_b_004) (CanOperate unit0)) (stv 1.0 0.9)) (12))))

!(println! (QUALIFICATION_RESULT (PLN.Query (kb) (CanOperate unit0) 100 4097 4097)))
