#!/usr/bin/env python3
"""Voeg een Nederlandse narratie toe aan de demo-video."""

import subprocess
import sys
import wave
from pathlib import Path

DEMO_DIR = Path(__file__).parent
VOICES_DIR = DEMO_DIR / "voices"
SOURCE_VIDEO = DEMO_DIR / "source_video.mp4"
OUTPUT_VIDEO = DEMO_DIR / "demo_met_narratie.mp4"
AUDIO_FILE = DEMO_DIR / "narratie.wav"

VOICE = "nl_NL-mls_5809-low"

# ~220 woorden, ~100 seconden — afgestemd op de 5 scènes van de demo-video (1:48)
# Scène 1: Homepage | Scène 2: Instellingen | Scène 3: Chat | Scène 4: Dashboard | Scène 5: Dark mode
NARRATIE = """\
Onderwijsdata Chat is een AI-assistent voor open Nederlandse onderwijsdata. \
De homepage geeft direct toegang tot chat en dashboards, zonder BI-kennis of technische achtergrond. \
De assistent beschikt over honderdtwintig open datasets uit CBS, RIO en DUO.

Bij de eerste keer gebruik stel je je instelling en rol in. \
Hier Hogeschool Utrecht als beleidsmedewerker. \
Deze context personaliseert de interface en de suggestievragen.

In de chat stel je een vraag in gewone taal. \
De assistent doorzoekt automatisch de catalogus en roept de juiste databron aan. \
Hier worden DUO-datasets over voltijdinschrijvingen opgehaald. \
Het antwoord verschijnt als overzichtelijke markdown met een tabel per jaar. \
Daarna biedt de assistent slimme vervolgvragen aan — \
klik om direct dieper in te zoomen op sectoren, regio of vergelijkingen.

Via de dashboardpagina open je voorgebouwde overzichten. \
Live KPI's en grafieken: totale instroom, eerstejaars en gediplomeerden per sector in één scherm. \
Wil je een eigen dashboard? \
Beschrijf in gewone taal wat je wilt zien — de assistent bouwt het automatisch op basis van de beschikbare data.

Tot slot de donkere modus. \
Eén klik, en alle pagina's en grafieken passen zich aan. \
Ook de dashboards draaien volledig in dark mode.\
"""


def download_voice():
    onnx = VOICES_DIR / f"{VOICE}.onnx"
    if onnx.exists():
        print(f"Stem al aanwezig: {onnx}")
        return
    print(f"Stem downloaden: {VOICE}...")
    VOICES_DIR.mkdir(exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "piper.download_voices",
         "--download-dir", str(VOICES_DIR), VOICE],
        check=True,
    )
    print("Stem gedownload.")


def generate_audio():
    from piper import PiperVoice

    onnx = VOICES_DIR / f"{VOICE}.onnx"
    print("Narratie genereren...")
    voice = PiperVoice.load(str(onnx))
    with wave.open(str(AUDIO_FILE), "wb") as wav_file:
        voice.synthesize_wav(NARRATIE, wav_file)
    with wave.open(str(AUDIO_FILE), "rb") as wav_file:
        duration = wav_file.getnframes() / wav_file.getframerate()
    print(f"Audio: {AUDIO_FILE.name} ({duration:.1f}s)")


def combine():
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    print("Video en audio samenvoegen...")
    result = subprocess.run(
        [
            ffmpeg, "-y", "-v", "quiet",
            "-i", str(SOURCE_VIDEO),
            "-i", str(AUDIO_FILE),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(OUTPUT_VIDEO),
        ],
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(result.stderr.decode())
        raise RuntimeError("ffmpeg mislukt")
    size_mb = OUTPUT_VIDEO.stat().st_size / 1_000_000
    print(f"Klaar: {OUTPUT_VIDEO.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    download_voice()
    generate_audio()
    combine()
