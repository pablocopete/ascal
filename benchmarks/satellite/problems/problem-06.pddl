(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation1 groundstation3 star0 star2 planet4 planet5 star6 planet7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 instrument8 - instrument
   spectrograph2 thermograph0 spectrograph1 - mode
 )
 (:init (supports instrument0 thermograph0) (supports instrument0 spectrograph2) (calibration_target instrument0 star2) (supports instrument1 spectrograph2) (supports instrument1 thermograph0) (calibration_target instrument1 star0) (on_board instrument0 satellite0) (on_board instrument1 satellite0) (power_avail satellite0) (pointing satellite0 planet7) (supports instrument2 thermograph0) (supports instrument2 spectrograph1) (supports instrument2 spectrograph2) (calibration_target instrument2 groundstation1) (on_board instrument2 satellite1) (power_avail satellite1) (pointing satellite1 groundstation1) (supports instrument3 thermograph0) (supports instrument3 spectrograph2) (calibration_target instrument3 star2) (supports instrument4 spectrograph1) (supports instrument4 thermograph0) (calibration_target instrument4 groundstation1) (supports instrument5 spectrograph2) (supports instrument5 spectrograph1) (calibration_target instrument5 groundstation3) (on_board instrument3 satellite2) (on_board instrument4 satellite2) (on_board instrument5 satellite2) (power_avail satellite2) (pointing satellite2 star0) (supports instrument6 thermograph0) (calibration_target instrument6 groundstation3) (supports instrument7 spectrograph2) (supports instrument7 thermograph0) (calibration_target instrument7 star0) (supports instrument8 thermograph0) (supports instrument8 spectrograph1) (calibration_target instrument8 star2) (on_board instrument6 satellite3) (on_board instrument7 satellite3) (on_board instrument8 satellite3) (power_avail satellite3) (pointing satellite3 planet5))
 (:goal (and (have_image planet4 spectrograph2) (have_image planet5 thermograph0) (have_image star6 spectrograph2) (have_image planet7 spectrograph2)))
)
