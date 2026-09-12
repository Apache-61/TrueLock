# Graph analysis & visualization research

## Canonical graph shape

```
NODES:  COMPANY, SUPPLIER, INVOICE, PAYMENT, ACCOUNT, TRANSACTION
EDGES:
  COMPANY  --ISSUED-->      INVOICE
  SUPPLIER --ISSUED-->      INVOICE
  INVOICE  --PAID_BY-->     PAYMENT
  PAYMENT  --SETTLED_AS-->  TRANSACTION
  ACCOUNT  --SENT-->        TRANSACTION
  TRANSACTION --TO-->       ACCOUNT
  COMPANY  --OWNS/USES-->   ACCOUNT
```

## Operations needed

Traversal, shortest path, connected components, cycle detection, degree,
fan-in, fan-out, time-bounded path search. All standard NetworkX
operations — no custom graph algorithm work expected.

## Analysis engine: NetworkX

In-process, no service to deploy, fast enough for hackathon-scale data. A
graph database (Neo4j etc.) is explicitly not used unless the dataset or
measured performance proves NetworkX insufficient — see
`research/rejected-ideas/README.md` and the "NetworkX" row in
`history/experiments/README.md`.

## Visualization: Cytoscape.js

Purpose-built for entity/relationship graphs, works well embedded in a
Next.js frontend. Fallback if rendering becomes a time sink: a plain
table/path view (see `research/infrastructure/README.md`'s
fallback matrix).

## Frontend graph screen requirements

Entities, relationships, and the highlighted suspicious path must be
visible together — see `docs/demo/runbook.md` step 5 and
`docs/contracts/api.md` for the `/graph/:id` shape.
