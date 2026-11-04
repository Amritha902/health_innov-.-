"""Assembles the recorded scenes, stage graphics and narration into demo.mp4.
Usage: python demo/compose.py <workdir>   (workdir holds raw/, vo/, stage/)"""
import json
import subprocess
import sys
from pathlib import Path

W = Path(sys.argv[1])
HERE = Path(__file__).parent
script = json.loads((HERE / "script.json").read_text())
dur = json.loads((W / "vo" / "durations.json").read_text())
PAD, T, LEAD = 1.2, 0.7, 0.45          # tail after narration, transition length, narration lead-in
SCREEN = (1180, 92, 414, 897)          # phone screen box on the stage (x, y, w, h)
TRANSITIONS = {"title": "fadeblack", "problem": "circleopen", "landing": "smoothleft", "chat": "smoothleft", "watch": "smoothleft", "labreport": "smoothleft", "explain": "slideup", "journey": "smoothleft",
               "graph": "smoothleft", "result": "smoothleft", "clinician": "smoothleft", "dashboard": "smoothleft", "whatsapp": "smoothleft", "privacy": "fadeblack", "proof": "fadeblack"}
seg = W / "seg"
seg.mkdir(exist_ok=True)


def run(args):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


clips = []
for sc in script:
    d = round(dur[sc["id"]] + PAD, 2)
    out = seg / f"{sc['id']}.mp4"
    raw = W / "raw" / f"{sc['id']}.webm"
    if sc["kind"] in ("card", "desk"):
        run(["-i", raw, "-t", str(d), "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p,tpad=stop_mode=clone:stop_duration=3",
             "-t", str(d), "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-an", out])
    else:
        x, y, w, h = SCREEN
        bg, frame = W / "stage" / f"{sc['id']}.png", W / "stage" / "frame.png"
        run(["-loop", "1", "-i", bg, "-i", raw, "-loop", "1", "-i", frame, "-filter_complex",
             f"[1:v]fps=30,scale={w}:{h}:flags=lanczos,tpad=stop_mode=clone:stop_duration=3[ph];"
             f"[0:v][ph]overlay={x}:{y}:shortest=0[a];[a][2:v]overlay=0:0,format=yuv420p,fps=30",
             "-t", str(d), "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-an", out])
    clips.append((sc["id"], d, out))

# chain with xfade; track where each scene starts so narration lines up
inputs, filt, starts = [], [], []
offset, label = 0.0, "0:v"
for i, (sid, d, path) in enumerate(clips):
    inputs += ["-i", path]
    starts.append(offset if i == 0 else offset)
    if i == 0:
        offset = d
        continue
    prev = clips[i - 1][0]
    offset_x = offset - T
    starts[-1] = offset_x
    nl = f"v{i}"
    filt.append(f"[{label}][{i}:v]xfade=transition={TRANSITIONS.get(prev, 'fade')}:duration={T}:offset={offset_x:.2f}[{nl}]")
    label, offset = nl, offset_x + d
total = offset

audio_in, amix = [], []
for i, (sid, d, _) in enumerate(clips):
    audio_in += ["-i", W / "vo" / f"{sid}.wav"]
    ms = int((starts[i] + LEAD) * 1000)
    amix.append(f"[{len(clips) + i}:a]adelay={ms}|{ms},aformat=sample_rates=48000:channel_layouts=stereo[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(clips)))
filt += amix + [f"{mix}amix=inputs={len(clips)}:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={total - 1.2:.2f}:d=1.2[aout]",
                f"[{label}]fade=t=in:st=0:d=0.6,fade=t=out:st={total - 0.9:.2f}:d=0.9[vout]"]
run([*inputs, *audio_in, "-filter_complex", ";".join(filt), "-map", "[vout]", "-map", "[aout]",
     "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
     "-movflags", "+faststart", W / "demo.mp4"])
print(f"demo.mp4 {total:.1f}s")
