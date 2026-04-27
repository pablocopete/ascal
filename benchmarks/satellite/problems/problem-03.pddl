(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   star0 groundstation1 star2 star3 planet4 planet5 planet6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 - instrument
   infrared2 infrared0 thermograph1 - mode
 )
 (:init (supports instrument0 infrared2) (calibration_target instrument0 star0) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 groundstation1) (supports instrument1 thermograph1) (supports instrument1 infrared0) (supports instrument1 infrared2) (calibration_target instrument1 groundstation1) (supports instrument2 infrared2) (supports instrument2 thermograph1) (supports instrument2 infrared0) (calibration_target instrument2 groundstation1) (on_board instrument1 satellite1) (on_board instrument2 satellite1) (power_avail satellite1) (pointing satellite1 star2) (supports instrument3 thermograph1) (supports instrument3 infrared0) (calibration_target instrument3 star2) (on_board instrument3 satellite2) (power_avail satellite2) (pointing satellite2 planet6) (supports instrument4 infrared2) (calibration_target instrument4 star3) (on_board instrument4 satellite3) (power_avail satellite3) (pointing satellite3 star0))
 (:goal (and (pointing satellite1 planet5) (pointing satellite3 star2) (have_image planet4 infrared2) (have_image planet5 thermograph1) (have_image planet6 infrared0) (have_image star7 infrared2)))
)
