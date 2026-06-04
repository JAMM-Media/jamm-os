// frontend/src/app/(dashboard)/timesheets/QuarterlyTab.tsx
'use client'

import AggregateTab, { type AggregateTabProps } from './AggregateTab'

type Props = Omit<AggregateTabProps, 'period'>

export default function QuarterlyTab(props: Props) {
  return <AggregateTab period="quarterly" {...props} />
}
