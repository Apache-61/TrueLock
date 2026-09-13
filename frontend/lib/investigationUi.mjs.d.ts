export function canAskQuestion(
  caseId: string | null | undefined,
  question: string,
  loading: boolean
): boolean;

export function formatEvidenceRefs(refs: string[] | null | undefined): string;

export function isGroundedAnswer(answer: string, refs: string[]): boolean;
