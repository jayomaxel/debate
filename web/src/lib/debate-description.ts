export interface DebateDescriptionMeta {
  raw: string;
  rounds: string;
  roundsInfo: string;
  knowledgePoints: string[];
  knowledgePointsText: string;
  hasStructuredMeta: boolean;
}

type ParsedStructuredMeta = {
  rounds?: string;
  knowledgePoints?: string[];
  summary?: string;
  hasStructuredMeta: boolean;
};

const ROUNDS_LABEL_PATTERN = /^(?:发言轮次|轮次)\s*[:：]\s*(.+)$/i;
const KNOWLEDGE_LABEL_PATTERN = /^(?:支撑知识点|知识点)\s*[:：]\s*(.*)$/i;
const BULLET_PREFIX_PATTERN = /^[-*•]\s*/;
const JSON_START_PATTERN = /^\s*\{/;

function sanitizeText(value: unknown): string {
  if (typeof value !== 'string') {
    return '';
  }

  return value.trim();
}

function normalizeRounds(value: unknown): string {
  const text =
    typeof value === 'number' ? String(value) : sanitizeText(value);
  if (!text) {
    return '';
  }

  const matched = text.match(/\d+/);
  return matched ? matched[0] : text;
}

function normalizeKnowledgePoints(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => sanitizeText(item))
      .filter(Boolean);
  }

  const text = sanitizeText(value);
  if (!text) {
    return [];
  }

  return text
    .split(/[\r\n,，;；、]+/)
    .map((item) => sanitizeText(item))
    .filter(Boolean);
}

function parseJsonStructuredMeta(raw: string): ParsedStructuredMeta | null {
  if (!JSON_START_PATTERN.test(raw)) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const rounds = normalizeRounds(parsed.rounds);
    const knowledgePoints = normalizeKnowledgePoints(
      parsed.knowledgePoints ?? parsed.knowledge_points
    );
    const summary = sanitizeText(
      parsed.summary ?? parsed.description ?? parsed.note
    );

    if (!rounds && knowledgePoints.length === 0 && !summary) {
      return null;
    }

    return {
      rounds,
      knowledgePoints,
      summary,
      hasStructuredMeta: true,
    };
  } catch {
    return null;
  }
}

function parseLabeledStructuredMeta(raw: string): ParsedStructuredMeta | null {
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return null;
  }

  let rounds = '';
  const knowledgePoints: string[] = [];
  const summaryLines: string[] = [];
  let collectingKnowledgePoints = false;

  for (const line of lines) {
    const roundsMatch = line.match(ROUNDS_LABEL_PATTERN);
    if (roundsMatch) {
      rounds = normalizeRounds(roundsMatch[1]);
      collectingKnowledgePoints = false;
      continue;
    }

    const knowledgeMatch = line.match(KNOWLEDGE_LABEL_PATTERN);
    if (knowledgeMatch) {
      knowledgePoints.push(...normalizeKnowledgePoints(knowledgeMatch[1]));
      collectingKnowledgePoints = knowledgeMatch[1].trim().length === 0;
      continue;
    }

    if (collectingKnowledgePoints) {
      if (BULLET_PREFIX_PATTERN.test(line)) {
        knowledgePoints.push(
          ...normalizeKnowledgePoints(line.replace(BULLET_PREFIX_PATTERN, ''))
        );
        continue;
      }

      collectingKnowledgePoints = false;
    }

    summaryLines.push(line);
  }

  const summary = summaryLines.join('\n').trim();
  if (!rounds && knowledgePoints.length === 0) {
    return null;
  }

  return {
    rounds,
    knowledgePoints,
    summary,
    hasStructuredMeta: true,
  };
}

export function parseDebateDescription(
  description?: string | null
): DebateDescriptionMeta {
  const raw = sanitizeText(description);
  const emptyResult: DebateDescriptionMeta = {
    raw: '',
    rounds: '',
    roundsInfo: '',
    knowledgePoints: [],
    knowledgePointsText: '',
    hasStructuredMeta: false,
  };

  if (!raw) {
    return emptyResult;
  }

  const parsed =
    parseJsonStructuredMeta(raw) ?? parseLabeledStructuredMeta(raw);

  if (!parsed) {
    return {
      ...emptyResult,
      raw,
    };
  }

  const knowledgePoints = normalizeKnowledgePoints(parsed.knowledgePoints);
  const rounds = normalizeRounds(parsed.rounds);
  const summary = sanitizeText(parsed.summary) || raw;

  return {
    raw: summary,
    rounds,
    roundsInfo: rounds ? `发言轮次：${rounds}轮` : '',
    knowledgePoints,
    knowledgePointsText: knowledgePoints.join('、'),
    hasStructuredMeta: parsed.hasStructuredMeta,
  };
}

export function buildDebateDescription(
  rounds?: string | number,
  knowledgePoints?: string | string[]
): string {
  const normalizedRounds = normalizeRounds(rounds);
  const normalizedKnowledgePoints = normalizeKnowledgePoints(knowledgePoints);
  const lines: string[] = [];

  if (normalizedRounds) {
    lines.push(`发言轮次：${normalizedRounds}轮`);
  }

  if (normalizedKnowledgePoints.length > 0) {
    lines.push(`支撑知识点：${normalizedKnowledgePoints.join('、')}`);
  }

  return lines.join('\n').trim();
}
