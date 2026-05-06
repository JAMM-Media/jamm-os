STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Bold @mention chips in firm chat messages

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

Find this span in the renderBody function:
  <span
    key={key++}
    className="bg-status-blue text-status-blue-text rounded px-1"
  >

Change to:
  <span
    key={key++}
    className="bg-status-blue text-status-blue-text rounded px-1 font-medium"
  >

That is the only change needed.