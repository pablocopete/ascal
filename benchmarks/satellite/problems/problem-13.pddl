(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation2 groundstation1 groundstation0 groundstation3 phenomenon4 star5 planet6 planet7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 - instrument
   infrared0 spectrograph2 infrared1 - mode
 )
 (:init (supports instrument0 infrared1) (calibration_target instrument0 groundstation2) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 planet6) (supports instrument1 spectrograph2) (supports instrument1 infrared0) (calibration_target instrument1 groundstation1) (supports instrument2 infrared0) (supports instrument2 spectrograph2) (supports instrument2 infrared1) (calibration_target instrument2 groundstation2) (on_board instrument1 satellite1) (on_board instrument2 satellite1) (power_avail satellite1) (pointing satellite1 groundstation1) (supports instrument3 infrared1) (supports instrument3 spectrograph2) (calibration_target instrument3 groundstation1) (supports instrument4 infrared0) (supports instrument4 infrared1) (supports instrument4 spectrograph2) (calibration_target instrument4 groundstation0) (on_board instrument3 satellite2) (on_board instrument4 satellite2) (power_avail satellite2) (pointing satellite2 phenomenon4) (supports instrument5 infrared0) (calibration_target instrument5 groundstation3) (supports instrument6 infrared1) (supports instrument6 infrared0) (calibration_target instrument6 groundstation0) (supports instrument7 infrared1) (supports instrument7 spectrograph2) (calibration_target instrument7 groundstation3) (on_board instrument5 satellite3) (on_board instrument6 satellite3) (on_board instrument7 satellite3) (power_avail satellite3) (pointing satellite3 planet7))
 (:goal (and (pointing satellite1 groundstation1) (have_image phenomenon4 infrared0) (have_image star5 infrared1) (have_image planet6 infrared0) (have_image planet7 spectrograph2)))
)
