from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test import TestCase, override_settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from rest_framework.test import APIClient

from accounts.models import User
from transactional_notifications.models import TransactionalNotification
from transactional_notifications.services import enqueue_password_reset_notification


class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset@example.test",
            password="ExistingPassword123!",
        )

    def _request(self, email):
        return self.client.post(
            "/api/auth/password-reset/request/",
            {"email": email},
            format="json",
        )

    def _token_parts(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = PasswordResetTokenGenerator().make_token(self.user)
        return uid, token

    def test_request_is_neutral_for_known_and_unknown_emails(self):
        known = self._request("RESET@example.test")
        unknown = self._request("unknown@example.test")

        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(
            TransactionalNotification.objects.filter(kind=TransactionalNotification.Kind.PASSWORD_RESET).count(),
            1,
        )

    def test_notification_has_account_scope_and_no_raw_token_field(self):
        response = self._request(self.user.email)

        self.assertEqual(response.status_code, 202)
        notification = TransactionalNotification.objects.get(
            kind=TransactionalNotification.Kind.PASSWORD_RESET,
        )
        self.assertIsNone(notification.company_id)
        self.assertIsNone(notification.order_id)
        self.assertEqual(notification.recipient_email, self.user.email)
        self.assertEqual(notification.template_name, "password_reset_v1")
        self.assertIn("reset_url", notification.payload)
        self.assertNotIn("token", notification.payload)

    def test_enqueue_password_reset_is_idempotent_for_same_url(self):
        first = enqueue_password_reset_notification(
            self.user,
            "http://localhost:4200/reset-password?uid=MQ&token=opaque",
        )
        second = enqueue_password_reset_notification(
            self.user,
            "http://localhost:4200/reset-password?uid=MQ&token=opaque",
        )

        self.assertTrue(first[1])
        self.assertFalse(second[1])
        self.assertEqual(first[0].pk, second[0].pk)

    def test_confirm_accepts_valid_token_and_invalidates_it_after_use(self):
        uid, token = self._token_parts()
        response = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "password": "NewStrongPassword123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        replay = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "password": "AnotherStrongPassword123!"},
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

    def test_confirm_rejects_invalid_token_and_weak_password(self):
        uid, token = self._token_parts()
        invalid_token = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": "invalid-token", "password": "NewStrongPassword123!"},
            format="json",
        )
        weak_password = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "password": "password"},
            format="json",
        )

        self.assertEqual(invalid_token.status_code, 400)
        self.assertEqual(weak_password.status_code, 400)
        self.assertTrue(weak_password.data.get("password"))

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_confirm_rejects_expired_token(self):
        uid, token = self._token_parts()
        expired = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "password": "NewStrongPassword123!"},
            format="json",
        )

        self.assertEqual(expired.status_code, 400)
