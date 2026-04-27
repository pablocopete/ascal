(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation0 star1 groundstation2 groundstation3 star4 phenomenon5 star6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 - instrument
   image1 image2 image0 - mode
 )
 (:init (supports instrument0 image2) (supports instrument0 image0) (calibration_target instrument0 groundstation2) (supports instrument1 image0) (calibration_target instrument1 groundstation2) (supports instrument2 image2) (calibration_target instrument2 groundstation2) (supports instrument3 image2) (supports instrument3 image0) (supports instrument3 image1) (calibration_target instrument3 groundstation2) (on_board instrument0 satellite0) (on_board instrument1 satellite0) (on_board instrument2 satellite0) (on_board instrument3 satellite0) (power_avail satellite0) (pointing satellite0 star4) (supports instrument4 image0) (supports instrument4 image1) (calibration_target instrument4 groundstation3) (supports instrument5 image0) (calibration_target instrument5 groundstation2) (on_board instrument4 satellite1) (on_board instrument5 satellite1) (power_avail satellite1) (pointing satellite1 star6) (supports instrument6 image0) (supports instrument6 image1) (calibration_target instrument6 groundstation3) (on_board instrument6 satellite2) (power_avail satellite2) (pointing satellite2 star7) (supports instrument7 image2) (supports instrument7 image0) (calibration_target instrument7 groundstation3) (on_board instrument7 satellite3) (power_avail satellite3) (pointing satellite3 phenomenon5))
 (:goal (and (pointing satellite0 groundstation0) (have_image star4 image2) (have_image phenomenon5 image1) (have_image star6 image0) (have_image star7 image1)))
)
