from enum import Enum


class APIErrorCode(str, Enum):
    COURSE_FORBIDDEN = 'course_forbidden'
    MISSING_REQUIRED_FIELDS = 'missing_required_fields'
    TOKEN_REQUIRED = 'token_required'
    STUDENT_NOT_ENROLLED = 'student_not_enrolled'
    SESSION_EXPIRED = 'session_expired'
    INVALID_OR_EXPIRED_TOKEN = 'invalid_or_expired_token'
    ATTENDANCE_ID_REQUIRED = 'attendance_id_required'
    COURSE_ID_REQUIRED = 'course_id_required'
    ATTENDANCE_NOT_FOUND = 'attendance_not_found'
    INVALID_STUDENT_ID = 'invalid_student_id'
    INVALID_CREDENTIALS = 'invalid_credentials'
    INVALID_STAFF_ID = 'invalid_staff_id'
    INVALID_GPS_COORDINATES = 'invalid_gps_coordinates'
    LOCATION_OUT_OF_RANGE = 'location_out_of_range'
    UNAUTHORIZED = 'unauthorized'
    LECTURER_COORDINATES_NOT_SET = 'lecturer_coordinates_not_set'
