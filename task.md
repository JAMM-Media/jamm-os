STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix firm chat — ... dropdown Manage Members click not registering

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM: The ... button on channel rows is only visible when
isHovered === true. When the user moves the mouse from the channel row
to the dropdown menu, isHovered goes false, which hides the ... button.
This can cause the dropdown to flicker or the click to not register.

FIX: Change the ... button visibility condition so it shows when EITHER
the channel is hovered OR its dropdown is open.

Find this condition on the ... button:
  {isFirmOwner && isHovered && (
    <button
      onClick={(e) => {
        e.stopPropagation()
        setOpenDropdownId((prev) => (prev === ch.id ? null : ch.id))
      }}

Change it to:
  {isFirmOwner && (isHovered || openDropdownId === ch.id) && (
    <button
      onClick={(e) => {
        e.stopPropagation()
        setOpenDropdownId((prev) => (prev === ch.id ? null : ch.id))
      }}

This ensures the ... button stays visible while its dropdown is open,
preventing the dropdown from disappearing mid-interaction.

Also: the global mousedown handler closes the dropdown on any click
outside. The dropdown div has onMouseDown stopPropagation but the
individual menu buttons inside it do not. Add onMouseDown stopPropagation
to the Manage Members button inside the dropdown:

Find:
  <button
    onClick={(e) => { e.stopPropagation(); openMembersModal(ch.id) }}
    className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
  >
    Manage Members
  </button>

Change to:
  <button
    onClick={(e) => { e.stopPropagation(); openMembersModal(ch.id) }}
    onMouseDown={(e) => e.stopPropagation()}
    className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
  >
    Manage Members
  </button>

Show the updated ... button condition and the updated Manage Members
button after making changes.