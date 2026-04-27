(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   star0 star2 star3 star1 star4 planet5 planet6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 instrument8 - instrument
   image0 image2 infrared1 - mode
 )
 (:init (supports instrument0 image2) (calibration_target instrument0 star2) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 star1) (supports instrument1 infrared1) (calibration_target instrument1 star0) (supports instrument2 image2) (supports instrument2 image0) (supports instrument2 infrared1) (calibration_target instrument2 star2) (supports instrument3 image2) (supports instrument3 image0) (calibration_target instrument3 star1) (on_board instrument1 satellite1) (on_board instrument2 satellite1) (on_board instrument3 satellite1) (power_avail satellite1) (pointing satellite1 star0) (supports instrument4 infrared1) (calibration_target instrument4 star3) (supports instrument5 image0) (supports instrument5 image2) (supports instrument5 infrared1) (calibration_target instrument5 star2) (supports instrument6 image0) (supports instrument6 infrared1) (calibration_target instrument6 star1) (on_board instrument4 satellite2) (on_board instrument5 satellite2) (on_board instrument6 satellite2) (power_avail satellite2) (pointing satellite2 planet5) (supports instrument7 infrared1) (supports instrument7 image0) (supports instrument7 image2) (calibration_target instrument7 star3) (supports instrument8 infrared1) (supports instrument8 image0) (supports instrument8 image2) (calibration_target instrument8 star1) (on_board instrument7 satellite3) (on_board instrument8 satellite3) (power_avail satellite3) (pointing satellite3 star3))
 (:goal (and (pointing satellite0 star0) (pointing satellite2 star0) (have_image star4 image2) (have_image planet5 image2) (have_image planet6 image2) (have_image star7 infrared1)))
)
