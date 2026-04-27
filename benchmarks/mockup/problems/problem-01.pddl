(define (problem mockup-1)
 (:domain mockup)
 (:objects
   b1 b2 b3 - object
 )
 (:init (arm_empty) (on_table b1) (on_table b2) (on_table b3)(clear b1) (clear b2) (clear b3))
 (:goal (on b1 b2))
)
