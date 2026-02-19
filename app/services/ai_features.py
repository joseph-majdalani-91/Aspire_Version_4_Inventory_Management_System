from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime

from app.models import Item, ItemStatus, QuantityEvent

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency for offline fallback mode
    OpenAI = None  # type: ignore[assignment]


def _get_openai_client() -> tuple[object | None, str | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key or OpenAI is None:
        return None, None
    try:
        return OpenAI(api_key=api_key), model
    except Exception:
        return None, None


def _extract_json_object(text: str) -> dict[str, object] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        return None
    return None


def build_reorder_suggestions(items: list[Item], limit: int = 20) -> dict[str, object]:
    scoped = [item for item in items if not item.is_deleted and item.status != ItemStatus.DISCONTINUED]

    ranked: list[dict[str, object]] = []
    for item in scoped:
        target = max(item.reorder_threshold * 2, item.reorder_threshold + 10)
        recommended = max(0, target - item.quantity)
        if item.status in {ItemStatus.LOW_STOCK, ItemStatus.ORDERED} or recommended > 0:
            ranked.append(
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "status": item.status,
                    "current_quantity": item.quantity,
                    "reorder_threshold": item.reorder_threshold,
                    "recommended_order_qty": recommended,
                    "reason": (
                        "Quantity is at/below policy threshold"
                        if item.quantity <= item.reorder_threshold
                        else "Maintain target cover stock"
                    ),
                }
            )

    ranked.sort(
        key=lambda row: (
            0 if row["current_quantity"] <= row["reorder_threshold"] else 1,
            -int(row["recommended_order_qty"]),
            str(row["sku"]),
        )
    )
    fallback = ranked[:limit]

    client, model = _get_openai_client()
    if client is None or not fallback:
        return {"source": "fallback", "model": None, "suggestions": fallback}

    try:
        prompt_payload = [
            {
                "item_id": row["item_id"],
                "sku": row["sku"],
                "name": row["name"],
                "status": str(row["status"]),
                "current_quantity": row["current_quantity"],
                "reorder_threshold": row["reorder_threshold"],
                "recommended_order_qty": row["recommended_order_qty"],
            }
            for row in fallback
        ]

        response = client.responses.create(  # type: ignore[union-attr]
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an inventory analyst. Return strict JSON with this shape: "
                        "{\"reasons\": {\"<item_id>\": \"short explanation\"}}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Provide concise reorder reason per item: {json.dumps(prompt_payload)}",
                },
            ],
        )

        parsed = _extract_json_object(getattr(response, "output_text", ""))
        reason_map = parsed.get("reasons", {}) if parsed else {}
        if isinstance(reason_map, dict):
            for row in fallback:
                candidate = reason_map.get(str(row["item_id"]))
                if isinstance(candidate, str) and candidate.strip():
                    row["reason"] = candidate.strip()

        return {"source": "ai", "model": model, "suggestions": fallback}
    except Exception:
        return {"source": "fallback", "model": None, "suggestions": fallback}


