## Automation Presets > Overview > What Automation Presets Are

Automation presets are pre-built rules that fire automatically when specific events occur in JAMM PX. Each preset has a trigger, a set of actions, and an on or off state. When a preset is enabled and its trigger condition is met, the actions run without any staff involvement.

Every firm gets 16 presets seeded automatically when the account is created. Some are on by default. Others are off and must be enabled to activate.

Navigate to Settings in the left sidebar and select Automations to manage presets.

---

## Automation Presets > Overview > How Presets Work

A preset watches for a specific event. When that event occurs, the preset runs its actions in order. Actions can send an email to a client, send a notification to a staff member, create a task, or create a draft invoice.

Each preset shows its execution count and the date it last fired. This tells you how active each preset is and whether it has been triggered recently.

Presets fire for new activity going forward from when they are enabled. Enabling a preset does not retroactively fire it against existing records.

---

## Automation Presets > Overview > Managing Presets

Navigate to Settings and select Automations. Each preset is listed with its name, description, trigger, and an on or off toggle. Enable or disable each preset individually.

To reset a preset to its original default actions, select Reset to Default. This restores the preset to the configuration it had when the firm was created.

---

## Automation Presets > Overview > Recommended Presets to Enable First

The three highest-value presets for most firms to enable in the first week are Notify Staff When Documents Are Complete, Auto-Create Invoice on Engagement Completion, and Return Completed: Client Delivery Loop. These three handle the most common manual follow-up tasks that firms do after finishing work.

For tax firms, also enable 1040 Season Kickoff and Extension Filed Auto-Notify. For bookkeeping firms, also enable Recurring Engagement Kickoff Notification.

---

## Automation Presets > Preset Reference > Preset 1: Document Request Reminder

Name: Document Request Reminder (3-day). Default state: on.

Trigger: a document request is created. Action: sends a reminder email to the client 3 days after the request is created, if the request is still pending.

Use this to reduce manual follow-up on outstanding document requests. The reminder goes out automatically if the client has not uploaded anything within 3 days.

---

## Automation Presets > Preset Reference > Preset 2: E-Signature Reminder

Name: E-Signature Reminder (2-day). Default state: on.

Trigger: an engagement letter is sent for signature. Action: sends a reminder email to the client 2 days after the letter is sent, if it has not yet been signed.

Use this to reduce manual follow-up on unsigned engagement letters.

---

## Automation Presets > Preset Reference > Preset 3: Overdue Task Alert to Staff

Name: Overdue Task Alert to Staff. Default state: on.

Trigger: a task is assigned. Action: sends a notification to the assigned staff member when the task becomes overdue.

Use this to keep staff aware of tasks that have passed their due date without being completed.

---

## Automation Presets > Preset Reference > Preset 4: Auto-Create Invoice on Engagement Completion

Name: Auto-Create Invoice on Engagement Completion. Default state: off.

Trigger: an engagement is marked completed. Action: automatically creates a draft invoice for the engagement with a due date 30 days from the completion date.

Enable this for firms that bill on completion. The draft invoice requires review and sending before the client receives it. It does not send automatically.

---

## Automation Presets > Preset Reference > Preset 5: New Client Welcome Email

Name: New Client Welcome Email. Default state: on.

Trigger: a new client is created. Action: sends a welcome email to the client.

This fires as soon as a client record is created. If you are importing clients in bulk, consider disabling this preset before the import and re-enabling it afterward.

---

## Automation Presets > Preset Reference > Preset 6: Notify Staff When Documents Are Complete

Name: Notify Staff When Documents Are Complete. Default state: off.

Trigger: a document request is completed. Action: sends a notification to the assigned staff member that the client has uploaded all requested documents.

Enable this so staff know immediately when a client finishes uploading, without having to check manually. This is one of the highest-value presets for reducing response lag.

---

## Automation Presets > Preset Reference > Preset 7: Invoice Overdue Reminder

Name: Invoice Overdue Reminder. Default state: on.

Trigger: an invoice becomes overdue. Action: sends a payment reminder email to the client.

This fires once when the invoice first becomes overdue. For an escalating sequence that sends multiple reminders over two weeks, see Preset 12.

---

## Automation Presets > Preset Reference > Preset 8: Recurring Engagement Kickoff Notification

Name: Recurring Engagement Kickoff Notification. Default state: off.

Trigger: a recurring engagement is automatically created. Action: sends a notification to the assigned staff member that a new recurring engagement is ready for review.

Enable this for firms using recurring engagement templates for monthly bookkeeping or quarterly payroll, so staff are alerted when new work cycles spawn automatically.

---

## Automation Presets > Preset Reference > Preset 9: 1040 Season Kickoff

Name: 1040 Season Kickoff. Default state: off.

Trigger: an engagement is created. Actions: sends a welcome email to the client, creates a task to collect the prior year return, and creates a task to verify contact info and entity type.

