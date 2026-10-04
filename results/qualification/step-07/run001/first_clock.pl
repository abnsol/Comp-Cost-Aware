% Whole-loop timer. Inputs and callable are prepared before Start.
first_clock(Ns) :- py_call(time:process_time_ns(), Ns).
first_identity(X, X).

first_probes(true) :-
    first_clock(_),
    forall(between(0, 29, I),
      ( Goal = first_identity([], Out),
        first_clock(Start), once(Goal), first_clock(End),
        Out == [], Ns is End - Start,
        format('(FIRST_EMPTY ~d ~d)~n', [I, Ns]) )).

first_measure(Tasks, Beliefs, Step, Max, TQ, BQ, Expected, Out) :-
    Goal = 'PLN.Derive'(Tasks, Beliefs, Step, Max, TQ, BQ, Out),
    first_clock(Start),
    ( once(Goal) -> true ; throw(error(first_native_failure, first_measure/8)) ),
    first_clock(End),
    ( ground(Out), Out == Expected -> true
    ; throw(error(first_queue_mismatch, first_measure/8)) ),
    % A separate post-timing determinism check; never warm inference beforehand.
    findall(Check, 'PLN.Derive'(Tasks, Beliefs, Step, Max, TQ, BQ, Check), All),
    ( All == [Expected] -> true
    ; throw(error(first_solution_mismatch, first_measure/8)) ),
    Ns is End - Start,
    format('(FIRST_CPU ~d)~n', [Ns]).

:- maplist(register_fun, [first_probes, first_measure]).
