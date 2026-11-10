# KPI Benchmarks

Canonical industrial-maintenance KPI benchmarks for the Plant Pulse Report skill. Every benchmark traces to a named source the end user can look up.

Status thresholds used by the skill:
- **on-target** — value meets or beats the world-class/acceptable threshold
- **warning** — value is in the acceptable/median band
- **at-risk** — value is at or past the at-risk threshold

When a current value crosses a threshold, the skill labels the KPI card with the matching status color and cites the source in the card footer.

---

## pm_compliance
- **Display name:** PM Compliance
- **Unit:** %
- **Direction:** higher is better
- **World-class:** ≥ 90
- **Acceptable:** 80–90
- **At-risk:** < 80
- **Source:** SMRP Best Practice Metric 5.4.3 "PM & PdM Compliance"; Palmer, *Maintenance Planning and Scheduling Handbook* (3rd ed., McGraw-Hill, 2019).
- **Citation (short):** SMRP 5.4.3
- **Caveat:** Compliance is measured against the SMRP frequency-compliance window (typically ±10% of the scheduled interval), not a calendar month. If source data uses a calendar definition, flag the number as indicative.

## schedule_compliance
- **Display name:** Schedule Compliance
- **Unit:** %
- **Direction:** higher is better
- **World-class:** ≥ 90
- **Acceptable:** 80–90
- **At-risk:** < 80
- **Source:** SMRP Best Practice Metric 5.4.2 "Schedule Compliance — Hours"; Palmer ch. 2.
- **Citation (short):** SMRP 5.4.2
- **Caveat:** Palmer's argument: 100% compliance is a red flag — it signals the schedule is too loose. Target 85–90%, not 100%.

## reactive_work
- **Display name:** Reactive Work
- **Unit:** %
- **Direction:** lower is better
- **World-class:** ≤ 10
- **Acceptable:** 20–30
- **At-risk:** > 40
- **Source:** SMRP Best Practice Metric 5.4.1 "Reactive Work"; Moore, *Making Common Sense Common Practice* (4th ed., Reliabilityweb Press, 2017).
- **Citation (short):** SMRP 5.4.1; Moore (2017)
- **Caveat:** Moore: sustained reactive work above 40–50% essentially precludes proactive improvement — break the spiral before adding any new program.

## backlog_crew_weeks
- **Display name:** Backlog (crew-weeks)
- **Unit:** crew-weeks
- **Direction:** target band (not monotonic)
- **World-class:** 2–4
- **Acceptable:** 4–6
- **At-risk:** < 2 or > 6
- **Source:** SMRP 5.4.x backlog metric series; Palmer ch. 3.
- **Citation (short):** SMRP 5.4.x; Palmer ch. 3
- **Caveat:** Raw open-WO count is **not** the standardized metric — prefer this measure, which normalizes for crew size. Too little backlog is as bad as too much (idle crews).

## mtbf
- **Display name:** MTBF
- **Unit:** hours
- **Direction:** higher is better (trend-based)
- **World-class:** asset-class specific
- **Acceptable:** flat or increasing trend
- **At-risk:** declining trend over 3+ periods
- **Source:** SMRP Best Practice Metric 5.5.1 "MTBF"; ISO 14224:2016.
- **Citation (short):** SMRP 5.5.1; ISO 14224
- **Caveat:** No universal MTBF benchmark exists. The skill judges MTBF on trend direction and variance vs. OEM-published figures, not an absolute value.

## mttr
- **Display name:** MTTR
- **Unit:** hours
- **Direction:** lower is better (trend-based)
- **World-class:** stable or declining trend
- **Acceptable:** stable
- **At-risk:** increasing trend; long tail > 2× median
- **Source:** SMRP Best Practice Metric 5.5.3 "MTTR"; ISO 14224:2016.
- **Citation (short):** SMRP 5.5.3; ISO 14224

## oee
- **Display name:** OEE
- **Unit:** %
- **Direction:** higher is better
- **World-class:** 85 (with caveat)
- **Acceptable:** 60
- **At-risk:** < 40
- **Source:** Nakajima, *Introduction to TPM* (Productivity Press, 1988); Hansen, *Overall Equipment Effectiveness* (Industrial Press, 2001).
- **Citation (short):** Nakajima (1988); Hansen (2001)
- **Caveat:** The 85% figure is widely cited but contested (Hansen). Continuous-process refineries routinely exceed 95%; discrete job-shop CNCs may top out at 70%. Always report the Availability × Performance × Quality decomposition, not just the product.

## wrench_time
- **Display name:** Wrench Time
- **Unit:** %
- **Direction:** higher is better
- **World-class:** 55–65
- **Acceptable:** 35–45
- **At-risk:** < 30
- **Source:** Palmer, *Maintenance Planning and Scheduling Handbook* ch. 1 & 5.
- **Citation (short):** Palmer ch. 1, 5
- **Caveat:** Wrench time is reliable only when measured by formal work sampling (Palmer ch. 5). Self-reported or system-estimated numbers are indicative at best — mark them as such in the report.

## asset_availability
- **Display name:** Asset Availability
- **Unit:** %
- **Direction:** higher is better
- **World-class:** > 95 (continuous process); > 90 (discrete)
- **Acceptable:** 85–90
- **At-risk:** < 80
- **Source:** SMRP Best Practice Metric 5.1.2 "Availability"; Solomon Associates refinery benchmarking (subscription).
- **Citation (short):** SMRP 5.1.2
- **Caveat:** Benchmark against asset class and industry. Solomon primary data is subscription-only; cite thresholds generically.

## mro_turns
- **Display name:** MRO Inventory Turns
- **Unit:** turns/year
- **Direction:** higher is better (with caveat)
- **World-class:** 2–3
- **Acceptable:** 1–2
- **At-risk:** < 1
- **Source:** SMRP MRO metric series; Wireman, *Benchmarking Best Practices in Maintenance Management* (2nd ed., Industrial Press, 2004).
- **Citation (short):** SMRP; Wireman (2004)
- **Caveat:** Unlike finished-goods, low MRO turns are not always bad. Insurance spares for critical assets may legitimately turn < 0.1/year. Segment by ABC-XYZ before judging.

## trir
- **Display name:** TRIR
- **Unit:** per 100 FTE-yr
- **Direction:** lower is better
- **World-class:** < 0.5
- **Acceptable:** compare to BLS NAICS average (US manufacturing ≈ 2.7, BLS 2022)
- **At-risk:** > industry NAICS average
- **Source:** US BLS *Employer-Reported Workplace Injuries and Illnesses* (annual); OSHA 29 CFR 1904.
- **Citation (short):** BLS IIF; OSHA 29 CFR 1904
- **Caveat:** Benchmark against the plant's specific NAICS code, not a global average. TRIR is a lagging indicator — NP-08 in narrative-patterns.md covers the leading signal.

## open_work_orders
- **Display name:** Open Work Orders
- **Unit:** count
- **Direction:** lower is better (trend-based)
- **World-class:** no standardized benchmark
- **Acceptable:** stable or declining trend
- **At-risk:** rising over 3+ periods; aged items > 20% of total
- **Source:** no SMRP standard for raw count — this KPI is included because it appears on most dashboards, but the skill flags it as non-standardized and recommends `backlog_crew_weeks` as the primary measure.
- **Citation (short):** non-standardized
- **Caveat:** Report the trend, not the absolute number. Pair with backlog aging breakdown (0–30d / 31–60d / 61–90d / 90d+) for a real read.