def build_anomaly_alerts(
    events: list[QuantityEvent],
    item_index: dict[int, Item],
    limit: int = 20,
) -> dict[str, object]:
    if not events:
        return {"source": "fallback", "model": None, "alerts": []}

    magnitudes = [abs(event.quantity_delta) for event in events]
    avg = sum(magnitudes) / len(magnitudes)
    variance = sum((value - avg) ** 2 for value in magnitudes) / max(1, len(magnitudes) - 1)
    std = math.sqrt(variance)
    threshold = max(10.0, avg + (2 * std))

    fallback: list[dict[str, object]] = []
    for event in sorted(events, key=lambda row: row.created_at, reverse=True):
        magnitude = abs(event.quantity_delta)
        if magnitude < threshold:
            continue

        item = item_index.get(event.item_id)
        if not item:
            continue

        severity = "high" if magnitude >= threshold * 1.5 else "medium"
        fallback.append(
            {
                "item_id": item.id,
                "sku": item.sku,
                "name": item.name,
                "severity": severity,
                "quantity_delta": event.quantity_delta,
                "explanation": (
                    f"Unusually large {event.event_type.value} movement "
                    f"({event.quantity_delta:+d}) compared with recent baseline."
                ),
                "suggested_action": "Review related orders and count inventory for this SKU.",
                "created_at": event.created_at,
            }
        )
        if len(fallback) >= limit:
            break

    client, model = _get_openai_client()
    if client is None or not fallback:
        return {"source": "fallback", "model": None, "alerts": fallback}

    try:
        response = client.responses.create(  # type: ignore[union-attr]
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an inventory risk analyst. Return strict JSON: "
                        "{\"notes\": {\"<item_id>\": {\"explanation\": \"...\", \"action\": \"...\"}}}"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [
                            {
                                "item_id": row["item_id"],
                                "sku": row["sku"],
                                "name": row["name"],
                                "severity": row["severity"],
                                "quantity_delta": row["quantity_delta"],
                                "created_at": str(row["created_at"]),
                            }
                            for row in fallback
                        ]
                    ),
                },
            ],
        )

        parsed = _extract_json_object(getattr(response, "output_text", ""))
        note_map = parsed.get("notes", {}) if parsed else {}
        if isinstance(note_map, dict):
            for row in fallback:
                node = note_map.get(str(row["item_id"]))
                if isinstance(node, dict):
                    explanation = node.get("explanation")
                    action = node.get("action")
                    if isinstance(explanation, str) and explanation.strip():
                        row["explanation"] = explanation.strip()
                    if isinstance(action, str) and action.strip():
                        row["suggested_action"] = action.strip()

        return {"source": "ai", "model": model, "alerts": fallback}
    except Exception:
        return {"source": "fallback", "model": None, "alerts": fallback}


def parse_natural_language_filters(query: str) -> dict[str, object]:
    normalized = query.strip()
    fallback: dict[str, object] = {
        "q": normalized,
        "category": None,
        "status": None,
        "min_qty": None,
        "max_qty": None,
        "sort_by": "updated_at",
        "sort_dir": "desc",
    }

    category_match = re.search(r"category\s*[:=]\s*([a-zA-Z0-9\-\s]+)", normalized, re.IGNORECASE)
    if category_match:
        fallback["category"] = category_match.group(1).strip()

    lowered = normalized.lower()
    status_map = {
        "in stock": ItemStatus.IN_STOCK.value,
        "low stock": ItemStatus.LOW_STOCK.value,
        "ordered": ItemStatus.ORDERED.value,
        "discontinued": ItemStatus.DISCONTINUED.value,
    }
    for phrase, status in status_map.items():
        if phrase in lowered:
            fallback["status"] = status
            break

    under_match = re.search(r"(?:under|below|less than)\s+(\d+)", lowered)
    above_match = re.search(r"(?:above|over|more than)\s+(\d+)", lowered)
    if under_match:
        fallback["max_qty"] = int(under_match.group(1))
    if above_match:
        fallback["min_qty"] = int(above_match.group(1))

    client, model = _get_openai_client()
    if client is None:
        fallback["source"] = "fallback"
        fallback["model"] = None
        return fallback

    try:
        response = client.responses.create(  # type: ignore[union-attr]
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON with keys q, category, status, min_qty, max_qty, "
                        "sort_by, sort_dir. status must be one of in_stock, low_stock, ordered, discontinued."
                    ),
                },
                {"role": "user", "content": normalized},
            ],
        )

        parsed = _extract_json_object(getattr(response, "output_text", ""))
        if not parsed:
            fallback["source"] = "fallback"
            fallback["model"] = None
            return fallback

        merged = {**fallback}
        for key in ("q", "category", "status", "min_qty", "max_qty", "sort_by", "sort_dir"):
            value = parsed.get(key)
            if value is None:
                continue
            merged[key] = value

        merged["source"] = "ai"
        merged["model"] = model
        return merged
    except Exception:
        fallback["source"] = "fallback"
        fallback["model"] = None
        return fallback


def make_ai_note_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"
