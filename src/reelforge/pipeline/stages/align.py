"""Stage 6 Alignment for ReelForge.
Aligns speech audio with script text to produce word-level timestamps (words.json)
using faster-whisper with proportional timing fallback.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from reelforge.pipeline.stages.dialogue import CallEvent, DialogueScript

logger = logging.getLogger(__name__)


class WordTimestampItem(BaseModel):
    word: str
    start: float
    end: float
    speaker: str


def compute_proportional_word_timestamps(
    turn_text: str,
    turn_start: float,
    turn_end: float,
    speaker: str,
) -> List[WordTimestampItem]:
    """Fallback word timestamp generator distributing duration proportionally across words."""
    words = turn_text.split()
    if not words:
        return []

    total_chars = sum(len(w) for w in words)
    duration = turn_end - turn_start
    items = []
    cur_t = turn_start

    for w in words:
        w_dur = max(0.12, duration * (len(w) / total_chars)) if total_chars > 0 else duration / len(words)
        end_t = min(turn_end, cur_t + w_dur)
        items.append(
            WordTimestampItem(
                word=w,
                start=round(cur_t, 3),
                end=round(end_t, 3),
                speaker=speaker,
            )
        )
        cur_t = end_t

    return items


def align_speech(
    script: DialogueScript,
    turn_timings: List[Dict[str, Any]],
    per_turn_clips: List[str],
    run_dir: Path,
    use_whisper: bool = True,
) -> Dict[str, Any]:
    """Generate word-level timestamps and anchor call events to absolute timestamps."""
    all_words: List[WordTimestampItem] = []
    whisper_model = None

    if use_whisper:
        try:
            from faster_whisper import WhisperModel
            whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception as e:
            logger.warning(f"Could not load faster-whisper model ({e}), falling back to proportional alignment.")
            whisper_model = None

    for i, timing in enumerate(turn_timings):
        turn = script.turns[i]
        turn_start = timing["start"]
        turn_end = timing["end"]
        clip_path = per_turn_clips[i] if i < len(per_turn_clips) else None

        aligned_for_turn = []
        if whisper_model and clip_path and Path(clip_path).exists():
            try:
                segments, _ = whisper_model.transcribe(clip_path, word_timestamps=True, language="en")
                for seg in segments:
                    if seg.words:
                        for w in seg.words:
                            aligned_for_turn.append(
                                WordTimestampItem(
                                    word=w.word.strip(),
                                    start=round(turn_start + w.start, 3),
                                    end=round(turn_start + w.end, 3),
                                    speaker=turn.speaker,
                                )
                            )
            except Exception as e:
                logger.warning(f"Whisper turn alignment error: {e}")

        # If whisper returned no words or fallback needed
        if not aligned_for_turn:
            aligned_for_turn = compute_proportional_word_timestamps(
                turn.text, turn_start, turn_end, turn.speaker
            )

        all_words.extend(aligned_for_turn)

    # Anchor call events to turn timestamps
    anchored_events = []
    for evt in script.events:
        idx = min(evt.turn_index, len(turn_timings) - 1)
        event_time = turn_timings[idx]["start"] + 0.4
        anchored_events.append(
            {
                "turn_index": evt.turn_index,
                "time_seconds": round(event_time, 2),
                "type": evt.type,
                "text": evt.text,
            }
        )

    words_data = [w.model_dump() for w in all_words]
    words_path = run_dir / "words.json"
    with open(words_path, "w", encoding="utf-8") as f:
        json.dump(words_data, f, indent=2)

    events_path = run_dir / "events.json"
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump(anchored_events, f, indent=2)

    return {
        "words_path": str(words_path),
        "events_path": str(events_path),
        "words": words_data,
        "events": anchored_events,
        "total_words_aligned": len(words_data),
    }
