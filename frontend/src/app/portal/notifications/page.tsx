// frontend/src/app/portal/notifications/page.tsx
// Redirect for backward compatibility with old bookmarks and links.
// Notifications now live at /portal?tab=notifications.
import { redirect } from 'next/navigation'

export default function PortalNotificationsRedirect() {
  redirect('/portal?tab=notifications')
}
