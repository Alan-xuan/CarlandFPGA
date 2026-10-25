# Main continuous-enclosure review plan

This is independent pure geometry preparation, not C02/C03 admission or a real
observed map. Only A operates the physical board. Preserve the frozen H01-H15
contract and all its unfulfilled gates.

For each declared capsule point its distance from the center pivot is at most
R=0.40+0.12=0.52m. A body rotation through total angle theta moves such a point
by at most 2R sin(theta/2). This is monotone for theta in [0,pi]. Every collision
substep must enforce the much smaller frozen 0.05deg limit. The baseline0.5mm
alone exceeds its roughly0.454mm maximum angular displacement, but translation,
initial uncertainty and numerical error need separate additional bounds.

If the center follows an arbitrary nonreversing path of length L from p0 to p1,
every intermediate center is within L of p0, which belongs to the chord p0-p1.
Thus L is a valid conservative deviation enclosure from that chord even when
the tight circular sagitta assumptions are unproved. It can substantially
over-reject. Combining this with the angular displacement, declared initial
position/orientation uncertainty and an outward numerical margin encloses the
whole continuous rigid body in the translated start-shape sweep. An AABB
containing that expanded sweep is a further conservative enclosure. Checking
all occupied/unknown intersections of that bound has no endpoint-only hole.

An initial orientation error delta in [0,pi] around the declared start pivot
can move any later path point by at most2(R+cumulative_length)sin(delta/2),
provided the same fixed world rotation error applies to the entire mathematical
rollout. This is not a bound on unmodeled real dynamics or future odometry drift.
If uncertainty semantics differ, the proof does not apply; reject or widen it.

Known-free acceptance must contain the entire conservative support. Requiring
one supplied free AABB to contain it is sufficient but incomplete; a union of
smaller regions can be conservatively unresolved. Occupied/unknown overrides,
missing coverage, contact with solid cube boundaries and unfinished budget work
cannot create clearance. Increasing margins cannot create a new clear result.

The 80-digit analytic controls freeze piecewise acceleration and exact body-arc
results before author release. Combined constant curvature is an oblique planar
arc; sequential different body axes can generate a noncoplanar 3D path. These
controls test correct signs, body/world order and distance integration, not an
invented torsion requirement. No author test or model code is imported.
