from utils.roles_enum import UserRole

def role_constants(request):
    return {
        'ROLE_MANAGER_VALUE': UserRole.MANAGER.value,
        'ROLE_EMPLOYEE_VALUE': UserRole.EMPLOYEE.value,
    }
