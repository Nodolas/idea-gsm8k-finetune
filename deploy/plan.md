# Deploy plan: test of interest

Learning projects: not used; Ready to ship writes results.md.

`/build` fills the `<...>` fields at Ready to ship, from `inception/brief.md` [[brief]]. Nico runs every command by hand. Agents never run them (charter rules 4 and 9); a deny rule refuses `wrangler deploy` in runs.

## Target
Cloudflare Workers, free plan: `https://idea-gsm8k-finetune.<account>.workers.dev`. Static assets, plus a small Worker that writes the waitlist to <D1 | KV | nothing>. No domain, no card. Needs Nico's own free Cloudflare account; agents never create accounts.

## Cost: EUR 0
- Free plan, no payment method on the account. At a free limit the Worker returns an error (1027) instead of billing.
- Static asset requests are free and unlimited; Worker code gets 100,000 requests a day and 10 ms CPU per request. D1 and KV have their own daily free limits. These numbers come from the factory's v1 research; check developers.cloudflare.com/workers/platform/limits on deploy day.
- No live Claude calls (rule 4: no API keys). The test is a <fake door | waitlist | demo video | concierge test>.

## Interest metric
- Hypothesis: At least <X>% of <Y> will <Z> within <T>.
- Metric: <what is counted>. Threshold: <number>. Deadline: <YYYY-MM-DD>.
- If by the deadline the metric is below the threshold, Nico kills the ticket: `gate:kill` and `kill: falsified <words>`.

## Where Nico reads it
- Cloudflare dashboard > Workers & Pages > `idea-gsm8k-finetune` > Metrics: requests per day.
- Waitlist rows (D1 only): `npx wrangler d1 execute idea-gsm8k-finetune --remote --command "SELECT COUNT(*) FROM <table>"`

## Nico's commands
In a Mint terminal, in `~/Projects/idea-gsm8k-finetune` (wrangler is a project dev dependency, rule 7):
```bash
git pull --ff-only
npm ci
npx wrangler login                                    # once: browser login to the free Cloudflare account
npx wrangler d1 create idea-gsm8k-finetune                  # D1 only: put the printed database_id into the wrangler config, commit
npx wrangler d1 execute idea-gsm8k-finetune --remote --file=<schema file>   # D1 only
npx wrangler deploy                                   # prints the workers.dev URL
```
Then open the URL once, add `gate:ship` to https://github.com/Nodolas/idea-factory/issues/6 and comment the URL in a new comment: `/build` reads the URL only from a comment newer than the `stage:ready-to-ship` label.

## Teardown
On a kill, or after the deadline:
```bash
npx wrangler delete idea-gsm8k-finetune
npx wrangler d1 delete idea-gsm8k-finetune                  # D1 only
```
