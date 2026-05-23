// frontend/src/app/(dashboard)/timesheets/YearlyTab.tsx
'use client'

import AggregateTab, { type AggregateTabProps } from './AggregateTab'

type Props = Omit<AggregateTabProps, 'period'>

export default function YearlyTab(props: Props) {
  return <AggregateTab period="yearly" {...props} />
}
