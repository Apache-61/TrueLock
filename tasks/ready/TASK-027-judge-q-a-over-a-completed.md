# TASK-027: Judge Q&A over a completed case

- **type:** feature
- **priority:** P1
- **status:** READY
- **execution_mode:** auto
- **owner (area):** agent
- **depends_on:** TASK-026
- **human_authorization:** no

## Objective

Answer free-form questions about a completed case, grounded strictly in the evidence and decision log -- 'why do you think this supplier is fraudulent', 'what would change your mind', 'how did you find this'.

This is the demo's most exposed surface: it is answered live, in front of judges, on questions nobody scripted. Grounding is everything -- the correct answer to a question the evidence cannot support is to say so.

## Allowed paths

```
agent/qa/**
agent/prompts/qa.md
```

## Forbidden paths

```
frontend/**
detection/**
database/**
evidence/**
```

## Acceptance criteria

- [ ] Every answer cites the evidence or decision-log entries it rests on.
- [ ] A question the case cannot answer gets an explicit 'the evidence does not show that', never an invented answer.
- [ ] Answers are bounded in length and latency, so the demo does not stall.
- [ ] The Q&A cannot reach the answer keys -- it sees only what the investigation produced.

## Tests required

`tests/unit/` with a fixed case: an answerable question, an unanswerable one, and one whose premise is false.

## Documentation requirements

Update `agent/README.md`.
