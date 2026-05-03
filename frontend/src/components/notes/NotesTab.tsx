// frontend/src/components/notes/NotesTab.tsx
'use client'

interface NotesTabProps {
  unreadCount: number
  onClick: () => void
}

export function NotesTab({ unreadCount, onClick }: NotesTabProps) {
  return (
    <button
      onClick={onClick}
      aria-label="Open notes panel"
      style={{
        position: 'fixed',
        right: 0,
        top: '50%',
        transform: 'translateY(-50%)',
        width: 36,
        height: 80,
        borderRadius: '8px 0 0 8px',
        zIndex: 50,
        cursor: 'pointer',
        border: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      className="bg-brand dark:bg-brand-btn"
    >
      {/* Pencil icon */}
      <svg
        width="16"
        height="16"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M11.013 1.427a1.75 1.75 0 0 1 2.474 2.474L4.92 12.467l-3.468.462.462-3.468L11.013 1.427Zm1.06 1.414-.707-.707-9.2 9.2-.23 1.73 1.73-.23 8.407-8.993Z"
          fill="white"
        />
      </svg>

      {unreadCount > 0 && (
        <span
          style={{
            position: 'absolute',
            top: -6,
            left: -6,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: '#E24B4A',
            color: '#fff',
            fontSize: 11,
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            lineHeight: 1,
          }}
        >
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      )}
    </button>
  )
}
