# Metrics and Reference Ranges

This page defines every metric in `report.json` / `report.md` and explains each reference
range. The reader is assumed to know basic golf or basketball technique, not computer vision.

## Conventions

| Term | Meaning |
| --- | --- |
| Image plane | Angles use x/y only. MediaPipe's monocular depth (`z`) is too noisy for joint angles. |
| Aspect correction | x is multiplied by width/height before any geometry, so one unit is the frame height on both axes. |
| Torso length | Distance from the shoulder midpoint to the hip midpoint, median over the clip. Distances are divided by it. |
| Phase value | Median over the five frames centred on the phase, to absorb single-frame glitches. |
| Confidence | Mean landmark visibility over the rep, reduced when phase timing is implausible. |

A joint whose visibility is below 0.3 counts as hidden; metrics that need it are `n/a`.

## Golf

| Key | Meaning |
| --- | --- |
| `timing.backswing_s` | Address to top (includes any pause at the top). |
| `timing.downswing_s` | Top to impact. |
| `timing.tempo_ratio` | Backswing time divided by downswing time. |
| `address.lead_knee_angle_deg` | Hip-knee-ankle angle of the lead leg; 180 is straight. |
| `address.stance_width_torso` | Ankle-to-ankle distance in torso lengths. |
| `top.lead_arm_angle_deg` | Shoulder-elbow-wrist angle of the lead arm. |
| `top.hand_height_torso` | How far the hands are above the shoulder midpoint. |
| `top.hip_sway_torso` | Horizontal hip-midpoint shift from address to top. |
| `top.shoulder_hip_separation_deg` | Angle between the shoulder line and the hip line in the image. Meaningful mainly face-on. |
| `impact.head_drift_torso` | Nose displacement from address to impact. |
| `impact.hip_slide_torso` | Horizontal hip shift from address to impact. |
| `impact.peak_hand_speed_torso_s` | Fastest hand speed between top and impact. |

**Phase detection.** The top is the highest point of the hands, moved to the end of any pause.
Address is the last quiet frame before the takeaway. Impact is the first low point of the hands
on the way down, within 0.7 s of the top. Finish is the first frame after impact where the
hands are quiet and above the shoulders. At 30 fps the hands blur during the downswing, so
impact is a pose proxy that can be off by one or two frames.

| Check | Range | Rationale |
| --- | --- | --- |
| Tempo | 2.0 to 4.0 | Many skilled swings cluster near a 3:1 backswing-to-downswing ratio. The range is wide because "address" here is the last still frame, not the club's first movement. |
| Lead arm at top | at least 145 deg | A fairly straight lead arm keeps the swing radius stable. |
| Hip sway | at most 0.35 torso | Large lateral drift moves the low point of the swing. |
| Head drift to impact | at most 0.35 torso | A steady head is a common proxy for a steady swing centre. |
| Knee flex at address | 135 to 175 deg | Moderate flex; camera angle affects this, so treat it as a trend metric. |

## Basketball

| Key | Meaning |
| --- | --- |
| `timing.dip_to_release_s` | Deepest knee bend to release. |
| `dip.shooting_knee_angle_deg` | Hip-knee-ankle angle of the shooting-side leg at the dip. |
| `release.shooting_elbow_angle_deg` | Shoulder-elbow-wrist angle at release. |
| `release.wrist_above_head_torso` | Shooting wrist height above the nose. |
| `release.guide_hand_gap_torso` | Distance between the two wrists at release. |
| `landing.lateral_drift_torso` | Horizontal hip shift from set to landing. |

**Phase detection.** Release is a peak of "wrist above head + elbow extension". The dip is the
deepest knee bend in the 0.9 s before release; set, lift, follow-through and landing are found
relative to those two. `--side auto` tries both hands because selfie-mode video is mirrored.

| Check | Range | Rationale |
| --- | --- | --- |
| Elbow extension | at least 145 deg | A full extension makes the launch repeatable. |
| Knee bend in dip | 95 to 160 deg | Enough leg drive without an overly deep load. |
| Release height | at least 0.2 torso above the head | A proxy for a high set point. |
| Dip-to-release | 0.2 to 0.8 s | A one-motion shot moves through the load quickly. |
| Sideways drift | at most 0.5 torso | Landing near the take-off spot is a simple balance proxy. |

## Badminton

| Key | Meaning |
| --- | --- |
| `stroke` | `overhead` (hand above the head at contact), `drive` (between hip and head) or `underhand`. |
| `timing.backswing_to_contact_s` | Most cocked racket arm to contact. |
| `ready.knee_angle_deg` | Smaller of the two knee angles in the ready position. |
| `backswing.off_hand_height_torso` | Free hand height above the shoulders during the backswing. |
| `contact.racket_elbow_angle_deg` | Racket-arm extension at contact. |
| `contact.racket_hand_height_torso` | Racket hand height above the shoulder midpoint at contact. |
| `contact.peak_hand_speed_torso_s` | Fastest racket-hand speed through the swing. |
| `contact.stance_width_torso` | Ankle-to-ankle distance at contact. |

**Stroke detection.** A stroke is a peak in racket-hand speed. For drives and lifts, contact
is that peak. On an overhead the arm keeps accelerating downward after the hit, so when the
hand was above the head in the preceding 0.4 s, contact moves to the highest-hand frame.
`--side auto` picks the hand with the higher 90th-percentile speed. The racket head and
shuttle are not tracked, so contact is a pose proxy.

| Stroke | Check | Range | Rationale |
| --- | --- | --- | --- |
| overhead | Arm extension at contact | at least 150 deg | Contact at full reach gives the steepest angle and most power. |
| overhead | Contact height | at least 0.8 torso above the shoulders | A high contact point keeps more shot options. |
| overhead | Free arm raised | at least shoulder height | Pointing the free arm helps timing and trunk rotation. |
| drive / underhand | Backswing-to-contact | 0.08 to 0.5 s | Compact, early preparation is easier to time. |
| drive / underhand | Base width at contact | at least 0.7 torso | A wide base keeps balance on fast strokes. |
| all | Ready knee bend | 115 to 165 deg | A flexed ready stance shortens the first step. |

## Tuning

The ranges are starter values for spotting outliers in single-camera 2D video, not coaching
standards. To fit your own baseline, edit `CHECKS` in `src/motionmirror/profiles/golf.py`,
`basketball.py` or `badminton.py` (`CHECKS_BY_STROKE`); each `Check` holds its range, cue text and rationale.
