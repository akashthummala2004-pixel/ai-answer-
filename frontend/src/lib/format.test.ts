import { describe, expect, it } from 'vitest';
import { formatErrorDetail } from './api';
import { effectiveVerdict, formatPercent, highlightClaims, scoreTone } from './format';

describe('format helpers', () => {
  it('formats percentages and missing values', () => {
    expect(formatPercent(0.856)).toBe('86%');
    expect(formatPercent(null)).toBe('—');
  });

  it('prefers the reviewer verdict over the system verdict', () => {
    expect(effectiveVerdict({ verdict: 'uncertain', review: null })).toBe('uncertain');
    expect(
      effectiveVerdict({ verdict: 'uncertain', review: { verdict: 'supported', note: '', reviewer: null, reviewed_at: '' } }),
    ).toBe('supported');
  });

  it('maps reliability scores to tones', () => {
    expect(scoreTone(90)).toBe('good');
    expect(scoreTone(60)).toBe('warning');
    expect(scoreTone(10)).toBe('critical');
    expect(scoreTone(null)).toBe('neutral');
  });

  it('highlights claim text found verbatim in the answer', () => {
    const segs = highlightClaims('Paris is in France. It is big.', [
      { id: 'C1', text: 'Paris is in France.' },
      { id: 'C2', text: 'Not present' },
    ]);
    expect(segs).toEqual([
      { text: 'Paris is in France.', claimId: 'C1' },
      { text: ' It is big.', claimId: null },
    ]);
  });

  it('formats FastAPI validation errors', () => {
    expect(formatErrorDetail([{ loc: ['body', 'answer'], msg: 'too short' }])).toBe('answer: too short');
    expect(formatErrorDetail('Plain message')).toBe('Plain message');
  });
});
