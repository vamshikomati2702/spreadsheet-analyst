# Test questions

Expected answers were checked by hand against `sample.csv`.

| # | Question | Expected answer | What it tests |
|---|---|---|---|
| 1 | How many tickets are tagged Urgent even though the customer says it's not urgent? | 2: tickets 4 (Enterprise) and 72 (Free). Four tickets say "not urgent" in total; the other two are tagged Low. | Comparing a column against what the text actually says |
| 2 | Which ticket mentions the biggest file, and what plan is that customer on? | A 4-way tie at 1,000,000 rows: tickets 4 (Enterprise), 46 (Starter), 52 (Free) and 91 (Pro). Only 21 of the 100 tickets mention a file size. | Pulling numbers with commas out of text, and reporting a tie instead of picking one |
| 3 | Do Free customers have smaller teams than Enterprise customers? | No. The data doesn't support it. Free averages 28 active users across 7 tickets, Enterprise 26.25 across 4. Only 21 tickets mention team size, so a good answer flags the evidence as thin. | Checking an assumption instead of confirming it, and being honest about sample size |
| 4 | For tickets about broken imports or garbled characters, which tool did customers export from most often? | Excel (3 tickets), ahead of HubSpot (2). But 19 of the 28 matching tickets don't name a source, and a good answer says so. | Grouping 6 different subject lines into one theme on its own, then extracting from text |
| 5 | What's the average time to resolve a billing ticket? | Can't be answered. The file has no dates or resolution data. | Saying "the data can't answer this" instead of inventing a number |

## Run how

```bash
python cli.py sample.csv "<question>"
```
