// frontend/src/components/layout/Breadcrumb.tsx

import Link from 'next/link'

interface BreadcrumbItem {
  label: string
  href?: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="flex items-center gap-1.5 text-[13px] mb-4">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && (
            <span className="text-[#9CA3AF]">/</span>
          )}
          {item.href ? (
            <Link
              href={item.href}
              className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-brand dark:text-[#EDEEF0] font-medium">
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  )
}
