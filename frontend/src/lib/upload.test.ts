import { describe, expect, it } from 'vitest';
import { fileKind, formatBytes, validateFile } from './upload';

const mb = 1024 * 1024;

describe('upload validation', () => {
  it('recognises supported types by MIME or extension', () => {
    expect(fileKind({ name: 'a.pdf', type: 'application/pdf' })).toBe('pdf');
    expect(fileKind({ name: 'shot.WEBP', type: '' })).toBe('image');
    expect(fileKind({ name: 'notes.txt', type: 'text/plain' })).toBeNull();
  });

  it('enforces size, emptiness, duplicates and count', () => {
    expect(validateFile({ name: 'big.pdf', type: 'application/pdf', size: 11 * mb }, [])).toMatch(/10 MB/);
    expect(validateFile({ name: 'big.png', type: 'image/png', size: 6 * mb }, [])).toMatch(/5 MB/);
    expect(validateFile({ name: 'e.png', type: 'image/png', size: 0 }, [])).toMatch(/empty/);
    expect(validateFile({ name: 'a.png', type: 'image/png', size: 10 }, [{ name: 'a.png', size: 10 }])).toMatch(/already added/);
    const three = [1, 2, 3].map((n) => ({ name: `${n}.png`, size: n }));
    expect(validateFile({ name: 'x.png', type: 'image/png', size: 99 }, three)).toMatch(/up to 3/);
    expect(validateFile({ name: 'ok.jpg', type: 'image/jpeg', size: 2 * mb }, [])).toBeNull();
  });

  it('formats sizes', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2 KB');
    expect(formatBytes(3.5 * mb)).toBe('3.5 MB');
  });
});
