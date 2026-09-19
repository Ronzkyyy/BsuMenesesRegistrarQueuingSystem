// Strips every character but ASCII digits 0-9, so a numeric-only field's
// model can't end up holding a letter or symbol no matter how it got typed
// (physical keyboard, paste, IME). `inputmode="numeric"` alone only hints
// the on-screen keyboard shown on mobile - it doesn't block a physical one,
// so it isn't enough by itself to keep the field numeric.
export function digitsOnly(value) {
  return (value ?? '').replace(/[^0-9]/g, '')
}
