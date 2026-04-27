(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation0 star3 star2 star1 phenomenon4 phenomenon5 planet6 phenomenon7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 - instrument
   image1 spectrograph0 infrared2 - mode
 )
 (:init (supports instrument0 infrared2) (supports instrument0 spectrograph0) (calibration_target instrument0 star3) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 groundstation0) (supports instrument1 image1) (calibration_target instrument1 star2) (on_board instrument1 satellite1) (power_avail satellite1) (pointing satellite1 star3) (supports instrument2 image1) (supports instrument2 spectrograph0) (supports instrument2 infrared2) (calibration_target instrument2 star1) (supports instrument3 image1) (calibration_target instrument3 star1) (on_board instrument2 satellite2) (on_board instrument3 satellite2) (power_avail satellite2) (pointing satellite2 groundstation0) (supports instrument4 image1) (calibration_target instrument4 star1) (on_board instrument4 satellite3) (power_avail satellite3) (pointing satellite3 phenomenon7))
 (:goal (and (pointing satellite3 phenomenon7) (have_image phenomenon4 spectrograph0) (have_image phenomenon5 image1) (have_image planet6 image1) (have_image phenomenon7 spectrograph0)))
)
