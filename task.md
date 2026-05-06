STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Visual feedback in firm chat compose box when @mention is active

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

When the @mention popover is showing (showMentionPopover is true),
change the compose textarea border color to brand blue to signal
an active mention. When the popover closes (mention selected or
dismissed), border returns to normal.

Find the compose textarea — it has this className:
  "flex-1 resize-none bg-surface-input dark:bg-dark-page border border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors overflow-hidden"

Change the className to use a template literal that applies
border-[#4A7FA5] when showMentionPopover is true:

  className={`flex-1 resize-none bg-surface-input dark:bg-dark-page border ${
    showMentionPopover
      ? 'border-[#4A7FA5]'
      : 'border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5]'
  } rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors overflow-hidden`}

Also: after a mention is selected via handleMentionSelect, the
composed text now contains @Name. To make it slightly more visible
in the textarea, add a subtle background tint to the textarea when
composeMentionIds.length > 0 (mentions have been added):

Combine both conditions:

  className={`flex-1 resize-none border ${
    showMentionPopover
      ? 'border-[#4A7FA5] bg-[#EFF6FF] dark:bg-[#1e2a3a]'
      : composeMentionIds.length > 0
        ? 'bg-[#EFF6FF] dark:bg-[#1e2a3a] border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5]'
        : 'bg-surface-input dark:bg-dark-page border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5]'
  } rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors overflow-hidden`}

Show the updated textarea className after the change.