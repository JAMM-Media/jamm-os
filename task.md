STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Add channel header bar with Members button to firm chat

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

Add a header bar to the active channel message feed. Currently the feed
goes straight from the channel list to messages with no header. The
header should show the channel name and a visible Members button.

Find this block inside the message feed section (inside the <> fragment
after the activeChannelId check):

  <>
    {/* Messages list */}
    <div className="flex-1 overflow-y-auto">

Add a channel header bar BEFORE the Messages list div:

  <>
    {/* Channel header */}
    <div
      className="flex-shrink-0 flex items-center justify-between px-4 border-b border-[#C8CDD6] dark:border-[#484848] bg-surface-page dark:bg-dark-page"
      style={{ height: 48 }}
    >
      <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
        #{activeChannel?.name ?? ''}
      </span>
      {isFirmOwner && (
        <button
          onClick={(e) => { e.stopPropagation(); openMembersModal(activeChannelId) }}
          className="flex items-center gap-1.5 h-7 px-3 rounded-md text-[12px] font-medium text-[#4A7FA5] border border-[#C8CDD6] dark:border-[#484848] hover:bg-[#D5D8DE] dark:hover:bg-dark-card transition-colors"
        >
          <Users className="w-[12px] h-[12px]" />
          Members
        </button>
      )}
    </div>

    {/* Messages list */}
    <div className="flex-1 overflow-y-auto">

Note: Users is already imported from lucide-react so no import change needed.

After making the change show the updated <> fragment opening so I can
verify the header is in the right place.