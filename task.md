STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix firm chat send_message parameter mismatch

The router calls firm_chat_service.send_message with requesting_user=
and attachment_name=, attachment_size= but the service function signature
uses sender_user= and only has attachment_key=.

FILE TO EDIT: app/api/firm_chat.py

Find the send_message endpoint and fix the service call to match the
actual service signature:

    return firm_chat_service.send_message(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        sender_user=current_user,
        data=data,
        attachment_key=None,
    )

Remove attachment_name=None and attachment_size=None — they don't exist
on the service function.
Change requesting_user=current_user to sender_user=current_user.

Show the updated function after the change.