// path: frontend/src/lib/concierge/assembleSSEStream.test.ts
//
// Regression test for the SSE reassembly bug found and fixed on 2026-06-19.
// Run with: node --test --import tsx src/lib/concierge/assembleSSEStream.test.ts
//
// This test exists specifically to prevent words from ever being silently
// glued together across SSE line boundaries again (e.g. "Two" + "engagements"
// arriving as separate lines must never reassemble as "Twoengagements").

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { assembleSSELines } from './assembleSSEStream'

test('preserves a line break between two consecutive data lines', () => {
  const rawLines = ['data: Two', 'data: engagements are overdue.']
  const result = assembleSSELines(rawLines)
  assert.equal(result, 'Two\nengagements are overdue.')
})

test('does not glue words together across a line boundary (the exact bug found in production)', () => {
  const rawLines = ['data: Two', 'data: engagements are past their deadlines']
  const result = assembleSSELines(rawLines)
  assert.ok(!result.includes('Twoengagements'), `Bug regressed: got "${result}"`)
})

test('does not corrupt a year number split across lines', () => {
  // Reproduces the "20262" bug seen in production where a digit from a
  // following line bled into a year number from a preceding line.
  const rawLines = ['data: due March 15, 2026', 'data: 2. Next item']
  const result = assembleSSELines(rawLines)
  assert.ok(!result.includes('20262'), `Bug regressed: got "${result}"`)
})

test('ignores non-data lines (blank lines, comments)', () => {
  const rawLines = ['data: Hello', '', 'data: world']
  const result = assembleSSELines(rawLines)
  assert.equal(result, 'Hello\nworld')
})

test('collapses 3+ consecutive newlines down to a paragraph break', () => {
  const rawLines = ['data: First section', 'data: ', 'data: ', 'data: Second section']
  const result = assembleSSELines(rawLines)
  assert.equal(result, 'First section\n\nSecond section')
})

test('strips a single trailing newline', () => {
  const rawLines = ['data: Final line']
  const result = assembleSSELines(rawLines)
  assert.equal(result, 'Final line')
  assert.ok(!result.endsWith('\n'))
})

test('reassembles correctly regardless of how the same text is chunked across network boundaries', () => {
  // Simulates the real-world scenario: the same backend message arriving in
  // different chunk sizes depending on network conditions. The final
  // reassembled text must be identical regardless of how it was split.
  const fullText = 'Three engagements are overdue.\nReview them in the Dashboard.'
  const linesAsOneEventEach = fullText.split('\n').map((l) => `data: ${l}`)

  const result = assembleSSELines(linesAsOneEventEach)
  assert.equal(result, fullText)
})