Enable this for tax firms to automate the intake process for each new 1040 engagement. All three actions run automatically when the engagement is created.

---

## Automation Presets > Preset Reference > Preset 10: Extension Filed Auto-Notify

Name: Extension Filed Auto-Notify. Default state: on.

Trigger: an extension is filed. Actions: sends an extension confirmation email to the client and creates a task to prepare the return by the extended deadline.

This handles client communication and deadline tracking automatically when an extension is filed. The task ensures the extended deadline stays visible in the task list.

---

## Automation Presets > Preset Reference > Preset 11: IRS Authorization Expiry Warning

Name: IRS Authorization Expiry Warning. Default state: on.

Trigger: an IRS authorization is approaching expiry. Actions: sends a notification to staff, creates a task to renew the Form 8821 or 2848 before expiry, and sends a warning email to the client.

This is one of the most important presets for tax firms. IRS authorizations expire and losing access to transcripts mid-engagement creates significant delays. Keep this preset on.

---

## Automation Presets > Preset Reference > Preset 12: Invoice Overdue Escalating Sequence

Name: Invoice Overdue Escalating Sequence. Default state: on.

Trigger: an invoice becomes overdue. Actions: sends a payment reminder email on day 1, sends a follow-up email on day 7, and notifies the firm owner on day 14.

This preset and Preset 7 both respond to the invoice overdue trigger. Use this one if you want escalating follow-up over two weeks. Disable Preset 7 if you enable this one to avoid sending duplicate day-one reminders.

---

## Automation Presets > Preset Reference > Preset 13: Engagement Deadline Approaching 14-Day Alert

Name: Engagement Deadline Approaching -- 14-day Alert. Default state: on.

Trigger: an engagement deadline is approaching. Action: sends a notification to the assigned staff member 14 days before the engagement deadline.

Use this to give staff advance notice before deadlines arrive. The 14-day window gives enough time to complete outstanding tasks and request missing documents.

---

## Automation Presets > Preset Reference > Preset 14: Return Completed Client Delivery Loop

Name: Return Completed: Client Delivery Loop. Default state: off.

Trigger: an engagement is marked completed. Actions: creates a task to upload the final return to the client portal, generates a draft invoice from time entries, sends the client a return-ready email, and creates a follow-up task to confirm client acknowledgment within 5 days.

This is the highest-value preset for tax firms. It handles the entire post-completion workflow automatically. Enable it after configuring your fee schedule so the generated invoice reflects accurate amounts.

---

## Automation Presets > Preset Reference > Preset 15: New Client Full Onboarding Sequence

Name: New Client Full Onboarding Sequence. Default state: off.

Trigger: a new client is created. Actions: sends a portal welcome email, creates a task to schedule an onboarding call, and creates a task to collect entity documents.

If Preset 5 (New Client Welcome Email) is also enabled, both will fire when a client is created and the client will receive two emails. Disable Preset 5 if you enable this one to avoid duplicate welcome emails.

---

## Automation Presets > Preset Reference > Preset 16: Budget Variance Alert

Name: Budget Variance Alert. Default state: off.

Trigger: a client's actual spending deviates from their QBO budget by more than 15% in any category. Action: creates a task to review the budget variance, due within 3 days.

This preset requires a connected QuickBooks Online account with a budget configured for the client. It does not fire for clients without a QBO connection or without an active budget.

---

## Automation Presets > Preset Reference > Morning Briefing Preset

Name: Morning Briefing. Default state: off.

This preset controls the Morning Briefing feature. When enabled, JAMM PX generates a daily AI summary of the firm's current engagement status, incomplete items, and upcoming due dates when the firm owner opens the dashboard each morning.

The briefing fires once per day per firm. It does not fire again until 18 hours have passed since the last briefing. Enable this from Settings > Automations > Morning Briefing.

---

## Automation Presets > Troubleshooting > Preset Is Not Firing

If a preset is not firing when expected, check these things in order.

Confirm the preset is enabled. Navigate to Settings and select Automations. Find the preset and confirm its toggle is on.

Confirm the trigger condition has been met. Some presets require specific conditions such as a due date being set on the engagement, a document request being in pending status, or a QBO connection being active.

Check the execution count. If the count has not changed since the last expected firing, the trigger event did not occur or the preset conditions were not met.

Presets with delay actions such as the 3-day document reminder only fire after the delay period passes. The trigger must still be active when the delay expires.

---

## Automation Presets > Troubleshooting > Clients Receiving Duplicate Emails

If clients are receiving duplicate emails, two presets with overlapping triggers may both be enabled. The most common case is Preset 5 and Preset 15 both firing on client creation, or Preset 7 and Preset 12 both firing on invoice overdue.

Navigate to Settings and select Automations. Review which presets are enabled and identify any that share the same trigger. Disable the one you do not want to fire for that trigger.
