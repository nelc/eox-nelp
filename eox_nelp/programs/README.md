# Programs API

This module provides API endpoints for managing program metadata in the eox-nelp system.

## API Endpoints

### GET eox-nelp/api/v1/programs/metadata/{course_id}/

Retrieves metadata for a specific course program.

#### Authentication
- **JWT Token**: Include JWT token in Authorization header
- **Session**: Valid Django session authentication


#### Parameters
- `course_id` (path parameter): Course identifier (e.g., `course-v1:edX+DemoX+Demo_Course`)

#### Response Format
```json
{
    "trainer_type": 10,
    "Type_of_Activity": 155,
    "Mandatory": "01",
    "Program_ABROVE": "00",
    "Program_code": "FX-TEACHER-101"
}
```

#### Status Codes
- `200 OK`: Successfully retrieved program metadata
- `400 Bad Request`: Invalid course ID format
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Program metadata not found
- `500 Internal Server Error`: Server error

#### Example Usage

**With JWT Token:**
```bash
curl -H "Authorization: Bearer <jwt_token>" \
     https://your-domain.com/eox-nelp/api/v1/programs/metadata/course-v1:edX+DemoX+Demo_Course/
```

**With Session Authentication:**
```bash
curl -H "Cookie: sessionid=<session_id>" \
     https://your-domain.com/eox-nelp/api/v1/programs/metadata/course-v1:edX+DemoX+Demo_Course/
```

## Implementation Details

### Authentication
The API uses Django REST Framework with edx-drf-extensions for authentication:
- JWT Authentication via `JwtAuthentication`
- Session Authentication via `SessionAuthenticationAllowInactiveUser`
- Configured as class attributes: `authentication_classes` and `permission_classes`


### Data Model
The API currently uses mock data. In production, this would integrate with:
- Course database for course information
- External services for program metadata
- Learning management system APIs

### Error Handling
Comprehensive error handling for:
- Invalid course IDs
- Authentication failures
- Rate limit violations
- Server errors

## Development

### File Structure
```
eox_nelp/programs/
├── __init__.py
├── README.md
└── api/
    ├── __init__.py
    ├── urls.py
    └── v1/
        ├── __init__.py
        ├── urls.py
        ├── views.py
        └── serializers.py
```

### Adding New Endpoints
1. Add new views in `api/v1/views.py`
2. Create serializers in `api/v1/serializers.py`
3. Update URLs in `api/v1/urls.py`
4. Update this README with documentation

### Testing
The API includes mock data for testing. To test with real data:
1. Implement `_get_program_metadata()` method in `ProgramsMetadataView`
2. Connect to appropriate data sources
3. Add proper error handling for data retrieval
