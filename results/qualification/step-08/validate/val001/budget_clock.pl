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
