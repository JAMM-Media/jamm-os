// frontend/src/app/(dashboard)/timesheets/MonthlyTab.tsx
'use client'

import AggregateTab, { type AggregateTabProps } from './AggregateTab'

type Props = Omit<AggregateTabProps, 'period'>

export default function MonthlyTab(props: Props) {
  return <AggregateTab period="monthly" {...props} />
}
