"""Narration for the MotionMirror promo, one entry per scene.

Numbers quoted here must match the example reports; ``make_promo.py`` checks
them against examples/*/report.json before rendering.
"""

VOICE_ID = "nPczCjzI2devNBz1zQrb"  # ElevenLabs "Brian": warm, deep American narrator
MODEL_ID = "eleven_multilingual_v2"

SCENES = [
    ("title",
     "This is MotionMirror. Open-source motion analysis that turns a single phone video "
     "into clear, explainable feedback. No sensors. No studio. Just the camera in your pocket."),
    ("bb_intro",
     "Meet Rayford, shooting on an oceanside court. He fills less than a tenth of the frame, "
     "so MotionMirror first finds him, then zooms in, and tracks thirty-three body landmarks "
     "on every single frame."),
    ("bb_phases",
     "Filmed at a hundred and twenty frames per second, the shot is broken into six phases: "
     "set, dip, lift, release, follow-through, and landing."),
    ("bb_metrics",
     "At release, his shooting arm reaches a hundred and seventy-six degrees of extension, "
     "well above his head. Dip to release takes just over a third of a second. "
     "Every check, in range."),
    ("bd_intro",
     "Next, Chen Jingyi on the badminton court. A brand-new badminton profile detects every "
     "stroke from the speed of the racket hand, and classifies it: drive, or overhead."),
    ("bd_overhead",
     "On an overhead, the arm keeps accelerating after the hit. So MotionMirror places contact "
     "at the highest point of the reach, then measures arm extension, contact height, "
     "and the position of the free arm."),
    ("bd_feedback",
     "The feedback is specific, and honest about what it sees. On this overhead, contact is "
     "a little low. Take the shuttle earlier, above the head."),
    ("outputs",
     "Every run produces a full report, an annotated video, key-pose frames, a metric "
     "timeline, and the raw data, ready for your own analysis."),
    ("honesty",
     "Each number traces back to a frame and a reference range. When the camera can't see "
     "a joint, MotionMirror says so, instead of guessing."),
    ("close",
     "Golf, basketball, and badminton, today. One command to try it. "
     "MotionMirror. See your form."),
]
