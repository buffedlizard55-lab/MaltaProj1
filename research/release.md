# Release verification — supplemental evidence dashboard

## Published release

- **Live site:** https://buffedlizard55-lab.github.io/MaltaProj1/dashboard/
- **PR31:** https://github.com/buffedlizard55-lab/MaltaProj1/pull/31
- **Merged:** 2026-10-13T19:40:54Z, explicit merge after successful checks; no user review gate.
- **Merge commit:** `303ee4bf4ad7f4200634753c02a0592c99d6856e`.
- **PR head verification:** https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38456645912 — success.
- **Main verification:** https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38456771169 — success.
- **Actual legacy Pages deployment:** https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38456769451 — success.
- **Pages build API:** confirmed `status: built`, exact merge commit above, `error.message: null`, updated2026-10-13T19:41:17Z. Existing `main:/` source and legacy build type are unchanged.

## Independent live checks

Official public Pages fetches returned the expected titles/content for the landing page, Source inventory, Flagged for Review, Repository audit and Sources/evidence. The published inventory contains380 captured state entries, distinctly labeled cached/historical versus rendered cards. The review page contains22 general/combined-audit findings plus250 unpriced fixture rows, each with official review links.

Live Repository audit returned the newer19:42 verification time and session-branch JSON link, independently demonstrating automatic branch-data delivery after the initial19:36 static publication. CSS-hidden fallback warnings/expiry labels may appear in text-only extractors; interactive Chromium checks separately confirmed correct hidden/visible states and expiry.

## Automatic post-merge collection

https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38456771049 completed **success**, including37 tests, live source collection, real-snapshot browser checks, build/source/internal-link validation and session-branch-only return. The live update branch remains `arena/4f599d7c-maltaproj1`; repository auto-delete-after-merge is false. Scheduled collection is enabled by the workflow now on main, at17 and47 minutes past each hour, subject to GitHub scheduling delay.

Public contents transport returned HTTP200 and `Access-Control-Allow-Origin: *`. Local browser tests used normal web security; the portable browser's missing sandbox outbound-proxy CA required a test-context-only TLS exception for that one live-transport check. Delivered client/production collector do not disable TLS validation or retain tokens.

## Dataset and verification boundaries

Snapshot counts at release:258 rendered fixtures (27 CS2 /231 LoL),380 source-state records,14 eligible primary moneylines,8 exact matched fixture calculations,250 intentionally blank fixture lines. The live snapshot supersedes these dated counts automatically.

No Hotspawn crowd percentages, unsupported aliases, generic priors, rank heuristics or invented odds are probability inputs. Official fixtures/formats/publication timestamps/complete-list claims that cannot be confirmed remain blank or explicitly flagged. Current pricing is single-book proportional no-vig, not a calibrated true chance or guaranteed executable offer.

37 offline tests;11 HTML pages including404;742 dashboard internal links/assets/downloads/anchors checked;zero data rows without official-source links. Responsive Chromium checks passed at1440px/390px, including search, query persistence, game/coverage filters, accessible sorting, CSV, complete state inventory, expired-value hiding, mobile navigation/Escape and no body overflow/script errors.

Combined tracked-tree audit:260 files /138,798 text lines /1,564 internal targets;6 inherited CSV/static-anchor review findings. Other owners' root/docs/models/data remain preserved and separate—not silently certified as primary quote evidence. See [full audit](repository-audit.md) and [coordination log](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/COORDINATION.md).

Flagged/unverified data is non-blocking by design. Failed checks or broken dashboard links are not bypassed; the release proceeded only after successful verification and confirmed publication.
