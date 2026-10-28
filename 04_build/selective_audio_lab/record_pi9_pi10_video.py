"""Record actual UI + disclosed synthetic Spanish narration, as a support demo.

Optional: pip install playwright==1.55.0 espeakng-loader==0.2.4;
playwright install chromium. Requires ffmpeg. Does not impersonate the tesista.
"""
from __future__ import annotations

import argparse
import ctypes as c
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from playwright.sync_api import sync_playwright
import espeakng_loader

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from web_server import create_server


def make_voice(texts):
    lib = espeakng_loader.load_library()
    lib.espeak_Initialize.argtypes = [c.c_int, c.c_int, c.c_char_p, c.c_int]
    lib.espeak_Initialize.restype = c.c_int
    sr = lib.espeak_Initialize(2, 0, str(Path(espeakng_loader.get_data_path()).parent).encode(), 0)
    if sr <= 0:
        raise RuntimeError("Narration engine unavailable")
    chunks = []
    @c.CFUNCTYPE(c.c_int, c.POINTER(c.c_short), c.c_int, c.c_void_p)
    def cb(wav, n, events):
        if n:
            chunks.append(c.string_at(wav, n * 2))
        return 0
    lib.espeak_SetSynthCallback(cb)
    assert lib.espeak_SetVoiceByName(b"es") == 0
    lib.espeak_SetParameter(1, 155, 0)
    lib.espeak_Synth.argtypes = [c.c_void_p, c.c_size_t, c.c_uint, c.c_int, c.c_uint, c.c_uint, c.c_void_p, c.c_void_p]
    voices = []
    for text in texts:
        chunks.clear()
        data = text.encode("utf-8")
        assert lib.espeak_Synth(data, len(data) + 1, 0, 1, 0, 1, None, None) == 0
        lib.espeak_Synchronize()
        audio = np.frombuffer(b"".join(chunks), dtype="int16").astype(np.float32) / 32768
        voices.append(np.concatenate([audio * .9, np.zeros(sr, np.float32)]))
    return sr, voices


