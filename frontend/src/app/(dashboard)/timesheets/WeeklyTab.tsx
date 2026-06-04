// frontend/src/app/(dashboard)/timesheets/WeeklyTab.tsx
'use client'

import AggregateTab, { type AggregateTabProps } from './AggregateTab'

type Props = Omit<AggregateTabProps, 'period'>

export default function WeeklyTab(props: Props) {
  return <AggregateTab period="weekly" {...props} />
}
