# Retrieval proof

Run on 2026-11-19, session `c4d88638`, model `nvidia/nemotron-3.5-super-vl:free`.

## Question

```
pitu_agent.py "what did we decide about the Q3 launch?"
```

## Tool call

```
[model] CALL search_notes args={'question': 'Q3 launch decision'}
```

## Tool result

```
2026-09-14-q3-launch-sync.md: Launch moved to 12 October. We cut the analytics
dashboard from v1 and ship it in 3.1.
```

## Reply

```
Per 2026-09-14-q3-launch-sync.md: The Q3 launch was moved to 12 October, and the
analytics dashboard was cut from v1 (it will ship in 3.1 instead).
```

## Negative case

```
pitu_agent.py "what's our lunch policy?"
```

```
[model] CALL search_notes args={'question': 'lunch policy'}
[tools] NO_RELEVANT_NOTES
[model] I don't have any notes covering a lunch policy. The meeting notes I can
        search don't include information about it.
```

The model did not invent a policy. `parse_citations` also drops any filename not in
the corpus, so a hallucinated `c.md` becomes `NO_RELEVANT_NOTES` rather than an answer.
