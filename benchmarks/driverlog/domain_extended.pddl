(define (domain dlog_3_3_3_problem_problem-domain)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:types
    location locatable - object
    driver truck obj - locatable
 )
 (:predicates (at_ ?obj - locatable ?loc - location) (in ?obj1 - obj ?obj_0 - truck) (driving ?d - driver ?v - truck) (link ?x - location ?y - location) (path ?x - location ?y - location) (empty ?v - truck))
 (:action load_truck
  :parameters ( ?obj_1 - obj ?truck - truck ?loc - location ?oobj - obj ?otruck - truck ?oloc - location)
  :precondition (and (not (= ?obj_1 ?oobj)) (not (= ?truck ?otruck)) (not (= ?loc ?oloc)) (at_ ?truck ?loc) (at_ ?obj_1 ?loc))
  :effect (and (not (at_ ?obj_1 ?loc)) (in ?obj_1 ?truck)))
 (:action unload_truck
  :parameters ( ?obj_1 - obj ?truck - truck ?loc - location ?oobj - obj ?otruck - truck ?oloc - location)
  :precondition (and (not (= ?obj_1 ?oobj)) (not (= ?truck ?otruck)) (not (= ?loc ?oloc)) (at_ ?truck ?loc) (in ?obj_1 ?truck))
  :effect (and (not (in ?obj_1 ?truck)) (at_ ?obj_1 ?loc)))
 (:action board_truck
  :parameters ( ?driver - driver ?truck - truck ?loc - location ?odriver - driver ?otruck - truck ?oloc - location)
  :precondition (and (not (= ?driver ?odriver)) (not (= ?truck ?otruck)) (not (= ?loc ?oloc)) (at_ ?truck ?loc) (at_ ?driver ?loc) (empty ?truck))
  :effect (and (not (at_ ?driver ?loc)) (driving ?driver ?truck) (not (empty ?truck))))
 (:action disembark_truck
  :parameters ( ?driver - driver ?truck - truck ?loc - location ?odriver - driver ?otruck - truck ?oloc - location)
  :precondition (and (not (= ?driver ?odriver)) (not (= ?truck ?otruck)) (not (= ?loc ?oloc)) (at_ ?truck ?loc) (driving ?driver ?truck))
  :effect (and (not (driving ?driver ?truck)) (at_ ?driver ?loc) (empty ?truck)))
 (:action drive_truck
  :parameters ( ?truck - truck ?loc_from - location ?loc_to - location ?driver - driver ?otruck - truck ?oloc1 - location ?oloc2 - location ?odriver - driver)
  :precondition (and (not (= ?loc_from ?loc_to)) (not (= ?loc_from ?oloc1)) (not (= ?loc_from ?oloc2)) (not (= ?loc_to ?oloc1)) (not (= ?loc_to ?oloc2)) (not (= ?oloc1 ?oloc2)) (not (= ?driver ?odriver)) (not (= ?truck ?otruck)) (at_ ?truck ?loc_from) (driving ?driver ?truck) (link ?loc_from ?loc_to))
  :effect (and (not (at_ ?truck ?loc_from)) (at_ ?truck ?loc_to)))
 (:action walk
  :parameters ( ?driver - driver ?loc_from - location ?loc_to - location ?odriver - driver ?oloc1 - location ?oloc2 - location)
  :precondition (and (not (= ?loc_from ?loc_to)) (not (= ?loc_from ?oloc1)) (not (= ?loc_from ?oloc2)) (not (= ?loc_to ?oloc1)) (not (= ?loc_to ?oloc2)) (not (= ?oloc1 ?oloc2)) (not (= ?driver ?odriver)) (at_ ?driver ?loc_from) (path ?loc_from ?loc_to))
  :effect (and (not (at_ ?driver ?loc_from)) (at_ ?driver ?loc_to)))
)
