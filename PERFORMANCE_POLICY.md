# Scanner performance and accuracy tradeoffs

Revised by the user on 2026-11-21: **scan quality now takes priority over
speed.** This supersedes the 2026-11-01 budget (25% normal, 25–50%
exceptional, never above 50%), which itself superseded the older 5% preference
/ 10% hold. It changes the performance budget, not the correctness
requirements or the goal's completion criteria. Preserve historical
measurements and their original verdicts; a result held under an older budget
is only reconsidered through a new review (see the last section).

## Acceptance budget

Percentages are additional whole-scan time per affected representative source,
relative to the named stable baseline, measured as described below.

- **Up to +50%**: normal budget for meaningful, verified accuracy improvements
  with all required correctness protections passing.
- **More than +50%, up to and including +100%**: allowed for big improvements —
  substantial verified gains (for example several real corrections per room,
  gains in more than one visual family, or a large reduction in a room's
  actionable errors). Document the accuracy/time tradeoff explicitly.
- **Above +100%** (more than double): not acceptable for the default scan path.
  Such a method may only ship as an explicit opt-in mode, off by default, with
  its own measured cost and the default path unchanged.

Speed still matters: do not slow unchanged screens unnecessarily, prefer
gating expensive evidence to the cases that need it, and keep the app usable
interactively. A result within the budget is eligible for review, not
automatically approved.
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
on its active sparse case. Those measurements fit the normal budget, but
remaining protection, maintained-port and integration checks are still required.
Likewise the maintained 4096 whole-ABBA12 candidate (+15.08% 128r, +9.09% 138r,
+3.21% 130r, held in October under the 5/10% rule) is timing-eligible now; its
accuracy and protection review is still outstanding.
