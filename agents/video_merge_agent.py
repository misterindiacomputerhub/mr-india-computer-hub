import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

"""
video_merge_agent.py
Combines 3 user-uploaded clips (from Gemini/Veo) into one final video:
concatenates them and optionally overlays the shop logo. Writes to the same
OUTPUT_DIR the rest of the pipeline uses (main.py), not media_library —
media_library is reserved for the shop's own real photos/clips.
"""

import os
from moviepy.editor import (
    VideoFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
LOGO_PATH = os.getenv("SHOP_LOGO_PATH", "assets/logo.png")  # TODO: confirm real path if you have one


def merge_clips(clip_paths, topic_id):
    """
    clip_paths: list of 3 local file paths (uploaded via dashboard)
    topic_id: string used to namespace the output filename
    Returns the path to the final merged video, written into OUTPUT_DIR
    alongside the rest of the pipeline's video files.
    """
    if len(clip_paths) != 3:
        raise ValueError(f"Expected 3 clips, got {len(clip_paths)}")

    clips = [VideoFileClip(p) for p in clip_paths]

    target_w, target_h = clips[0].size
    clips = [c if c.size == (target_w, target_h) else c.resize((target_w, target_h)) for c in clips]

    final = concatenate_videoclips(clips, method="compose")

    if os.path.exists(LOGO_PATH):
        logo = (
            ImageClip(LOGO_PATH)
            .set_duration(final.duration)
            .resize(height=int(target_h * 0.12))
            .margin(right=20, top=20, opacity=0)
            .set_pos(("right", "top"))
        )
        final = CompositeVideoClip([final, logo])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"{topic_id}_clip_final.mp4")

    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        threads=4,
        logger=None,
    )

    for c in clips:
        c.close()
    final.close()

    return output_path
