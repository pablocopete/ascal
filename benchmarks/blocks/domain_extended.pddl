(define (domain bw_rand_8_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem_problem-domain)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:predicates (on ?x - object ?y - object) (on_table ?x - object) (clear ?x - object) (arm_empty) (holding ?x - object))
 (:action pickup
  :parameters ( ?x - object ?y - object ?z - object)
  :precondition (and (clear ?x) (on_table ?x) (arm_empty) (not (= ?x ?y)) (not (= ?x ?z)) (not (= ?y ?z)))
  :effect (and (not (on_table ?x)) (not (clear ?x)) (not (arm_empty)) (holding ?x)))
 (:action putdown
  :parameters ( ?x - object ?y - object ?z - object)
  :precondition (and (holding ?x) (not (= ?x ?y)) (not (= ?x ?z)) (not (= ?y ?z)))
  :effect (and (not (holding ?x)) (clear ?x) (arm_empty) (on_table ?x)))
 (:action stack
  :parameters ( ?x - object ?y - object ?z - object)
  :precondition (and (holding ?x) (clear ?y) (not (= ?x ?y)) (not (= ?x ?z)) (not (= ?y ?z)))
  :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (arm_empty) (on ?x ?y)))
 (:action unstack
  :parameters ( ?x - object ?y - object ?z - object)
  :precondition (and (on ?x ?y) (clear ?x) (arm_empty) (not (= ?x ?y)) (not (= ?x ?z)) (not (= ?y ?z)))
  :effect (and (holding ?x) (clear ?y) (not (clear ?x)) (not (arm_empty)) (not (on ?x ?y))))
)
