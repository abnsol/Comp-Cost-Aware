% Native confidence/queue handling; shared Python description via embedded Janus.
% [calls, classified, descriptorCPU, predictions, featureCPU, selectorCPU,
%  coverageFallbacks, predictionFallbacks, singletons]. Windows overlap.
benefit_config(Mode, Query, Scope, true) :-
    memberchk(Mode, ['N','B','BO','BC']),
    nb_setval(benefit_config, config(Mode, Query, Scope)).
benefit_reset :- nb_setval(benefit_stats, [0,0,0,0,0,0,0,0,0]).
benefit_reset_test(true) :- benefit_reset.
benefit_stats(Stats) :- nb_getval(benefit_stats, Stats).

benefit_ranks(Tasks, Beliefs, Query, Scope, Result) :-
    py_call('pln_cost.benefit_selection':native_ranks(Tasks, Beliefs, Query, Scope), Result).

benefit_ranked([], [], _, []).
benefit_ranked([R|Rs], [K|Ks], Max, Out) :-
    R = ['Sentence',[_,[stv,_,C]],_],
    benefit_ranked(Rs, Ks, Max, Rest),
    (C =:= Max -> Out = [[R,K]|Rest] ; Out = Rest).

benefit_finalists(Tasks, Categories, Max, Finalists) :-
    benefit_ranked(Tasks, Categories, Max, Ranked),
    findall(K, member([_,K], Ranked), Ks), max_list(Ks, Best),
    findall(R, member([R,Best], Ranked), Finalists).

benefit_cost(Mode, Finalists, Tasks, Beliefs, Selected, NP, FC, PF, S) :-
    Finalists = [First|_],
    ( Finalists = [_] -> Selected = First, NP = 0, FC = 0, PF = 0, S = 1
    ; Mode == 'B' -> Selected = First, NP = 0, FC = 0, PF = 0, S = 0
    ; nb_getval(cost_model, model(_, Means, Scales, Weights, Intercept)),
      budget_clock(F0), length(Beliefs, NB), length(Tasks, NT),
      findall([R,X], (member(R, Finalists), cost_row(Beliefs, NB, NT, R, X)), Rows),
      budget_clock(F1), FC is F1-F0,
      cost_predictions(Rows, Means, Scales, Weights, Intercept, Predictions),
      length(Predictions, NP), S = 0,
      ( member([_,invalid], Predictions) -> Selected = First, PF = 1
      ; Mode == 'BO' -> Selected = First, PF = 0
      ; cost_best(Predictions, Selected), PF = 0 ) ).

benefit_select(Tasks, Beliefs, Selected) :-
    budget_clock(Start),
    nb_getval(benefit_config, config(Mode, Query, Scope)),
    ( Mode == 'N' ->
      'BestCandidate'('PriorityRank', [], Tasks, Selected),
      NC=0, DC=0, NP=0, FC=0, CF=0, PF=0, S=0
    ; cost_eligible(Tasks, Native, Eligible),
      ( Eligible = [_] -> Selected=Native, NC=0, DC=0, NP=0, FC=0, CF=0, PF=0, S=1
      ; budget_clock(D0), benefit_ranks(Tasks, Beliefs, Query, Scope, Description),
        budget_clock(D1), DC is D1-D0,
        ( Description = [covered, Categories] ->
          length(Tasks, NC), length(Categories, NC),
          Native = ['Sentence',[_,[stv,_,Max]],_],
          benefit_finalists(Tasks, Categories, Max, Finalists), CF=0,
          benefit_cost(Mode, Finalists, Tasks, Beliefs, Selected, NP, FC, PF, S)
        ; Description = [unknown, []] ->
          Selected=Native, NC=0, NP=0, FC=0, CF=1, PF=0, S=0
        ; throw(error(invalid_benefit_description, benefit_select/3)) ) ) ),
    budget_clock(End), Total is End-Start,
    nb_getval(benefit_stats, Old),
    maplist(plus, Old, [1,NC,DC,NP,FC,Total,CF,PF,S], New),
    nb_setval(benefit_stats, New).

:- maplist(register_fun, [benefit_config, benefit_stats, benefit_select,
                         benefit_ranks, benefit_reset_test]).
