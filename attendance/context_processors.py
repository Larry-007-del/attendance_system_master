"""
Context processors for the Exodus Attendance System.
"""


def user_avatar(request):
    """Inject avatar metadata for the authenticated user into every template.

    Returns:
        avatar_initials:  1–2 letter string (e.g. "JD" for John Doe)
        avatar_color:     Tailwind colour class for the avatar background
        avatar_url:       Absolute URL to the real profile picture, if uploaded
    """
    if not request.user.is_authenticated:
        return {}

    user = request.user
    avatar_url = None

    # Try to fetch real profile picture from related models
    if hasattr(user, 'student') and getattr(user.student, 'profile_picture'):
        avatar_url = user.student.profile_picture.url
    elif hasattr(user, 'lecturer') and getattr(user.lecturer, 'profile_picture'):
        avatar_url = user.lecturer.profile_picture.url

    # Build initials
    first = (user.first_name or '').strip()
    last = (user.last_name or '').strip()
    if first and last:
        initials = (first[0] + last[0]).upper()
    elif first:
        initials = first[:2].upper()
    elif user.username:
        initials = user.username[:2].upper()
    else:
        initials = 'U'

    # Deterministic colour from username hash (10 warm/cool palette options)
    COLOURS = [
        'bg-indigo-500',
        'bg-purple-500',
        'bg-blue-500',
        'bg-emerald-500',
        'bg-teal-500',
        'bg-rose-500',
        'bg-amber-500',
        'bg-cyan-500',
        'bg-fuchsia-500',
        'bg-lime-500',
    ]
    colour = COLOURS[hash(user.username) % len(COLOURS)]

    return {
        'avatar_initials': initials,
        'avatar_color': colour,
        'avatar_url': avatar_url,
    }
