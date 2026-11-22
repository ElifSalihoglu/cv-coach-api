export interface Piece { text: string; changed: boolean }

const words = (text: string) => text.split(/\s+/).filter(Boolean);

/**
 * Word-level difference between two texts, for showing what was removed
 * (`before`) and what was added (`after`). Spacing is ignored (line breaks,
 * repeated and non-breaking spaces all split words the same way), but letters,
 * digits and case are compared exactly, so "3 years" vs "5 years" marks only the number.
 */
export function diffWords(before: string, after: string): { before: Piece[]; after: Piece[] } {
  const a = words(before);
  const b = words(after);
  // Longest common subsequence of words.
  const lcs: number[][] = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const outBefore: Piece[] = [];
  const outAfter: Piece[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      outBefore.push({ text: a[i], changed: false });
      outAfter.push({ text: b[j], changed: false });
      i++; j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      outBefore.push({ text: a[i++], changed: true });
    } else {
      outAfter.push({ text: b[j++], changed: true });
    }
  }
  while (i < a.length) outBefore.push({ text: a[i++], changed: true });
  while (j < b.length) outAfter.push({ text: b[j++], changed: true });
  return { before: outBefore, after: outAfter };
}
