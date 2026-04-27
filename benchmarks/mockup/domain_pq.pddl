(define (domain debug_pq)
  (:requirements :strips :negative-preconditions)
  (:predicates (p) (q))

  (:action set_p
    :parameters ()
    :precondition (not (p))
    :effect (p))

  (:action clear_p
    :parameters ()
    :precondition (p)
    :effect (not (p)))

  (:action set_q
    :parameters ()
    :precondition (not (q))
    :effect (q))

  (:action clear_q
    :parameters ()
    :precondition (q)
    :effect (not (q)))
)
