STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix client messages compose box not visible

FILE TO EDIT: frontend/src/app/(dashboard)/clients/[id]/page.tsx

PROBLEM: The messages tab container uses h-[500px] with flex-col but
the compose box is not visible. The parent div wrapping the tab content
likely does not have a fixed height, so the flex container collapses.

FIX: Change the messages tab container to not rely on a fixed height.
Instead use a min-height and let the compose box always be visible.

Find:
  {activeTab === 'messages' && (
    <div className="flex flex-col h-[500px]">
      {/* Messages list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">

Change to:
  {activeTab === 'messages' && (
    <div className="flex flex-col" style={{ minHeight: 400 }}>
      {/* Messages list */}
      <div className="overflow-y-auto px-4 py-4 space-y-3" style={{ minHeight: 300 }}>

This removes flex-1 from the messages list so it doesn't consume all
available space, and gives the compose box room to always render below.

Show the updated container divs after the change.