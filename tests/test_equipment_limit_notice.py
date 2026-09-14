"""Equipment limit failures stay transactional and become inline notices."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from test_equipment import equipment_session
from openreunion.core import GameError
from openreunion.dos.equipment import EquipmentTransferLimit
from openreunion.dos.original_ui import OriginalApp


class EquipmentLimitNoticeTests(unittest.TestCase):
    def assert_limit(self, session, expected_notice, **arguments):
        before = deepcopy(session.state)
        with self.assertRaises(EquipmentTransferLimit) as raised:
            session.apply("equip_fleet", **arguments)
        self.assertEqual(raised.exception.notice, expected_notice)
        self.assertEqual(session.state, before)

    def test_loading_without_depot_stock_is_typed_and_atomic(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=2)
        session.state["products"][5]["stock"] = 0

        self.assert_limit(
            session,
            "No stock available",
            fleet_index=0,
            category=1,
            hull=1,
        )

    def test_carrier_payload_capacity_is_typed_and_atomic(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=4)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1)
        session.apply("equip_fleet", fleet_index=0, category=1, hull=1, component=1)

        self.assert_limit(
            session,
            "Equipment bay full",
            fleet_index=0,
            category=1,
            hull=1,
            component=1,
        )

    def test_empty_unload_is_typed_and_atomic(self):
        session = equipment_session()
        session.apply("create_fleet", fleet_type=2)

        self.assert_limit(
            session,
            "Nothing to unload",
            fleet_index=0,
            category=1,
            hull=1,
            quantity=-1,
        )

    def make_app(self, *, side_effect=None):
        app = object.__new__(OriginalApp)
        view = Mock()
        view.bank = "moving"
        view.index = 0
        view.notice = "old notice"
        view.row.return_value = [0] * 161
        view.category_rule.return_value = {"id": 1}
        app.equipment_view = view
        app.equipment_context = Mock()
        app.session = SimpleNamespace(state={})
        app.catalog = object()
        app.act = Mock(side_effect=side_effect)
        app.status = Mock()
        app.pointer = Mock()
        app.render_original = Mock()
        return app, view

    def test_limit_is_inline_notice_and_does_not_escape(self):
        app, view = self.make_app(
            side_effect=EquipmentTransferLimit("Equipment bay full")
        )

        app.equipment_action(("equipment_transfer", 1, 1), 1)

        self.assertEqual(view.notice, "Equipment bay full")
        app.status.set.assert_called_once_with(
            "The transfer exceeds available stock or the hull's equipment capacity."
        )
        app.pointer.cancel.assert_called_once_with(reset=True)
        app.render_original.assert_called_once_with()

    def test_success_clears_old_notice_and_unrelated_game_error_propagates(self):
        app, view = self.make_app()
        app.equipment_action(("equipment_transfer", 1, 0), 1)
        self.assertEqual(view.notice, "")
        app.status.set.assert_not_called()

        app, view = self.make_app(side_effect=GameError("bad context"))
        with self.assertRaises(GameError):
            app.equipment_action(("equipment_transfer", 1, 0), 1)
        self.assertEqual(view.notice, "")


if __name__ == "__main__":
    unittest.main()
