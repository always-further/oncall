# Oncall User Guide

## What is oncall?

oncall is a shift tracker for your team. When you're the oncall engineer, you start a shift in Slack, log the tickets you work on, add notes as you go, and end the shift when you're done. Everything shows up on a shared dashboard so the team has visibility into oncall activity.

## Getting started

### Log in to the dashboard

1. Go to [https://oncall.alwaysfurther.io](https://oncall.alwaysfurther.io)
2. Click **Log in with GitHub**
3. Authorize the app with your GitHub account

You need to be a member of the **always-further** GitHub org to access the dashboard.

<!-- SCREENSHOT: login page with "Log in with GitHub" button -->

## Slack commands

| Command | What it does |
|---|---|
| `/oncall` | Start your oncall shift |
| `/oncall-ticket <url>` | Log a ticket — it becomes your active ticket |
| `/oncall-ticket #123` | Switch back to a previously logged ticket |
| `/oncall-note <text>` | Add a note to your active ticket (or to the shift if no ticket is active) |
| `/offcall` | End your shift and post a summary to the channel |

## A day in the life

### 1. Start your shift

When your oncall rotation begins, open the relevant Slack channel and type:

```
/oncall
```

You'll get a confirmation message (only visible to you). Your shift is now live and will appear in the **Active Shifts** section of the dashboard.

<!-- SCREENSHOT: active shift card on dashboard showing user name and elapsed time -->

### 2. Pick up a ticket

When you start working on something, log it:

```
/oncall-ticket https://github.com/always-further/nono/issues/434
```

This does two things:
- Logs the ticket to your shift
- Makes it your **active ticket** — any notes you add will be attached to it

You'll see a confirmation like:

> Ticket logged: #434 (now active). Use `/oncall-note` to add notes to this ticket.

### 3. Add notes as you work

As you investigate and work on the ticket, log what you're doing:

```
/oncall-note assigned myself, looking at the logs
```

```
/oncall-note found the root cause - missing env var on prod-api-3
```

```
/oncall-note fixed, made a PR - please review next on shift
```

Each note is timestamped and attached to the active ticket (#434 in this case). On the dashboard, they show up as a threaded timeline under that ticket.

### 4. Move to the next ticket

When a new issue comes in, log it the same way:

```
/oncall-ticket https://github.com/always-further/nono/issues/441
```

This becomes your new active ticket. Notes now go to #441.

### 5. Switch back to a previous ticket

Need to add a follow-up note to an earlier ticket? Switch back by issue number:

```
/oncall-ticket #434
```

> Switched to #434. Notes will attach to this ticket.

Now `/oncall-note` goes to #434 again.

### 6. General notes (no ticket)

If you want to log something that isn't tied to a specific ticket — like a quiet period or helping a colleague — just use `/oncall-note` when no ticket is active (before logging your first ticket), or it'll attach to whatever ticket is currently active. General shift notes show separately on the dashboard.

```
/oncall-note quiet shift, reviewed alerts dashboard and updated runbook
```

### 7. End your shift

When your oncall rotation is over:

```
/offcall
```

This posts a summary to the channel, grouped by ticket:

> **Oncall shift ended for @luke**
> Duration: 8h 23m
>
> **Tickets (2):**
>   **#434** - https://github.com/always-further/nono/issues/434
>     - assigned myself, looking at the logs
>     - found the root cause - missing env var on prod-api-3
>     - fixed, made a PR - please review next on shift
>   **#441** - https://github.com/always-further/nono/issues/441
>     - investigating, looks like a flaky test in CI
>     - confirmed flaky, added retry - monitoring

<!-- SCREENSHOT: offcall summary message posted in Slack channel -->

## The dashboard

The dashboard at [https://oncall.alwaysfurther.io](https://oncall.alwaysfurther.io) gives you an overview of all oncall activity.

<!-- SCREENSHOT: full dashboard view -->

### What you'll see

- **Stats bar** — total shifts, total hours, and average hours per shift across the team
- **Active shifts** — who's currently oncall and how long they've been on
- **Shift history** — completed shifts with user, start/end times, duration, and ticket count. Click any row to expand and see the tickets with their threaded notes
- **Hours by user** — a breakdown of average oncall hours per person

The dashboard refreshes automatically every 30 seconds.

## Example shift

Here's a complete example of a typical oncall shift:

```
/oncall

/oncall-ticket https://github.com/always-further/nono/issues/434
/oncall-note PagerDuty alert - 5xx spike on checkout service
/oncall-note checked logs, bad deploy v2.3.1 - missing DATABASE_POOL_SIZE env var
/oncall-note rolled back to v2.3.0, error rate back to normal
/oncall-note root cause PR: added env var to deploy config, tagged for review

/oncall-ticket https://github.com/always-further/nono/issues/441
/oncall-note flaky test blocking main branch
/oncall-note added retry logic, tests passing now - merged

/oncall-ticket #434
/oncall-note PR reviewed and merged by @sarah, deploying v2.3.2

/offcall
```

## Tips

- **Log as you go.** Don't wait until the end of your shift. It's easier to capture context in the moment.
- **Be specific.** "Fixed thing" is less useful than "Rolled back deploy v2.3.1 after 5xx spike, root cause was missing env var".
- **One shift at a time.** You can't start a new shift if you already have one active. Use `/offcall` first.
- **Multiple people can be oncall.** Primary and secondary oncall can both have active shifts simultaneously.
- **Use ticket switching.** If you need to go back to an earlier ticket to add a follow-up note, use `/oncall-ticket #123` instead of re-logging the URL.

## Quick reference

```
/oncall                              Start shift
/oncall-ticket <github issue url>    Log a ticket (becomes active)
/oncall-ticket #123                  Switch to a previous ticket
/oncall-note <what you did>          Add a note (to active ticket or shift)
/offcall                             End shift + post summary
```
