(define (problem dlog_3_3_3_problem_problem-problem)
 (:domain dlog_3_3_3_problem_problem-domain)
 (:objects
   s0 s1 s2 s3 s4 s5 p0_2 p0_4 p1_5 p2_3 p2_4 p4_0 p4_1 p4_5 p5_2 - location
   driver1 driver2 driver3 - driver
   truck1 truck2 truck3 - truck
   package1 package2 package3 - obj
 )
 (:init (at_ driver1 s1) (at_ driver2 s1) (at_ driver3 s0) (at_ truck1 s3) (empty truck1) (at_ truck2 s0) (empty truck2) (at_ truck3 s1) (empty truck3) (at_ package1 s5) (at_ package2 s3) (at_ package3 s2) (path s0 p0_2) (path p0_2 s0) (path s2 p0_2) (path p0_2 s2) (path s0 p0_4) (path p0_4 s0) (path s4 p0_4) (path p0_4 s4) (path s1 p1_5) (path p1_5 s1) (path s5 p1_5) (path p1_5 s5) (path s2 p2_3) (path p2_3 s2) (path s3 p2_3) (path p2_3 s3) (path s2 p2_4) (path p2_4 s2) (path s4 p2_4) (path p2_4 s4) (path s4 p4_1) (path p4_1 s4) (path s1 p4_1) (path p4_1 s1) (path s4 p4_5) (path p4_5 s4) (path s5 p4_5) (path p4_5 s5) (path s5 p5_2) (path p5_2 s5) (path s2 p5_2) (path p5_2 s2) (link s0 s2) (link s2 s0) (link s1 s2) (link s2 s1) (link s2 s4) (link s4 s2) (link s2 s5) (link s5 s2) (link s3 s0) (link s0 s3) (link s3 s2) (link s2 s3) (link s3 s4) (link s4 s3) (link s4 s0) (link s0 s4) (link s5 s0) (link s0 s5) (link s5 s3) (link s3 s5) (link s5 s4) (link s4 s5))
 (:goal (and (at_ driver1 s5) (at_ driver2 s4) (at_ driver3 s2) (at_ truck1 s1) (at_ package1 s2) (at_ package2 s3) (at_ package3 s3)))
)
