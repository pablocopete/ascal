(define (domain mockup)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:predicates (on ?x - object ?y - object) (on_table ?x - object) (clear ?x - object) (arm_empty) (holding ?x - object))
 (:action pickup
  :parameters ( ?x - object)
  :precondition (and (clear ?x) (on_table ?x) (arm_empty))
  :effect (and (not (on_table ?x)) (not (clear ?x)) (not (arm_empty)) (holding ?x)))
)
