% A measurement adapter only. Cost.Expand is compiled by the pinned PeTTa from
% the same validated MeTTa helper. No inference rule or queue operation is here.
thin_clock(Ns) :- py_call(time:process_time_ns(), Ns).

% Check the complete solution set separately, before any timed samples. During
% timing once/1 bounds residual choicepoints; this guard prohibits dropping a
% second solution on these exact ground inputs.
thin_verify(Tasks, Beliefs, Selected, TQ, BQ, Expected, true) :-
    findall(Out, 'Cost.Expand'(Tasks, Beliefs, Selected, TQ, BQ, Out), Results),
    ( Results == [Expected] -> true
    ; throw(error(thin_native_output_mismatch, thin_verify/7)) ).

thin_identity(Expected, Expected).

% Build the callable term BEFORE the clock. Reuse immutable original inputs.
thin_goal('Real', Tasks, Beliefs, Selected, TQ, BQ, _, Out,
          'Cost.Expand'(Tasks, Beliefs, Selected, TQ, BQ, Out)).
thin_goal('Empty', _, _, _, _, _, Expected, Out, thin_identity(Expected, Out)).

thin_sample(Phase, Pair, Route, Mode, Tasks, Beliefs, Selected, TQ, BQ, Expected, Preparation, true) :-
    thin_goal(Mode, Tasks, Beliefs, Selected, TQ, BQ, Expected, Out, Goal),
    thin_clock(Start),
    ( once(Goal) -> true ; throw(error(thin_operation_failed, thin_sample/12)) ),
    thin_clock(End),
    % No accumulation of outputs. Verify this output after its end clock, before
    % moving to the next original-state trial. Never pass Out to the next call.
    ( ground(Out), Out == Expected -> true
    ; throw(error(thin_native_output_mismatch, thin_sample/12)) ),
    Duration is End - Start,
    format('(PAIRED_SAMPLE ~w ~d ~w 1 ~d ~d true)~n', [Phase, Pair, Route, Preparation, Duration]).

thin_probe(Index, true) :-
    thin_clock(Start), thin_clock(End), Duration is End - Start,
    format('(THIN_CLOCK_PROBE ~d ~d)~n', [Index, Duration]).

:- maplist(register_fun, [thin_verify, thin_sample, thin_probe]).
