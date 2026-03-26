import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import WebAuthnCredential
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorAttachment,
    UserVerificationRequirement,
    RegistrationCredential,
    AuthenticationCredential,
)
from webauthn.helpers.exceptions import InvalidRegistrationResponse, InvalidAuthenticationResponse

RP_NAME = "Exodus Attendance"

def get_rp_id(request):
    return request.get_host().split(':')[0]

def get_origin(request):
    return f"{request.scheme}://{request.get_host()}"

@login_required
def register_begin(request):
    """Generate options for WebAuthn registration"""
    user = request.user
    
    # Existing credentials to prevent re-registration of the same authenticator
    credentials = WebAuthnCredential.objects.filter(user=user)
    exclude_credentials = [{"id": base64url_to_bytes(c.credential_id), "type": "public-key"} for c in credentials]

    options = generate_registration_options(
        rp_id=get_rp_id(request),
        rp_name=RP_NAME,
        user_id=str(user.id).encode("utf-8"),
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            # Enforce built-in biometrics like TouchID/Fingerprint rather than roaming USBs
            authenticator_attachment=AuthenticatorAttachment.PLATFORM, 
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    # Store challenge in session for verification phase
    request.session["registration_challenge"] = options.challenge

    return JsonResponse(json.loads(options_to_json(options)))

@csrf_exempt
@login_required
def register_complete(request):
    """Verify WebAuthn registration response and save credential"""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    challenge = request.session.get("registration_challenge")
    if not challenge:
        return JsonResponse({"error": "No challenge found in session"}, status=400)

    try:
        data = json.loads(request.body)
        credential = RegistrationCredential.parse_raw(request.body)
        
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=get_rp_id(request),
            expected_origin=get_origin(request),
        )

        # Remove challenge
        del request.session["registration_challenge"]

        # Save the new credential
        WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=verification.credential_id.decode("utf-8"), # base64 string
            public_key=verification.credential_public_key.decode("utf-8"),
            sign_count=verification.sign_count,
            name="Platform Authenticator (Fingerprint)",
        )

        return JsonResponse({"status": "success", "message": "Biometric registered successfully."})

    except InvalidRegistrationResponse as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def authenticate_begin(request):
    """Generate options for biometric authentication"""
    # If the user is logged in (e.g., verifying attendance), use their specific credentials.
    # If they are anonymously logging in, allow any credential.
    user = request.user if request.user.is_authenticated else None
    
    allow_credentials = []
    if user:
        creds = WebAuthnCredential.objects.filter(user=user)
        allow_credentials = [{"id": base64url_to_bytes(c.credential_id), "type": "public-key"} for c in creds]
        if not allow_credentials:
            return JsonResponse({"error": "No biometric credentials registered."}, status=400)

    options = generate_authentication_options(
        rp_id=get_rp_id(request),
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    request.session["authentication_challenge"] = options.challenge

    return JsonResponse(json.loads(options_to_json(options)))

@csrf_exempt
def authenticate_complete(request):
    """Verify WebAuthn authentication response"""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    challenge = request.session.get("authentication_challenge")
    if not challenge:
        return JsonResponse({"error": "No challenge found in session"}, status=400)

    try:
        credential = AuthenticationCredential.parse_raw(request.body)
        
        # Look up the stored public key for this credential ID
        stored_cred = WebAuthnCredential.objects.filter(credential_id=credential.id).first()
        if not stored_cred:
            return JsonResponse({"error": "Credential not found."}, status=404)

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=get_rp_id(request),
            expected_origin=get_origin(request),
            credential_public_key=base64url_to_bytes(stored_cred.public_key),
            credential_current_sign_count=stored_cred.sign_count,
        )

        del request.session["authentication_challenge"]

        # Update sign count to prevent replay attacks
        stored_cred.sign_count = verification.new_sign_count
        stored_cred.save()

        # Mark session as biometrically verified (useful for attendance checking)
        request.session["biometric_verified"] = True
        
        # We can also log the user in if this is a login flow.
        if not request.user.is_authenticated:
            from django.contrib.auth import login
            login(request, stored_cred.user)
            
        return JsonResponse({"status": "success", "message": "Biometric verified successfully."})

    except InvalidAuthenticationResponse as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
