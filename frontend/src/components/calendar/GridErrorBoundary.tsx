// path: frontend/src/components/calendar/GridErrorBoundary.tsx
'use client'
import React from 'react'

interface GEBProps {
  children?: React.ReactNode
  resetKey: string
}

interface GEBState {
  hasError: boolean
}

export class GridErrorBoundary extends React.Component<GEBProps, GEBState> {
  constructor(props: GEBProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): GEBState {
    return { hasError: true }
  }

  componentDidCatch(error: Error): void {
    console.error('Calendar grid failed to render', error)
  }

  componentDidUpdate(prev: Readonly<GEBProps>): void {
    if (this.state.hasError && prev.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false })
    }
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return (
        <div role="alert" className="flex-1 flex items-center justify-center text-[13px] text-muted-foreground px-4 text-center">The time grid could not be displayed. Switch to Month or Agenda, or reload the page.</div>
      )
    }
    return this.props.children
  }
}
