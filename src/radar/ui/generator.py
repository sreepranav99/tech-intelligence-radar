import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from jinja2 import Template
from radar.config import BRIEFINGS_DIR

TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

def classify_ring(novelty: float, velocity: float) -> str:
    """Classify into Thoughtworks Radar rings."""
    if velocity >= 8.5 and novelty >= 7.5:
        return "ADOPT"
    elif velocity >= 7.0 or novelty >= 7.0:
        return "TRIAL"
    elif velocity >= 5.5:
        return "ASSESS"
    return "HOLD"

def generate_radar_html_from_state(state, output_dir: Path = BRIEFINGS_DIR) -> Path:
    """Generate visual interactive Tech Radar HTML file from a RadarState instance."""
    items_payload: List[Dict[str, Any]] = []

    for item in state.verified_items:
        cand = item.candidate
        sig = cand.signal
        ring = classify_ring(cand.novelty_score, cand.velocity_score)
        v_delta = sig.metrics.get("velocity_delta", {})

        items_payload.append({
            "title": sig.title,
            "url": sig.url,
            "category": cand.category,
            "ring": ring,
            "novelty_score": cand.novelty_score,
            "velocity_score": cand.velocity_score,
            "source_type": sig.source_type,
            "verified_metrics": item.verified_metrics,
            "velocity_delta": v_delta,
            "justification": cand.justification,
            "fact_check_notes": item.fact_check_notes
        })

    return _render_template(
        topic=state.topic_query,
        run_id=state.run_id,
        items=items_payload,
        output_dir=output_dir
    )

def generate_radar_html_from_entities(
    topic: str,
    entities: List[Dict[str, Any]],
    output_dir: Path = BRIEFINGS_DIR
) -> Path:
    """Generate visual interactive Tech Radar HTML from raw SQLite database rows."""
    items_payload: List[Dict[str, Any]] = []

    for idx, e in enumerate(entities, start=1):
        novelty = float(e.get("novelty_score", 6.0))
        velocity = float(e.get("velocity_score", 6.0))
        ring = classify_ring(novelty, velocity)
        
        metrics = {}
        if e.get("verified_metrics_json"):
            try:
                metrics = json.loads(e["verified_metrics_json"])
            except Exception:
                pass

        items_payload.append({
            "title": e.get("entity_name", f"Entity {idx}"),
            "url": e.get("source_url", "#"),
            "category": e.get("category", "Framework / SDK"),
            "ring": ring,
            "novelty_score": novelty,
            "velocity_score": velocity,
            "source_type": e.get("source_type", "github"),
            "verified_metrics": metrics,
            "velocity_delta": {"badge": "Tracked Entity"},
            "justification": e.get("summary", ""),
            "fact_check_notes": e.get("key_takeaways", "Verified from Radar Database.")
        })

    now_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return _render_template(
        topic=topic,
        run_id=f"db_{now_slug}",
        items=items_payload,
        output_dir=output_dir
    )

def _render_template(
    topic: str,
    run_id: str,
    items: List[Dict[str, Any]],
    output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_str)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    radar_data = {
        "topic": topic,
        "run_id": run_id,
        "generated_at": now_str,
        "items": items
    }

    rendered_html = template.render(
        topic=topic,
        run_id=run_id[:8] if len(run_id) > 8 else run_id,
        generated_at=now_str,
        radar_data_json=json.dumps(radar_data, indent=2)
    )

    # Save timestamped archive & latest file
    archive_file = output_dir / f"radar_{date_slug}_{run_id[:8]}.html"
    latest_file = output_dir / "radar_latest.html"

    archive_file.write_text(rendered_html, encoding="utf-8")
    latest_file.write_text(rendered_html, encoding="utf-8")

    return latest_file
