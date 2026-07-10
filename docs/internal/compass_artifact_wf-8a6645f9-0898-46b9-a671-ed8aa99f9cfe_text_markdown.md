# Backtag Reference Data: Historical US Hunting License Research (R1–R5, R7)

## Executive Summary — Confidence & Key Corrections

1. **CORRECTION (R1, high-impact): The "OUT-OF-STATE = Co. 68" printed-tag belief is UNVERIFIED and likely conflates a modern administrative code with the 1913–1937 metal-tag era.** No dated nonresident PA tag reading "OUT-OF-STATE Co. 68" could be found; contrary evidence (a genuine 1935 PA nonresident metal license, #8251) shows nonresidents were identified by a statewide serial number, not a county code. Recommend keeping code 68 (it appears on the project's modern PA county-code PDF) but re-labeling its note as a modern administrative code, not a verified early-tag printing.
2. **CONFIRMED (R1): PA county numbers were used 1913–1937 and were stable/alphabetical (Adams 01 … York 67).** Nuance: "Special Issue" un-numbered licenses were issued 1920–1937 when a county exhausted its numbered allotment.
3. **CORRECTION (R3): The PA "Special Spring Turkey Permit 1968" belief mixes up season and permit.** PA's first spring gobbler season was 1968, but no separate permit was required then — the spring tag came bundled with the general license. A purchasable *separate* spring-turkey permit exists today only as the optional second-bird tag.
4. **CONFIRMED dates:** PA Bear License **1981** (verified — PGC Black Bear Management Plan); PA elk lottery 2001; PA pheasant permit 2017; PA DMAP 2003; PA muzzleloader/flintlock season 1974; PA archery season + $2 archery license 1951; PA Duck Stamp 1983; MD Migratory Game Bird Stamp 1974 (physical stamp discontinued after the 2024 issue); MD black bear permit 2004; Atlantic-Flyway snow-goose conservation order 2009; OH first deer-gun season 1943; OH spring turkey season 1966; OH Wetlands Habitat Stamp 1982; Federal Duck Stamp 1934; HIP nationwide 1998.
5. **Thin sourcing (flagged low confidence):** exact first-years for MD Archery/Muzzleloader/Sika/Bonus Antlered/Furbearer stamps; OH archery/muzzleloader deer permit first years; MD integral deer/turkey tag span.

---

## R1 — PA County Numbers + Out-of-State Unit

**(a) Numbering stability:** PA resident license tags carried a county number that was stable and alphabetical (Adams 01 … York 67) across the era. The PA Game and Fish Collector states: *"Between 1913 and 1937, licenses were printed with a county number on them."* A second collector site (Old Tackle Box) dates the numbered top-stamp to "From 1924 to 1937" and references an explicit "COUNTY NUMBER LIST," confirming the alphabetical scheme persisted. Dated artifacts corroborate stability: a 1936 metal license shows "Lehigh County No. 39," and 1937 metal licenses exist for Bucks County — consistent with no renumbering. Source: http://pagameandfishcollector.com/pa-hunting-licenses/resident

**(b) Era spans (verified/corrected):**
- County numbers on PA licenses/back tags: **1913–1937** (start year possibly 1924 per Old Tackle Box; both sources agree the practice ended 1937). The back-tag *display* requirement itself ran from 1913 until repealed effective Feb. 13, 2012. Material progression: canvas 1913–1923, aluminum 1924–1926, metal 1927–1941, cardboard from 1942. Source: http://pagameandfishcollector.com/pa-hunting-licenses/resident ; https://www.bowhunting.com/news/2012/02/19/pennsylvania-hunters-no-longer-required-to-display-back-tag/
- County-issued antlerless deer licenses using county identification: **1951–~2002.** County quota system began 1951; county treasurers became issuing agents 1952; the system shifted from county boundaries to Wildlife Management Units around 2003. Source: https://www.tnonline.com/20190214/pennsylvania-hunting-history/
- Special Issue (un-numbered overflow) licenses: 1920–1937. Source: http://pagameandfishcollector.com/pa-hunting-licenses/special-issue

**(c) OUT-OF-STATE = 68:** Not confirmed as a printed early-tag code. The number 68 appears on the project's modern PA county-code map PDF as the administrative code for out-of-state, but no 1913–1937 nonresident artifact printing "Co. 68" was located, and a 1935 nonresident metal license used serial #8251 instead. Treat 68 as a modern administrative code. Source: https://www.ebay.com/itm/193052440005

**Final geographic_units.csv row:**
```
"PA","Out-of-State","County","68","","False","True","69","Modern administrative code for non-resident/out-of-state; appears on PA county-code map PDF. NOT verified as printed on 1913-1937 nonresident metal tags (those used statewide serial numbers, e.g. 1935 NR license #8251). Confidence: medium for code value, low for early-tag printing."
```

---

## R2 — PA Historical Add-on / Standalone-License Products

```
"PA","Turkey Tag","Tag","Turkey","Any","False","False","","2011","Fall turkey tag printed integral/attached to the back-tag license (seen on 1969 test artifact). First year unknown (mid-20th century); integral-to-back-tag format ended when PA redesigned to wallet-size license and repealed the back-tag display requirement (eff. Feb 2012). NOT the modern Special Spring Turkey Permit. Confidence: low (first), medium (last).","https://www.bowhunting.com/news/2012/02/19/pennsylvania-hunters-no-longer-required-to-display-back-tag/"
"PA","Big Game Tag","Tag","Multiple","Any","False","False","","2011","Big-game attach portion on mid-century PA back-tag licenses (seen on 1969 test artifact; a 1969 PA non-resident license with 'Big Game & Turkey Tag' is documented at auction). Integral-to-back-tag format ended ~2011 with wallet-size redesign. Confidence: low (first), medium (last).","https://www.ebay.com/itm/165732600802"
"PA","Antlerless Deer License","License","Antlerless Deer","Any","False","False","1951","2002","Standalone paper license, county-issued under county quotas; county quota system began 1951, county treasurers designated issuing agents 1952. County identification used until the shift to Wildlife Management Units ~2003. Separate row from the modern Antlerless Deer Permit. Famous pink-envelope lottery era. Confidence: high (first), medium (last).","https://www.tnonline.com/20190214/pennsylvania-hunting-history/"
"PA","Muzzleloader License","License","Deer","Muzzleloader","False","False","1974","","Standalone paper muzzleloader/flintlock license; PA's first muzzleloader (flintlock-only) deer season was held in 1974 on 37 state game lands (seen on 1970s test artifact). Pre-dates the modern Muzzleloader privilege/stamp. Last year unknown - naming transitioned over time. Confidence: high (first), low (last).","https://www.tnonline.com/20190214/pennsylvania-hunting-history/"
"PA","Archery License","License","Deer","Archery","False","False","1951","","Standalone paper archery license; PA's first archery deer season was 1951, requiring a special $2 archery license (5,542 sold, 33 bucks taken). Pre-dates the modern Archery privilege/stamp. Last year unknown - naming transitioned over time. Confidence: high (first), low (last).","https://www.statecollege.com/articles/local-news/how-things-have-changed-archery-hunting-then-and-now/"
```
Context notes: bow/arrow first legalized as PA hunting gear in 1929; the first dedicated archery season and $2 archery license came in 1951; does first allowed to archers in 1957; archers required to hold a doe license to take a doe beginning 1993. PA's first "statewide" antlerless season was 1928 (51 of 67 counties), but the standalone county-quota *paper Antlerless Deer License* artifact era begins 1951.

---

## R3 — Year Floors for EXISTING Addon Rows

**PA (9 rows):**
```
"PA","Archery Stamp","Stamp","Deer","Archery","False","False","1951","","Archery hunting privilege required since PA's first archery season (1951, $2 archery license). Naming varied (license vs stamp) over time. Confidence: high (privilege floor), low (stamp-name start).","https://www.statecollege.com/articles/local-news/how-things-have-changed-archery-hunting-then-and-now/"
"PA","Muzzleloader Stamp","Stamp","Deer","Muzzleloader","False","False","1974","","Muzzleloader (flintlock) privilege required since PA's first muzzleloader season (1974). Naming varied (license vs stamp). Confidence: high (privilege floor), low (stamp-name start).","https://www.tnonline.com/20190214/pennsylvania-hunting-history/"
"PA","Bear Permit","Permit","Bear","Any","False","True","1981","","VERIFIED: In 1981 the PA Legislature created a bear license that must be purchased in addition to a general hunting license before hunting bear (annual allocation initially 100,000; allocation cap removed 1989; sold at all issuing agents from 1997). Confidence: high.","https://www.huntingpa.com/threads/history-of-deer-management.118831/"
"PA","Antlerless Deer Permit","Permit","Antlerless Deer","Any","False","False","2003","","Modern WMU-based antlerless deer permit replacing the county-quota paper Antlerless Deer License ~2003. Confidence: medium.","https://www.altoonamirror.com/sports/outdoors/2024/11/50-years-of-changes-to-pa-deer-hunting/"
"PA","Elk License (Lottery)","License","Elk","Any","False","True","2001","","PA modern elk lottery adopted June 8, 2001 (eff. June 9, 2001); regulated hunt began 2001 via random-drawing lottery. Confidence: high.","https://www.pacodeandbulletin.gov/Display/pacode?file=/secure/pacode/data/058/chapter143/subchapKtoc.html&d=reduce"
"PA","Waterfowl/Migratory Bird Stamp","Stamp","Waterfowl","Any","False","False","1983","","Pennsylvania Duck Stamp program began 1983; revenues to Game Fund for wetlands. Confidence: high.","https://huntwildpa.com/2018/12/28/federal-duck-stamp-display-at-pgc-headquarters-through-jan-24/"
"PA","Pheasant Permit","Permit","Pheasant","Any","False","True","2017","","PA pheasant permit program effective May 13, 2017 (adult permit required 2017-18; junior free permit added 2018). Confidence: high.","https://www.outdoornews.com/2017/03/30/pennsylvania-pheasant-permit-needed-2017-18/"
"PA","DMAP Antlerless Tags","Tag","Antlerless Deer","Any","False","False","2003","","Deer Management Assistance Program established by PGC at its April 8, 2003 meeting; permits first issued 2003-04 license year. Confidence: high.","https://www.pacodeandbulletin.gov/Display/pabull?file=/secure/pabulletin/data/vol33/33-24/1116.html"
"PA","Special Spring Turkey Permit","Permit","Turkey","Any","False","False","1968","","CORRECTION: PA's first spring gobbler season was 1968 (take of 1,636), but NO separate permit was required at the start - the spring tag came bundled with the general license. A purchasable separate spring-turkey permit exists today only as the optional SECOND-bird tag (modern). Confidence: high (season year), low (separate-permit start).","https://www.pa.gov/agencies/pgc/newsroom/spring-gobbler-season-is-calling"
```

**MD (8 rows):**
```
"MD","MD Migratory Game Bird Stamp","Stamp","Migratory Birds","Any","False","True","1974","2024","Maryland's state migratory game bird (duck) stamp program began 1974; 50th and final design contest held 2023-24; physical stamp no longer produced (replaced by printed receipt + commemorative decal). Confidence: high.","https://www.chesapeakebaymagazine.com/50th-md-migratory-game-bird-stamp-winner-named-at-waterfowl-festival/"
"MD","Archery Stamp","Stamp","Deer","Archery","False","False","","","MD Archery Deer Stamp first-year not verified in this pass. Confidence: low.","https://dnr.maryland.gov/pages/service_hunting_license.aspx"
"MD","Muzzleloader Stamp","Stamp","Deer","Muzzleloader","False","False","","","MD Muzzleloader Deer Stamp first-year not verified in this pass. Confidence: low.","https://dnr.maryland.gov/pages/service_hunting_license.aspx"
"MD","Bonus Antlered Deer Stamp","Stamp","Antlered Deer","Any","False","False","","","MD Bonus Antlered Deer Stamp allows one additional antlered whitetail (Region B); first-year not verified. Confidence: low.","https://www.eregulations.com/maryland/hunting/deer-seasons-bag-limits"
"MD","Sika Deer Stamp","Stamp","Sika Deer","Any","False","False","","","MD annual Sika Deer Stamp required to hunt sika deer; relatively recent (nonresident sika stamp added 2024-25); first-year not verified. Confidence: low.","https://www.eregulations.com/maryland/hunting/deer-seasons-bag-limits"
"MD","Furbearer Permit","Permit","Furbearer","Any","False","True","","","MD Furbearer Permit required to hunt/trap/chase furbearers; first-year not verified. Confidence: low.","https://dnr.maryland.gov/pages/service_hunting_license.aspx"
"MD","Black Bear Hunting Permit","Permit","Bear","Any","False","True","2004","","Maryland resumed black bear hunting in 2004 (first season in 51 years; 200 permits issued, 20 bears taken). Lottery-issued permit. Confidence: high.","https://www.washingtonexaminer.com/news/3086677/maryland-opens-bear-hunt-lottery/"
"MD","Snow Goose Conservation Order Permit","Permit","Snow Goose","Any","False","True","2009","","MD's $5 Snow Goose Conservation Order permit; Atlantic Flyway conservation order implemented spring 2009 (federal/state regs amended fall 2008). Distinct from the 1999 mid-continent order. Confidence: high.","https://dnr.maryland.gov/wildlife/documents/2019-af_lightgeeseassessment.pdf"
```

**OH (6 rows):**
```
"OH","Archery Deer Permit","Permit","Deer","Archery","False","True","","","OH archery deer permit; first-year not verified in this pass (Ohio deer permit system dates to the 1943 deer season but archery-specific permit start not confirmed). Confidence: low.","https://www.eregulations.com/ohio/hunting/deer-hunting-regulations"
"OH","Deer Gun Permit","Permit","Deer","Gun","False","True","1943","","Ohio's first modern deer-gun season was 1943 (3 southern counties, 168 deer); a deer permit has been required since. Confidence: high (season floor).","https://www.outdoornews.com/2024/11/28/ohios-deer-gun-season-gets-underway-dec-2-8/"
"OH","Deer Muzzleloader Permit","Permit","Deer","Muzzleloader","False","True","","","OH muzzleloader deer permit; first-year not verified in this pass. Confidence: low.","https://www.eregulations.com/ohio/hunting/deer-hunting-regulations"
"OH","Antlerless Deer Permit","Permit","Antlerless Deer","Any","False","False","","","OH antlerless/deer-management permit (antlerless-only); modern program; first-year not verified. Confidence: low.","https://www.outdoornews.com/2024/11/28/ohios-deer-gun-season-gets-underway-dec-2-8/"
"OH","Spring Turkey Permit","Permit","Turkey","Any","False","True","1966","","Ohio's first modern spring turkey season opened 1966 in nine counties; statewide season began 2000. Separate spring turkey permit required. Confidence: high.","https://ohiodnr.gov/discover-and-learn/safety-conservation/about-ODNR/news/ohios-spring-wild-turkey-hunting-begins-in-april"
"OH","OH Wetlands Habitat Stamp","Stamp","Waterfowl","Any","False","True","1982","","Ohio Wetlands Habitat Stamp (first-of-state) authorized by 1981 HB 371; first stamp issued 1982 (John A. Ruthven wood ducks), sold from Aug 1982. No earlier Ohio state duck stamp. Confidence: high.","https://ohiodnr.gov/buy-and-apply/gifts-and-mechandise/wildlife-legacy-stamp/wetlands-habitat-stamp"
```

**FEDERAL (2 rows, confirm only):**
```
"US","Federal Duck Stamp","Stamp","Waterfowl","Any","True","True","1934","","Migratory Bird Hunting and Conservation Stamp Act signed March 16, 1934; first stamp 1934 (Darling mallards). Confidence: high.","https://www.fws.gov/law/migratory-bird-hunting-and-conservation-stamp-act"
"US","HIP Certification","Permit","Migratory Birds","Any","True","True","1998","","Harvest Information Program piloted 1991-92 (CA, MO, SD); became a federal requirement nationwide (all 49 states except HI) in 1998. Confidence: high.","https://www.fws.gov/program/migratory-bird-harvest-surveys/what-we-do"
```

---

## R4 — MD Historical Integral Tags

```
"MD","Deer Tag","Tag","Deer","Any","False","False","","","Integral deer tag printed on 1960s MD statewide hunter's licenses (seen on 1969 'STATE-WIDE HUNTER' test artifact). Exact start/end of the integral-tag format on MD licenses not verified in this pass; analogous regional format documented circa 1969. Modern MD uses a separate Big Game Harvest Record + e-check instead. Confidence: low.","https://www.law.cornell.edu/regulations/maryland/COMAR-08-03-04-03"
"MD","Turkey Tag","Tag","Turkey","Any","False","False","","","Integral turkey tag printed on 1960s MD statewide hunter's licenses (seen on 1969 test artifact). Exact span not verified; superseded by Big Game Harvest Record + e-check. Confidence: low.","https://www.law.cornell.edu/regulations/maryland/COMAR-08-03-04-03"
```
**MD county vs statewide license context (for license_classes.csv):** County-scoped resident hunter's licenses (e.g., "Resident Hunter's License, WASHINGTON COUNTY") were issued from the 1910s into at least the late 1960s (dated artifacts: Washington Co. 1917/1936/1946/1965; Howard Co. 1918-19; Kent Co. 1968). A "State Wide Hunter" license existed by 1947 and was common by 1958–1962. The two forms **overlapped for ~two decades**; no single clean switchover year was confirmed. A MD DNR licensing reference point of July 1, 1977 anchors the modern regime (pre-1977 holders grandfathered). This justifies adding both a county-scoped and a statewide license class for MD in license_classes.csv. Sources: https://waterfowlstampsandmore.com/earliest-hunting-fishing-licenses/ ; https://dnr.maryland.gov/wildlife/pages/licenses/home.aspx

---

## R5 — Audit of "License"-Named Addon Rows (Decision Table)

| State | Row | Decision | Justification |
|---|---|---|---|
| GA | Big Game License (deer/turkey/bear) | **Keep** (addon_type='License') | Standalone big-game privilege document layered atop the base GA hunting license; a distinct physical/collectible add-on artifact. |
| MI | Deer License (Firearm) | **Keep** (addon_type='License') | Standalone firearm-deer license/tag; a distinct purchasable privilege artifact, not the base license. |
| IN | Deer License Bundle | **Delete** | Modern e-licensing bundle with no distinct collectible physical artifact. |
| PA | Elk License (Lottery) | **Keep** (addon_type='License') | Standalone lottery-awarded elk license; distinct collectible artifact (lottery began 2001). |
| PA | Antlerless Deer License (historical) | **Keep** | Standalone county-issued paper license artifact (1951–2002); see R2 row. |
| OH | (deer/turkey rows) | n/a | Ohio uses "Permit" instrument names, not "License"; no change. |
| MD | (deer/bear rows) | n/a | Maryland uses "Stamp"/"Permit" instrument names; base privilege is "Hunting License" → belongs in license_classes, not addons. |

---

## R6 — Proposed gold.json Schema (Scope Note Only; NO Image Labeling)

```json
{
  "state": "PA",
  "license_year": 1969,
  "geographic_unit": "Lancaster (Co. 36)",
  "serial_number": "A12345",
  "residency": "resident | nonresident | unknown",
  "activity_scope": "general | deer | antlerless | archery | muzzleloader | spring_turkey | waterfowl | furbearer | small_game",
  "duration": "annual | multi-year | short-term | conservation-order-season",
  "addons": ["Turkey Tag", "Big Game Tag"],
  "material": "canvas | aluminum | metal | cardboard | paper | plastic",
  "shape": "rectangle | oval | shield | strip | button",
  "colors": ["green", "black"]
}
```
Conventions: `serial_number` must preserve EXACT characters including any prefix/suffix letters and their position relative to digits (store "A12345" vs "12345A" distinctly; do not normalize spacing or strip letters). `geographic_unit` should capture both the county name and any printed county number (e.g., "Lancaster (Co. 36)"). `addons` is a list of artifact names matching addons_permits.csv `addon_name` values. Leave fields null when not legible. **Per task scope this is a schema proposal only; the 17 sandbox images are explicitly out of scope and are NOT labeled here.**

---

## R7 — Ohio Extension (Historical OH Products + Context)

New/confirmed Ohio addons_permits.csv rows (the OH R3 rows above already cover Deer Gun Permit 1943, Spring Turkey Permit 1966, and Wetlands Habitat Stamp 1982). Additional historical/contextual rows:
```
"OH","Deer Tag","Tag","Deer","Any","False","True","1943","","Ohio required a deer permit/tag from its first modern deer-gun season (1943, three southern counties, 168 deer; all 88 counties open by 1956). Earliest OH deer artifacts are paper permits/tags. Confidence: high (program floor).","https://www.outdoornews.com/2024/11/28/ohios-deer-gun-season-gets-underway-dec-2-8/"
"OH","Fall Turkey Permit","Permit","Turkey","Any","False","True","","","Ohio fall turkey season/permit (distinct from the 1966 spring permit); modern; first-year not verified in this pass. Confidence: low.","https://codes.ohio.gov/ohio-administrative-code/rule-1501:31-15-10"
```
**OH license-form history (for license_classes.csv context, no rows required):** Ohio issued its first resident hunting license on Sept. 27, 1913 (one of five states — with AZ, AR, DE, PA — to begin resident licensing that year). A 1944 Ohio paper resident hunting license is in the project test set, consistent with paper-form licenses in the WWII era. Ohio's Division of Wildlife traces to the Ohio Fish Commission (1873); wild turkeys were extirpated ~1904 and reintroduced from the 1950s; deer were extirpated by 1904 and rebuilt by the 1930s–40s, enabling the 1943 season. Sources: https://waterfowlstampsandmore.com/1913-hunting-and-fishing-licenses-in-historical-context-part-three/ ; https://ohiodnr.gov/discover-and-learn/safety-conservation/about-ODNR/news/ohios-spring-wild-turkey-hunting-begins-in-april

---

## Recommendations (Staged)

1. **Ship now (high confidence):** Load all rows marked high/medium confidence. The verified first-year floors (PA Bear 1981, PA Elk 2001, PA Pheasant 2017, PA DMAP 2003, PA Duck Stamp 1983, MD Migratory Stamp 1974, MD Bear 2004, MD Snow Goose 2009, OH Spring Turkey 1966, OH Wetlands 1982, OH Deer Gun 1943, Federal Duck 1934, HIP 1998) are reliable enough to gate prefill/suggestion matching. The PA Antlerless Deer License 1951 floor and PA Archery/Muzzleloader 1951/1974 floors are the most valuable for rejecting modern permits as matches for mid-century artifacts.
2. **Use the PA "68" row as-is but with the corrected note** — keep it for completeness/ordering, but do not present it to users as a verified historical printed code.
3. **Fill the low-confidence blanks before relying on them:** MD Archery/Muzzleloader/Sika/Bonus Antlered/Furbearer stamp first-years and OH archery/muzzleloader permit first-years. Best next sources: MD DNR Guide-to-Hunting-and-Trapping back issues (HathiTrust/state archives) and ODNR historical regulation digests. **Threshold to change:** if a dated artifact or agency digest pins a first-year, promote the row to medium/high and populate approx_first_year.
4. **Resolve the Co. 68 question** by acquiring a clear photo of any 1913–1937 PA *nonresident* metal tag. **Threshold:** if such a tag shows a "68"/"Out-of-State" stamp, change the note to confirmed and set approx_first_year≈1913; if it shows only a serial number (as the 1935 #8251 example suggests), finalize the note as "modern administrative code only."
5. **Confirm the MD integral-tag span** with a dated 1950s–1970s MD statewide license photo to set the Deer Tag / Turkey Tag year floors; until then leave years blank (they gate suggestions, not validity).

---

## Caveats
- Several MD stamp first-years and OH archery/muzzleloader permit first-years remain unverified (marked low confidence, blank year) — these gate suggestions only, never validity. Missing first-year floors mean these rows will not mechanically reject modern matches; fill them before depending on that behavior.
- The "Co. 68 / OUT-OF-STATE" early-tag printing is the most important open question and is currently contradicted by the one nonresident artifact found (1935 #8251, serial-numbered).
- Integral MD deer/turkey tag spans are inferred from a single 1969 artifact plus a regional analogue (a 1969 PA nonresident license with integral Big Game & Turkey tags); treat as low confidence.
- Old Tackle Box and PA Game and Fish Collector disagree on the county-number *start* year (1924 vs 1913); both agree it ended 1937. The 1937 end-year is the reliable one for matching logic.
- The PA back-tag *display* law (1913) and the county-*number* printing era (1913/1924–1937) are distinct facts — do not conflate the 2012 back-tag-display repeal with the end of county numbering.