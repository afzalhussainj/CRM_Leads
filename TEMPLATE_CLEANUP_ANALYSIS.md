# Template Cleanup Analysis

## Current Template Status

### ✅ Templates That Exist and Are Used

#### Email Templates (Still Needed - Used by Backend)
- `registration/password_reset_email.html` - ✅ Used in password reset
- `emails/follow_up_reminder.html` - ✅ Used for follow-up reminders
- `emails/follow_up_reminder.txt` - ✅ Used for follow-up reminders
- `common/user_delete_email.html` - ✅ Used in tasks.py
- `common/user_status.html` - ✅ Exists (may be used)
- `common/user_status_activate.html` - ✅ Exists
- `common/user_status_deactivate.html` - ✅ Exists
- `root_email_template_new.html` - ✅ Base email template
- `root_email_template.html` - ✅ Base email template

#### UI Templates (Potentially Obsolete - Moving to React)
- `dashboard.html` - ⚠️ Used by TemplateView (may be obsolete)
- `site_admin.html` - ⚠️ Used by SiteAdminView (may be obsolete)
- `ui/leads_list.html` - ⚠️ Used by LeadListUI (may be obsolete)
- `ui/leads_new.html` - ⚠️ Used by LeadCreateUI (may be obsolete)
- `ui/leads_edit.html` - ⚠️ Used by LeadUpdateUI (may be obsolete)
- `ui/lead_detail.html` - ⚠️ Used by LeadDetailUI (may be obsolete)
- `ui/lead_confirm_delete.html` - ⚠️ Used by LeadDeleteUI (may be obsolete)
- `ui/reminders.html` - ⚠️ Used by RemindersView (may be obsolete)
- `ui/projects_list.html` - ⚠️ Used by ProjectsListView (may be obsolete)
- `ui/add_employee.html` - ⚠️ Used by AddEmployeeView (may be obsolete)
- `ui/employee_management.html` - ⚠️ Used by EmployeeManagementView (may be obsolete)
- `ui/combined_management.html` - ⚠️ Used by CombinedManagementView (may be obsolete)
- `ui/leads/column_cell.html` - ⚠️ Used by UI views (may be obsolete)
- `ui/projects/column_cell.html` - ⚠️ Used by UI views (may be obsolete)
- `base_admin.html` - ⚠️ Base template for UI (may be obsolete)
- `root.html` - ⚠️ Base template for UI (may be obsolete)
- `common/test_email.html` - ⚠️ Used by TestEmailView (may be obsolete)
- `common/user_activation_status.html` - ⚠️ May be obsolete
- `healthz.html` - ⚠️ Health check template (may be obsolete)

### ❌ Templates Referenced But Missing

1. **`user_status_in.html`** - Referenced in `common/tasks.py` (lines 52, 166)
   - **Status**: Missing
   - **Action**: Should be created or reference should be updated to use existing template

2. **`lead_assigned.html`** - Referenced in `leads/tasks.py` (line 66)
   - **Status**: Missing
   - **Action**: Should be created or task should be updated

3. **`ui/projects_column_customization.html`** - Referenced in `leads/ui_views.py` (line 904)
   - **Status**: Missing
   - **Action**: Should be created or view should be updated

## Recommendations

### Option 1: Keep Django UI (Hybrid Approach)
- Keep all UI templates
- Create missing templates
- Maintain both React frontend and Django UI

### Option 2: Remove Django UI (Full React Migration)
- Remove all UI templates (`ui/*.html`, `dashboard.html`, `site_admin.html`, etc.)
- Remove UI view classes
- Keep only email templates
- Create missing email templates

### Option 3: Minimal Cleanup (Recommended)
- Keep email templates (needed for backend)
- Remove unused UI templates if confirmed obsolete
- Create missing email templates
- Comment out or remove UI view routes if not needed

## Missing Templates to Create

If keeping email functionality, these need to be created:

1. **`common/templates/user_status_in.html`** - For user activation emails
2. **`leads/templates/lead_assigned.html`** - For lead assignment emails
3. **`ui/projects_column_customization.html`** - Only if keeping UI

## Files That Reference Missing Templates

- `CRM/common/tasks.py` - References `user_status_in.html` (2 places)
- `CRM/leads/tasks.py` - References `lead_assigned.html`
- `CRM/leads/ui_views.py` - References `projects_column_customization.html`

