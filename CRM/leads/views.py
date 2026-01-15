from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from rest_framework import status, serializers
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.models import LeadSource, LeadStatus, Profile
from common.serializer import ProfileSerializer
from .models import Lead, LeadNote, LeadNoteRead
from leads.serializer import (
    LeadCreateSerializer,
    LeadSerializer,
    LeadNoteSerializer,
    LeadNoteCreateSerializer,
    RemindersResponseSerializer,
)
from utils.roles_enum import UserRole


class LeadListView(APIView, LimitOffsetPagination):
    """
    API View for listing and creating leads.
    
    GET: Returns all leads with role-based filtering
        - Employees: Only see leads assigned to them
        - Managers: See all leads
    
    POST: Creates a new lead
        - Anyone can create leads
        - Employees can only assign to themselves
        - Managers can assign to any employee
    """
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """
        Get queryset with role-based filtering.
        Employees see only assigned leads, Managers see all leads.
        """
        request = self.request
        
        # Base queryset with optimizations
        queryset = (
            self.model.objects.select_related(
                'status',
                'assigned_to',
                'assigned_to__user',
                'created_by'
            )
            .filter(is_active=True, is_project=False)  # Only active leads, exclude projects
            .order_by("-created_at")
        )
        
        # Role-based filtering
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            user_profile = request.user.profile
            user_role = int(user_profile.role) if user_profile.role is not None else None
            
            # Employees can only see leads assigned to them
            if user_role == UserRole.EMPLOYEE.value:
                queryset = queryset.filter(assigned_to=user_profile)
            # Managers can see all leads (no additional filter needed)
        
        return queryset

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        request = self.request
        
        # Get base queryset with role-based filtering
        queryset = self.get_queryset()
        
        # Apply search filters
        if params:
            if params.get("name"):
                queryset = queryset.filter(
                    Q(company_name__icontains=params.get("name"))
                    | Q(contact_first_name__icontains=params.get("name"))
                    | Q(contact_last_name__icontains=params.get("name"))
                )
            if params.get("city"):
                queryset = queryset.filter(
                    Q(company_name__icontains=params.get("city"))
                )
            if params.get("email"):
                queryset = queryset.filter(
                    contact_email__icontains=params.get("email")
                )
            if params.get("status"):
                queryset = queryset.filter(status=params.get("status"))
            if params.get("source"):
                queryset = queryset.filter(source=params.get("source"))
            if params.get("assigned_to"):
                queryset = queryset.filter(assigned_to=params.get("assigned_to"))

        context = {}
        search = False
        if (
            params.get("name")
            or params.get("city")
            or params.get("email")
            or params.get("status")
            or params.get("source")
            or params.get("assigned_to")
        ):
            search = True
        count = queryset.count()

        if params.get("limit") and params.get("offset"):
            page_size = int(params.get("limit"))
            offset = int(params.get("offset"))
            queryset = queryset[offset:offset + page_size]
        else:
            page_size = 10
            offset = 0
            queryset = queryset[:page_size]

        context["leads"] = LeadSerializer(queryset, many=True).data
        context["count"] = count
        context["offset"] = offset
        context["limit"] = page_size
        context["search"] = search
        
        #statuses and sources along with lead data

        statuses = LeadStatus.objects.all().order_by('sort_order', 'name')
        statuses_data = [
            {
                'id': s.id,
                'name': s.name,
            }
            for s in statuses
        ]
        

        sources = LeadSource.objects.all().order_by('source')
        sources_data = [
            {
                'id': src.id,
                'name': src.source,
            }
            for src in sources
        ]

        context["statuses"] = statuses_data
        context["sources"] = sources_data

        # Employees along with leads data

        if int(self.request.user.profile.role) == UserRole.MANAGER.value or self.request.user.is_superuser:
            users = Profile.objects.select_related('user').filter(
                is_active=True,
                user__is_deleted=False
            )

            users = ProfileSerializer(users, many=True).data
            context["users"] = users
        else:
            
            context["users"] = []

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return Response(context)


    def post(self, request, *args, **kwargs):
        """
        Create a new lead.
        - Anyone (authenticated user) can create leads
        - Employees can only assign leads to themselves
        - Managers can assign leads to any employee
        """
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Prepare data (exclude CSRF token and other non-model fields)
        data = {}
        for key, value in request.data.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value
        
        # Role-based assignment validation
        if data.get("assigned_to"):
            try:
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                
                # Employees can only assign to themselves
                if user_role == UserRole.EMPLOYEE.value:
                    if assigned_to.id != user_profile.id:
                        return Response(
                            {"error": True, "message": "You can only assign leads to yourself."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                
                # Managers can assign to any employee
                data["assigned_to"] = assigned_to.id
            except Profile.DoesNotExist:
                return Response(
                    {"error": True, "message": "Invalid assigned_to profile ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # If no assignment specified, employees are auto-assigned to themselves
            if user_role == UserRole.EMPLOYEE.value:
                data["assigned_to"] = user_profile.id

        # Set defaults for new leads
        if "is_active" not in data:
            data["is_active"] = True

        # Validate and create lead
        serializer = LeadCreateSerializer(data=data)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=request.user,
            )

            # Handle assignment
            if data.get("assigned_to"):
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                lead_obj.assigned_to = assigned_to
                lead_obj.save()

            # Return the created lead with full details
            lead_serializer = LeadSerializer(lead_obj)
            return Response(
                {
                    "success": True,
                    "message": "Lead created successfully",
                    "lead": lead_serializer.data
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

class LeadDetailView(APIView):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        # Optimize: Use select_related
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def get(self, request, pk, **kwargs):
        lead_obj = self.get_object(pk)
        context = {}
        context["UserRole"] = UserRole
        context["lead_obj"] = LeadSerializer(lead_obj).data
        return Response(context)


    def patch(self, request, pk, **kwargs):
        """
        Update a lead.
        - Employees can only update leads assigned to them
        - Managers can update any lead
        """
        lead_obj = self.get_object(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only update leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only update leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        params = request.data
        data = {}
        for key, value in params.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value

        serializer = LeadCreateSerializer(lead_obj, data=data)
        if serializer.is_valid():
            lead_obj = serializer.save()

            # Handle assignment - optimize with select_related
            if data.get("assigned_to"):
                try:
                    assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                    lead_obj.assigned_to = assigned_to
                    lead_obj.save()
                except Profile.DoesNotExist:
                    return Response(
                        {"error": True, "message": "Invalid assigned_to profile ID."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Return updated lead data
            lead_serializer = LeadSerializer(lead_obj)
            return Response(
                {
                    "error": False,
                    "message": "Lead Updated Successfully",
                    "lead": lead_serializer.data
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


    def delete(self, request, pk, **kwargs):
        lead_obj = self.get_object(pk)
        lead_obj.delete()
        return Response(
            {"error": False, "message": "Lead Deleted Successfully"},
            status=status.HTTP_200_OK,
        )


class LeadAlwaysActiveUpdateView(APIView):
    """
    API View for updating always_active status of a lead.
    
    PATCH: Updates the always_active field
        - Employees can only update leads assigned to them
        - Managers can update any lead
    
    Accepts: true/false or 1/0 (boolean)
    """
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        """Get lead object with optimizations"""
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )


    def patch(self, request, pk, **kwargs):
        """
        Update always_active status of a lead.
        """
        lead_obj = self.get_object(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only update leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only update always_active status for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Get always_active from request data
        always_active = request.data.get("always_active")
        
        if always_active is None:
            return Response(
                {"error": True, "message": "always_active is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Convert to boolean (handle string "true"/"false", 1/0, etc.)
        if isinstance(always_active, str):
            always_active = always_active.lower() in ('true', '1', 'yes', 'on')
        else:
            always_active = bool(always_active)
        
        # Update the always_active status
        lead_obj.always_active = always_active
        lead_obj.save(update_fields=["always_active"])
        
        # Return updated lead data
        lead_serializer = LeadSerializer(lead_obj)
        return Response(
            {
                "error": False,
                "message": "Always active status updated successfully",
                "always_active": always_active,
                "lead": lead_serializer.data
            },
            status=status.HTTP_200_OK,
        )



class LeadFollowUpStatusUpdateView(APIView):
    """
    API View for updating follow-up status of a lead.
    
    PATCH: Updates the follow_up_status field
        - Employees can only update leads assigned to them
        - Managers can update any lead
    
    Accepts: 'pending' or 'done' (case-insensitive)
    """
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        """Get lead object with optimizations"""
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def patch(self, request, pk, **kwargs):
        """
        Update follow-up status of a lead.
        """
        lead_obj = self.get_object(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only update leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only update follow-up status for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Get follow_up_status from request data
        follow_up_status = request.data.get("follow_up_status")
        
        if follow_up_status is None:
            return Response(
                {"error": True, "message": "follow_up_status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Validate and normalize follow_up_status (case-insensitive)
        follow_up_status = str(follow_up_status).lower().strip()
        valid_choices = ['pending', 'done']
        
        if follow_up_status not in valid_choices:
            return Response(
                {"error": True, "message": f"follow_up_status must be one of: {', '.join(valid_choices)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Update the follow-up status
        lead_obj.follow_up_status = follow_up_status
        lead_obj.save(update_fields=["follow_up_status"])
        
        # Return updated lead data
        lead_serializer = LeadSerializer(lead_obj)
        return Response(
            {
                "error": False,
                "message": "Follow-up status updated successfully",
                "follow_up_status": follow_up_status,
                "lead": lead_serializer.data
            },
            status=status.HTTP_200_OK,
        )


class LeadNotesListView(APIView):
    """
    API View for listing and creating notes for a lead.
    
    GET: Returns all notes for a specific lead
        - Employees: Can only see notes for leads assigned to them
        - Managers: Can see all notes
    
    POST: Creates a new note for a lead
        - Employees: Can only create notes for leads assigned to them
        - Managers: Can create notes for any lead
    """
    permission_classes = (IsAuthenticated,)

    def get_lead(self, pk):
        """Get lead object with optimizations"""
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def get(self, request, pk, **kwargs):
        """
        Get all notes for a specific lead.
        """
        lead_obj = self.get_lead(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only see notes for leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only view notes for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Get all notes for this lead, ordered by created_at (oldest first)
        notes = LeadNote.objects.filter(lead=lead_obj).select_related(
            'author',
            'author__user'
        ).order_by('created_at')
        
        # Serialize notes with read status
        serializer = LeadNoteSerializer(notes, many=True, context={'request': request})
        
        return Response({
            "success": True,
            "lead_id": str(lead_obj.id),
            "count": notes.count(),
            "notes": serializer.data
        }, status=status.HTTP_200_OK)


    def post(self, request, pk, **kwargs):
        """
        Create a new note for a lead.
        """
        lead_obj = self.get_lead(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only create notes for leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only create notes for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Validate and create note
        serializer = LeadNoteCreateSerializer(data=request.data)
        if serializer.is_valid():
            note_obj = serializer.save(
                lead=lead_obj,
                author=user_profile,
                created_by=request.user,
            )
            
            # Return the created note with full details
            note_serializer = LeadNoteSerializer(note_obj, context={'request': request})
            return Response(
                {
                    "success": True,
                    "message": "Note created successfully",
                    "note": note_serializer.data
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LeadNotesUnreadListView(APIView):
    """
    API View for getting unread notes for a specific lead.
    
    GET: Returns all unread notes for a lead
        - Employees: Can only see unread notes for leads assigned to them
        - Managers: Can see all unread notes
    """
    permission_classes = (IsAuthenticated,)

    def get_lead(self, pk):
        """Get lead object with optimizations"""
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def get(self, request, pk, **kwargs):
        """
        Get all unread notes for a specific lead.
        """
        lead_obj = self.get_lead(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only see unread notes for leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only view unread notes for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Get unread notes for this lead (notes that the current user hasn't read)
        # Use exclude to filter out notes that have been read by the current user
        unread_notes = LeadNote.objects.filter(
            lead=lead_obj
        ).exclude(
            read_by__user=request.user
        ).select_related(
            'author',
            'author__user'
        ).order_by('created_at')
        
        # Serialize unread notes
        serializer = LeadNoteSerializer(unread_notes, many=True, context={'request': request})
        
        return Response({
            "success": True,
            "lead_id": str(lead_obj.id),
            "count": unread_notes.count(),
            "unread_notes": serializer.data
        }, status=status.HTTP_200_OK)



class LeadNoteDetailView(APIView):
    """
    API View for retrieving and deleting a specific note.
    
    GET: Get a specific note
    DELETE: Delete a note (only by author)
    """
    permission_classes = (IsAuthenticated,)

    def get_note(self, pk, note_pk):
        """Get note object with optimizations"""
        lead_obj = get_object_or_404(Lead, pk=pk)
        return get_object_or_404(
            LeadNote.objects.select_related('lead', 'author', 'author__user'),
            pk=note_pk,
            lead=lead_obj
        )

    def get(self, request, pk, note_pk, **kwargs):
        """
        Get a specific note.
        """
        note_obj = self.get_note(pk, note_pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only see notes for leads assigned to them
            if note_obj.lead.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only view notes for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        serializer = LeadNoteSerializer(note_obj, context={'request': request})
        return Response({
            "success": True,
            "note": serializer.data
        }, status=status.HTTP_200_OK)

    def delete(self, request, pk, note_pk, **kwargs):
        """
        Delete a note (only by author).
        """
        note_obj = self.get_note(pk, note_pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        
        # Only the author can delete the note
        if note_obj.author != user_profile:
            return Response(
                {"error": True, "message": "You can only delete your own notes."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        note_obj.delete()
        return Response(
            {"success": True, "message": "Note deleted successfully"},
            status=status.HTTP_200_OK,
        )


class LeadNoteMarkReadView(APIView):
    """
    API View for marking a note as read.
    
    POST: Mark a note as read by the current user
    """
    permission_classes = (IsAuthenticated,)

    def get_note(self, pk, note_pk):
        """Get note object"""
        lead_obj = get_object_or_404(Lead, pk=pk)
        return get_object_or_404(
            LeadNote.objects.select_related('lead', 'author', 'author__user'),
            pk=note_pk,
            lead=lead_obj
        )


    def post(self, request, pk, note_pk, **kwargs):
        """
        Mark a note as read by the current user.
        """
        note_obj = self.get_note(pk, note_pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only mark notes as read for leads assigned to them
            if note_obj.lead.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only mark notes as read for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Check if already read
        read_record, created = LeadNoteRead.objects.get_or_create(
            note=note_obj,
            user=request.user,
            defaults={'created_by': request.user}
        )
        
        if created:
            message = "Note marked as read"
        else:
            message = "Note was already marked as read"
        
        return Response(
            {
                "success": True,
                "message": message,
                "note_id": str(note_obj.id),
                "is_read": True
            },
            status=status.HTTP_200_OK,
        )


class RemindersListView(APIView):
    """
    API View for getting reminders categorized by status.
    
    GET: Returns reminders in 4 categories:
        - overdue: follow_up_at is in the past and follow_up_status is 'pending'
        - due_today: follow_up_at is today and follow_up_status is 'pending'
        - upcoming: follow_up_at is in the future and follow_up_status is 'pending'
        - done: follow_up_status is 'done'
    
    Role-based filtering:
        - Employees: Only see reminders for leads assigned to them
        - Managers: See all reminders
    """
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Get queryset with role-based filtering"""
        request = self.request
        
        # Base queryset: only active leads with follow_up_at set
        queryset = Lead.objects.filter(
            is_active=True,
            follow_up_at__isnull=False
        ).select_related(
            'status',
            'assigned_to',
            'assigned_to__user',
            'created_by'
        )
        
        # Role-based filtering
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            user_profile = request.user.profile
            user_role = int(user_profile.role) if user_profile.role is not None else None
            
            # Employees can only see reminders for leads assigned to them
            if user_role == UserRole.EMPLOYEE.value:
                queryset = queryset.filter(assigned_to=user_profile)
            # Managers can see all reminders (no additional filter needed)
        
        return queryset


    def get(self, request, *args, **kwargs):
        """
        Get all reminders categorized by status.
        """
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        queryset = self.get_queryset()
        
        # Overdue: follow_up_at is in the past and status is 'pending'
        overdue = queryset.filter(
            follow_up_at__lt=today_start,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Due today: follow_up_at is today and status is 'pending'
        due_today = queryset.filter(
            follow_up_at__gte=today_start,
            follow_up_at__lt=today_end,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Upcoming: follow_up_at is in the future (after today) and status is 'pending'
        upcoming = queryset.filter(
            follow_up_at__gte=today_end,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Done: follow_up_status is 'done'
        done = queryset.filter(
            follow_up_status='done'
        ).order_by('-follow_up_at')
        
        # Serialize all categories
        overdue_serializer = LeadSerializer(overdue, many=True)
        due_today_serializer = LeadSerializer(due_today, many=True)
        upcoming_serializer = LeadSerializer(upcoming, many=True)
        done_serializer = LeadSerializer(done, many=True)
        
        return Response({
            "success": True,
            "overdue": {
                "count": overdue.count(),
                "leads": overdue_serializer.data
            },
            "due_today": {
                "count": due_today.count(),
                "leads": due_today_serializer.data
            },
            "upcoming": {
                "count": upcoming.count(),
                "leads": upcoming_serializer.data
            },
            "done": {
                "count": done.count(),
                "leads": done_serializer.data
            }
        }, status=status.HTTP_200_OK)
