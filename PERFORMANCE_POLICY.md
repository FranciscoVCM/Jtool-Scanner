# Scanner performance and accuracy tradeoffs

Approved by the user on 2026-11-01. This supersedes the older 5% preference /
10% hold in historical goal text, handoffs and experiment plans. It changes the
performance budget, not the correctness requirements or the goal's completion
criteria. Preserve historical measurements and their original verdicts.

## Acceptance budget

- Up to 25% additional whole-scan time may be accepted for meaningful, verified
  accuracy improvements, with all required correctness protections passing.
- More than 25%, up to and including 50%, is exceptional: require substantial
  gains across different visual families and a documented accuracy/time tradeoff.
- Above 50% is not acceptable for deployment.

A result within the budget is eligible for review, not automatically approved.
Do not slow unchanged screens unnecessarily. Report absolute seconds as well as
percentages, each representative family's result, and cumulative changes from
the named stable baseline; averages must not conceal an expensive case.

## Measurement and correctness

Keep quiet, serial AC-powered whole-scanner before/after measurements, at least
two samples per mode per dense/sparse/heavier affected source. Record source,
options, complete feature selectors, runtime/dependency identity and expected
full output. Check scan time and time including exports separately. A faster
helper or an unchanged compact bypass does not establish whole-scanner cost.
Preserve interrupted runs and every valid sample; do not discard slow samples.
Accuracy work can continue on battery while controlled timing is unavailable.

Retain source-based whole/every-delta review, original regression protections,
exact-control bounds, affected tests and the final full unittest suite. No
room/palette/coordinate answer branches, weakened evidence, hidden failures or
silent positive losses are authorized by a larger time budget. References are
post-scan evaluation only.

## Reconsidering held work

Keep each old receipt immutable. A candidate previously held above 10% can be
reconsidered under this policy in a separate review referencing the original
measurements, exact implementation and outstanding correctness checks. Do not
rewrite an old FAIL as a PASS or treat eligibility as deployment qualification.

For example, the private combined hollow-recognition/sampling candidate measured
approximately +5.13% on its dense case, +1.80% on its heavier control and +17.34%
on its active sparse case. Those measurements fit the new normal budget, but
remaining protection, maintained-port and integration checks are still required.
