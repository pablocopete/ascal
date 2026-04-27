(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   star0 groundstation2 groundstation3 groundstation1 phenomenon4 star5 planet6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 - instrument
   thermograph0 image1 thermograph2 - mode
 )
 (:init (supports instrument0 thermograph2) (calibration_target instrument0 groundstation1) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 groundstation2) (supports instrument1 thermograph0) (supports instrument1 image1) (supports instrument1 thermograph2) (calibration_target instrument1 groundstation2) (on_board instrument1 satellite1) (power_avail satellite1) (pointing satellite1 groundstation3) (supports instrument2 thermograph2) (supports instrument2 image1) (calibration_target instrument2 groundstation3) (supports instrument3 thermograph0) (calibration_target instrument3 groundstation3) (supports instrument4 thermograph2) (supports instrument4 image1) (supports instrument4 thermograph0) (calibration_target instrument4 groundstation1) (supports instrument5 image1) (supports instrument5 thermograph0) (supports instrument5 thermograph2) (calibration_target instrument5 groundstation3) (on_board instrument2 satellite2) (on_board instrument3 satellite2) (on_board instrument4 satellite2) (on_board instrument5 satellite2) (power_avail satellite2) (pointing satellite2 star7) (supports instrument6 thermograph0) (supports instrument6 image1) (supports instrument6 thermograph2) (calibration_target instrument6 groundstation1) (on_board instrument6 satellite3) (power_avail satellite3) (pointing satellite3 phenomenon4))
 (:goal (and (have_image phenomenon4 image1) (have_image star5 image1) (have_image planet6 image1) (have_image star7 thermograph2)))
)
