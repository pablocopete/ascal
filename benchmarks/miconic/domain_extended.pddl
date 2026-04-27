(define (domain mixed_f8_p4_u0_v0_d0_a0_n0_a0_b0_n0_f0_problem_problem_problem_problem-domain)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:types passenger floor)
 (:predicates (origin ?person - passenger ?floor - floor) (destin ?person - passenger ?floor - floor) (above ?floor1 - floor ?floor2 - floor) (boarded ?person - passenger) (not_boarded ?person - passenger) (served ?person - passenger) (not_served ?person - passenger) (lift_at ?floor - floor))
 (:action board
  :parameters ( ?f1 - floor ?p1 - passenger ?f2 - floor ?p2 - passenger)
  :precondition (and (not (= ?f1 ?f2)) (not (= ?p1 ?p2)) (lift_at ?f1) (origin ?p1 ?f1))
  :effect (and (boarded ?p1)))
 (:action depart
  :parameters ( ?f1 - floor ?p1 - passenger ?f2 - floor ?p2 - passenger)
  :precondition (and (not (= ?f1 ?f2)) (not (= ?p1 ?p2)) (lift_at ?f1) (destin ?p1 ?f1) (boarded ?p1))
  :effect (and (not (boarded ?p1)) (served ?p1)))
 (:action up
  :parameters ( ?f1 - floor ?f2 - floor ?p1 - passenger ?p2 - passenger)
  :precondition (and (not (= ?f1 ?f2)) (not (= ?p1 ?p2)) (lift_at ?f1) (above ?f1 ?f2))
  :effect (and (lift_at ?f2) (not (lift_at ?f1))))
 (:action down
  :parameters ( ?f1 - floor ?f2 - floor ?p1 - passenger ?p2 - passenger)
  :precondition (and (not (= ?f1 ?f2)) (not (= ?p1 ?p2)) (lift_at ?f1) (above ?f2 ?f1))
  :effect (and (lift_at ?f2) (not (lift_at ?f1))))
)
