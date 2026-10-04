% CPU-budget/first-goal adapter; all inference and selection remain native.
budget_clock(Ns) :- py_call(time:process_time_ns(), Ns).

budget_goal(Beliefs, Query, Strength, Minimum, Tolerance, Answer) :-
    member(Record, Beliefs),
    Record = ['Sentence', [Term, [stv, F, C]], _], Term == Query,
    number(F), number(C), abs(F-Strength) =< Tolerance,
    C >= Minimum-Tolerance, C =< 1,
    !, Answer = Record.
budget_goal(_, _, _, _, _, []).

% State holds immutable input policy and mutable counters, no oracle checkpoint.
budget_continue(Step, Tasks, Beliefs, Continue) :-
    budget_clock(T0),
    nb_getval(pln_budget, State),
    State = state(Start, Budget, Query, Strength, Minimum, Tolerance,
                  Max, _, _, Observer, _, _),
    Done is Step-1,
    Elapsed0 is T0-Start,
    ( Elapsed0 >= Budget -> Answer = [], Decision = deadline
    ; budget_goal(Beliefs, Query, Strength, Minimum, Tolerance, Answer),
      ( Answer \== [] -> Decision = found
      ; (Step > Max ; Tasks == []) -> Decision = exhausted
      ; Decision = continue ) ),
    budget_clock(T1),
    Elapsed1 is T1-Start,
    ( Elapsed1 >= Budget -> FinalDecision = deadline
    ; FinalDecision = Decision ),
    ObserverNext is Observer + T1-T0,
    nb_setval(pln_budget, state(Start, Budget, Query, Strength, Minimum, Tolerance,
                              Max, Done, FinalDecision, ObserverNext, Answer, Elapsed1)),
    ( FinalDecision == continue -> Continue = true ; Continue = false ).

budget_run(KB, Query, Budget, Max, TQ, BQ, Strength, Minimum, Tolerance, Result) :-
    Goal = 'PLN.Derive'(KB, KB, 1, Max, TQ, BQ, Queues),
    budget_clock(_), % initialize the bridge outside this loaded-engine interval
    budget_clock(Start),
    cost_reset,
    nb_setval(pln_budget, state(Start, Budget, Query, Strength, Minimum, Tolerance,
                              Max, 0, continue, 0, [], 0)),
    ( once(Goal) -> true ; throw(error(budget_native_failure, budget_run/10)) ),
    nb_getval(pln_budget, state(_, _, _, _, _, _, _, Done, Reason, Observer, Answer, Detection)),
    % Include guard bookkeeping and complete recursion unwind in deadline score.
    budget_clock(End),
    CPU is End-Start,
    ( Reason == found, CPU =< Budget -> Status = success
    ; Reason == found -> Status = late_return
    ; Status = Reason ),
    Result = [Status, Done, CPU, Observer, Detection, Answer, Queues].

:- maplist(register_fun, [budget_continue, budget_run]).

% Ground PLN selection adapter. Rules and queue operations stay in MeTTa.
% Sorted evidence stamps are guaranteed by fixture validation/native inference.
:- use_module(library(ordsets)).

cost_config(Mode, Means, Scales, Weights, Intercept, true) :-
    memberchk(Mode, ['N','O','C']),
    length(Means, 10), length(Scales, 10), length(Weights, 10),
    nb_setval(cost_model, model(Mode, Means, Scales, Weights, Intercept)).

cost_reset :- nb_setval(cost_stats, [0,0,0,0,0,0]).
cost_stats(Stats) :- nb_getval(cost_stats, Stats).

cost_nodes(Term, N) :-
    ( is_list(Term) -> maplist(cost_nodes, Term, Ns), sum_list(Ns, Sum), N is Sum+1
    ; N = 1 ).

cost_counts([], _, _, _, 0, 0, 0).
cost_counts([['Sentence',[Other,_],Stamp]|Rest], Term, Ev, Imp, D, S, M) :-
    cost_counts(Rest, Term, Ev, Imp, D0, S0, M0),
    ( ord_disjoint(Ev, Stamp) ->
      D is D0+1,
      (Other == Term -> S is S0+1 ; S = S0),
      (Other = ['Implication',Ante,_], Ante == Term -> F = 1 ; F = 0),
      (Imp == 1, Term = ['Implication',Ante2,_], Ante2 == Other -> B = 1 ; B = 0),
      M is M0+F+B
    ; D = D0, S = S0, M = M0 ).

