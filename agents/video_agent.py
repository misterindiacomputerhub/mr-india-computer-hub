import os as _os, moviepy.config as mpy_config; mpy_config.IMAGEMAGICK_BINARY = "/opt/homebrew/bin/magick" if _os.path.exists("/opt/homebrew/bin/magick") else "/usr/bin/magick"
"""
video_agent.py
Renders the final vertical video: AI-generated topic images (via image_agent,
Google Imagen) + voiceover audio + burned-in captions. Each image gets a
Ken Burns zoom in/out effect so the video doesn't look static.

Requires: moviepy, ffmpeg installed on the system.
"""
import os
import random
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips,
)

from agents import image_agent

VIDEO_SIZE = (1080, 1920)  # vertical, for Shorts/Reels
ZOOM_RATIO = 0.18  # how much the image scales over its on-screen duration


def _ken_burns_clip(image_path: str, duration: float) -> ImageClip:
    """
    Loads an image, resizes it to fully cover the 1080x1920 frame (like
    CSS background-size: cover) with extra headroom, then animates a slow
    zoom in or zoom out over the clip's duration so it reads as dynamic
    footage instead of a static photo.
    """
    base = ImageClip(image_path)
    img_w, img_h = base.size
    target_w, target_h = VIDEO_SIZE

    # Cover the frame, plus extra headroom so zooming never reveals a border.
    cover_scale = max(target_w / img_w, target_h / img_h) * (1 + ZOOM_RATIO)
    base = base.resize(cover_scale).set_duration(duration)

    zoom_in = random.choice([True, False])

    def _scale_at(t):
        progress = t / duration if duration > 0 else 0
        if zoom_in:
            return 1 + (ZOOM_RATIO * 0.5) * progress
        return (1 + ZOOM_RATIO * 0.5) - (ZOOM_RATIO * 0.5) * progress

    animated = base.resize(_scale_at).set_position(("center", "center"))
    return CompositeVideoClip([animated], size=VIDEO_SIZE).set_duration(duration)


def render_video(script_text: str, voiceover_path: str, topic_id: str,
                  topic_title: str, out_path: str) -> str:
    audio = AudioFileClip(voiceover_path)
    duration = audio.duration

    image_paths = image_agent.generate_images_for_topic(topic_id, topic_title)
    per_clip = duration / len(image_paths)

    clips = [_ken_burns_clip(p, per_clip) for p in image_paths]
    base = concatenate_videoclips(clips, method="compose").set_audio(audio)

    # Simple burned-in caption using the first line of the script as a title card.
    # For full line-by-line captions, feed timestamped segments from a
    # speech-to-text pass over the voiceover instead.
    headline = script_text.strip().split("\n")[0][:60]
    caption = (
        TextClip(headline, fontsize=60, color="white", font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                size=(VIDEO_SIZE[0] - 100, None), method="caption")
        .set_position(("center", "bottom"))
        .set_duration(min(4, duration))
    )

    final = CompositeVideoClip([base, caption], size=VIDEO_SIZE)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac")
    return out_path


if __name__ == "__main__":
    print("Run via main.py — this module expects a script, voiceover path, topic_id, and topic_title.")
