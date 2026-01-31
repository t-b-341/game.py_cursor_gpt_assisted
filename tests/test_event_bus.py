"""Tests for the event bus (EventBus, GameEvent) and enemy_killed integration."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from event_bus import EventBus, GameEvent


def test_game_event_dataclass():
    """GameEvent has type and payload."""
    ev = GameEvent(type="test", payload={"a": 1})
    assert ev.type == "test"
    assert ev.payload == {"a": 1}


def test_subscribe_publish_single_handler():
    """Subscribe and publish calls the handler with the event."""
    bus = EventBus()
    received: list[GameEvent] = []

    def handler(ev: GameEvent) -> None:
        received.append(ev)

    bus.subscribe("foo", handler)
    bus.publish(GameEvent("foo", {"x": 42}))
    assert len(received) == 1
    assert received[0].type == "foo"
    assert received[0].payload == {"x": 42}


def test_subscribe_multiple_handlers_order():
    """Multiple handlers for same type are called in registration order."""
    bus = EventBus()
    order: list[int] = []

    def h1(ev: GameEvent) -> None:
        order.append(1)

    def h2(ev: GameEvent) -> None:
        order.append(2)

    def h3(ev: GameEvent) -> None:
        order.append(3)

    bus.subscribe("a", h1)
    bus.subscribe("a", h2)
    bus.subscribe("a", h3)
    bus.publish(GameEvent("a", {}))
    assert order == [1, 2, 3]


def test_publish_no_subscribers_no_op():
    """Publishing to an event type with no subscribers does not raise."""
    bus = EventBus()
    bus.publish(GameEvent("nonexistent", {}))


def test_unsubscribe():
    """Unsubscribe removes the handler; it is not called on next publish."""
    bus = EventBus()
    received: list[GameEvent] = []

    def handler(ev: GameEvent) -> None:
        received.append(ev)

    bus.subscribe("b", handler)
    bus.publish(GameEvent("b", {}))
    assert len(received) == 1

    bus.unsubscribe("b", handler)
    bus.publish(GameEvent("b", {}))
    assert len(received) == 1


def test_handler_raises_others_still_run(caplog: pytest.LogCaptureFixture):
    """If a handler raises, it is logged and other handlers still run."""
    bus = EventBus()
    seen: list[str] = []

    def failing(ev: GameEvent) -> None:
        seen.append("fail")
        raise RuntimeError("handler failed")

    def ok(ev: GameEvent) -> None:
        seen.append("ok")

    bus.subscribe("err", failing)
    bus.subscribe("err", ok)
    with caplog.at_level(logging.ERROR):
        bus.publish(GameEvent("err", {}))

    assert "fail" in seen
    assert "ok" in seen
    assert any("handler failed" in rec.message for rec in caplog.records)


def test_enemy_killed_integration():
    """When kill_enemy is called with an event_bus, 'enemy_killed' is published with expected payload."""
    from systems.enemy_death import kill_enemy
    from state import GameState

    bus = EventBus()
    received: list[GameEvent] = []
    bus.subscribe("enemy_killed", lambda ev: received.append(ev))

    state = GameState()
    state.wave_number = 2
    state.run_time = 10.0
    state.enemies = []
    state.enemy_projectiles = []
    state.damage_numbers = []
    state.enemy_defeat_messages = []
    state.enemies_killed = 0
    state.score = 0
    state.player_rect = None

    enemy = {
        "type": "test_enemy",
        "rect": MagicMock(center=(100, 100)),
        "is_boss": False,
        "is_spawner": False,
        "is_suicide": False,
    }
    state.enemies.append(enemy)

    kill_enemy(enemy, state, 800, 600, event_bus=bus)

    assert len(received) == 1
    assert received[0].type == "enemy_killed"
    payload = received[0].payload
    assert payload.get("enemy_type") == "test_enemy"
    assert payload.get("is_boss") is False
    assert payload.get("wave_number") == 2
    assert "score_delta" in payload
