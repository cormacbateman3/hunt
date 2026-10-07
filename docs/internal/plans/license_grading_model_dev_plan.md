Automated License Grading - Development Plan
Starting scope: Pennsylvania hunting licenses
The idea: Train an ML model that grades a license from its front and back photos, stores the result in a database, and issues the user a digital badge/cert — same model as graded cards and coins. Two phases: prove it works, then build it out. Most of the manual work (photographing, grading) sits on your end and can wait until you have time; the modeling is on me.
Why it's worth doing: Grading is a big part of why other collectible markets took off — it adds trust and a shared quality benchmark, so people buy and sell at higher prices with confidence. Over 26 million cards were graded in 2025 (up 32% year-over-year). For coins, the grade alone is the difference between scrap melt value and thousands of dollars.
Phase 1 — Prototype / feasibility
–	Define the grading scale, likely mirroring an existing one (coins use the Sheldon scale, 1–70).
–	You photograph licenses (front + back) and grade each in a labeling tool — Label Studio is free and self-hosted.
–	I scrape additional license images off the web for you to grade as well.
–	Target ~500–1,000 graded front/back pairs to bootstrap a usable score distribution.
–	Three tests: (1) can a baseline model predict grades consistently? (2) how many observations do we actually need (learning curve)? (3) do your photos and the scraped images produce different score distributions (KS test)?
–	If the scraped images hold up, it (1) lets me pull data programmatically so you're not shooting everything by hand, and (2) removes the bias from your buying habits, which won't match the overall market.
–	Go / no-go bar: model lands within about one grade of the true grade most of the time.
Phase 2 — Full build (only if Phase 1 clears the bar)
–	Same process, scaled up to more observations.
–	2–3 other SMEs grade independently → consensus labels and less individual bias (tracked with an inter-rater agreement score).
–	Model outputs an overall grade plus sub-scores (centering, corners, edges, surface) for more useful feedback.
–	Ship the app flow: auto-grade on image upload → store the result → issue a digital badge/cert with a unique lookup ID.
