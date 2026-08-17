# Judge challenge questions

1. **Why AI?** It estimates nonlinear ETA, delay, and conflict risk from interacting state features; validation compares it with credible deterministic rules.
2. **What fails without AI?** The simulator still runs safely, but proactive risk ranking may be less accurate.
3. **Why XGBoost?** It is effective on structured tabular operational features, fast to train, and inspectable.
4. **What data is used?** Clearly labelled controlled seed infrastructure, timetable, trains, and twin-generated episodes.
5. **How was it evaluated?** Episode-isolated splits with MAE/RMSE and precision/recall/F1.
6. **What is the baseline?** No intervention and priority-aware minimum-safe-hold rules.
7. **How does delay propagation work?** A queue follows calculated temporal overlap on shared resources and records every causal edge.
8. **Digital twin versus simulator?** The twin maintains live computational state that controller decisions update; the simulator advances that state.
9. **How is an action chosen?** Cloned what-if outcomes feed a configurable CP-SAT objective.
10. **What prevents unsafe recommendations?** A separate rule-based safety validator can reject optimizer output.
11. **If the model is wrong?** Low-confidence output cannot override simulation constraints or safety checks.
12. **If no action is feasible?** The API reports no safe recommendation; it does not invent one.
13. **Biggest scalability bottleneck?** Repeated what-if and validation simulations across many trains and horizons.
14. **What is synthetic?** Timetables, movements, disruptions, and training episodes. Station context/topology provenance is documented separately.
15. **How are results validated?** Repeated deterministic scenarios against two baselines with provenance-complete exports.
16. **What did the team build?** Ownership is recorded only in the verified team-contribution document.
17. **Third-party components?** FastAPI, SimPy, NetworkX, XGBoost, scikit-learn, OR-Tools, PostgreSQL/PostGIS, Redis, React, and Tailwind.
18. **Why not simple rules?** The validation report measures whether prediction and optimization improve on a credible rule policy; failed improvements remain visible.
19. **Why not just a dashboard?** The UI reads state produced by resource-locked discrete-event simulation, trained models, optimization, and safety validation.
20. **What is required for deployment?** Official infrastructure/operational feeds, railway-domain verification, cybersecurity, scale testing, governance, and formal safety approval.
