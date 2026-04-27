(define (domain mockup)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:predicates (on ?x - object ?y - object) (on_table ?x - object) (clear ?x - object) (arm_empty) (holding ?x - object))
 (:action pickup
  :parameters ( ?x - object)
  :precondition (and (clear ?x) (on_table ?x) (arm_empty))
  :effect (and (not (on_table ?x)) (not (clear ?x)) (not (arm_empty)) (holding ?x)))
  
 (:action stack
  :parameters ( ?x - object ?y - object)
  :precondition (and (holding ?x) (clear ?y))
  :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (arm_empty) (on ?x ?y)))
)
