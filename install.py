"""
Python script to create a shelf button for Texelator in Maya.
This script is executed by install.mel.
Copyright 2025 by Hasan Çivili. All Rights Reserved.
"""
import os
import maya.cmds as cmds

def create_texelator_shelf_button(install_script_path):
    """Creates a shelf button for Texelator."""
    try:
        if not install_script_path:
            cmds.warning("Texelator Installer: Script path not provided.")
            return

        # The project root contains install.py, Texelator.py and the assets folder.
        script_dir = os.path.dirname(install_script_path)
        script_dir_norm = os.path.normpath(script_dir)

        tool_module_name = "Texelator"
        tool_script_file = tool_module_name + ".py"
        tool_script_path_full = os.path.join(script_dir_norm, tool_script_file)

        if not os.path.exists(tool_script_path_full):
            cmds.warning(f"Texelator Installer: Main tool script '{tool_script_file}' not found at: {tool_script_path_full}")
            return

        icon_name = "Texelator_Icon.png"
        icon_path = os.path.join(
            script_dir_norm, "assets", "images", icon_name)
        icon_path_norm = os.path.normpath(icon_path)

        if not os.path.exists(icon_path_norm):
            cmds.warning(f"Texelator Installer: Icon file '{icon_name}' not found at: {icon_path_norm}. Using default Maya icon.")
            icon_path_for_shelf = "pythonFamily.png"  # Default Maya icon
        else:
            icon_path_for_shelf = icon_path_norm
            
        shelf_name = cmds.optionVar(q="currentShelf") # Get current active shelf
        if not shelf_name:
            # Fallback if no shelf is active, or create a specific one
            shelf_name = "Custom" # Or your preferred shelf name like "TextureTools"
            if not cmds.shelfLayout(shelf_name, exists=True):
                cmds.shelfLayout(shelf_name, parent="ShelfLayout") # Maya's main shelf area

        # Ensure script_dir_norm uses forward slashes for the Python command string, or is a raw string
        escaped_tool_dir = script_dir_norm.replace("\\\\", "/").replace("\\", "/")

        # This is the command that the shelf button will execute.
        # It imports Texelator and calls its show_ui function.
        shelf_command = f"""
import sys
import os
import maya.cmds as cmds
import importlib

tool_dir = r'{escaped_tool_dir}'
tool_module_name = '{tool_module_name}'

if tool_dir not in sys.path:
    sys.path.append(tool_dir)

try:
    module_to_run = importlib.import_module(tool_module_name)
    module_to_run = importlib.reload(module_to_run)
    module_to_run.show_ui()
except ImportError as e_import:
    error_msg = f"Texelator: IMPORT ERROR - {{e_import}}. Could not import '{{tool_module_name}}'. Ensure it is in: {{tool_dir}}."
    cmds.warning(error_msg)
except AttributeError as e_attr:
    error_msg = f"Texelator: ATTRIBUTE ERROR - {{e_attr}}. Could not find 'show_ui' in '{{tool_module_name}}'."
    cmds.warning(error_msg)
except Exception as e_runtime:
    error_msg = f"Texelator: RUNTIME ERROR - {{e_runtime}}."
    cmds.warning(error_msg)
"""

        # Check if a button with this label already exists on the shelf
        shelf_buttons = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
        existing_button = None
        for btn in shelf_buttons:
            try:
                if cmds.shelfButton(btn, query=True, label=True) in ("2D Texture Rigger", "Texture Rigger", "Texelator"):
                    existing_button = btn
                    break
                if cmds.shelfButton(btn, query=True, command=True) == shelf_command: # More robust check by command
                    existing_button = btn
                    break
            except RuntimeError: # Button might not be a shelfButton or might be deleted
                pass

        button_label = "Texelator"

        if existing_button:
            print(f"Texelator Installer: Updating existing shelf button '{button_label}' on shelf '{shelf_name}'.")
            cmds.shelfButton(
                existing_button,
                edit=True,
                label=button_label,
                command=shelf_command,
                image=icon_path_for_shelf,
                imageOverlayLabel="", # Keep the shelf icon unobstructed.
                annotation="Runs Texelator.",
                sourceType="python"
            )
        else:
            print(f"Texelator Installer: Creating new shelf button '{button_label}' on shelf '{shelf_name}'.")
            cmds.shelfButton(
                parent=shelf_name,
                label=button_label,
                command=shelf_command,
                image=icon_path_for_shelf,
                imageOverlayLabel="", # Keep the shelf icon unobstructed.
                annotation="Runs Texelator.",
                sourceType="python"
            )

        cmds.confirmDialog(
            title="Texelator Installer",
            message=f"Texelator shelf button installed/updated on shelf '{shelf_name}' successfully!",
            button="OK"
        )

    except Exception as e:
        error_message = f"Texelator Installer: Failed to create shelf button. Error: {e}"
        import traceback
        traceback.print_exc()
        cmds.warning(error_message)

if __name__ == "__main__":
    # This block is executed when install.mel runs `exec(code_to_exec)`
    # TEXELATOR_SCRIPT_PATH is globally defined by install.mel's Python execution context.
    if 'TEXELATOR_SCRIPT_PATH' in globals():
        create_texelator_shelf_button(globals()['TEXELATOR_SCRIPT_PATH'])
    else:
        # This case should ideally not happen if install.mel is used.
        cmds.error("Texelator Installer: TEXELATOR_SCRIPT_PATH global variable not found. Cannot determine script path for installation.")

