"""Deprecated alias: SwingForm AI is now MotionMirror. Use ``import motionmirror``."""

import importlib
import pkgutil
import sys
import warnings

import motionmirror

warnings.warn("swingform_ai was renamed to motionmirror; please update your imports.",
              DeprecationWarning, stacklevel=2)

sys.modules[__name__] = motionmirror
for _mod in pkgutil.walk_packages(motionmirror.__path__, "motionmirror."):
    _alias = "swingform_ai" + _mod.name[len("motionmirror"):]
    sys.modules.setdefault(_alias, importlib.import_module(_mod.name))
