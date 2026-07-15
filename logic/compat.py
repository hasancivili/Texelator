"""Maya-version compatibility helpers shared by Texelator modules."""

import maya.cmds as cmds


def create_compatible_math_node(new_type, legacy_type, name):
    """Use renamed Maya 2026 math nodes while supporting Maya 2022-2025."""
    try:
        maya_version = int(str(cmds.about(version=True))[:4])
    except (TypeError, ValueError):
        maya_version = 0
    return cmds.createNode(
        new_type if maya_version >= 2026 else legacy_type, name=name)