def record(out):
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = out.parent / "video_work"
    work.mkdir(parents=True, exist_ok=True)
    script = json.loads((ROOT.parents[1] / "06_presentation/pi9_pi10/video_script.json").read_text())
    sr, voices = make_voice([x["text"] for x in script])
    print("NARRATION_SECONDS", sum(len(x)/sr for x in voices), flush=True)
    outputs = ROOT / "outputs/pi9_pi10_video"
    server = create_server("127.0.0.1", 0, output_root=outputs,
                           evidence_root=outputs/"isolated_status", dataset_root=ROOT/"data/not_mounted")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    tracks, chapters = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                      record_video_dir=str(work), record_video_size={"width": 1440, "height": 1000})
            video_start = time.monotonic()
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}")
            page.wait_for_function("document.querySelector('#healthText').textContent==='Servicio operativo'")
            page.add_style_tag(content="body:after{content:'PI9 / PI10 · Captura real automatizada · Narración sintética de apoyo';position:fixed;bottom:0;left:0;right:0;z-index:99;background:#111827;color:white;font:13px system-ui;padding:9px;text-align:center;pointer-events:none}")
            tracks.append(np.zeros(round((time.monotonic()-video_start)*sr), np.float32))
            def wait_until(deadline):
                while time.monotonic() < deadline:
                    page.wait_for_timeout(min(10000, max(1, (deadline-time.monotonic())*1000)))
                    print("RECORDING", round(time.monotonic()-video_start), flush=True)
            for chapter, voice in zip(script, voices):
                ident = chapter["id"]
                print("CHAPTER", ident, flush=True)
                chapter_start = time.monotonic()
                chapter_offset = sum(len(t) for t in tracks) / sr
                chapters.append({"id": ident, "title": chapter["title"], "start_seconds": chapter_offset})
                media = []
                if ident in ("overview", "deep", "benchmark", "edge"):
                    page.locator(f'[data-page="{ident}"]').click()
                    page.evaluate("scrollTo(0,0)")
                elif ident == "cnn":
                    page.locator('[data-page="attenuation"]').click()
                    page.locator("#engine").select_option("cnn_experimental")
                    page.locator("#demoTarget").select_option("drilling_synthetic")
                    page.locator("#runAttBtn").click()
                    page.locator("#attResults").wait_for(state="visible", timeout=60000)
                    run_id = page.locator("#policyBox code").first.inner_text()
                    page.locator("#attResults").scroll_into_view_if_needed()
                    media = [("#mixAudio", outputs/run_id/"mixture.wav"), ("#outAudio", outputs/run_id/"output_selective.wav")]
                elif ident == "comparison":
                    page.evaluate("scrollTo(0,0)")
                    page.locator("#compareBtn").click()
                    page.locator("#comparisonResults").wait_for(state="visible", timeout=60000)
                    page.locator("#verifyComparisonBtn").click()
                    page.wait_for_function("document.querySelector('#comparisonIntegrity').textContent.includes('ÍNTEGRA')")
                    pair_id = page.locator("#comparisonIdentity").inner_text().split(" · ")[0]
                    page.locator("#comparisonRows").scroll_into_view_if_needed()
                    media = [("#comparisonMedia audio >> nth=0", outputs/f"{pair_id}-ORACLE"/"output_selective.wav"),
                             ("#comparisonMedia audio >> nth=1", outputs/f"{pair_id}-CNN"/"output_selective.wav")]
                elif ident == "block":
                    page.evaluate("scrollTo(0,0)")
                    page.locator("#demoTarget").select_option("siren_synthetic")
                    page.locator("#runAttBtn").click()
                    page.locator("#attResults").wait_for(state="visible", timeout=60000)
                    page.locator("#policyBox").scroll_into_view_if_needed()
                    assert "cnn_experimental / bypass" in page.locator("#policyBox").inner_text()
                elif ident == "evidence":
                    page.locator('[data-page="evidence"]').click()
                    page.locator('#runRows button', has_text="Verificar").first.click()
                    page.wait_for_function("document.querySelector('#runRows').textContent.includes('ÍNTEGRO')")
                    page.evaluate("scrollTo(0,0)")
                tracks.append(voice)
                wait_until(chapter_start + len(voice)/sr)
                for selector, path in media:
                    data, audio_sr = sf.read(path, dtype="float32")
                    if audio_sr != sr:
                        from math import gcd
                        g = gcd(audio_sr, sr)
                        data = resample_poly(data, sr//g, audio_sr//g)
                    # Playback volume only; experiment artifacts remain unchanged.
                    page.locator(selector).evaluate("a=>{a.volume=.35; return a.play()}")
                    tracks.append(np.concatenate([data*.35, np.zeros(sr, np.float32)]))
                    wait_until(time.monotonic() + len(data)/sr + 1)
                # Compensate UI/encoding overhead with silence to keep next chapter aligned.
                actual = time.monotonic() - video_start
                scheduled = sum(len(t) for t in tracks)/sr
                if actual > scheduled:
                    tracks.append(np.zeros(round((actual-scheduled)*sr), np.float32))
            raw_video = Path(page.video.path())
            ctx.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    wav = work / "narration_and_actual_demo_audio.wav"
    sf.write(wav, np.concatenate(tracks), sr)
    duration = sum(len(t) for t in tracks)/sr
    if not 300 <= duration <= 480:
        raise ValueError(f"Video must be 5–8 min; generated {duration}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw_video), "-i", str(wav),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    report = {"duration_seconds": duration, "narration": "synthetic eSpeak Spanish; not tesista voice",
              "capture": "actual automated Chromium UI interaction; no mock measurements",
              "chapters": chapters, "scope": "technical support video; tesista/advisor review pending"}
    (out.with_suffix(".json")).write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    record(p.parse_args().out)
