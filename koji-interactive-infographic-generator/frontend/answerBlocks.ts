export interface AnswerBlock { kind: "heading" | "paragraph" | "list"; text: string; marker?: string }

/** Presentation only: preserve answer order, wording and evidence citations. */
export function answerBlocks(answer: string): AnswerBlock[] {
  return answer.replace(/\r\n/g, "\n").split("\n").flatMap<AnswerBlock>(line => {
    const text = line.trim();
    if (!text) return [];
    const heading = text.match(/^#{1,6}\s+(.+)$/) || text.match(/^\*\*(.+?)\*\*\s*:?$/);
    if (heading) return [{ kind: "heading" as const, text: heading[1].replace(/:$/, "") }];
    const list = text.match(/^([-*•]|\d+[.)])\s+(.+)$/);
    if (list) return [{ kind: "list" as const, marker: /^\d/.test(list[1]) ? list[1] : "•", text: list[2] }];
    const section = text.match(/^([A-Za-z][A-Za-z /'-]{1,65}):\s*(.*)$/);
    if (section) return [{ kind: "heading" as const, text: section[1] }, ...(section[2] ? [{ kind: "paragraph" as const, text: section[2] }] : [])];
    return [{ kind: "paragraph" as const, text }];
  });
}
