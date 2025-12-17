# Password Reset API Endpoints

This document describes all API endpoints for the password reset functionality.

## Base URL
```
https://crm-leads-cwml.onrender.com/api/common
```

---

## 1. Request Password Reset Link

**Endpoint:** `POST /api/common/auth/password-reset-request/`

**Description:** Sends a password reset link to the user's email address.

**Authentication:** Not required (public endpoint)

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Success Response (200 OK):**
```json
{
  "message": "If an account with this email exists, a password reset link has been sent."
}
```

**Error Responses:**

- **400 Bad Request** - Missing email:
```json
{
  "error": "Email is required"
}
```

- **404 Not Found** - Account not found or inactive:
```json
{
  "error": "Account not found. Please contact your manager for assistance."
}
```

- **500 Internal Server Error** - Failed to send email:
```json
{
  "error": "Failed to send password reset email. Please try again later."
}
```

**Notes:**
- For security reasons, the API always returns the same success message regardless of whether the email exists in the system.
- The reset link is sent to the email address if the account exists and is active.
- The reset link expires after 3 days (Django default).
- The reset link points to the frontend URL: `{FRONTEND_URL}/reset-password/{uid}/{token}/`

---

## 2. Confirm Password Reset

**Endpoint:** `POST /api/common/auth/password-reset-confirm/`

**Description:** Resets the user's password using the token from the reset link and automatically logs them in.

**Authentication:** Not required (public endpoint)

**Request Body:**
```json
{
  "uid": "base64_encoded_user_id",
  "token": "password_reset_token",
  "password": "new_password_here"
}
```

**Success Response (200 OK):**
```json
{
  "message": "Password reset successfully. You are now logged in.",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "email": "user@example.com",
    "role": "manager"
  }
}
```

**Error Responses:**

- **400 Bad Request** - Missing required fields:
```json
{
  "error": "uid, token, and password are required"
}
```

- **400 Bad Request** - Password too short:
```json
{
  "error": "Password must be at least 8 characters long"
}
```

- **400 Bad Request** - Invalid or expired token:
```json
{
  "error": "Invalid or expired reset link. Please request a new password reset link."
}
```

- **400 Bad Request** - Invalid user ID:
```json
{
  "error": "Invalid reset link. Please request a new password reset link."
}
```

- **403 Forbidden** - Account inactive:
```json
{
  "error": "Account is inactive. Please contact your manager for assistance."
}
```

- **500 Internal Server Error** - Server error:
```json
{
  "error": "An error occurred while resetting your password. Please try again."
}
```

**Notes:**
- The `uid` and `token` are extracted from the reset link URL.
- After successful password reset, the user is automatically logged in and receives JWT tokens.
- The access token should be used for subsequent authenticated requests.
- The refresh token can be used to get a new access token when it expires.

---

## Frontend Integration Flow

### Step 1: User Requests Password Reset
1. User enters their email on the password reset request page.
2. Frontend calls: `POST /api/common/auth/password-reset-request/`
3. User receives email with reset link.

### Step 2: User Clicks Reset Link
1. Reset link format: `https://skycrm.vercel.app/reset-password/{uid}/{token}/`
2. Frontend extracts `uid` and `token` from URL parameters.
3. Frontend displays password reset form.

### Step 3: User Submits New Password
1. User enters new password and confirms it.
2. Frontend calls: `POST /api/common/auth/password-reset-confirm/`
3. Frontend receives JWT tokens and user info.
4. Frontend stores tokens and redirects user to dashboard.

---

## Security Features

1. **Token Expiration:** Reset tokens expire after 3 days (Django default).
2. **One-time Use:** Tokens are invalidated after successful password reset.
3. **Email Verification:** Only active accounts can reset passwords.
4. **Secure Token Generation:** Uses Django's `default_token_generator` which includes:
   - User ID
   - Timestamp
   - User's last login timestamp
   - User's password hash (invalidated when password changes)
5. **Base64 Encoding:** User ID is base64 encoded in the URL for security.
6. **Generic Error Messages:** Prevents email enumeration attacks.

---

## Example Frontend Implementation

### Request Password Reset
```javascript
const requestPasswordReset = async (email) => {
  try {
    const response = await fetch('https://crm-leads-cwml.onrender.com/api/common/auth/password-reset-request/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
};
```

### Confirm Password Reset
```javascript
const confirmPasswordReset = async (uid, token, password) => {
  try {
    const response = await fetch('https://crm-leads-cwml.onrender.com/api/common/auth/password-reset-confirm/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ uid, token, password }),
    });
    
    const data = await response.json();
    
    if (response.ok) {
      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      // Redirect to dashboard
      window.location.href = '/dashboard';
    }
    
    return data;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
};
```

---

## Testing

### Test Password Reset Request
```bash
curl -X POST https://crm-leads-cwml.onrender.com/api/common/auth/password-reset-request/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

### Test Password Reset Confirm
```bash
curl -X POST https://crm-leads-cwml.onrender.com/api/common/auth/password-reset-confirm/ \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "base64_encoded_uid",
    "token": "reset_token",
    "password": "newpassword123"
  }'
```

---

## Related Endpoints

- **Login:** `POST /api/common/auth/login/`
- **Logout:** `POST /api/common/auth/logout/`
- **Refresh Token:** `POST /api/common/auth/refresh-token/`

