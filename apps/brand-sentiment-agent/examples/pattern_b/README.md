# Pattern B example run (Chipotle, effort=high)

Real Agent API run via `agent_api_v2.py "Chipotle" --window-days 90`. Raw extraction in
`raw.json`.

This particular run found 2 themes that cleared the minimum sample size (Portion Size
Customer Complaints: 6 items; Menu Innovation and Limited-Time Offerings: 5 items) but
neither escalated: negative volume was flat versus the prior window. That is a real,
valid outcome, not every run of a live brand will have a theme actively worsening in the
90 days sampled. The `examples/chipotle_result.json` Pattern A run captured earlier the
same day did find two escalating themes with sourced quotes; both are legitimate real
runs of the same agent logic on the same brand, and the difference is a fair
illustration of run-to-run variance in what a live web search surfaces, not a bug in
either path.
