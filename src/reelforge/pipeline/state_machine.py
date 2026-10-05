"""ReelForge Resumable Pipeline State Machine.
Orchestrates sequential video generation stages:
PLANNED -> PROFILED -> SCRIPTED -> VOICED -> ALIGNED -> RENDERED -> QC_PASSED -> AWAITING_APPROVAL -> APPROVED -> UPLOADED -> PUBLISHED -> METRICS_COLLECTED
Plus FAILED_<STAGE> and REJECTED states.
Idempotent per stage; supports automatic resume and run artifact tracking.
"""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid
from sqlmodel import Session, select

from reelforge.config import ReelForgeConfig, load_config
from reelforge.db import get_engine, init_db
from reelforge.models import Business, Fingerprint, Plan, Run, Video
from reelforge.pipeline.stages.align import align_speech
from reelforge.pipeline.stages.approve import run_approval_stage
from reelforge.pipeline.stages.captions import generate_post_caption
from reelforge.pipeline.stages.dialogue import generate_dialogue, DialogueScript
from reelforge.pipeline.stages.profile import generate_business_profile, BusinessProfile
from reelforge.pipeline.stages.qc import run_qc_stage
from reelforge.pipeline.stages.render import prepare_render_props, render_video
from reelforge.pipeline.stages.simulate import ScriptedSimulator
from reelforge.pipeline.stages.tts import run_tts_and_mix
from reelforge.pipeline.stages.upload import run_upload_stage
from reelforge.pipeline.stages.publish import run_publish_stage
from reelforge.diversity.sampler import NoveltySampler
from reelforge.diversity.fingerprint import FingerprintEngine

logger = logging.getLogger(__name__)


class PipelineExecutionError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(f"Stage {stage} failed: {message}")
        self.stage = stage
        self.message = message


