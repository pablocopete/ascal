(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation2 groundstation3 star0 star1 star4 phenomenon5 star6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 - instrument
   image1 thermograph2 spectrograph0 - mode
 )
 (:init (supports instrument0 image1) (supports instrument0 spectrograph0) (supports instrument0 thermograph2) (calibration_target instrument0 star1) (supports instrument1 image1) (supports instrument1 thermograph2) (supports instrument1 spectrograph0) (calibration_target instrument1 star1) (supports instrument2 thermograph2) (supports instrument2 spectrograph0) (supports instrument2 image1) (calibration_target instrument2 groundstation3) (on_board instrument0 satellite0) (on_board instrument1 satellite0) (on_board instrument2 satellite0) (power_avail satellite0) (pointing satellite0 star1) (supports instrument3 thermograph2) (supports instrument3 image1) (calibration_target instrument3 groundstation3) (supports instrument4 image1) (calibration_target instrument4 star1) (on_board instrument3 satellite1) (on_board instrument4 satellite1) (power_avail satellite1) (pointing satellite1 star7) (supports instrument5 thermograph2) (supports instrument5 image1) (calibration_target instrument5 star1) (on_board instrument5 satellite2) (power_avail satellite2) (pointing satellite2 star1) (supports instrument6 thermograph2) (supports instrument6 spectrograph0) (supports instrument6 image1) (calibration_target instrument6 star0) (supports instrument7 spectrograph0) (calibration_target instrument7 star1) (on_board instrument6 satellite3) (on_board instrument7 satellite3) (power_avail satellite3) (pointing satellite3 star1))
 (:goal (and (pointing satellite0 star6) (pointing satellite1 groundstation3) (pointing satellite3 star7) (have_image star4 spectrograph0) (have_image phenomenon5 thermograph2) (have_image star6 spectrograph0) (have_image star7 image1)))
)
