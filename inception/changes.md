# Changes

The spec changes first when reality differs (charter rule 11). One dated line per change, newest last, committed together with the changed spec files as `spec(<unit>): ...`:

`- YYYY-MM-DD <unit>: <what changed, with IDs, e.g. FR2.1 [[requirements]]>. Why: <reason>. Class: change|stop.`

Class `stop` (weakens the data loop or the value case, needs money, an account or a deploy) is a blocker: no new code until Nico answers on the ticket. Its line and spec files stay uncommitted until he does. If he accepts it after the unit's blocked work was committed, the line ends with `Accepted YYYY-MM-DD; after code: blocked work in progress.`

A test Nico rules wrong gets its own line before the changed test is committed: `- YYYY-MM-DD <unit>: test <file> <name> was wrong: <why>. Class: change; after code: test ruled wrong.`

Any spec commit made after code on the same branch (an accepted stop, a test ruled wrong, a fix after a blocker or a reviewer FAIL) ends its line with `; after code: <reason>`.

Gate 3 shows this log next to `git diff <approved_spec_commit>..HEAD` of the spec files.

## Log
- 2026-10-30 brief: the UI becomes a local three-page results website (landing with a halftone wordmark headline, highest scores, training with live curves and dials), styled from Nico's screenshots and his pasted 21st.dev component in `inputs/`; agents still never install from the 21st.dev registry. Learning path step 3, Goal, tools and Risks 8 in brief [[brief]]. Why: Nico asked for it in session on 2026-10-30 (`inputs/website-request.md`) and said he will provide screenshots for the 21st.dev design. Class: change.
