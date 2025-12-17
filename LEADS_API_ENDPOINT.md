# All Leads API Endpoint

This document describes the API endpoint for retrieving leads that will be shown in the "All Leads" tab.

## Endpoint

**URL:** `GET /api/leads/`

**Base URL:** `https://crm-leads-cwml.onrender.com/api/leads/`

**Authentication:** Required (JWT Token)

**Method:** `GET`

---

## Role-Based Access Control

The endpoint automatically filters leads based on the authenticated user's role:

### Managers
- **Can see:** All active leads (excluding projects)
- **Filter applied:** None (sees all leads where `is_active=True` and `is_project=False`)

### Employees
- **Can see:** Only leads assigned to them
- **Filter applied:** `assigned_to = user.profile`

### Development Leads
- **Can see:** All active leads (same as managers)

---

## Request Parameters

### Query Parameters (Optional)

All query parameters are optional and can be used for filtering/searching:

| Parameter | Type | Description | Example |
|-----------|------|-------------|----------|
| `name` | string | Search by company name, first name, or last name | `?name=John` |
| `city` | string | Search by city (searches in company name) | `?city=New York` |
| `email` | string | Search by contact email | `?email=john@example.com` |
| `status` | string | Filter by lead status | `?status=new` |
| `source` | string | Filter by lead source | `?source=website` |
| `assigned_to` | string | Filter by assigned user ID | `?assigned_to=123` |
| `limit` | integer | Number of results per page (default: 10) | `?limit=20` |
| `offset` | integer | Number of results to skip (for pagination) | `?offset=20` |

---

## Response Format

### Success Response (200 OK)

```json
{
  "leads": [
    {
      "id": "uuid",
      "title": "Lead Title",
      "status": {
        "id": 1,
        "name": "New"
      },
      "source": "website",
      "description": "Lead description",
      "company_name": "Company Name",
      "contact_first_name": "John",
      "contact_last_name": "Doe",
      "contact_email": "john@example.com",
      "contact_phone": "+1234567890",
      "contact_position_title": "CEO",
      "contact_linkedin_url": "https://linkedin.com/in/johndoe",
      "assigned_to": {
        "id": "uuid",
        "user": {
          "id": "uuid",
          "email": "employee@example.com",
          "first_name": "Employee",
          "last_name": "Name"
        },
        "role": 1
      },
      "follow_up_at": "2024-01-15T10:00:00Z",
      "follow_up_status": "pending",
      "created_by": {
        "id": "uuid",
        "email": "creator@example.com",
        "first_name": "Creator",
        "last_name": "Name"
      },
      "created_at": "2024-01-10T08:00:00Z",
      "is_active": true
    }
  ],
  "count": 50,
  "offset": 0,
  "limit": 10,
  "search": false,
  "close_leads": {
    "leads_count": 5,
    "close_leads": [...],
    "offset": 0
  },
  "users": [
    {
      "id": "uuid",
      "user__email": "user@example.com"
    }
  ],
  "UserRole": {
    "MANAGER": 0,
    "EMPLOYEE": 1,
    "DEV_LEAD": 2
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `leads` | array | List of lead objects |
| `count` | integer | Total number of leads (before pagination) |
| `offset` | integer | Current offset (for pagination) |
| `limit` | integer | Number of results per page |
| `search` | boolean | Whether search filters were applied |
| `close_leads` | object | Information about closed leads |
| `users` | array | List of available users (for assignment) |
| `UserRole` | object | User role enum values |

---

## Example Requests

### Get All Leads (Manager)

```bash
curl -X GET "https://crm-leads-cwml.onrender.com/api/leads/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Leads with Pagination

```bash
curl -X GET "https://crm-leads-cwml.onrender.com/api/leads/?limit=20&offset=0" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Search Leads by Name

```bash
curl -X GET "https://crm-leads-cwml.onrender.com/api/leads/?name=John" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Filter Leads by Status

```bash
curl -X GET "https://crm-leads-cwml.onrender.com/api/leads/?status=new" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Filter Leads by Assigned User

```bash
curl -X GET "https://crm-leads-cwml.onrender.com/api/leads/?assigned_to=user-uuid" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Frontend Integration Example

### JavaScript/React Example

```javascript
const fetchLeads = async (filters = {}) => {
  try {
    // Build query string from filters
    const queryParams = new URLSearchParams();
    
    if (filters.name) queryParams.append('name', filters.name);
    if (filters.status) queryParams.append('status', filters.status);
    if (filters.source) queryParams.append('source', filters.source);
    if (filters.assigned_to) queryParams.append('assigned_to', filters.assigned_to);
    if (filters.limit) queryParams.append('limit', filters.limit);
    if (filters.offset) queryParams.append('offset', filters.offset);
    
    const queryString = queryParams.toString();
    const url = `https://crm-leads-cwml.onrender.com/api/leads/${queryString ? `?${queryString}` : ''}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch leads');
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching leads:', error);
    throw error;
  }
};

// Usage examples:

// Get all leads (role-based filtering is automatic)
const allLeads = await fetchLeads();

// Get leads with pagination
const page2 = await fetchLeads({ limit: 20, offset: 20 });

// Search leads
const searchResults = await fetchLeads({ name: 'John' });

// Filter by status
const newLeads = await fetchLeads({ status: 'new' });
```

---

## Important Notes

1. **Role-Based Filtering:** The endpoint automatically applies role-based filtering:
   - **Managers** see all active leads
   - **Employees** only see leads assigned to them
   - **Development Leads** see all active leads

2. **Projects Excluded:** Projects (`is_project=True`) are automatically excluded from results.

3. **Active Leads Only:** Only active leads (`is_active=True`) are returned.

4. **Default Pagination:** If `limit` and `offset` are not provided, default pagination is applied (10 results per page).

5. **Search Functionality:** Multiple search parameters can be combined for advanced filtering.

6. **Ordering:** Results are ordered by creation date (newest first: `-created_at`).

---

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Related Endpoints

- **Create Lead:** `POST /api/leads/`
- **Get Lead Detail:** `GET /api/leads/{id}/`
- **Update Lead:** `PUT /api/leads/{id}/`
- **Delete Lead:** `DELETE /api/leads/{id}/`

