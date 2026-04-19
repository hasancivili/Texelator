import maya.cmds as cmds
import importlib
import re

# Import logic files
import step1_logic
import step2_logic
import step3_logic
import step3_uv_logic  # Add import for the new module

# For reloading modules during development (optional)
importlib.reload(step1_logic)
importlib.reload(step2_logic)
importlib.reload(step3_logic)
importlib.reload(step3_uv_logic)  # Add reload for the new module

class TextureRiggerUI:
    def __init__(self):
        self.window_name = "textureRiggerMainWindow"
        self.ui_title = "Texture Rigger 0.0.3"

        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        
        self.locators_data = {}
        self.follicles_data = {}
        self.textures_data = {}
        
        self.name_prefix = "Prefix"

        self.name_field = None

        self.step1_frame = None
        self.select_mesh_button = None
        self.create_locator_button = None
        self.locator_list_widget = None
        self.step1_status_label = None

        self.step2_frame = None
        self.create_follicles_button = None
        self.step2_status_label = None
        
        self.step3_frame = None
        self.step3_top_col_layout = None  # Burada eksik olan değişkeni ekliyoruz
        self.texture_selection_layout = None
        self.texture_path_fields = {}
        self.select_texture_buttons = {}
        self.connect_all_textures_button = None
        self.step3_status_label = None

        self.sequence_checkboxes = {}  # {prefix: checkbox_widget}
        self.projection_checkboxes = {}  # {prefix: checkbox_widget} - Add this new line

    def on_window_close(self, *args):
        self.reset_tool_state()
        step1_logic.clear_reference_follicle()

    def create_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name, window=True)

        self.window = cmds.window(
            self.window_name, 
            title=self.ui_title, 
            widthHeight=(450, 600),
            sizeable=True,
            closeCommand=self.on_window_close
        )
        
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, parent=self.window)

        self.step1_frame = cmds.frameLayout("step1_frame", label="STEP 1: Select Mesh & Create Locators", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5)
        step1_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step1_frame, rowSpacing=5)
        
        self.select_mesh_button = cmds.button(label="Select Mesh", command=self.on_select_mesh_click, parent=step1_col_layout, height=30)
        
        name_row_layout = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 80), (2, 300)], parent=step1_col_layout, rowSpacing=(1,3))
        cmds.text(label="Prefix:", align="right")
        self.name_field = cmds.textField(text=self.name_prefix, parent=name_row_layout, 
                                    changeCommand=self.on_name_changed)
        cmds.setParent("..")
        
        self.create_locator_button = cmds.button(label="Create Locator", command=self.on_create_locator_click, parent=step1_col_layout, height=30, enable=False)
        
        cmds.text(label="Created Locators:", align="left", parent=step1_col_layout)
        self.locator_list_widget = cmds.textScrollList(numberOfRows=4, allowMultiSelection=False, parent=step1_col_layout, height=60)
        
        self.step1_status_label = cmds.text(label="Status: Waiting for mesh selection...", align="left", parent=step1_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")

        self.step2_frame = cmds.frameLayout("step2_frame", label="STEP 2: Create Follicles and Control Curves", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False)
        step2_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step2_frame, rowSpacing=5)
        cmds.text(label="Move the created locators to desired positions on the mesh.", align="left", parent=step2_col_layout)
        self.create_follicles_button = cmds.button(label="Create Follicles and Control Curves", command=self.on_create_follicles_click, parent=step2_col_layout, height=30)
        self.step2_status_label = cmds.text(label="Status: Waiting for locator positioning and follicle creation...", align="left", parent=step2_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")

        self.step3_frame = cmds.frameLayout("step3_frame", label="STEP 3: Select Textures & Connect to Materials", collapsable=False, collapse=False, parent=main_layout, marginWidth=10, marginHeight=5, enable=False)
        self.step3_top_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step3_frame, rowSpacing=5)

        self.texture_selection_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=3, parent=self.step3_top_col_layout) 
        cmds.setParent("..")

        self.connect_all_textures_button = cmds.button(label="Connect All Selected Textures to Materials", command=self.on_connect_all_textures_click, parent=self.step3_top_col_layout, height=30, enable=False)
        self.step3_status_label = cmds.text(label="Status: Waiting for follicle creation to enable texture selection...", align="left", parent=self.step3_top_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.showWindow(self.window)

    def on_name_changed(self, new_name):
        if not new_name or new_name.isspace():
            self.name_prefix = "textureRig" 
            cmds.textField(self.name_field, edit=True, text=self.name_prefix)
            cmds.warning("Prefix cannot be empty. Using default 'textureRig'.")
        else:
            cleaned_name = ''.join(c for c in new_name if c.isalnum() or c == '_')
            if cleaned_name != new_name:
                cmds.textField(self.name_field, edit=True, text=cleaned_name)
            self.name_prefix = cleaned_name

    def _is_prefix_unique(self, prefix_to_check):
        return prefix_to_check not in self.locators_data

    def _update_locator_list_widget(self):
        cmds.textScrollList(self.locator_list_widget, edit=True, removeAll=True)
        for prefix, locator_name in self.locators_data.items():
            cmds.textScrollList(self.locator_list_widget, edit=True, append=f"{prefix}: {locator_name}")

    def _update_status(self, status_label, message, success=None):
        color = (0.9, 0.9, 0.9)
        if success is True: color = (0.6, 0.9, 0.6)
        elif success is False: color = (0.9, 0.6, 0.6)
        cmds.text(status_label, edit=True, label=f"Status: {message}", backgroundColor=color)
        
    def update_step1_status(self, message, success=None):
        self._update_status(self.step1_status_label, message, success)

    def update_step2_status(self, message, success=None):
        self._update_status(self.step2_status_label, message, success)

    def update_step3_status(self, message, success=None):
        self._update_status(self.step3_status_label, message, success)

    def on_create_follicles_click(self, *args):
        if not self.selected_mesh_shape:
            self.update_step2_status("Mesh not selected from Step 1.", success=False)
            return
        if not self.locators_data:
            self.update_step2_status("No locators created in Step 1.", success=False)
            return

        step1_logic.clear_reference_follicle()
        
        all_successful = True
        created_count = 0
        self.follicles_data.clear()

        for prefix, locator_name in self.locators_data.items():
            if not cmds.objExists(self.selected_mesh_shape) or not cmds.objExists(locator_name):
                self.update_step2_status(f"Mesh or locator '{locator_name}' (prefix: '{prefix}') no longer exists.", success=False)
                all_successful = False
                continue
                
            follicle_transform, main_control = step2_logic.run_step2_logic(self.selected_mesh_shape, locator_name, prefix)
            
            if follicle_transform and main_control:
                self.follicles_data[prefix] = {
                    'follicle': follicle_transform, 
                    'control': main_control,
                    'locator_at_creation': locator_name
                }
                created_count += 1
                try:
                    if cmds.objExists(locator_name):
                        cmds.delete(locator_name)
                except Exception as e:
                    print(f"Could not delete locator '{locator_name}': {e}")
            else:
                all_successful = False
                self.update_step2_status(f"Failed to create follicle for prefix '{prefix}'.", success=False)

        processed_prefixes = list(self.follicles_data.keys())
        for prefix in processed_prefixes:
            if prefix in self.locators_data:
                del self.locators_data[prefix]
        self._update_locator_list_widget()

        if created_count > 0:
            self.update_step2_status(f"Successfully created {created_count} follicle(s)/control(s).", success=True)
            cmds.button(self.create_follicles_button, edit=True, enable=False)
            cmds.button(self.create_locator_button, edit=True, enable=False)
            cmds.textField(self.name_field, edit=True, enable=False)
            
            self._populate_texture_selection_ui()
            cmds.frameLayout(self.step3_frame, edit=True, enable=True)
            self.update_step3_status(f"Select textures for {len(self.follicles_data)} prefix(es).")
            if self.follicles_data:
                cmds.button(self.connect_all_textures_button, edit=True, enable=True)
        elif not self.locators_data:
            self.update_step2_status("No locators available or all failed. Please restart Step 1.", success=False)
        else:
            self.update_step2_status(f"Processed locators. {created_count} created. Some may have failed or remain.", success=all_successful)

    def _populate_texture_selection_ui(self):
        children = cmds.columnLayout(self.texture_selection_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)
        
        self.texture_path_fields.clear()
        self.select_texture_buttons.clear()
        self.sequence_checkboxes.clear()
        self.projection_checkboxes.clear()  # Clear projection checkboxes

        if not self.follicles_data:
            cmds.text(label="No follicles created. Cannot select textures.", parent=self.texture_selection_layout)
            return

        for prefix in self.follicles_data.keys():
            # Create main row layout for texture selection
            row_layout = cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 120), (2, 200), (3, 100)], parent=self.texture_selection_layout, rowSpacing=(1,3))
            cmds.text(label=f"Texture for '{prefix}':", align="right")
            path_field = cmds.textField(text="No texture selected", editable=False, width=190) 
            select_button = cmds.button(label="Select File...", command=lambda ignored_arg, p_captured=prefix: self._on_select_single_texture_click(p_captured))
            cmds.setParent("..")
            
            # Create checkboxes row (both sequence and projection)
            checkboxes_row = cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 120), (2, 150), (3, 150)], parent=self.texture_selection_layout, rowSpacing=(1,3))
            cmds.text(label="", align="left")  # Spacer
            seq_checkbox = cmds.checkBox(label="is sequence?", value=False, 
                                       changeCommand=lambda state, p_captured=prefix: self._on_sequence_checkbox_changed(p_captured, state))
            proj_checkbox = cmds.checkBox(label="Projection?", value=True,  # Default to True for backward compatibility
                                       changeCommand=lambda state, p_captured=prefix: self._on_projection_checkbox_changed(p_captured, state))
            cmds.setParent("..")
            
            # Add separator for visual clarity
            cmds.separator(height=5, style='single', parent=self.texture_selection_layout)

            self.texture_path_fields[prefix] = path_field
            self.select_texture_buttons[prefix] = select_button
            self.sequence_checkboxes[prefix] = seq_checkbox
            self.projection_checkboxes[prefix] = proj_checkbox
            
            self.textures_data[prefix] = {
                'file_path': None, 'file_node': None, 'projection_node': None, 
                'place2d_node': None, 'place3d_node': None, 
                'layered_texture': None, 'material': None,
                'is_sequence': False,  # Flag for sequence textures
                'use_projection': True  # Default to True for backward compatibility
            }

    def _on_sequence_checkbox_changed(self, prefix, state):
        """
        Handle sequence checkbox state changes.
        
        Args:
            prefix (str): Prefix of the texture
            state (bool): New state of the checkbox
        """
        print(f"Sequence checkbox for '{prefix}' changed to: {state}")
        
        # Update our data structure
        if prefix in self.textures_data:
            self.textures_data[prefix]['is_sequence'] = state
        
        # If we've already created file nodes, update them immediately
        if (prefix in self.textures_data and 
            self.textures_data[prefix]['file_node'] and 
            cmds.objExists(self.textures_data[prefix]['file_node'])):
            
            file_node = self.textures_data[prefix]['file_node']
            slide_ctrl = None
            
            # Find the slide ctrl for this prefix
            if prefix in self.follicles_data and self.follicles_data[prefix]['control']:
                follicle_data = self.follicles_data[prefix]
                control_name = follicle_data['control']
                
                if "_Slide_ctrl" in control_name:
                    slide_ctrl = control_name
                else:
                    # Try to find the Slide ctrl as a child
                    children = cmds.listRelatives(control_name, allDescendents=True, type="transform") or []
                    for child in children:
                        if "_Slide_ctrl" in child:
                            slide_ctrl = child
                            break
            
            if slide_ctrl and file_node:
                step3_logic.setup_sequence_texture(file_node, slide_ctrl, state)
                if state:
                    self.update_step3_status(f"Activated sequence mode for '{prefix}'", success=True)
                else:
                    self.update_step3_status(f"Deactivated sequence mode for '{prefix}'", success=True)

    def _on_projection_checkbox_changed(self, prefix, state):
        """
        Handle projection checkbox state changes.
        
        Args:
            prefix (str): Prefix of the texture
            state (bool): New state of the checkbox
        """
        print(f"Projection checkbox for '{prefix}' changed to: {state}")
        
        # Update our data structure
        if prefix in self.textures_data:
            self.textures_data[prefix]['use_projection'] = state

    def _on_select_single_texture_click(self, prefix):
        file_paths = cmds.fileDialog2(fileMode=1, caption=f"Select Texture for Prefix: {prefix}")
        if file_paths and file_paths[0]:
            selected_file = file_paths[0]
            self.textures_data[prefix]['file_path'] = selected_file
            cmds.textField(self.texture_path_fields[prefix], edit=True, text=selected_file)
            self.update_step3_status(f"Texture for '{prefix}' selected. Ready to connect all.", success=True)
        else:
            self.update_step3_status(f"Texture selection cancelled for '{prefix}'.", success=False)

    def on_connect_all_textures_click(self, *args):
        """
        Process all selected textures and connect them to their respective follicles
        """
        if not self.selected_mesh_transform:
            cmds.warning("No mesh selected or initial locator created. Please complete Step 1.")
            return
        
        if not self.textures_data:
            cmds.warning("No textures selected or locators processed for texture connection.")
            return

        all_successful = True
        for prefix, tex_data in self.textures_data.items():
            texture_file_path = tex_data.get('file_path')
            if not texture_file_path or texture_file_path == "No texture selected":
                cmds.warning(f"No texture file selected for prefix '{prefix}'. Skipping.")
                continue

            follicle_info = self.follicles_data.get(prefix)
            if not follicle_info:
                cmds.warning(f"Follicle data not found for prefix '{prefix}'. Cannot connect texture.")
                all_successful = False
                continue
            
            created_follicle_transform = follicle_info.get('follicle')
            if not created_follicle_transform:
                cmds.warning(f"Follicle transform not found for prefix '{prefix}'.")
                all_successful = False
                continue
            
            # Get flags
            is_sequence = tex_data.get('is_sequence', False)
            use_projection = tex_data.get('use_projection', True)
            
            if use_projection:
                # Use original projection-based method
                file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material_node, updated_mesh_transform = step3_logic.run_step3_logic(
                    mesh_transform=self.selected_mesh_transform,
                    image_file_path=texture_file_path,
                    name_prefix=prefix,
                    follicle_transform=created_follicle_transform,
                    is_sequence=is_sequence
                )
                
                if file_node:
                    self.textures_data[prefix].update({
                        'file_node': file_node,
                        'projection_node': projection_node,
                        'place2d_node': place2d_node,
                        'place3d_node': place3d_node,
                        'layered_texture_node': layered_texture_node,
                        'material_node': material_node
                    })
                    self.selected_mesh_transform = updated_mesh_transform
                else:
                    cmds.warning(f"Texture connection failed for prefix '{prefix}'.")
                    all_successful = False
            else:
                # Use UV-based method
                file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material_node, updated_mesh_transform = step3_uv_logic.run_step3_uv_logic(
                    mesh_transform=self.selected_mesh_transform,
                    image_file_path=texture_file_path,
                    name_prefix=prefix,
                    follicle_transform=created_follicle_transform,
                    is_sequence=is_sequence
                )
                
                if file_node:
                    self.textures_data[prefix].update({
                        'file_node': file_node,
                        'projection_node': projection_node,  # Will be None for UV method
                        'place2d_node': place2d_node,
                        'place3d_node': place3d_node,  # Will be None for UV method
                        'layered_texture_node': layered_texture_node,
                        'material_node': material_node
                    })
                    self.selected_mesh_transform = updated_mesh_transform
                else:
                    cmds.warning(f"Texture connection failed for prefix '{prefix}'.")
                    all_successful = False

        if all_successful:
            cmds.headsUpMessage(f"All selected textures connected and scene organized.", time=5.0)
            self.reset_tool_state()
        else:
            cmds.warning("Some textures could not be connected. Check the script editor.")

    def reset_step2_and_beyond(self):
        cmds.frameLayout(self.step2_frame, edit=True, enable=False)
        cmds.button(self.create_follicles_button, edit=True, enable=True)
        self.update_step2_status("Waiting for locator positioning and follicle creation...")
        self.follicles_data.clear()

        cmds.frameLayout(self.step3_frame, edit=True, enable=False)
        children = cmds.columnLayout(self.texture_selection_layout, query=True, childArray=True) or []
        for child in children: cmds.deleteUI(child)
        self.texture_path_fields.clear()
        self.select_texture_buttons.clear()
        self.sequence_checkboxes.clear()
        self.projection_checkboxes.clear()
        cmds.button(self.connect_all_textures_button, edit=True, enable=False)
        self.update_step3_status("Waiting for follicle creation to enable texture selection...")
        self.textures_data.clear()

    def reset_tool_state(self):
        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        
        self.locators_data.clear()
        self._update_locator_list_widget()
        
        self.reset_step2_and_beyond()

        cmds.button(self.select_mesh_button, edit=True, enable=True)
        cmds.button(self.create_locator_button, edit=True, enable=False)
        
        default_prefix = "Prefix"
        self.name_prefix = default_prefix
        cmds.textField(self.name_field, edit=True, text=default_prefix, enable=True)
        
        self.update_step1_status("Waiting for mesh selection...")
        step1_logic.clear_reference_follicle()

    def on_select_mesh_click(self, *args):
        self.reset_step2_and_beyond()
        step1_logic.clear_reference_follicle()
        
        selected_objects = cmds.ls(selection=True, transforms=True)
        if not selected_objects:
            self.update_step1_status("No objects selected. Please select a mesh.", success=False)
            return

        mesh_transform = mesh_shape = None
        for obj in selected_objects:
            shapes = cmds.listRelatives(obj, shapes=True) or []
            for shape in shapes:
                if cmds.objectType(shape, isType="mesh"):
                    mesh_transform = obj
                    mesh_shape = shape
                    break
            if mesh_transform: break
        
        if not mesh_transform or not mesh_shape:
            self.update_step1_status("Selected object is not a mesh.", success=False)
            return
        
        # Check if mesh has UV coordinates
        if not step1_logic.has_uv_map(mesh_shape):
            self.update_step1_status("Selected mesh does not have UV coordinates. Please select a mesh with UVs.", success=False)
            return
        
        self.selected_mesh_transform = mesh_transform
        self.selected_mesh_shape = mesh_shape
        
        follicle_transform, follicle_shape, null_group = step1_logic.create_reference_follicle(
            mesh_transform, mesh_shape)
        
        if follicle_transform and null_group:
            self.update_step1_status(f"Mesh '{mesh_transform}' selected and reference follicle created.", success=True)
            cmds.button(self.create_locator_button, edit=True, enable=True)
        else:
            self.update_step1_status("Failed to create reference follicle.", success=False)
    
    def on_create_locator_click(self, *args):
        if not self.selected_mesh_transform or not self.selected_mesh_shape:
            self.update_step1_status("No mesh selected. Please select a mesh first.", success=False)
            return

        current_prefix = cmds.textField(self.name_field, query=True, text=True)
        self.name_prefix = current_prefix
        
        if not current_prefix or current_prefix.isspace():
            self.update_step1_status("Prefix cannot be empty.", success=False)
            return
            
        if not self._is_prefix_unique(current_prefix):
            self.update_step1_status(f"Prefix '{current_prefix}' already exists.", success=False)
            return
        
        locator = step1_logic.create_locator_at_null_position(current_prefix)
        
        if locator:
            self.locators_data[current_prefix] = locator
            self._update_locator_list_widget()
            self.update_step1_status(f"Added locator '{locator}'.", success=True)
            
            match = re.match(r'^(.+?)_(\d+)$', current_prefix)
            if match:
                base = match.group(1)
                num = int(match.group(2))
                next_prefix = f"{base}_{num + 1}"
            else:
                next_prefix = f"{current_prefix}_1"
                
            cmds.textField(self.name_field, edit=True, text=next_prefix)
            self.name_prefix = next_prefix
            
            cmds.frameLayout(self.step2_frame, edit=True, enable=True)
            self.update_step2_status("Move locators. Create more or proceed to create follicles.")
        else:
            self.update_step1_status(f"Failed to add locator with prefix '{current_prefix}'.", success=False)

def show_ui():
    tool_ui = TextureRiggerUI()
    tool_ui.create_ui()
    return tool_ui

if __name__ == "__main__":
    ui_instance = show_ui()

