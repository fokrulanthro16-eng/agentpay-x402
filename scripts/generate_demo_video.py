"""Automated Demo Video Recording & MP4 Rendering Pipeline for AgentPay-x402.

Uses Playwright to automate full 1080p browser actions matching DEMO_SCRIPT.md,
captures raw high-fidelity screen recording, and synchronizes with the AI voiceover
track using FFmpeg to export assets/demo_video.mp4.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"


def get_audio_duration(audio_path: Path) -> float:
    """Extract exact duration of the voiceover audio file using FFmpeg."""
    cmd = [FFMPEG_EXE, "-i", str(audio_path)]
    result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            # Parse 'Duration: 00:02:57.19, start: ...'
            parts = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = parts.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 150.0  # Default 2m 30s


def record_browser_automation(output_dir: Path, target_runtime_sec: float) -> Path:
    """Drive Playwright to record the live dashboard and execute demo script actions."""
    from playwright.sync_api import sync_playwright

    recordings_temp = output_dir / "temp_recording"
    recordings_temp.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("      AgentPay-x402: Automated Video Recording (Playwright 1080p)      ")
    print("=" * 75)
    print(f"Target Runtime:     {target_runtime_sec:.1f} seconds")
    print(f"Viewport:           1920 x 1080 (Full HD)")
    print(f"Target Gateway URL: http://127.0.0.1:8000")
    print("=" * 75)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=str(recordings_temp),
            record_video_size={"width": 1920, "height": 1080},
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Automatically accept browser dialogs/alerts (e.g. for replay attack testing)
        page.on("dialog", lambda dialog: dialog.accept())

        start_time = time.time()

        def elapsed():
            return time.time() - start_time

        def wait_until(target_sec: float):
            rem = target_sec - elapsed()
            if rem > 0:
                page.wait_for_timeout(int(rem * 1000))

        # -------------------------------------------------------------
        # Scene 1: The Problem & Dashboard Overview (0s - 35s)
        # -------------------------------------------------------------
        print("\n>> [Scene 1/5] Recording: Hook & System Overview (0s - 35s)...")
        page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Highlight Logo & Status Badges
        page.hover("header .flex.items-center.gap-3")
        page.wait_for_timeout(3000)

        # Hover over top live status pills
        page.hover("header span:has-text('Solana Devnet')")
        page.wait_for_timeout(3000)

        # Smooth scroll to Wallet Cards
        page.mouse.wheel(0, 200)
        page.wait_for_timeout(2000)
        page.hover("#merchant-pubkey-short")
        page.wait_for_timeout(4000)
        page.hover("#agent-pubkey-short")
        page.wait_for_timeout(4000)

        # Click balance refresh button to show live RPC polling
        page.click("button[title='Refresh Balance']")
        page.wait_for_timeout(4000)

        wait_until(35.0)

        # -------------------------------------------------------------
        # Scene 2: Protocol Mechanics & Raw 402 Challenge (35s - 70s)
        # -------------------------------------------------------------
        print(">> [Scene 2/5] Recording: Raw RFC/x402 Protocol Challenge (35s - 70s)...")
        # Scroll to Controls
        page.mouse.wheel(0, 150)
        page.wait_for_timeout(2000)

        # Click Unauthenticated Browser Test (Raw 402)
        btn_unauth = page.locator("button:has-text('Unauthenticated Browser Test')")
        btn_unauth.hover()
        page.wait_for_timeout(2000)
        btn_unauth.click()
        page.wait_for_timeout(2000)

        # Modal is open: hover over response headers & body
        page.hover("#modal-402-headers")
        page.wait_for_timeout(10000)
        page.hover("#modal-402-body")
        page.wait_for_timeout(10000)

        # Close modal
        page.click("#modal-402 button:has-text('Close')")
        page.wait_for_timeout(2000)

        wait_until(70.0)

        # -------------------------------------------------------------
        # Scene 3: Autonomous Live Run & LLM Settlement (70s - 120s)
        # -------------------------------------------------------------
        print(">> [Scene 3/5] Recording: Autonomous AI Agent Simulation (70s - 120s)...")
        # Click Simulate Autonomous Agent Run (GET market feed: 20,000 lamports)
        btn_sim = page.locator("#btn-run-agent")
        btn_sim.hover()
        page.wait_for_timeout(1500)
        btn_sim.click()

        # Allow SSE stream to populate terminal logs (settlement + Alpaca metrics)
        page.wait_for_timeout(15000)

        # Scroll into terminal logs to inspect output
        page.hover("#terminal-logs")
        page.wait_for_timeout(5000)

        # Switch dropdown to POST /api/v1/agent-inference (5,000 lamports)
        page.select_option("#select-endpoint", "/api/v1/agent-inference")
        page.wait_for_timeout(2000)

        # Click Simulate again to run Nebius Nemotron inference
        btn_sim.click()
        page.wait_for_timeout(20000)

        # Hover over Nemotron reasoning trace
        page.mouse.wheel(0, 100)
        page.wait_for_timeout(5000)

        wait_until(115.0)

        # -------------------------------------------------------------
        # Scene 4: Security & Replay Attack Defense (115s - 150s)
        # -------------------------------------------------------------
        print(">> [Scene 4/5] Recording: Replay Attack Defense & Activity Feed (115s - 150s)...")
        # Click Test Replay Attack Defense
        btn_replay = page.locator("button:has-text('Test Replay Attack Defense')")
        btn_replay.hover()
        page.wait_for_timeout(2000)
        btn_replay.click()
        page.wait_for_timeout(4000)

        # Scroll down to Live Activity Feed
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(3000)
        page.hover("#activity-feed-list")
        page.wait_for_timeout(8000)

        wait_until(150.0)

        # -------------------------------------------------------------
        # Scene 5: Outro & System Architecture Overview (150s - End)
        # -------------------------------------------------------------
        print(f">> [Scene 5/5] Recording: Architecture Outro (150s - {target_runtime_sec:.1f}s)...")
        # Scroll smoothly back up to showcase complete interface
        page.mouse.wheel(0, -600)
        page.wait_for_timeout(2000)
        page.hover("header")
        
        # Hold until target audio runtime completes
        wait_until(target_runtime_sec + 1.0)

        video_path = page.video.path()
        context.close()
        browser.close()

    print(f">> Browser automation complete in {elapsed():.1f}s.")
    return Path(video_path)


def render_synchronized_video(raw_video_path: Path, audio_path: Path, output_video_path: Path, raw_screen_mp4: Path):
    """Combine video and audio using FFmpeg with high quality H.264 & AAC encoding."""
    print("=" * 75)
    print("      Encoding Raw Screen MP4 and Merging Synchronized Video           ")
    print("=" * 75)

    # 1. Convert raw WebM to raw_screen.mp4 (H.264 video, no audio)
    print(f">> Exporting raw screen recording to: {raw_screen_mp4}...")
    cmd_raw = [
        FFMPEG_EXE, "-y",
        "-i", str(raw_video_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        str(raw_screen_mp4)
    ]
    subprocess.run(cmd_raw, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    print(f">> [OK] Raw screen saved ({raw_screen_mp4.stat().st_size:,} bytes).")

    # 2. Synchronize with demo_voiceover.mp3 to produce demo_video.mp4
    print(f">> Merging with audio track: {audio_path} -> {output_video_path}...")
    cmd_merge = [
        FFMPEG_EXE, "-y",
        "-i", str(raw_screen_mp4),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_video_path)
    ]
    subprocess.run(cmd_merge, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    print(f">> [OK] Synchronized demo video exported ({output_video_path.stat().st_size:,} bytes).")


def main():
    workspace = Path(__file__).resolve().parent.parent
    assets_dir = workspace / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    audio_file = assets_dir / "demo_voiceover.mp3"
    raw_screen_file = assets_dir / "raw_screen.mp4"
    final_video_file = assets_dir / "demo_video.mp4"

    if not audio_file.exists():
        print(f"Voiceover file missing at {audio_file}. Generating voiceover first...")
        import scripts.generate_voiceover as vo
        import asyncio
        asyncio.run(vo.main())

    target_duration = get_audio_duration(audio_file)
    print(f"Detected Voiceover Duration: {target_duration:.2f} seconds ({int(target_duration//60)}m {int(target_duration%60)}s)")

    # Execute browser recording
    temp_webm = record_browser_automation(assets_dir, target_duration)

    # Encode & Merge
    render_synchronized_video(temp_webm, audio_file, final_video_file, raw_screen_file)

    # Cleanup temporary WebM directory
    temp_dir = assets_dir / "temp_recording"
    if temp_dir.exists():
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Validate output
    assert final_video_file.exists(), "Final video file was not generated"
    final_dur = get_audio_duration(final_video_file)

    print("\n" + "=" * 75)
    print("      AUTOMATED DEMO VIDEO GENERATION COMPLETE                         ")
    print("=" * 75)
    print(f"Raw Screen Recording:  {raw_screen_file} ({raw_screen_file.stat().st_size:,} bytes)")
    print(f"Final Demo Video:      {final_video_file} ({final_video_file.stat().st_size:,} bytes)")
    print(f"Final Video Duration:  {final_dur:.2f} seconds")
    print(f"Resolution & Codec:    1920x1080 (Full HD) | H.264 / AAC")
    print("=" * 75)


if __name__ == "__main__":
    main()
