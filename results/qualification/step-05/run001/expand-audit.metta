; Mechanically extracted from the pinned native PLN.Derive.
(= (Cost.Expand $Tasks $Beliefs $Selected $taskqueuesize $beliefqueuesize)
   (let (Sentence $x $Ev1) $Selected
     (let $derivations (collapse (superpose ((let* (((Sentence $y $Ev2) (superpose $Beliefs)))
                                             (if (let $Allowed (StampDisjoint $Ev1 $Ev2) (progn (println! (COST_GUARD $Allowed)) $Allowed))
                                                 (let $stamp (msort (append $Ev1 $Ev2))
                                                      (superpose ((case (progn (println! (COST_ATTEMPT forward)) (|- $x $y))
                                                                    ((($Txy $TVxy) (progn (println! (COST_GENERATED binary (Sentence ($Txy $TVxy) $stamp))) (Sentence ($Txy $TVxy) $stamp)))))
                                                                  (case (progn (println! (COST_ATTEMPT backward)) (|- $y $x))
                                                                    ((($Tyx $TVyx) (progn (println! (COST_GENERATED binary (Sentence ($Tyx $TVyx) $stamp))) (Sentence ($Tyx $TVyx) $stamp))))))))
                                                 (empty)))
                                       (case (progn (println! (COST_ATTEMPT unary)) (|- $x)) ((($T3 $TV3) (progn (println! (COST_GENERATED unary (Sentence ($T3 $TV3) $Ev1))) (Sentence ($T3 $TV3) $Ev1))))))))
       (let* (($NextTasks (LimitSize (exclude-item (Sentence $x $Ev1) (ConcatUnique $Tasks $derivations)) $taskqueuesize)) ($NextBeliefs (LimitSize (ConcatUnique $Beliefs $derivations) $beliefqueuesize)))
         ($NextTasks $NextBeliefs $derivations)))))
