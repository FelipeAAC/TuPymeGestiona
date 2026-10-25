from django.test import SimpleTestCase, override_settings

from .services import MercadoPagoConflictError, _verify_test_mode


class MercadoPagoTestUserLiveModeTests(SimpleTestCase):
    @override_settings(
        MERCADO_PAGO_ACCEPT_LIVE_MODE=False,
        MERCADO_PAGO_TEST_USER_IDS={"3778177688"},
    )
    def test_test_user_live_mode_is_allowed_for_configured_collector(self):
        self.assertTrue(
            _verify_test_mode(
                {"live_mode": True, "collector_id": 3778177688},
            )
        )

    @override_settings(
        MERCADO_PAGO_ACCEPT_LIVE_MODE=False,
        MERCADO_PAGO_TEST_USER_IDS={"3778177688"},
    )
    def test_other_live_collector_is_rejected(self):
        with self.assertRaises(MercadoPagoConflictError):
            _verify_test_mode(
                {"live_mode": True, "collector_id": 999999999},
            )

    @override_settings(
        MERCADO_PAGO_ACCEPT_LIVE_MODE=False,
        MERCADO_PAGO_TEST_USER_IDS={"3778177688"},
    )
    def test_sandbox_false_is_allowed(self):
        self.assertFalse(_verify_test_mode({"live_mode": "false"}))
