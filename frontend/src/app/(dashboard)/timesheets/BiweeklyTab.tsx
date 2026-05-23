// frontend/src/app/(dashboard)/timesheets/BiweeklyTab.tsx
'use client'

import AggregateTab, { type AggregateTabProps } from './AggregateTab'

type Props = Omit<AggregateTabProps, 'period'>

export default function BiweeklyTab(props: Props) {
  return <AggregateTab period="biweekly" {...props} />
}
