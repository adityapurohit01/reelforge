"""Stage 8 QC Gates Pipeline Stage for ReelForge.
Runs automated checks across video, audio, claims, safe areas, and speech recognition.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from reelforge.config import ReelForgeConfig, load_config
from reelforge.qc.checks import QualityControlGate

logger = logging.getLogger(__name__)


def run_qc_stage(
    video_path: Path,
    audio_path: Path,
    script_text: str,
    hook_text: str,
    caption_text: str,
    words_data: List[Dict[str, Any]],
    run_dir: Path,
    config: Optional[ReelForgeConfig] = None,
    is_preview: bool = False,
) -> Dict[str, Any]:
    """Execute Stage 8 Quality Control Gate and write qc_report.json."""
    gate = QualityControlGate(config)
    report = gate.run_qc(
        video_path=video_path,
        audio_path=audio_path,
        script_text=script_text,
        hook_text=hook_text,
        caption_text=caption_text,
        words_data=words_data,
        is_preview=is_preview,
    )

    qc_report_path = run_dir / "qc_report.json"
    with open(qc_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(
        f"QC Gate completed. Passed: {report['passed']}. "
        f"Hard failures: {len(report['hard_failures'])}, Soft warnings: {len(report['soft_warnings'])}"
    )
    return report
