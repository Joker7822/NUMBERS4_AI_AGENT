# BOX posterior moment optimization

For fixed prior strength a, historical signature counts c_i and fair masses
p_i, q_i=(c_i+a*p_i)/(n+a). The Brier calculation only needs
sum(q_i^2)=(sum(c_i^2)+2*a*sum(c_i*p_i)+a^2*sum(p_i^2))/(n+a)^2.
The cross moment is represented exactly by integer permutation multiplicities.
The five pattern counts and total counts are updated only after scoring.
All 715 outcomes, including the ten four-equal outcomes, remain represented.

Full-vector posterior/score helpers are retained as reference implementations.
Four new tests compare individual scores, all signatures, pattern masses,
invalid inputs and complete reports. CI runs both full-history versions and
requires exact metadata/count equality and absolute float differences <=1e-12.
Floating-point summation order differs; bitwise equality is not claimed.
The timing is informational and does not establish a forecast advantage.
No model, selection, training authority or purchase policy change.

Run: python -m numbers4_agent.benchmark_box_moments
