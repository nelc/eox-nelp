# Programs API

This module provides API endpoints for managing program metadata in the eox-nelp system.

## API Endpoints

### GET eox-nelp/api/programs/v1/metadata/{course_key_string}
### POST eox-nelp/api/programs/v1/metadata/{course_key_string}
**POST Data Payload:**
 ```json
{
    "trainer_type": 10,
    "Type_of_Activity": 155,
    "Mandatory": "01",
    "Program_ABROVE": "00",
    "Program_code": "FX-TEACHER-101"
}
```

Retrieves metadata for a specific course program.

#### Authentication
- **JWT Token**: Include JWT token in Authorization header
- **Session**: Valid Django session authentication


#### Parameters
- `course_key_string` (path parameter): Course identifier (e.g., `course-v1:edX+DemoX+Demo_Course`)

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
     https://your-domain.com/eox-nelp/api/programs/v1/metadata/course-v1:edX+DemoX+Demo_Course
```

**With Session Authentication:**
```bash
curl -H "Cookie: sessionid=<session_id>" \
     https://your-domain.com/eox-nelp/api/programs/v1/metadata/course-v1:edX+DemoX+Demo_Course
```

### POST eox-nelp/api/programs/v1/metadata/{course_key_string}

Creates or updates program metadata for a specific course.

#### Request Body
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
- `201 Created`: Successfully created/updated program metadata
- `400 Bad Request`: Invalid data or course ID format
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Course not found
- `500 Internal Server Error`: Server error

## Implementation Details

### Authentication
The API uses Django REST Framework with edx-drf-extensions for authentication:
- JWT Authentication via `JwtAuthentication`
- Session Authentication via `SessionAuthenticationAllowInactiveUser`
- Configured as class attributes: `authentication_classes` and `permission_classes`


### Data Model
The API currently saves program_metada in `advanced_settings.other_course_settings` of the course structure.

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
