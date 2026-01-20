# Project Management Endpoints

## Overview
Two new endpoints have been added for managing projects (leads that have been converted to projects).

---

## 1. Get Projects List

### Endpoint Details
- **URL**: `/api/leads/projects/`
- **Method**: `GET`
- **Authentication**: Required (JWT Token)
- **Permissions**: 
  - Employees: See only projects assigned to them
  - Managers: See all projects

### Query Parameters (Optional)
- `name` - Filter by company name, contact first name, or last name
- `email` - Filter by contact email
- `status` - Filter by lead status ID
- `assigned_to` - Filter by assigned profile ID
- `limit` - Pagination limit
- `offset` - Pagination offset

### Response (Success - 200 OK)
```json
{
  "projects_count": 25,
  "projects": [
    {
      "id": "abc123",
      "title": "Project Title",
      "company_name": "Company Name",
      "status": {...},
      "lifecycle": {...},
      "assigned_to": {...},
      "is_project": true,
      "is_active": true,
      "priority": false,
      "follow_up_at": "2025-02-15T14:30:00Z",
      "follow_up_status": "pending",
      // ... other lead fields
    },
    // ... more projects
  ],
  "next": "http://api.example.com/api/leads/projects/?limit=10&offset=10",
  "previous": null
}
```

### Business Logic
1. **Filtering**: Returns only leads where `is_project=True` and `is_active=True`
2. **Role-Based Access**:
   - Employees: Only see projects assigned to them
   - Managers: See all projects
   - Superusers: See all projects
3. **Pagination**: Supports limit/offset pagination
4. **Search**: Can filter by name, email, status, assigned user

### Example Usage
```bash
# Get all projects (for manager)
curl -X GET https://your-domain.com/api/leads/projects/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Get projects with filters
curl -X GET "https://your-domain.com/api/leads/projects/?name=acme&status=5" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Get paginated projects
curl -X GET "https://your-domain.com/api/leads/projects/?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 2. Convert Lead to Project

### Endpoint Details
- **URL**: `/api/leads/{lead_id}/convert-to-project/`
- **Method**: `POST`
- **Authentication**: Required (JWT Token)
- **Permissions**: Only Managers can convert leads to projects

### Request Body
No request body required - this is a simple POST request.

### Response (Success - 200 OK)
```json
{
  "error": false,
  "message": "Lead successfully converted to project",
  "is_project": true,
  "project": {
    "id": "abc123",
    "title": "Project Title",
    "company_name": "Company Name",
    "is_project": true,
    // ... full lead/project object
  }
}
```

### Response (Error - 400 Bad Request)
**Already a project:**
```json
{
  "error": true,
  "message": "This lead is already a project."
}
```

**User profile not found:**
```json
{
  "error": true,
  "message": "User profile not found."
}
```

### Response (Error - 403 Forbidden)
```json
{
  "error": true,
  "message": "Only managers can convert leads to projects."
}
```

### Response (Error - 404 Not Found)
```json
{
  "detail": "Not found."
}
```

### Business Logic
1. **Permission Check**: Only managers (or superusers) can convert leads to projects
2. **Duplicate Check**: Prevents converting a lead that's already a project
3. **Simple Conversion**: Sets `is_project=True` on the lead
4. **Data Preservation**: All lead data remains intact (assigned_to, status, notes, etc.)
5. **Automatic Filtering**: After conversion, lead will:
   - Appear in `/api/leads/projects/` endpoint
   - No longer appear in `/api/leads/` endpoint (regular leads)

### Example Usage
```bash
# Convert a lead to a project
curl -X POST https://your-domain.com/api/leads/abc123/convert-to-project/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Integration Notes

### Lead vs Project Filtering
The existing `/api/leads/` endpoint has been updated to exclude projects:
- **Regular Leads**: `/api/leads/` - Returns only `is_project=False`
- **Projects**: `/api/leads/projects/` - Returns only `is_project=True`

This creates a clear separation between leads and projects in the system.

### Workflow
1. **Create Lead**: POST to `/api/leads/`
2. **Work on Lead**: Assign, add notes, schedule follow-ups
3. **Convert to Project**: POST to `/api/leads/{id}/convert-to-project/` (manager only)
4. **Manage Project**: View in `/api/leads/projects/`, continue working on it

### Common Use Cases

#### View All Projects for a Manager
```bash
GET /api/leads/projects/
```

#### View My Projects (Employee)
```bash
GET /api/leads/projects/
# Automatically filtered to assigned projects
```

#### Search Projects by Company Name
```bash
GET /api/leads/projects/?name=Acme
```

#### Convert Qualified Lead to Project
```bash
POST /api/leads/abc123/convert-to-project/
```

---

## Testing Checklist

### Projects List Endpoint
- [ ] Test as manager (should see all projects)
- [ ] Test as employee (should see only assigned projects)
- [ ] Test with no projects (should return empty array)
- [ ] Test search filters (name, email, status, assigned_to)
- [ ] Test pagination (limit, offset parameters)
- [ ] Verify projects_count is accurate

### Convert to Project Endpoint
- [ ] Test conversion as manager (should succeed)
- [ ] Test conversion as employee (should fail with 403)
- [ ] Test converting non-existent lead (should fail with 404)
- [ ] Test converting already-project lead (should fail with 400)
- [ ] Verify lead disappears from regular leads list
- [ ] Verify lead appears in projects list
- [ ] Verify all lead data preserved after conversion

---

## Frontend Integration

### Project List View
```javascript
// Fetch all projects
const response = await fetch('/api/leads/projects/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
const data = await response.json();
console.log(`Total projects: ${data.projects_count}`);
console.log('Projects:', data.projects);
```

### Convert Lead to Project
```javascript
// Convert button click handler
async function convertToProject(leadId) {
  const response = await fetch(`/api/leads/${leadId}/convert-to-project/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  const data = await response.json();
  
  if (data.error) {
    alert(data.message);
  } else {
    alert('Lead converted to project successfully!');
    // Refresh the view or redirect to projects page
  }
}
```

### UI Recommendations
1. Add "Convert to Project" button on lead detail page (manager only)
2. Create separate "Projects" navigation menu item
3. Use same lead detail view for projects (they're the same model)
4. Show "PROJECT" badge on converted leads
5. Disable/hide "Convert to Project" button if already a project

---

## Database Schema

No database changes required - uses existing `is_project` field on Lead model.

### Lead Model Fields Used
- `is_project` (BooleanField, default=False): Indicates if lead has been converted to project
- `is_active` (BooleanField): Both endpoints filter by is_active=True
- All other lead fields remain available for projects

---

## Security & Permissions

### Role-Based Access Control
| Action | Employee | Manager | Superuser |
|--------|----------|---------|-----------|
| View own projects | ✅ | ✅ | ✅ |
| View all projects | ❌ | ✅ | ✅ |
| Convert to project | ❌ | ✅ | ✅ |

### Permission Checks
- Both endpoints require authentication
- Employee users are automatically filtered to assigned projects only
- Only managers can convert leads to projects
- All existing lead permissions still apply to projects

---

## API Summary

| Endpoint | Method | Manager Only | Purpose |
|----------|--------|--------------|---------|
| `/api/leads/projects/` | GET | No* | List all projects |
| `/api/leads/{id}/convert-to-project/` | POST | Yes | Convert lead to project |

*Employees see only assigned projects; managers see all

---

## Migration Notes

No database migration required - the `is_project` field already exists in the Lead model.

All changes are code-only and can be deployed immediately.
