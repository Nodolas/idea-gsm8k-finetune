# Team Allocation

Who builds each Bolt. A **Bolt** is one build pass over one unit of work, ending in something that runs (`bolt-plan.md`). A **mob** would normally be the small group that builds a Bolt together; this project has one human and one AI developer, so there is a single mob. The units are listed in `inception/units-generation/unit-of-work.md`, and the way of working is in `inception/practices-discovery/team-practices.md`. There was no team-formation stage in this scope.

## Allocation

| Bolt | Unit | Built by | Long runs started by | Checkpoint approved by |
|---|---|---|---|---|
| B1 | u1-eval-skeleton | AI developer (aidlc-developer-agent, Claude Code under `/build`) | none | Nico |
| B2 | u2-baselines | AI developer | Nico (5 runs) | Nico |
| B3 | u3-sft | AI developer | Nico (2 runs) | Nico |
| B4 | u4-run-service | AI developer | none | Nico |
| B5 | u5-website | AI developer | none | Nico |
| B6 | u6-final-and-report | AI developer | Nico (6 runs) | Nico |
| B7 | u7-grpo (Could) | AI developer | Nico (1 run) | Nico |
| B8 | u8-tuning (Could) | AI developer | Nico (1 study) | Nico |
| B9 | u9-ablations (Could) | AI developer | Nico (3 runs) | Nico |

## Roles

- **AI developer** (Claude Code as the `/build` lead):
  - writes each unit's tests first, then its code
  - runs the quick suite and the trace check
  - commits in the order `spec`, `test`, `feat`, `chore(state)`
  - fast-forwards `main` when green
  - lists pending long runs in `STATE.md`
  - never starts a run over about 10 minutes, and never answers AI-DLC's questions for Nico (project.md, Forbidden)
- **Nico:**
  - answers AI-DLC's questions and approvals
  - starts every long run from a terminal or the website with its attempt id
  - approves each unit's checkpoint
  - answers the learning check questions
  - provides the design screenshots before B5
- **Reviewers** (AI-DLC's architecture and product reviewers) give advisory reviews at each stage. They never commit.

Changed 2026-10-31: several builder agents build the units of a batch at the same time (`/build`). Original plan: one builder works on one unit at a time, so there are no hand-offs between mobs and no Program Board, the cross-team view of who builds what and when.
