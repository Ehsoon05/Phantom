from bot_package.services.phone_verification_service import PhoneVerificationService


def test_normalize_iran_phone_accepts_common_formats():
    assert PhoneVerificationService.normalize_iran_phone("0912 123 4567") == "+989121234567"
    assert PhoneVerificationService.normalize_iran_phone("+98 912 123 4567") == "+989121234567"
    assert PhoneVerificationService.normalize_iran_phone("۰۰۹۸۹۱۲۱۲۳۴۵۶۷") == "+989121234567"


def test_normalize_iran_phone_rejects_non_iran_numbers():
    assert PhoneVerificationService.normalize_iran_phone("+4915112345678") is None
    assert PhoneVerificationService.normalize_iran_phone("02112345678") is None
