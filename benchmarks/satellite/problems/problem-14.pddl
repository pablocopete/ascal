(define (problem strips_sat_x_1_problem-problem)
 (:domain strips_sat_x_1_problem-domain)
 (:objects
   satellite0 satellite1 satellite2 satellite3 - satellite
   groundstation3 groundstation0 groundstation2 star1 planet4 star5 planet6 star7 - direction
   instrument0 instrument1 instrument2 instrument3 instrument4 instrument5 instrument6 instrument7 - instrument
   image0 thermograph2 infrared1 - mode
 )
 (:init (supports instrument0 thermograph2) (supports instrument0 infrared1) (calibration_target instrument0 star1) (on_board instrument0 satellite0) (power_avail satellite0) (pointing satellite0 groundstation3) (supports instrument1 infrared1) (supports instrument1 thermograph2) (calibration_target instrument1 groundstation2) (on_board instrument1 satellite1) (power_avail satellite1) (pointing satellite1 star7) (supports instrument2 thermograph2) (supports instrument2 image0) (supports instrument2 infrared1) (calibration_target instrument2 groundstation2) (supports instrument3 infrared1) (supports instrument3 image0) (supports instrument3 thermograph2) (calibration_target instrument3 groundstation3) (supports instrument4 thermograph2) (calibration_target instrument4 groundstation0) (supports instrument5 thermograph2) (supports instrument5 image0) (calibration_target instrument5 groundstation2) (on_board instrument2 satellite2) (on_board instrument3 satellite2) (on_board instrument4 satellite2) (on_board instrument5 satellite2) (power_avail satellite2) (pointing satellite2 star7) (supports instrument6 infrared1) (calibration_target instrument6 star1) (supports instrument7 infrared1) (supports instrument7 thermograph2) (supports instrument7 image0) (calibration_target instrument7 star1) (on_board instrument6 satellite3) (on_board instrument7 satellite3) (power_avail satellite3) (pointing satellite3 star5))
 (:goal (and (have_image planet4 image0) (have_image star5 infrared1) (have_image planet6 thermograph2) (have_image star7 image0)))
)
