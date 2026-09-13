import assert from "node:assert/strict";
import { canAskQuestion, formatEvidenceRefs, isGroundedAnswer } from "../lib/investigationUi.mjs";

assert.equal(canAskQuestion(null, "why?", false), false);
assert.equal(canAskQuestion("CASE-1", "", false), false);
assert.equal(canAskQuestion("CASE-1", "why?", true), false);
assert.equal(canAskQuestion("CASE-1", "why?", false), true);

assert.match(formatEvidenceRefs([]), /insufficiency/i);
assert.equal(formatEvidenceRefs(["EV-1", "EV-2"]), "Evidence refs: EV-1, EV-2");

assert.equal(isGroundedAnswer("INSUFFICIENT_EVIDENCE", []), true);
assert.equal(isGroundedAnswer("See EV-9", ["EV-1"]), false);
assert.equal(isGroundedAnswer("Claim backed by EV-1", ["EV-1"]), true);

console.log("investigationUi tests passed");
