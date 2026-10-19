// path: frontend/src/app/(app)/settings/settingsStaffCopyWiring.test.ts
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const cwd = process.cwd()
if (!existsSync(join(cwd, 'package.json'))) {
  throw new Error('vitest must run from the frontend folder; cwd is ' + cwd)
}

function readSrc(relPath: string): string {
  return readFileSync(join(cwd, 'src', relPath), 'utf8').replace(/\r\n/g, '\n')
}

const SETTINGS_PAGE = 'app/(app)/settings/page.tsx'
const TEAM_PAGE = 'app/(app)/settings/team/page.tsx'
const DELETE_MODAL = 'components/settings/DeleteStaffModal.tsx'
const EDIT_MODAL = 'components/settings/EditStaffModal.tsx'
const CONCIERGE_PANEL = 'components/concierge/ConciergePanel.tsx'

// Retired user-facing strings from the rename gate. Code identifiers such as
// the tab key 'team', listTeam, refetchTeam and the /settings/team route are
// deliberately not listed here: they were kept on purpose.
const RETIRED: Array<[string, string[]]> = [
  [SETTINGS_PAGE, [
    "label: 'Team'",
    'Team member added.',
    '+ Add Team Member',
    '>Team Members<',
    "? 'member' : 'members'",
    'No team members yet',
  ]],
  [TEAM_PAGE, [
    'manage team members',
    '>Team<',
    '              Team Members\n',
    'No team members found',
  ]],
  [DELETE_MODAL, ['Delete Team Member', 'delete team member']],
  [EDIT_MODAL, ['Edit Team Member', 'update team member']],
  [CONCIERGE_PANEL, ['Invite Team Member form', 'Navigated to Team Settings']],
]

const PRESENT: Array<[string, string[]]> = [
  [SETTINGS_PAGE, [
    "{ key: 'team', label: 'Staff' }",
    'Staff member added.',
    '+ Add Staff Member',
    '>Staff</span>',
    "? 'staff member' : 'staff members'",
    'No staff members yet. Use the form to add your first staff member.',
  ]],
  [TEAM_PAGE, [
    'manage staff members.',
    '>Staff</span>',
    '>Staff</h1>',
    '              Staff\n            </span>',
    'No staff members found.',
  ]],
  [DELETE_MODAL, ['Delete Staff Member</span>', 'Failed to delete staff member.']],
  [EDIT_MODAL, ['title="Edit Staff Member"', 'Failed to update staff member.']],
  [CONCIERGE_PANEL, ['Invite Staff Member form', 'Navigated to Staff Settings']],
]

describe('settings staff copy wiring: source guards', () => {
  for (const [file, strings] of RETIRED) {
    for (const s of strings) {
      it('retired copy is gone from ' + file + ': ' + JSON.stringify(s), () => {
        expect(readSrc(file)).not.toContain(s)
      })
    }
  }

  for (const [file, strings] of PRESENT) {
    for (const s of strings) {
      it('Staff copy is present in ' + file + ': ' + JSON.stringify(s), () => {
        expect(readSrc(file)).toContain(s)
      })
    }
  }

  it('Delete Staff Member heading appears on both confirmation steps', () => {
    const src = readSrc(DELETE_MODAL)
    expect(src.split('Delete Staff Member</span>').length - 1).toBe(2)
  })

  it('the team tab key and the /settings/team route are untouched', () => {
    expect(readSrc(SETTINGS_PAGE)).toContain("setActiveTab('team')")
    expect(readSrc(CONCIERGE_PANEL)).toContain("'/settings/team': 'Settings'")
  })
})
