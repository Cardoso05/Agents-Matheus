/**
 * Decode a Buffer trying UTF-8 first, falling back to Latin-1 (ISO-8859-1).
 * Many Brazilian banks (Itaú, Bradesco, BB) export CSV/OFX in Latin-1.
 */
export function decodeBuffer(buffer: Buffer): string {
  const utf8 = buffer.toString("utf-8");

  // Check for UTF-8 BOM
  if (utf8.charCodeAt(0) === 0xfeff) {
    return utf8.slice(1);
  }

  // Check for replacement character (U+FFFD) which indicates invalid UTF-8
  // Also check for common mojibake patterns from Latin-1 decoded as UTF-8
  if (utf8.includes("\uFFFD") || /Ã[£¡©]/g.test(utf8)) {
    return buffer.toString("latin1");
  }

  return utf8;
}
