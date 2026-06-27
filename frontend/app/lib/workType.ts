// Mirror of backend/services/work_type.py. Keep in sync.
const RAW_TO_CODE: Record<string, string> = {
  article: "article",
  review: "article",
  letter: "article",
  editorial: "article",
  book: "book",
  monograph: "book",
  "book-chapter": "book",
  "reference-entry": "book",
  dissertation: "thesis",
  preprint: "preprint",
  dataset: "dataset",
};

export const WORK_TYPE_CODES = [
  "article",
  "book",
  "thesis",
  "preprint",
  "dataset",
  "other",
  "unclassified",
] as const;

export function categoryFor(raw: string | null | undefined): string {
  if (raw == null) return "unclassified";
  return RAW_TO_CODE[raw.trim().toLowerCase()] ?? "other";
}
