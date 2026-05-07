STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix TypeScript error in NewClientModal

FILE TO EDIT: frontend/src/components/clients/NewClientModal.tsx

Find:
      const newClient = await clientsApi.create({
        name: form.name.trim(),
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        entity_type: form.entity_type || null,
      })

Change to:
      const newClient = await clientsApi.create({
        name: form.name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        entity_type: form.entity_type || undefined,
      })