cost_row(Beliefs, NB, NT, ['Sentence',[Term,_],Ev], [NB,NT,Nodes,NE,Imp,D,S,M,MB,MT]) :-
    cost_nodes(Term, Nodes), length(Ev, NE),
    (Term = ['Implication',_,_] -> Imp = 1 ; Imp = 0),
    cost_counts(Beliefs, Term, Ev, Imp, D, S, M), MB is M*NB, MT is M*NT.

cost_eligible(Tasks, Native, Eligible) :-
    'BestCandidate'('PriorityRank', [], Tasks, Native),
    Native = ['Sentence',[_,[stv,_,Max]],_],
    findall(R, (member(R, Tasks), R = ['Sentence',[_,[stv,_,C]],_], C =:= Max), Eligible).

cost_features(Tasks, Beliefs, Rows) :-
    cost_eligible(Tasks, _, Eligible),
    length(Beliefs, NB), length(Tasks, NT),
    findall([R,X], (member(R, Eligible), cost_row(Beliefs, NB, NT, R, X)), Rows).

cost_linear([], [], [], [], Score, Score).
cost_linear([X|Xs], [M|Ms], [S|Ss], [W|Ws], Acc, Score) :-
    Next is Acc + W*((X-M)/S), cost_linear(Xs, Ms, Ss, Ws, Next, Score).

cost_predict(Means, Scales, Weights, Intercept, X, Prediction) :-
    ( catch((cost_linear(X, Means, Scales, Weights, Intercept, Log),
             P is exp(Log), P > 0, float_class(P, Class), memberchk(Class, [normal,subnormal])), _, fail)
      -> Prediction = P ; Prediction = invalid ).

cost_predictions(Rows, Means, Scales, Weights, Intercept, Predictions) :-
    findall([R,P], (member([R,X], Rows), cost_predict(Means, Scales, Weights, Intercept, X, P)), Predictions).

cost_best([[R,P]|Rest], Best) :- cost_best_(Rest, R, P, Best).
cost_best_([], R, _, R).
cost_best_([[R,P]|Rest], Current, Score, Best) :-
    (P < Score -> cost_best_(Rest, R, P, Best) ; cost_best_(Rest, Current, Score, Best)).

cost_select(Tasks, Beliefs, Selected) :-
    budget_clock(Start),
    nb_getval(cost_model, model(Mode, Means, Scales, Weights, Intercept)),
    ( Mode == 'N' ->
        'BestCandidate'('PriorityRank', [], Tasks, Selected),
        Predicted = 0, FeatureCPU = 0, Fallback = 0, Singleton = 0
    ; cost_eligible(Tasks, Native, Eligible),
      ( Eligible = [_] -> Selected = Native, Predicted = 0, FeatureCPU = 0, Fallback = 0, Singleton = 1
      ; budget_clock(F0), length(Beliefs, NB), length(Tasks, NT),
        findall([R,X], (member(R, Eligible), cost_row(Beliefs, NB, NT, R, X)), Rows),
        budget_clock(F1), FeatureCPU is F1-F0,
        cost_predictions(Rows, Means, Scales, Weights, Intercept, Predictions),
        length(Predictions, Predicted),
        (member([_,invalid], Predictions) -> Selected = Native, Fallback = 1
        ; Mode == 'O' -> Selected = Native, Fallback = 0
        ; cost_best(Predictions, Selected), Fallback = 0), Singleton = 0 ) ),
    budget_clock(End),
    nb_getval(cost_stats, [N,P,F,T,B,S]),
    N1 is N+1, P1 is P+Predicted, F2 is F+FeatureCPU, T1 is T+End-Start,
    B1 is B+Fallback, S1 is S+Singleton,
    nb_setval(cost_stats, [N1,P1,F2,T1,B1,S1]).

% Validation probe; not the query endpoint. Preparation/printing are excluded,
% native candidate identification and all feature acquisition are included.
cost_feature_probe(Tasks, Beliefs, [CPU,Rows]) :-
    budget_clock(Start), cost_features(Tasks, Beliefs, Rows), budget_clock(End), CPU is End-Start.

:- maplist(register_fun, [cost_config, cost_stats, cost_select, cost_features, cost_feature_probe]).

cost_reset_test(true) :- cost_reset.
:- register_fun(cost_reset_test).
