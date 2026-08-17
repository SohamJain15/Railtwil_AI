# Optimization

Candidate holds, releases, platform/route changes, and priorities are evaluated on cloned twin states. OR-Tools CP-SAT selects a feasible minimum-score action from calculated delay/conflict penalties. The independent safety validator runs after selection. No feasible candidate produces an explicit no-solution result.
