# External Dependency Map

Everything a Bolt needs from outside the AI developer's own work. A **Bolt** is one build pass over one unit of work, ending in something that runs (`bolt-plan.md`). The project is local and costs nothing (`inception/requirements-analysis/requirements.md`, Constraints; `inception/practices-discovery/team-practices.md`, Deployment). There are no partner APIs, accounts, approvals or other teams. The units are in `inception/units-generation/unit-of-work.md`.

## Dependencies

| Dependency | Owner | Lead time | Blocks | If it slips |
|---|---|---|---|---|
| Public downloads: GSM8K, `Qwen/Qwen3-0.6B-Base`, `Qwen/Qwen3-1.7B-Base`, GSM-Plus, GSM-Symbolic, Python and npm packages | Hugging Face, PyPI, npm (public, no login) | Minutes, once; then cached in `.cache/` | B1 (GSM8K, 0.6B), B2 (1.7B), B5 (npm), B6 (GSM-Plus, GSM-Symbolic) | Retry later; nothing is paid or rate-limited for this use. A changed upstream dataset is caught by the saved split ids |
| Node.js under `.tools/node/` | Nico (OK'd in the brief) | Minutes | B5 | B5 waits; Python Bolts are unaffected |
| Nico's long runs (`STATE.md` `pending_runs`) | Nico | 10 minutes to 3 hours each, on this PC's GPU | B6 needs B2's baseline rows and B3's fine-tuned runs | B6 waits for the rows; all earlier Bolts proceed |
| Nico's design screenshots in `inputs/design/` | Nico | Whenever he adds them; one is there now | B5's Code Generation (AC4.1.3) | B5 builds structure and behaviour first; the look criterion stays open until they arrive |
| Nico's checkpoint approvals and answers to AI-DLC's questions | Nico | Per session | Every Bolt's close | The Bolt stays on its `wip/<unit>` branch until he approves |
| A finalist mark on a fine-tuned run | Nico, through the service or website | Seconds, after B3's runs and B4 or B5 | B6's final test score | B6 waits |

## Not Needed

No paid compute, no API keys, no accounts and no deploy targets (project.md, Forbidden). An item that turned out to need any of these would be a class `stop` blocker for Nico (`inception/changes.md`).
