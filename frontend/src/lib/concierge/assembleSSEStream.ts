// path: frontend/src/lib/concierge/assembleSSEStream.ts
//
// Pure function that reassembles a JAMM Concierge SSE stream into a single
// string, preserving the original line breaks the backend intentionally
// splits across separate "data:" events.
//
// Extracted from ConciergePanel.tsx so this logic can be tested in isolation
// without React, fetch, or the DOM. Do not duplicate this logic inline
// anywhere else -- import this function instead.

export interface SSELineEvent {
  /** Raw line as it would arrive over the wire, e.g. "data: Hello" */
  raw: string
}

/**
 * Given an array of raw SSE lines (each one a single "data: ..." line as
 * received from the network, in order, already split on \n by the caller),
 * reassemble them into the final text the backend intended to send.
 *
 * The backend sends each line of the original multi-line text as a separate
 * "data:" SSE event. This function must preserve a line break between every
 * consecutive data line, then collapse any resulting excess blank lines
 * (3+ consecutive newlines) down to a single paragraph break, and trim a
 * single trailing newline if present.
 */
export function assembleSSELines(rawLines: string[]): string {
  let assembled = ''
  for (const line of rawLines) {
    if (line.startsWith('data:')) {
      const chunk = line.replace(/^data:\s*/, '')
      assembled += chunk + '\n'
    }
  }
  return assembled.replace(/\n{3,}/g, '\n\n').replace(/\n$/, '')
}