class ReelForgeStateMachine:
    def __init__(self, config: Optional[ReelForgeConfig] = None, session: Optional[Session] = None):
        self.config = config or load_config()
        self.engine = get_engine()
        init_db(self.engine)
        self.session = session or Session(self.engine)
        self.sampler = NoveltySampler()
        self.simulator = ScriptedSimulator()
        self.fp_engine = FingerprintEngine(self.config)

    def _get_run_dir(self, run_id: str) -> Path:
        run_dir = Path("runs") / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def run_pipeline(
        self,
        run_id: Optional[str] = None,
        seed: Optional[int] = None,
        dry_run: bool = True,
        preview: bool = True,
        force: bool = False,
        stop_at_approval: bool = True,
    ) -> Dict[str, Any]:
        """Execute full end-to-end pipeline run with state persistence."""
        r_id = run_id or f"run_{uuid.uuid4().hex[:10]}"
        run_seed = seed if seed is not None else int(time.time() * 1000) % 1_000_000
        run_dir = Path(self._get_run_dir(r_id))
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. State / Run tracking in DB
        run_rec = self.session.exec(select(Run).where(Run.run_id == r_id)).first()
        if not run_rec:
            run_rec = Run(
                run_id=r_id,
                state="PLANNED",
                started_at=datetime.now(timezone.utc),
                stage_timings_json="{}",
            )
            self.session.add(run_rec)
            self.session.commit()
            self.session.refresh(run_rec)

        timings: Dict[str, float] = json.loads(run_rec.stage_timings_json or "{}")

        # --- Stage 1: Planning ---
        t0 = time.time()
        plan_rec = self.session.exec(select(Plan).where(Plan.run_id == r_id)).first()
        if not plan_rec or force:
            plan_axes, relaxations = self.sampler.sample_plan(session=self.session, seed=run_seed)
            if not plan_rec:
                plan_rec = Plan(
                    run_id=r_id,
                    axis_tuple_json=json.dumps(plan_axes),
                    seed=run_seed,
                    relaxations_json=json.dumps(relaxations),
                )
                self.session.add(plan_rec)
            else:
                plan_rec.axis_tuple_json = json.dumps(plan_axes)
                plan_rec.relaxations_json = json.dumps(relaxations)
            self.session.commit()
            self.session.refresh(plan_rec)
        else:
            plan_axes = json.loads(plan_rec.axis_tuple_json)
        timings["planner"] = round(time.time() - t0, 3)

        # --- Stage 2: Business Profile ---
        t0 = time.time()
        biz_rec = self.session.exec(
            select(Business).join(Video, Video.business_id == Business.id).where(Video.run_id == r_id)
        ).first()

        profile_path = run_dir / "profile.json"
        if not biz_rec or not profile_path.exists() or force:
            profile = generate_business_profile(plan_axes, seed=run_seed, use_llm=False)
            with open(profile_path, "w", encoding="utf-8") as f:
                f.write(profile.model_dump_json(indent=2))

            biz_rec = Business(
                name=profile.name,
                vertical=profile.vertical,
                city=profile.city,
                locale=profile.city,
                owner_name=profile.owner_first_name,
                profile_json=profile.model_dump_json(),
            )
            self.session.add(biz_rec)
            self.session.commit()
            self.session.refresh(biz_rec)
        else:
            profile = BusinessProfile.model_validate_json(biz_rec.profile_json)
        timings["profile"] = round(time.time() - t0, 3)

        # Ensure Video Record
        video_rec = self.session.exec(select(Video).where(Video.run_id == r_id)).first()
        if not video_rec:
            video_rec = Video(
                run_id=r_id,
                business_id=biz_rec.id,
                state="PROFILED",
            )
            self.session.add(video_rec)
            self.session.commit()
            self.session.refresh(video_rec)

        # --- Stage 3: Dialogue Script ---
        t0 = time.time()
        script_path = run_dir / "dialogue.json"
        if not video_rec.script_json or not script_path.exists() or force:
            script = generate_dialogue(plan_axes, profile, seed=run_seed, use_llm=False)
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script.model_dump_json(indent=2))
            video_rec.script_json = script.model_dump_json()
            video_rec.state = "SCRIPTED"
            self.session.commit()
        else:
            script = DialogueScript.model_validate_json(video_rec.script_json)
        timings["dialogue"] = round(time.time() - t0, 3)

        # --- Stage 4 & 5: Simulation & Audio TTS Mix ---
        t0 = time.time()
        simulated = self.simulator.run(script, profile)
        mix_wav_path = run_dir / "mix.wav"
        envelope_path = run_dir / "amplitude_envelope.json"

        if not mix_wav_path.exists() or force:
            audio_res = run_tts_and_mix(
                simulated_call=simulated,
                run_dir=run_dir,
                agent_voice=plan_axes.get("agent_voice", "af_heart"),
                caller_voice=plan_axes.get("caller_voice", "am_adam"),
                speed_jitter=plan_axes.get("speed_jitter", 0.0),
                phone_effect=plan_axes.get("phone_effect", False),
            )
            video_rec.audio_path = str(mix_wav_path)
            video_rec.loudness_lufs = audio_res.get("loudness_lufs")
            video_rec.duration_s = audio_res.get("duration_seconds")
            video_rec.state = "VOICED"
            self.session.commit()
        else:
            with open(envelope_path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
            audio_res = {
                "mix_wav_path": mix_wav_path,
                "envelope_path": envelope_path,
                "amplitude_envelope": envelope,
                "turn_timings": [
                    {"index": i, "start_time": t.pause_after_ms / 1000.0, "duration": 2.0}
                    for i, t in enumerate(script.turns)
                ],
                "per_turn_clips": list(run_dir.glob("turn_*.wav")),
                "loudness_lufs": video_rec.loudness_lufs or -14.0,
                "duration_seconds": video_rec.duration_s or 25.0,
            }
        timings["tts_and_mix"] = round(time.time() - t0, 3)

        # --- Stage 6: Word Alignment ---
        t0 = time.time()
        words_path = run_dir / "words.json"
        if not words_path.exists() or force:
            align_res = align_speech(
                script=script,
                turn_timings=audio_res["turn_timings"],
                per_turn_clips=audio_res["per_turn_clips"],
                run_dir=run_dir,
                use_whisper=False,
            )
            video_rec.state = "ALIGNED"
            self.session.commit()
        else:
            with open(words_path, "r", encoding="utf-8") as f:
                align_res = json.load(f)
        timings["alignment"] = round(time.time() - t0, 3)

        # --- Stage 7: Video Render (Remotion) ---
        t0 = time.time()
        video_output_path = run_dir / f"{r_id}.mp4"
        cover_output_path = run_dir / f"{r_id}_cover.jpg"

        if not video_output_path.exists() or force:
            comp_id, props_path = prepare_render_props(
                plan_axes=plan_axes,
                profile=profile,
                script=script,
                audio_result=audio_res,
                align_result=align_res,
                run_dir=run_dir,
            )
            render_res = render_video(
                composition_id=comp_id,
                props_path=props_path,
                output_video_path=video_output_path,
                cover_image_path=cover_output_path,
                preview=preview,
            )
            video_rec.video_path = str(video_output_path)
            video_rec.cover_path = str(cover_output_path)
            video_rec.state = "RENDERED"
            self.session.commit()
        timings["render"] = round(time.time() - t0, 3)

        # --- Stage 8: QC Gates ---
        t0 = time.time()
        qc_report_path = run_dir / "qc_report.json"
        post_meta = generate_post_caption(profile, script, plan_axes, seed=run_seed, config=self.config)
        video_rec.caption = post_meta.caption
        video_rec.hashtags_json = json.dumps(post_meta.hashtags)

        qc_report = run_qc_stage(
            video_path=video_output_path,
            audio_path=mix_wav_path,
            script_text=" ".join(t.text for t in script.turns),
            hook_text=script.hook_text,
            caption_text=post_meta.caption,
            words_data=align_res.get("words", []),
            run_dir=run_dir,
            config=self.config,
            is_preview=preview,
        )
        video_rec.qc_report_json = json.dumps(qc_report)
        video_rec.state = "QC_PASSED" if qc_report.get("passed", False) else "FAILED_QC"
        self.session.commit()
        timings["qc_gates"] = round(time.time() - t0, 3)

        if not qc_report.get("passed", False):
            run_rec.state = "FAILED_QC"
            run_rec.error = "; ".join(qc_report.get("hard_failures", []))
            self.session.commit()
            raise PipelineExecutionError("QC", run_rec.error)

        # --- Stage 9 & 10: Telegram Founder Approval ---
        t0 = time.time()
        allowed_chats = self.config.settings.telegram_allowed_chat_ids
        if isinstance(allowed_chats, (list, tuple)) and allowed_chats:
            target_chat = int(allowed_chats[0])
        elif isinstance(allowed_chats, str):
            try:
                parsed = json.loads(allowed_chats)
                target_chat = int(parsed[0]) if parsed else 12345678
            except Exception:
                clean = allowed_chats.replace("[", "").replace("]", "").split(",")
                target_chat = int(clean[0].strip()) if clean and clean[0].strip() else 12345678
        else:
            target_chat = 12345678
        approval_res = run_approval_stage(
            chat_id=target_chat,
            video_id=video_rec.id,
            video_path=video_output_path,
            cover_path=cover_output_path,
            caption_text=post_meta.caption,
            business_profile=profile.model_dump(),
            plan_axes=plan_axes,
            qc_report=qc_report,
            config=self.config,
        )
        video_rec.state = "AWAITING_APPROVAL"
        run_rec.state = "AWAITING_APPROVAL"
        self.session.commit()
        timings["approval_dispatch"] = round(time.time() - t0, 3)

        # Update run manifest
        manifest = {
            "run_id": r_id,
            "seed": run_seed,
            "state": run_rec.state,
            "business": profile.name,
            "vertical": profile.vertical,
            "city": profile.city,
            "layout": plan_axes.get("layout"),
            "palette": plan_axes.get("palette"),
            "timings_seconds": timings,
            "total_wall_clock_seconds": round(sum(timings.values()), 2),
            "video_path": str(video_output_path),
            "cover_path": str(cover_output_path),
        }
        with open(run_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        run_rec.stage_timings_json = json.dumps(timings)
        self.session.commit()

        if stop_at_approval:
            logger.info(f"Run {r_id} completed successfully and stopped at AWAITING_APPROVAL.")
            return manifest

        # --- Stage 11 & 12: Upload & Publish (if approval auto-granted) ---
        upload_res = run_upload_stage(video_output_path, cover_output_path, config=self.config)
        pub_res = run_publish_stage(
            video_id=video_rec.id,
            video_url=upload_res["video_url"],
            caption=post_meta.caption,
            cover_url=upload_res.get("cover_url"),
            session=self.session,
            config=self.config,
            dry_run=dry_run,
        )

        video_rec.state = "PUBLISHED"
        run_rec.state = "PUBLISHED"
        run_rec.finished_at = datetime.now(timezone.utc)
        self.session.commit()

        manifest["published"] = pub_res
        return manifest

    def resume_run(self, run_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """Resume an existing run from its last completed state."""
        run_rec = self.session.exec(select(Run).where(Run.run_id == run_id)).first()
        if not run_rec:
            raise ValueError(f"Run ID '{run_id}' not found in database.")

        logger.info(f"Resuming run {run_id} from current state: {run_rec.state}")
        # Run pipeline with force=False: finished stages are idempotent no-ops
        return self.run_pipeline(run_id=run_id, dry_run=dry_run, force=False)


def run_pipeline(
    run_id: Optional[str] = None,
    seed: Optional[int] = None,
    dry_run: bool = True,
    preview: bool = True,
    force: bool = False,
    stop_at_approval: bool = True,
) -> Dict[str, Any]:
    """Helper entry point for pipeline execution."""
    sm = ReelForgeStateMachine()
    return sm.run_pipeline(
        run_id=run_id,
        seed=seed,
        dry_run=dry_run,
        preview=preview,
        force=force,
        stop_at_approval=stop_at_approval,
    )


def resume_run(run_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """Helper entry point to resume a run."""
    sm = ReelForgeStateMachine()
    return sm.resume_run(run_id=run_id, dry_run=dry_run)
