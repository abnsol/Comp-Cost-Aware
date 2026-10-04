; Mechanically extracted from the pinned native PLN.Derive.
(= (Cost.Expand $Tasks $Beliefs $Selected $taskqueuesize $beliefqueuesize)
   (let (Sentence $x $Ev1) $Selected
     (let $derivations (collapse (superpose ((let* (((Sentence $y $Ev2) (superpose $Beliefs)))
                                             (if (StampDisjoint $Ev1 $Ev2)
                                                 (let $stamp (msort (append $Ev1 $Ev2))
                                                      (superpose ((case (|- $x $y)
                                                                    ((($Txy $TVxy) (Sentence ($Txy $TVxy) $stamp))))
                                                                  (case (|- $y $x)
                                                                    ((($Tyx $TVyx) (Sentence ($Tyx $TVyx) $stamp)))))))
                                                 (empty)))
                                       (case (|- $x) ((($T3 $TV3) (Sentence ($T3 $TV3) $Ev1)))))))
       (let* (($NextTasks (LimitSize (exclude-item (Sentence $x $Ev1) (ConcatUnique $Tasks $derivations)) $taskqueuesize)) ($NextBeliefs (LimitSize (ConcatUnique $Beliefs $derivations) $beliefqueuesize)))
         ($NextTasks $NextBeliefs $derivations)))))
