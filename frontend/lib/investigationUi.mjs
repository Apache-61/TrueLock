/**
 * @param {string | null | undefined} caseId
 * @param {string} question
 * @param {boolean} loading
 * @returns {boolean}
 */
export function canAskQuestion(caseId, question, loading) {
  return Boolean(caseId) && String(question || "").trim().length > 0 && !loading;
}

/**
 * @param {string[] | null | undefined} refs
 * @returns {string}
 */
export function formatEvidenceRefs(refs) {
  if (!refs || refs.length === 0) {
    return "No evidence refs — answer must state insufficiency.";
  }
  return `Evidence refs: ${refs.join(", ")}`;
}

/**
 * @param {string} answer
 * @param {string[]} refs
 * @returns {boolean}
 */
export function isGroundedAnswer(answer, refs) {
  if (!refs || refs.length === 0) {
    return /insufficient/i.test(answer || "");
  }
  return refs.some((ref) => String(answer || "").includes(ref)) || /Evidence refs:/i.test(answer || "");
}
