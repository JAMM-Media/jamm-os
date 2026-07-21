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
 *
 * When the backend's leak filter or safety net corrects a response after
 * streaming has already begun, it sends a sentinel line whose data content
 * is exactly [FILTERED], followed by the corrected final text. If this
 * sentinel is found, everything up to and including the last occurrence is
 * discarded and only the lines after it are assembled. If no sentinel is
 * present, the function behaves exactly as before.
 */
export function assembleSSELines(rawLines: string[]): string {
  // Find the last [FILTERED] sentinel. Use last occurrence in case the
  // backend sends the marker more than once, as the final one represents
  // the most fully corrected version intended to be displayed.
  let startIndex = 0
  for (let i = rawLines.length - 1; i >= 0; i--) {
    const line = rawLines[i]
    if (line.startsWith('data:') && line.replace(/^data:\s*/, '').trim() === '[FILTERED]') {
      startIndex = i + 1
      break
    }
  }

  let assembled = ''
  for (const line of rawLines.slice(startIndex)) {
    if (line.startsWith('data:')) {
      const chunk = line.replace(/^data:\s*/, '')
      assembled += chunk + '\n'
    }
  }
  return assembled.replace(/\n{3,}/g, '\n\n').replace(/\n$/, '')
}
