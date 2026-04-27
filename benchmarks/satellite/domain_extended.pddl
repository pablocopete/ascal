(define (domain strips_sat_x_1_problem-domain)
 (:requirements :strips :typing :negative-preconditions :equality)
 (:types satellite direction instrument mode)
 (:predicates (on_board ?i - instrument ?s - satellite) (supports ?i - instrument ?m - mode) (pointing ?s - satellite ?d - direction) (power_avail ?s - satellite) (power_on ?i - instrument) (calibrated ?i - instrument) (have_image ?d - direction ?m - mode) (calibration_target ?i - instrument ?d - direction))
 (:action turn_to
  :parameters ( ?s - satellite ?d_new - direction ?d_prev - direction ?osat - satellite ?odir1 - direction ?odir2 - direction)
  :precondition (and (not (= ?s ?osat)) (not (= ?d_new ?d_prev)) (not (= ?d_new ?odir1)) (not (= ?d_new ?odir2)) (not (= ?d_prev ?odir1)) (not (= ?d_prev ?odir2)) (not (= ?odir1 ?odir2)) (pointing ?s ?d_prev))
  :effect (and (pointing ?s ?d_new) (not (pointing ?s ?d_prev))))
 (:action switch_on
  :parameters ( ?i - instrument ?s - satellite ?oinst - instrument ?osat - satellite)
  :precondition (and (not (= ?i ?oinst)) (not (= ?s ?osat)) (on_board ?i ?s) (power_avail ?s))
  :effect (and (power_on ?i) (not (calibrated ?i)) (not (power_avail ?s))))
 (:action switch_off
  :parameters ( ?i - instrument ?s - satellite ?oinst - instrument ?osat - satellite)
  :precondition (and (not (= ?i ?oinst)) (not (= ?s ?osat)) (on_board ?i ?s) (power_on ?i))
  :effect (and (not (power_on ?i)) (power_avail ?s)))
 (:action calibrate
  :parameters ( ?s - satellite ?i - instrument ?d - direction ?osat - satellite ?oinst - instrument ?odir - direction)
  :precondition (and (not (= ?s ?osat)) (not (= ?i ?oinst)) (not (= ?d ?odir)) (on_board ?i ?s) (calibration_target ?i ?d) (pointing ?s ?d) (power_on ?i))
  :effect (and (calibrated ?i)))
 (:action take_image
  :parameters ( ?s - satellite ?d - direction ?i - instrument ?m - mode ?osat - satellite ?odir - direction ?oinst - instrument ?omode - mode)
  :precondition (and (not (= ?s ?osat)) (not (= ?i ?oinst)) (not (= ?d ?odir)) (not (= ?m ?omode)) (calibrated ?i) (on_board ?i ?s) (supports ?i ?m) (power_on ?i) (pointing ?s ?d))
  :effect (and (have_image ?d ?m)))
)
