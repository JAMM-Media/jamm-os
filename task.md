## Current Task — Add JAMM PX favicon

The logo file is at: C:\Users\Andre\Downloads\JAMM-Media\JAMM OS Build\jamm_px_mobile_logo.svg

### Step 1
Copy the SVG file to frontend/public/favicon.svg
Also copy it to frontend/public/logo.svg

### Step 2
In frontend/src/app/layout.tsx, find the existing metadata export and add or update the icons field:

export const metadata: Metadata = {
  title: 'JAMM PX',
  description: 'Practice Experience Platform',
  icons: {
    icon: '/favicon.svg',
    apple: '/logo.svg',
  },
}

Read the file first to see the exact current metadata object and preserve everything in it — only add the icons field.

### Step 3
Delete frontend/public/favicon.ico if it exists — the SVG will replace it.

### Step 4
Report back what was changed.

No pytest needed for this task.