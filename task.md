TASK: Add firm_owner option to the Team tab invite dropdown

FILE TO EDIT: frontend/src/app/settings/page.tsx

WHAT TO CHANGE:

1. Find the inviteRole state declaration:
   const [inviteRole, setInviteRole] = useState<'staff' | 'manager'>('staff')

   Change it to:
   const [inviteRole, setInviteRole] = useState<'staff' | 'manager' | 'firm_owner'>('staff')

2. Find the role select dropdown in the invite form. It currently has two options:
   <option value="staff">Staff</option>
   <option value="manager">Manager</option>

   Add a third option above Staff:
   <option value="firm_owner">Firm Owner</option>

3. Find the onChange handler for the role select:
   onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager')}

   Update the cast to:
   onChange={(e) => setInviteRole(e.target.value as 'staff' | 'manager' | 'firm_owner')}

No other changes needed. The backend already accepts firm_owner as a valid role
from the POST /users/ endpoint. No API changes required. No backend changes required.