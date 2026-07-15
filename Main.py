import maya.cmds as cmds
import importlib
import json
import os
import re
import uuid

# Import logic files
from logic import step1_logic
from logic import step2_logic
from logic import step3_logic
from logic import step3_uv_logic


TOOL_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSET_ROOT = os.path.join(TOOL_ROOT, 'assets', 'images')

# Maya keeps imported scripts alive for the entire application session. Reload
# local implementation modules so a shelf click cannot mix new UI code with an
# older cached Step module.
for _module in (step1_logic, step2_logic, step3_logic, step3_uv_logic):
    importlib.reload(_module)

class TexelatorUI:
    def __init__(self):
        self.window_name = "texelatorMainWindow"
        self.ui_title = "Texelator v0.1.4"
        self.color_primary = (30.0 / 255.0, 31.0 / 255.0, 35.0 / 255.0)
        self.color_secondary = (1.0, 1.0, 1.0)
        self.color_accent = (1.0, 106.0 / 255.0, 0.0)
        self.color_banner = (12.0 / 255.0, 13.0 / 255.0, 16.0 / 255.0)
        self.banner_path = os.path.join(ASSET_ROOT, 'Texelator_Banner.png')

        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        self.setup_group = None
        
        self.locators_data = {}
        self.parts_data = {}
        self._loading_part_settings = False
        self.follicles_data = {}
        self.textures_data = {}
        
        self.name_prefix = "Prefix"

        self.name_field = None

        self.step1_frame = None
        self.select_mesh_button = None
        self.create_locator_button = None
        self.delete_locator_button = None
        self.locator_list_widget = None
        self.step1_status_label = None
        self.step1_revert_button = None

        # Mirror options
        self.mirror_checkbox = None
        self.mirror_options_layout = None
        self.mirror_axis_radios = None
        self.mirror_side_radios = None
        # Mirror settings are captured with the first locator and cannot change
        # until all Step 1 locators have been removed.
        self.mirror_settings = None
        self.mirror_pairs = {}

        self.step2_frame = None
        self.create_follicles_button = None
        self.step2_status_label = None
        self.step2_revert_button = None

        # Control shape/color
        self.part_control_options_layout = None
        self.part_control_options = {}
        
        self.step3_frame = None
        self.step3_top_col_layout = None
        self.texture_selection_layout = None
        self.texture_path_fields = {}
        self.select_texture_buttons = {}
        self.connect_all_textures_button = None
        self.step3_status_label = None
        self.step3_revert_button = None

        self.sequence_checkboxes = {}
        self.projection_checkboxes = {}

        # Layer ordering (inside Step 3, pre-connect)
        self.texture_order = []  # ordered list of prefixes for layeredTexture input order
        self.order_list_widget = None
        self.layer_tree_items = {}
        self.layer_tree_labels = {}
        self.layer_tree_selected = None
        self._clearing_layer_tree_native_selection = False
        self.order_up_button = None
        self.order_down_button = None
        self.layer_order_warning_label = None
        self._qt_window = None
        self._qt_banner_area = None
        self._qt_banner_label = None
        self._qt_banner_separator = None
        self._banner_resize_filter = None
        self._banner_area_pointer = None

        # Post-connect layer reorder (for edit existing setup)
        self.layer_frame = None
        self.layer_list_widget = None
        self.layer_texture_node = None
        self.material_snapshots = {}

        # Existing setup edit
        self.edit_frame = None
        self.edit_setup_menu = None
        self.found_setups = []

    def on_window_close(self, *args):
        self.reset_tool_state()
        step1_logic.clear_reference_follicle()

    def _apply_qt_style(self):
        """Apply the branded Qt layer while keeping Maya-command fallbacks."""
        try:
            import maya.OpenMayaUI as omui
            try:
                from PySide6 import QtCore, QtGui, QtWidgets
                from shiboken6 import wrapInstance
            except ImportError:
                from PySide2 import QtCore, QtGui, QtWidgets
                from shiboken2 import wrapInstance
            pointer = omui.MQtUtil.findWindow(self.window_name)
            if not pointer:
                return
            self._qt_window = wrapInstance(int(pointer), QtWidgets.QWidget)
            self._qt_window.setMinimumWidth(512)
            checkmark_path = os.path.join(
                ASSET_ROOT, 'Texelator_Checkmark.svg').replace('\\', '/')
            style_sheet = """
                QWidget {
                    background-color: #1E1F23;
                    color: #FFFFFF;
                }
                QWidget#texelatorBannerArea,
                QLabel#texelatorBannerImage {
                    background-color: #0C0D10;
                }
                QLabel#texelatorBannerImage {
                    qproperty-alignment: AlignCenter;
                    border: none;
                }
                QLabel:disabled,
                QCheckBox:disabled,
                QRadioButton:disabled,
                QGroupBox:disabled,
                QWidget:disabled {
                    color: #74777F;
                }
                QLineEdit,
                QComboBox,
                QListView,
                QTreeView,
                QAbstractSpinBox,
                QMenu {
                    background-color: #292A2F;
                    color: #FFFFFF;
                    border: 1px solid #4B4D55;
                    border-radius: 2px;
                    padding: 3px;
                    selection-background-color: #FF6A00;
                    selection-color: #FFFFFF;
                }
                QLineEdit:focus,
                QComboBox:focus,
                QListView:focus,
                QTreeView:focus,
                QAbstractSpinBox:focus {
                    border: 1px solid #FF6A00;
                }
                QCheckBox {
                    spacing: 7px;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    background-color: #292A2F;
                    border: 2px solid #92959E;
                    border-radius: 2px;
                }
                QCheckBox::indicator:hover {
                    border-color: #FF6A00;
                    background-color: #32343A;
                }
                QCheckBox::indicator:checked {
                    background-color: #FF6A00;
                    border-color: #FF6A00;
                    image: url("__TEXELATOR_CHECKMARK__");
                }
                QCheckBox::indicator:disabled {
                    background-color: #25262B;
                    border-color: #50525A;
                }
                QCheckBox::indicator:checked:disabled {
                    background-color: #6A3C1C;
                    border-color: #6A3C1C;
                }
                QPushButton {
                    background-color: #303138;
                    color: #FFFFFF;
                    border: 1px solid #555862;
                    border-radius: 2px;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #383A42;
                    border-color: #FF6A00;
                }
                QPushButton:pressed {
                    background-color: #24252A;
                }
                QPushButton:disabled {
                    background-color: #25262B;
                    color: #74777F;
                    border-color: #383A41;
                }
                QPushButton#texelatorSelectMeshButton,
                QPushButton#texelatorCreateGuidesButton,
                QPushButton#texelatorCreateControlButton,
                QPushButton#texelatorBuildFinalButton {
                    background-color: #FF6A00;
                    color: #FFFFFF;
                    border: 1px solid #FF6A00;
                    font-weight: 600;
                }
                QPushButton#texelatorSelectMeshButton:hover,
                QPushButton#texelatorCreateGuidesButton:hover,
                QPushButton#texelatorCreateControlButton:hover,
                QPushButton#texelatorBuildFinalButton:hover {
                    background-color: #E85F00;
                }
                QPushButton#texelatorSelectMeshButton:disabled,
                QPushButton#texelatorCreateGuidesButton:disabled,
                QPushButton#texelatorCreateControlButton:disabled,
                QPushButton#texelatorBuildFinalButton:disabled {
                    background-color: #3A2B22;
                    color: #74777F;
                    border-color: #503524;
                }
                QFrame#texelatorBannerSeparator,
                QFrame#texelatorStepSeparator1,
                QFrame#texelatorStepSeparator2,
                QFrame#texelatorStepSeparator3 {
                    background-color: #FF6A00;
                    border: none;
                    min-height: 2px;
                    max-height: 2px;
                }
                QWidget#texelatorStep1Header,
                QWidget#texelatorStep2Header,
                QWidget#texelatorStep3Header {
                    background-color: #FF6A00;
                    color: #000000;
                    min-height: 28px;
                }
                QLabel#texelatorStep1HeaderLabel,
                QLabel#texelatorStep2HeaderLabel,
                QLabel#texelatorStep3HeaderLabel,
                QLabel#texelatorStep1HeaderLabel:disabled,
                QLabel#texelatorStep2HeaderLabel:disabled,
                QLabel#texelatorStep3HeaderLabel:disabled {
                    background-color: transparent;
                    color: #000000;
                    font-weight: 700;
                }
                QToolTip {
                    background-color: #292A2F;
                    color: #FFFFFF;
                    border: 1px solid #FF6A00;
                }
            """.replace('__TEXELATOR_CHECKMARK__', checkmark_path)
            self._qt_window.setStyleSheet(style_sheet)

            expanding_policy = (
                QtWidgets.QSizePolicy.Expanding
                if hasattr(QtWidgets.QSizePolicy, 'Expanding')
                else QtWidgets.QSizePolicy.Policy.Expanding)
            fixed_policy = (
                QtWidgets.QSizePolicy.Fixed
                if hasattr(QtWidgets.QSizePolicy, 'Fixed')
                else QtWidgets.QSizePolicy.Policy.Fixed)

            banner_pointer = omui.MQtUtil.findControl(
                'texelatorBannerArea')
            if banner_pointer:
                banner_area = wrapInstance(
                    int(banner_pointer), QtWidgets.QWidget)
                banner_area.setObjectName('texelatorBannerArea')
                banner_area.setFixedHeight(130)
                banner_area.setSizePolicy(expanding_policy, fixed_policy)

                banner_label = banner_area.findChild(
                    QtWidgets.QLabel, 'texelatorBannerImage')
                if banner_label is None:
                    banner_label = QtWidgets.QLabel(banner_area)
                    banner_label.setObjectName('texelatorBannerImage')

                banner_separator = banner_area.findChild(
                    QtWidgets.QFrame, 'texelatorBannerSeparator')
                if banner_separator is None:
                    banner_separator = QtWidgets.QFrame(banner_area)
                    banner_separator.setObjectName(
                        'texelatorBannerSeparator')

                align_center = (
                    QtCore.Qt.AlignCenter
                    if hasattr(QtCore.Qt, 'AlignCenter')
                    else QtCore.Qt.AlignmentFlag.AlignCenter)
                pixmap = QtGui.QPixmap(self.banner_path)
                if pixmap.isNull():
                    cmds.warning(
                        "Texelator banner could not be loaded: {}".format(
                            self.banner_path))
                banner_label.setPixmap(pixmap)
                banner_label.setAlignment(align_center)
                banner_label.setScaledContents(False)
                banner_label.setGeometry(0, 0, banner_area.width(), 128)
                banner_separator.setGeometry(
                    0, 128, banner_area.width(), 2)
                banner_label.show()
                banner_separator.show()
                banner_label.raise_()
                banner_separator.raise_()

                pointer_value = int(banner_pointer)
                if self._banner_area_pointer != pointer_value:
                    resize_event = (
                        QtCore.QEvent.Resize
                        if hasattr(QtCore.QEvent, 'Resize')
                        else QtCore.QEvent.Type.Resize)

                    class BannerResizeFilter(QtCore.QObject):
                        def __init__(self, image_label, separator, parent=None):
                            super(BannerResizeFilter, self).__init__(parent)
                            self.image_label = image_label
                            self.separator = separator

                        def eventFilter(self, watched, event):
                            if event.type() == resize_event:
                                width = watched.width()
                                self.image_label.setGeometry(
                                    0, 0, width, 128)
                                self.separator.setGeometry(
                                    0, 128, width, 2)
                            return False

                    self._banner_resize_filter = BannerResizeFilter(
                        banner_label, banner_separator, banner_area)
                    banner_area.installEventFilter(
                        self._banner_resize_filter)
                    self._banner_area_pointer = pointer_value

                self._qt_banner_area = banner_area
                self._qt_banner_label = banner_label
                self._qt_banner_separator = banner_separator
        except Exception as error:
            cmds.warning(
                "Texelator Qt styling could not be applied: {}".format(error))

    def create_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name, window=True)

        self.window = cmds.window(
            self.window_name, 
            title=self.ui_title, 
            widthHeight=(512, 760),
            backgroundColor=self.color_primary,
            sizeable=True,
            closeCommand=self.on_window_close
        )
        
        main_layout = cmds.columnLayout(
            adjustableColumn=True, rowSpacing=10, parent=self.window,
            backgroundColor=self.color_primary, enableBackground=True)

        if os.path.exists(self.banner_path):
            cmds.text(
                'texelatorBannerArea', label='', align='center', height=130,
                backgroundColor=self.color_banner, enableBackground=True,
                annotation='Texelator - 2D Texture Rigger',
                parent=main_layout)
        else:
            cmds.warning(
                "Texelator banner was not found: {}".format(self.banner_path))

        # Mesh selection is the prerequisite for every numbered build step, so
        # keep it outside and directly above the Step 1 frame.
        self.select_mesh_button = cmds.button(
            'texelatorSelectMeshButton',
            label="Select Mesh", command=self.on_select_mesh_click,
            parent=main_layout, height=30,
            backgroundColor=self.color_accent)

        self.step1_frame = cmds.frameLayout(
            "step1_frame", label="STEP 1: Create Guides", collapsable=False,
            collapse=False, parent=main_layout, marginWidth=10,
            marginHeight=5, labelVisible=False,
            backgroundColor=self.color_primary)
        step1_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step1_frame, rowSpacing=5)
        step1_header = cmds.rowLayout(
            'texelatorStep1Header', numberOfColumns=2, adjustableColumn=1,
            parent=step1_col_layout, backgroundColor=self.color_accent,
            enableBackground=True)
        cmds.text(
            'texelatorStep1HeaderLabel', label="STEP 1: Create Guides",
            align="left")
        self.step1_revert_button = cmds.button(label="Revert", command=self._on_clear_step1, height=20, width=55, enable=False)
        cmds.setParent('..')
        
        name_row_layout = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 80), (2, 300)], parent=step1_col_layout, rowSpacing=(1,3))
        cmds.text(label="Prefix:", align="right")
        self.name_field = cmds.textField(text=self.name_prefix, parent=name_row_layout, 
                                    changeCommand=self.on_name_changed)
        cmds.setParent("..")
        
        self.create_locator_button = cmds.button(
            'texelatorCreateGuidesButton',
            label="Create Guides", command=self.on_create_locator_click,
            parent=step1_col_layout, height=30, enable=False,
            backgroundColor=self.color_accent)

        # --- Mirror Options ---
        cmds.text(label="Mirror Setup:", align="left", parent=step1_col_layout)
        self.mirror_checkbox = cmds.checkBox(label="Create Mirrored Pair", value=False, changeCommand=self._on_mirror_toggle, parent=step1_col_layout)
        self.mirror_options_layout = cmds.rowColumnLayout(numberOfColumns=4, columnWidth=[(1, 80), (2, 100), (3, 80), (4, 100)], parent=step1_col_layout, visible=False)
        cmds.text(label="Axis:", align="right")
        self.mirror_axis_radios = cmds.radioCollection()
        mirror_axis_row = cmds.rowLayout(numberOfColumns=3, parent=self.mirror_options_layout)
        cmds.radioButton('mirror_X', label='X', select=True, collection=self.mirror_axis_radios, changeCommand=lambda *_: self._on_mirror_axis_changed())
        cmds.radioButton('mirror_Y', label='Y', collection=self.mirror_axis_radios, changeCommand=lambda *_: self._on_mirror_axis_changed())
        cmds.radioButton('mirror_Z', label='Z', collection=self.mirror_axis_radios, changeCommand=lambda *_: self._on_mirror_axis_changed())
        cmds.setParent('..')
        cmds.text(label="Original Side:", align="right")
        self.mirror_side_radios = cmds.radioCollection()
        mirror_side_row = cmds.rowLayout(numberOfColumns=2, parent=self.mirror_options_layout)
        cmds.radioButton('mirror_L', label='L_', select=True, collection=self.mirror_side_radios, changeCommand=lambda *_: self._on_mirror_side_changed())
        cmds.radioButton('mirror_R', label='R_', collection=self.mirror_side_radios, changeCommand=lambda *_: self._on_mirror_side_changed())
        cmds.setParent('..')
        cmds.setParent('..')

        # --- Locator List + Delete ---
        cmds.text(label="Parts:", align="left", parent=step1_col_layout)
        locator_list_row = cmds.rowColumnLayout(numberOfColumns=2, columnWidth=[(1, 330), (2, 80)], parent=step1_col_layout)
        self.locator_list_widget = cmds.textScrollList(
            numberOfRows=4, allowMultiSelection=False,
            selectCommand=self._on_part_selected, parent=locator_list_row,
            height=60, backgroundColor=self.color_primary)
        self.delete_locator_button = cmds.button(label="Delete", command=self.on_delete_locator_click, parent=locator_list_row, height=60, enable=False)
        cmds.setParent('..')
        
        self.step1_status_label = cmds.text(label="Status: Waiting for mesh selection...", align="left", parent=step1_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.separator(
            'texelatorStepSeparator1', height=2, style='none',
            parent=main_layout, backgroundColor=self.color_accent,
            enableBackground=True)

        self.step2_frame = cmds.frameLayout(
            "step2_frame", label="STEP 2: Create Control", collapsable=False,
            collapse=False, parent=main_layout, marginWidth=10,
            marginHeight=5, enable=False, labelVisible=False,
            backgroundColor=self.color_primary)
        step2_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step2_frame, rowSpacing=5)
        step2_header = cmds.rowLayout(
            'texelatorStep2Header', numberOfColumns=2, adjustableColumn=1,
            parent=step2_col_layout, backgroundColor=self.color_accent,
            enableBackground=True)
        cmds.text(
            'texelatorStep2HeaderLabel', label="STEP 2: Create Control",
            align="left")
        self.step2_revert_button = cmds.button(label="Revert", command=self._on_clear_step2, height=20, width=55, enable=False)
        cmds.setParent('..')
        cmds.text(label="Move the created locators to desired positions on the mesh.", align="left", parent=step2_col_layout)

        cmds.text(label="Part Control Settings:", align="left", parent=step2_col_layout)
        self.part_control_options_layout = cmds.columnLayout(adjustableColumn=True, parent=step2_col_layout)

        self.create_follicles_button = cmds.button(
            'texelatorCreateControlButton',
            label="Create Control", command=self.on_create_follicles_click,
            parent=step2_col_layout, height=30,
            backgroundColor=self.color_accent)
        self.step2_status_label = cmds.text(label="Status: Waiting for locator positioning and follicle creation...", align="left", parent=step2_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.separator(
            'texelatorStepSeparator2', height=2, style='none',
            parent=main_layout, backgroundColor=self.color_accent,
            enableBackground=True)

        self.step3_frame = cmds.frameLayout(
            "step3_frame",
            label="STEP 3: Select Textures & Connect to Materials",
            collapsable=False, collapse=False, parent=main_layout,
            marginWidth=10, marginHeight=5, enable=False,
            labelVisible=False,
            backgroundColor=self.color_primary)
        self.step3_top_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.step3_frame, rowSpacing=5)
        step3_header = cmds.rowLayout(
            'texelatorStep3Header', numberOfColumns=2, adjustableColumn=1,
            parent=self.step3_top_col_layout,
            backgroundColor=self.color_accent, enableBackground=True)
        cmds.text(
            'texelatorStep3HeaderLabel',
            label="STEP 3: Select Textures & Connect to Materials",
            align="left")
        self.step3_revert_button = cmds.button(label="Revert", command=self._on_clear_step3, height=20, width=55, enable=False)
        cmds.setParent('..')

        self.texture_selection_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=3, parent=self.step3_top_col_layout) 
        cmds.setParent("..")

        # --- Layer Ordering (inside Step 3, pre-connect) ---
        cmds.separator(height=8, style='in', parent=self.step3_top_col_layout)
        cmds.text(
            label='Layer Order (top first):', align='left',
            parent=self.step3_top_col_layout)
        order_row = cmds.rowLayout(
            numberOfColumns=2, adjustableColumn=1,
            columnWidth2=(380, 28), parent=self.step3_top_col_layout)
        self.order_list_widget = cmds.treeView(
            allowMultiSelection=False, allowDragAndDrop=False,
            allowReparenting=False, height=180,
            selectCommand=self._on_layer_tree_selection,
            backgroundColor=self.color_primary,
            parent=order_row)
        order_button_column = cmds.columnLayout(
            adjustableColumn=True, rowSpacing=1, parent=order_row)
        self.order_up_button = cmds.button(
            label='\u25B2', command=self._on_order_move_up,
            height=20, enable=False, parent=order_button_column)
        self.order_down_button = cmds.button(
            label='\u25BC', command=self._on_order_move_down,
            height=20, enable=False, parent=order_button_column)
        self.layer_order_warning_label = cmds.text(
            label='Select a layer to see its allowed order range.',
            align='left', parent=self.step3_top_col_layout)

        self.connect_all_textures_button = cmds.button(
            'texelatorBuildFinalButton',
            label="Build Final", command=self.on_connect_all_textures_click,
            parent=self.step3_top_col_layout, height=30, enable=False,
            backgroundColor=self.color_accent)
        self.step3_status_label = cmds.text(label="Status: Waiting for follicle creation to enable texture selection...", align="left", parent=self.step3_top_col_layout)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.separator(
            'texelatorStepSeparator3', height=2, style='none',
            parent=main_layout, backgroundColor=self.color_accent,
            enableBackground=True)

        # --- Layer Ordering Panel (post-connect / edit existing setup) ---
        self.layer_frame = cmds.frameLayout(
            "layer_frame", label="Reorder Existing Layers",
            collapsable=True, collapse=True, parent=main_layout,
            marginWidth=10, marginHeight=5, enable=False,
            backgroundColor=self.color_primary)
        layer_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.layer_frame, rowSpacing=5)
        cmds.text(
            label='Existing Layers (top first):', align='left',
            parent=layer_col_layout)
        layer_btn_row = cmds.rowLayout(
            numberOfColumns=2, adjustableColumn=1,
            columnWidth2=(380, 28), parent=layer_col_layout)
        self.layer_list_widget = cmds.textScrollList(
            numberOfRows=2, allowMultiSelection=False, height=42,
            parent=layer_btn_row, backgroundColor=self.color_primary)
        layer_button_column = cmds.columnLayout(
            adjustableColumn=True, rowSpacing=1, parent=layer_btn_row)
        cmds.button(
            label='\u25B2', command=self._on_layer_move_up,
            height=20, parent=layer_button_column)
        cmds.button(
            label='\u25BC', command=self._on_layer_move_down,
            height=20, parent=layer_button_column)
        cmds.setParent("..")
        cmds.setParent("..")

        # --- Existing Setup Edit Panel ---
        self.edit_frame = cmds.frameLayout(
            "edit_frame", label="Edit Existing Setup", collapsable=True,
            collapse=True, parent=main_layout, marginWidth=10,
            marginHeight=5, backgroundColor=self.color_primary)
        edit_col_layout = cmds.columnLayout(adjustableColumn=True, parent=self.edit_frame, rowSpacing=5)
        cmds.button(label="Scan Scene for Setups", command=self._on_scan_setups_click, height=25)
        self.edit_setup_menu = cmds.optionMenu(label="Found Setups:")
        cmds.menuItem(label="(none)")
        cmds.button(label="Load Selected Setup", command=self._on_load_setup_click, height=25)
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.showWindow(self.window)
        self._apply_qt_style()
        cmds.evalDeferred(self._apply_qt_style, lowestPriority=True)

    def on_name_changed(self, new_name):
        if not new_name or new_name.isspace():
            self.name_prefix = "texelator"
            cmds.textField(self.name_field, edit=True, text=self.name_prefix)
            cmds.warning("Prefix cannot be empty. Using default 'texelator'.")
        else:
            cleaned_name = ''.join(c for c in new_name if c.isalnum() or c == '_')
            if cleaned_name != new_name:
                cmds.textField(self.name_field, edit=True, text=cleaned_name)
            self.name_prefix = cleaned_name

    def _is_prefix_unique(self, prefix_to_check):
        return prefix_to_check not in self.locators_data

    def _ensure_setup_group(self):
        """One visible DAG container per mesh for all Texelator scene objects."""
        if self.setup_group and cmds.objExists(self.setup_group):
            return self.setup_group
        mesh_name = self.selected_mesh_transform.split('|')[-1].split(':')[-1]
        group_name = f"Texelator_{re.sub(r'[^A-Za-z0-9_]', '_', mesh_name)}"
        if cmds.objExists(group_name):
            is_setup = cmds.attributeQuery(
                'isTexelatorSetup', node=group_name, exists=True)
            stored_mesh = None
            if cmds.attributeQuery('texelatorMesh', node=group_name, exists=True):
                stored_mesh = cmds.getAttr(f'{group_name}.texelatorMesh')
            self.setup_group = (group_name if is_setup and stored_mesh in (None, self.selected_mesh_transform)
                                else cmds.group(empty=True, name=f'{group_name}#', world=True))
        else:
            self.setup_group = cmds.group(empty=True, name=group_name, world=True)
        if not cmds.attributeQuery('isTexelatorSetup', node=self.setup_group, exists=True):
            cmds.addAttr(self.setup_group, longName='isTexelatorSetup', attributeType='bool', defaultValue=True)
            cmds.setAttr(f'{self.setup_group}.isTexelatorSetup', lock=True)
        if not cmds.attributeQuery('texelatorSetupId', node=self.setup_group, exists=True):
            cmds.addAttr(self.setup_group, longName='texelatorSetupId', dataType='string')
            cmds.setAttr(f'{self.setup_group}.texelatorSetupId', str(uuid.uuid4()), type='string', lock=True)
        if not cmds.attributeQuery('texelatorMesh', node=self.setup_group, exists=True):
            cmds.addAttr(self.setup_group, longName='texelatorMesh', dataType='string')
            cmds.setAttr(f'{self.setup_group}.texelatorMesh', self.selected_mesh_transform, type='string')
        if not cmds.attributeQuery('texelatorStage', node=self.setup_group, exists=True):
            cmds.addAttr(self.setup_group, longName='texelatorStage', dataType='string')
            cmds.setAttr(f'{self.setup_group}.texelatorStage', 'selected_mesh', type='string')
        if not cmds.attributeQuery('texelatorData', node=self.setup_group, exists=True):
            cmds.addAttr(self.setup_group, longName='texelatorData', dataType='string')
            cmds.setAttr(f'{self.setup_group}.texelatorData', '{}', type='string')
        return self.setup_group

    def _set_setup_stage(self, stage):
        if self._ensure_setup_group() and cmds.attributeQuery('texelatorStage', node=self.setup_group, exists=True):
            cmds.setAttr(f'{self.setup_group}.texelatorStage', stage, type='string')
            self._save_setup_metadata(stage)

    def _save_setup_metadata(self, stage=None):
        """Persist the user choices required to resume a Core setup."""
        if not self.setup_group or not cmds.objExists(self.setup_group):
            return
        parts = {}
        for name, part in self.parts_data.items():
            parts[name] = {
                key: part.get(key) for key in (
                    'mirrored', 'axis', 'original_side', 'original_key',
                    'guide_key')
            }
        controls = {}
        for name, options in self.part_control_options.items():
            shape = options.get('shape_value', 'circle')
            color = options.get('color_value', 'Default')
            try:
                if (options.get('shape_menu') and
                        cmds.optionMenu(options['shape_menu'], exists=True)):
                    shape = cmds.optionMenu(
                        options['shape_menu'], query=True, value=True)
                if (options.get('color_menu') and
                        cmds.optionMenu(options['color_menu'], exists=True)):
                    color = cmds.optionMenu(
                        options['color_menu'], query=True, value=True)
            except RuntimeError:
                pass
            controls[name] = {'shape': shape, 'color': color}

        textures = {}
        for prefix, data in self.textures_data.items():
            if data.get('settings_owner', prefix) != prefix:
                continue
            textures[prefix] = {
                'file_path': data.get('file_path'),
                'is_sequence': bool(data.get('is_sequence')),
                'use_projection': bool(data.get('use_projection', True))
            }
        payload = {
            'version': 4,
            'edition': 'core',
            'stage': stage or (
                cmds.getAttr(f'{self.setup_group}.texelatorStage') or
                'selected_mesh'),
            'parts': parts,
            'controls': controls,
            'textures': textures,
            'texture_order': [
                prefix for prefix in self.texture_order
                if prefix in self.textures_data]
        }
        if cmds.attributeQuery(
                'texelatorData', node=self.setup_group, exists=True):
            cmds.setAttr(
                f'{self.setup_group}.texelatorData',
                json.dumps(payload, sort_keys=True), type='string')


    def _on_mirror_toggle(self, state):
        cmds.rowColumnLayout(self.mirror_options_layout, edit=True, visible=state)
        if self._loading_part_settings:
            return
        part_name = self._selected_part_name()
        if part_name and part_name in self.parts_data:
            self._set_part_mirror(part_name, state)
            return
        if state and self.locators_data:
            if not self.mirror_settings:
                self._capture_mirror_settings()
            axis_button = cmds.radioCollection(self.mirror_axis_radios, query=True, select=True)
            side_button = cmds.radioCollection(self.mirror_side_radios, query=True, select=True)
            self.mirror_settings['enabled'] = True
            self.mirror_settings['axis'] = axis_button.replace('mirror_', '') if axis_button else 'X'
            self.mirror_settings['original_side'] = side_button.replace('mirror_', '') if side_button else 'L'
            self._create_mirror_guides_for_existing()

    def _set_mirror_setup_enabled(self, enabled):
        """Lock pair creation options once locators exist; axis remains live."""
        cmds.checkBox(self.mirror_checkbox, edit=True, enable=True)
        cmds.radioButton('mirror_X', edit=True, enable=True)
        cmds.radioButton('mirror_Y', edit=True, enable=True)
        cmds.radioButton('mirror_Z', edit=True, enable=True)
        cmds.radioButton('mirror_L', edit=True, enable=True)
        cmds.radioButton('mirror_R', edit=True, enable=True)

    def _on_mirror_side_changed(self):
        """Rename the selected mirror pair so its chosen original side is explicit."""
        if self._loading_part_settings:
            return
        selected = cmds.radioCollection(self.mirror_side_radios, query=True, select=True)
        side = selected.replace('mirror_', '') if selected else 'L'
        if self.mirror_settings:
            self.mirror_settings['original_side'] = side
        part_name = self._selected_part_name()
        part = self.parts_data.get(part_name)
        if not part:
            return
        if not part['mirrored']:
            part['original_side'] = side
            return
        if part['original_side'] == side:
            return
        mirror_side = 'R' if side == 'L' else 'L'
        original_key, guide_key = f"{side}_{part_name}", f"{mirror_side}_{part_name}"
        temporary_name = cmds.rename(part['original'], f"{part_name}_mirrorSwap_locator")
        guide = cmds.rename(part['guide'], f"{guide_key}_locator")
        original = cmds.rename(temporary_name, f"{original_key}_locator")
        self.locators_data.pop(part['original_key'], None)
        self.locators_data.pop(part['guide_key'], None)
        self.locators_data.update({original_key: original, guide_key: guide})
        self.mirror_pairs.pop(part['original_key'], None)
        self.mirror_pairs[original_key] = {'original_prefix': original_key, 'original': original, 'guide_prefix': guide_key, 'guide': guide, 'utility_nodes': part['utility_nodes']}
        part.update({'original_side': side, 'original': original, 'original_key': original_key, 'guide': guide, 'guide_key': guide_key})
        self._update_locator_list_widget(select_part=part_name)
        self._save_setup_metadata()

    def _selected_part_name(self):
        selected = cmds.textScrollList(self.locator_list_widget, query=True, selectItem=True) or []
        return selected[0] if selected else None

    def _on_part_selected(self, *args):
        """Load the selected part's independent mirror settings into Step 1."""
        part_name = self._selected_part_name()
        part = self.parts_data.get(part_name)
        if not part:
            return
        self._loading_part_settings = True
        try:
            cmds.checkBox(self.mirror_checkbox, edit=True, value=part['mirrored'])
            cmds.rowColumnLayout(self.mirror_options_layout, edit=True, visible=part['mirrored'])
            cmds.radioCollection(self.mirror_axis_radios, edit=True, select=f"mirror_{part['axis']}")
            cmds.radioCollection(self.mirror_side_radios, edit=True, select=f"mirror_{part['original_side']}")
        finally:
            self._loading_part_settings = False

    def _set_part_mirror(self, part_name, enabled):
        """Add or remove a live mirror guide for exactly one selected part."""
        part = self.parts_data[part_name]
        if enabled == part['mirrored']:
            return
        if not enabled:
            for node in part.get('utility_nodes', []):
                if cmds.objExists(node): cmds.delete(node)
            if cmds.objExists(part.get('guide')): cmds.delete(part['guide'])
            self.locators_data.pop(part.get('guide_key'), None)
            self.mirror_pairs.pop(part.get('original_key'), None)
            original = cmds.rename(part['original'], f"{part_name}_locator")
            self.locators_data.pop(part['original_key'], None)
            self.locators_data[part_name] = original
            part.update({'mirrored': False, 'original': original, 'original_key': part_name, 'guide': None, 'guide_key': None, 'utility_nodes': []})
        else:
            side_button = cmds.radioCollection(self.mirror_side_radios, query=True, select=True)
            side = side_button.replace('mirror_', '') if side_button else 'L'
            axis_button = cmds.radioCollection(self.mirror_axis_radios, query=True, select=True)
            axis = axis_button.replace('mirror_', '') if axis_button else 'X'
            original_key, guide_key = f"{side}_{part_name}", f"{'R' if side == 'L' else 'L'}_{part_name}"
            original = cmds.rename(part['original'], f"{original_key}_locator")
            guide = step1_logic.create_mirrored_locator(original, self.selected_mesh_transform, axis, guide_key)
            if not guide:
                return
            cmds.parent(guide, self._ensure_setup_group())
            utilities = step1_logic.connect_mirror_guide(original, guide, self.selected_mesh_transform, axis, original_key)
            self.locators_data.pop(part['original_key'], None)
            self.locators_data.update({original_key: original, guide_key: guide})
            self.mirror_pairs[original_key] = {'original_prefix': original_key, 'original': original, 'guide_prefix': guide_key, 'guide': guide, 'utility_nodes': utilities}
            part.update({'mirrored': True, 'axis': axis, 'original_side': side, 'original': original, 'original_key': original_key, 'guide': guide, 'guide_key': guide_key, 'utility_nodes': utilities})
        self._update_locator_list_widget(select_part=part_name)
        self._save_setup_metadata()

    def _create_mirror_guides_for_existing(self):
        """Add live mirror guides to already-created unpaired guides."""
        original_side = self.mirror_settings['original_side']
        mirror_side = 'R' if original_side == 'L' else 'L'
        paired_names = {pair['original'] for pair in self.mirror_pairs.values()}
        paired_names.update(pair['guide'] for pair in self.mirror_pairs.values())
        for prefix, locator in list(self.locators_data.items()):
            if locator in paired_names or not cmds.objExists(locator):
                continue
            base_prefix = prefix[2:] if prefix.startswith(('L_', 'R_')) else prefix
            original_prefix = f"{original_side}_{base_prefix}"
            if original_prefix != prefix:
                if original_prefix in self.locators_data:
                    cmds.warning(f"Cannot mirror '{prefix}': prefix '{original_prefix}' already exists.")
                    continue
                locator = cmds.rename(locator, f"{original_prefix}_locator")
                del self.locators_data[prefix]
                self.locators_data[original_prefix] = locator
            mirror_prefix = f"{mirror_side}_{base_prefix}"
            if mirror_prefix in self.locators_data:
                continue
            guide = step1_logic.create_mirrored_locator(locator, self.selected_mesh_transform, self.mirror_settings['axis'], mirror_prefix)
            if not guide:
                continue
            cmds.parent(guide, self._ensure_setup_group())
            utility_nodes = step1_logic.connect_mirror_guide(locator, guide, self.selected_mesh_transform, self.mirror_settings['axis'], original_prefix)
            self.locators_data[mirror_prefix] = guide
            self.mirror_pairs[original_prefix] = {'original_prefix': original_prefix, 'original': locator, 'guide_prefix': mirror_prefix, 'guide': guide, 'utility_nodes': utility_nodes}
        self._update_locator_list_widget()

    def _capture_mirror_settings(self):
        """Read the setup once, before the first locator is made."""
        is_mirror = cmds.checkBox(self.mirror_checkbox, query=True, value=True)
        axis_button = cmds.radioCollection(self.mirror_axis_radios, query=True, select=True)
        side_button = cmds.radioCollection(self.mirror_side_radios, query=True, select=True)
        self.mirror_settings = {
            'enabled': is_mirror,
            'axis': axis_button.replace('mirror_', '') if axis_button else 'X',
            'original_side': side_button.replace('mirror_', '') if side_button else 'L'
        }
        self._set_mirror_setup_enabled(False)

    def _on_mirror_axis_changed(self):
        if self._loading_part_settings:
            return
        selected = cmds.radioCollection(self.mirror_axis_radios, query=True, select=True)
        axis = selected.replace('mirror_', '') if selected else 'X'
        part_name = self._selected_part_name()
        part = self.parts_data.get(part_name)
        if part and part['mirrored']:
            for node in part['utility_nodes']:
                if cmds.objExists(node): cmds.delete(node)
            part['utility_nodes'] = step1_logic.connect_mirror_guide(part['original'], part['guide'], self.selected_mesh_transform, axis, part['original_key'])
            part['axis'] = axis
            pair = self.mirror_pairs.get(part['original_key'])
            if pair is not None:
                pair['utility_nodes'] = part['utility_nodes']
            self._save_setup_metadata()
            return
        if not self.mirror_pairs:
            return
        for pair in self.mirror_pairs.values():
            for node in pair['utility_nodes']:
                if cmds.objExists(node): cmds.delete(node)
            pair['utility_nodes'] = step1_logic.connect_mirror_guide(pair['original'], pair['guide'], self.selected_mesh_transform, axis, pair['original_prefix'])
        self.mirror_settings['axis'] = axis
        self.update_step1_status(f"Mirror guide axis updated to {axis}.", success=True)

    def _unlock_mirror_setup_if_empty(self):
        if not self.locators_data:
            self.mirror_settings = None
            self._set_mirror_setup_enabled(True)

    def _confirm_cleanup(self, title, message):
        return cmds.confirmDialog(
            title=title, message=message, button=['Cancel', 'Continue'],
            defaultButton='Cancel', cancelButton='Cancel', dismissString='Cancel'
        ) == 'Continue'

    def _set_active_revert_step(self, step=None):
        """Only the revert action for the current completed stage is available."""
        cmds.button(self.step1_revert_button, edit=True, enable=step == 1)
        cmds.button(self.step2_revert_button, edit=True, enable=step == 2)
        cmds.button(self.step3_revert_button, edit=True, enable=step == 3)

    def _on_clear_step1(self, *args):
        """Return to the selected-mesh state while preserving the selection."""
        if not self._confirm_cleanup('Revert Step 1', 'Delete Texelator guides and return to the selected mesh?'):
            return
        for pair in self.mirror_pairs.values():
            for node in pair.get('utility_nodes', []):
                if cmds.objExists(node): cmds.delete(node)
        # Delete all locators from scene
        for prefix, locator_name in list(self.locators_data.items()):
            if cmds.objExists(locator_name):
                cmds.delete(locator_name)
        
        # Remove any downstream nodes as well.
        self._delete_step2_nodes()
        self._delete_step3_nodes()
        self._restore_material_snapshots()
        self.locators_data.clear()
        self.parts_data.clear()
        self.mirror_pairs.clear()
        self.follicles_data.clear()
        self._update_locator_list_widget()
        self._populate_part_control_options()
        self.reset_step2_and_beyond()
        if self.selected_mesh_transform and self.selected_mesh_shape:
            step1_logic.clear_reference_follicle()
            reference_follicle, _, _ = step1_logic.create_reference_follicle(
                self.selected_mesh_transform, self.selected_mesh_shape)
            if reference_follicle:
                cmds.parent(reference_follicle, self._ensure_setup_group())
            cmds.select(self.selected_mesh_transform, replace=True)
            cmds.button(self.create_locator_button, edit=True, enable=True)
            self._set_setup_stage('selected_mesh')
        self._set_active_revert_step()
        self.update_step1_status("Reverted to the selected mesh.", success=True)

    def _on_clear_step2(self, *args):
        """Deletes follicles, controls and their utility nodes, returning to Step 1."""
        if not self._confirm_cleanup('Revert Step 2', 'Delete Texelator controls and return to the guide stage?'):
            return
        self._delete_step2_nodes()
        self._delete_step3_nodes()
        self._restore_material_snapshots()
        
        # Reset step 2 and step 3 UI
        self.reset_step2_and_beyond()
        for locator in self.locators_data.values():
            if cmds.objExists(locator): cmds.setAttr(f"{locator}.visibility", 1)
        
        # Re-enable Step 1 locator creation (mesh is still selected)
        if self.selected_mesh_transform and self.selected_mesh_shape:
            cmds.frameLayout(self.step2_frame, edit=True, enable=True)
            cmds.button(self.create_locator_button, edit=True, enable=True)
            cmds.button(self.create_follicles_button, edit=True, enable=True)
            cmds.textField(self.name_field, edit=True, enable=True)
            self._set_setup_stage('guides')
            self.update_step1_status(
                f"Controls removed. Guides for '{self.selected_mesh_transform}' are ready.",
                success=True)
            self.update_step2_status("Adjust guides or click Create Control again.", success=True)
        else:
            self.update_step1_status("Controls removed.", success=True)
        self._set_active_revert_step(1)

    def _on_clear_step3(self, *args):
        """Delete the final build while preserving every Step 3 UI choice."""
        if not self._confirm_cleanup(
                'Revert Step 3',
                'Delete the final texture network but keep all Step 3 settings?'):
            return
        self._delete_step3_nodes()
        self._restore_material_snapshots()
        self._clear_texture_runtime_data()

        # The final network no longer exists, but texture paths, checkboxes and
        # Main layer ordering remain ready for another build.
        cmds.frameLayout(self.step3_frame, edit=True, enable=True)
        cmds.button(self.connect_all_textures_button, edit=True, enable=True)
        cmds.frameLayout(self.layer_frame, edit=True, enable=False, collapse=True)
        cmds.textScrollList(self.layer_list_widget, edit=True, removeAll=True)
        self.layer_texture_node = None
        self._set_setup_stage('controls')
        self.update_step3_status(
            'Final build reverted. Step 3 settings were preserved.',
            success=True)
        self._set_active_revert_step(2)

    def _delete_step2_nodes(self):
        """Deletes all nodes created by Step 2 (follicles, controls, DG utility nodes)."""
        for prefix, fol_data in list(self.follicles_data.items()):
            follicle_trans = fol_data.get('follicle')
            ctrl_group = None
            tracked_utilities = []
            if follicle_trans and cmds.objExists(follicle_trans):
                if cmds.attributeQuery(
                        'texelatorUtilityNodes', node=follicle_trans, exists=True):
                    tracked_utilities = cmds.listConnections(
                        f'{follicle_trans}.texelatorUtilityNodes',
                        source=True, destination=False) or []
                parents = cmds.listRelatives(
                    follicle_trans, parent=True, fullPath=True) or []
                if parents and parents[0].split('|')[-1].endswith('_Texture_ctrl_grp'):
                    ctrl_group = parents[0]
            
            # Delete the follicle transform hierarchy (includes ctrl, bind, position_grp etc.)
            if follicle_trans and cmds.objExists(follicle_trans):
                cmds.delete(follicle_trans)
            for node in tracked_utilities:
                if cmds.objExists(node):
                    cmds.delete(node)
            
            # Legacy setups predate message-based utility tracking.
            if not tracked_utilities:
                for suffix in (
                        '_compMat', '_multMat', '_decomMat', '_Translate_Invert',
                        '_Invert_U', '_Invert_V', '_Precision_U', '_Precision_V',
                        '_pos_U_driver', '_pos_V_driver', '_clamp'):
                    node_name = f'{prefix}{suffix}'
                    if cmds.objExists(node_name):
                        try:
                            cmds.delete(node_name)
                        except RuntimeError:
                            pass
            
            if ctrl_group and cmds.objExists(ctrl_group):
                cmds.delete(ctrl_group)
        
        # Clean up the current system group. Legacy groups remain discoverable.
        if cmds.objExists("TexelatorSystem"):
            for grp_name in ["RIG", "UTIL"]:
                children = cmds.listRelatives("TexelatorSystem", children=True, type="transform", fullPath=True) or []
                for child in children:
                    if child.split('|')[-1] == grp_name:
                        grp_children = cmds.listRelatives(child, children=True) or []
                        if not grp_children:
                            cmds.delete(child)
            
            remaining = cmds.listRelatives("TexelatorSystem", children=True) or []
            if not remaining:
                if cmds.attributeQuery("isTexelatorSetup", node="TexelatorSystem", exists=True):
                    cmds.setAttr("TexelatorSystem.isTexelatorSetup", lock=False)
                if cmds.attributeQuery("texelatorVersion", node="TexelatorSystem", exists=True):
                    cmds.setAttr("TexelatorSystem.texelatorVersion", lock=False)
                cmds.delete("TexelatorSystem")

    def _delete_step3_nodes(self):
        """Delete all nodes created by the Core Step 3 build."""
        deleted = set()

        def delete_tracked(value):
            if isinstance(value, dict):
                for item in value.values():
                    delete_tracked(item)
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    delete_tracked(item)
            elif (isinstance(value, str) and '.' not in value and
                  value not in deleted and cmds.objExists(value)):
                try:
                    cmds.delete(value)
                    deleted.add(value)
                except RuntimeError:
                    pass

        for tex_data in self.textures_data.values():
            delete_tracked(tex_data.get('network_details', {}))
            for key in ('file_node', 'projection_node', 'place2d_node'):
                node = tex_data.get(key)
                if node and node not in deleted and cmds.objExists(node):
                    cmds.delete(node)
                    deleted.add(node)

            place3d = tex_data.get('place3d_node')
            if place3d and place3d not in deleted and cmds.objExists(place3d):
                constraints = []
                for constraint_type in ('parentConstraint', 'scaleConstraint'):
                    constraints.extend(
                        cmds.listConnections(place3d, type=constraint_type) or [])
                if constraints:
                    cmds.delete(list(set(constraints)))
                cmds.delete(place3d)
                deleted.add(place3d)
            
    def _restore_material_snapshots(self):
        """Restore material inputs captured immediately before Build Final."""
        layers_by_material = {}
        for tex_data in self.textures_data.values():
            material = tex_data.get('material_node')
            layered = tex_data.get('layered_texture_node')
            if material and layered:
                layers_by_material.setdefault(material, set()).add(layered)
        for snapshot in self.material_snapshots.values():
            step3_logic.restore_material_state(
                snapshot, layers_by_material.get(snapshot.get('material'), set()))
        self.material_snapshots.clear()

    def _clear_texture_runtime_data(self):
        """Keep UI selections but discard Core Step 3 node references."""
        runtime_keys = (
            'file_node', 'projection_node', 'place2d_node', 'place3d_node',
            'layered_texture_node', 'material_node', 'network_details',
            'final_output')
        for tex_data in self.textures_data.values():
            for key in runtime_keys:
                tex_data[key] = None

    def on_delete_locator_click(self, *args):
        selected_items = cmds.textScrollList(self.locator_list_widget, query=True, selectItem=True)
        if not selected_items:
            self.update_step1_status("No locator selected in the list.", success=False)
            return
        
        selected_text = selected_items[0]
        prefix = selected_text.strip()

        if prefix in self.parts_data:
            part = self.parts_data[prefix]
            for node in part.get('utility_nodes', []):
                if cmds.objExists(node): cmds.delete(node)
            for locator in (part.get('original'), part.get('guide')):
                if locator and cmds.objExists(locator): cmds.delete(locator)
            self.locators_data.pop(part.get('original_key'), None)
            self.locators_data.pop(part.get('guide_key'), None)
            self.mirror_pairs.pop(part.get('original_key'), None)
            del self.parts_data[prefix]
            self._update_locator_list_widget()
            self.update_step1_status(f"Deleted part '{prefix}'.", success=True)
            if not self.parts_data:
                cmds.button(self.delete_locator_button, edit=True, enable=False)
            return
        
        if prefix in self.locators_data:
            locator_name = self.locators_data[prefix]
            pair_key = next((key for key, pair in self.mirror_pairs.items()
                             if prefix == key or prefix == pair.get('guide_prefix')), None)
            if pair_key:
                pair = self.mirror_pairs.pop(pair_key)
                for node in pair.get('utility_nodes', []):
                    if cmds.objExists(node): cmds.delete(node)
                for pair_prefix, pair_locator in ((pair_key, pair['original']), (pair.get('guide_prefix'), pair['guide'])):
                    if pair_locator and cmds.objExists(pair_locator): cmds.delete(pair_locator)
                    self.locators_data.pop(pair_prefix, None)
                self._update_locator_list_widget()
                self.update_step1_status(f"Deleted mirror pair for prefix '{pair_key}'.", success=True)
                if not self.locators_data:
                    cmds.button(self.delete_locator_button, edit=True, enable=False)
                    self._unlock_mirror_setup_if_empty()
                return
            if cmds.objExists(locator_name):
                cmds.delete(locator_name)
            del self.locators_data[prefix]
            self._update_locator_list_widget()
            self.update_step1_status(f"Deleted locator for prefix '{prefix}'.", success=True)
            
            if not self.locators_data:
                cmds.button(self.delete_locator_button, edit=True, enable=False)
                self.mirror_settings = None
                self._set_mirror_setup_enabled(True)

    def _update_locator_list_widget(self, select_part=None):
        cmds.textScrollList(self.locator_list_widget, edit=True, removeAll=True)
        part_names = self.parts_data.keys() if self.parts_data else self.locators_data.keys()
        for part_name in part_names:
            cmds.textScrollList(self.locator_list_widget, edit=True, append=part_name)
        if select_part and select_part in self.parts_data:
            cmds.textScrollList(self.locator_list_widget, edit=True, selectItem=select_part)

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

    def _populate_part_control_options(self):
        """Create independent control-shape and colour menus for every part."""
        previous_values = {}
        for part_name, options in self.part_control_options.items():
            previous_values[part_name] = (
                cmds.optionMenu(options['shape_menu'], query=True, value=True),
                cmds.optionMenu(options['color_menu'], query=True, value=True)
            )
        children = cmds.columnLayout(self.part_control_options_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)
        self.part_control_options = {}
        part_names = list(self.parts_data.keys()) or list(self.locators_data.keys())
        for part_name in part_names:
            row = cmds.rowColumnLayout(numberOfColumns=3, columnWidth=[(1, 130), (2, 130), (3, 130)], parent=self.part_control_options_layout)
            cmds.text(label=part_name, align='left')
            shape_menu = cmds.optionMenu()
            for shape_name in step2_logic.CONTROL_SHAPES:
                cmds.menuItem(label=shape_name)
            color_menu = cmds.optionMenu()
            for color_name in step2_logic.CONTROL_COLORS:
                cmds.menuItem(label=color_name)
            if part_name in previous_values:
                cmds.optionMenu(shape_menu, edit=True, value=previous_values[part_name][0])
                cmds.optionMenu(color_menu, edit=True, value=previous_values[part_name][1])
            self.part_control_options[part_name] = {
                'shape_menu': shape_menu, 'color_menu': color_menu,
                'shape_value': 'circle', 'color_value': 'Default'
            }
            cmds.setParent('..')

    def _control_options_for_prefix(self, prefix):
        for part_name, part in self.parts_data.items():
            part_prefixes = [
                value for value in (
                    part.get('original_key'), part.get('guide_key')) if value]
            if any(prefix == value or prefix.startswith(f'{value}_')
                   for value in part_prefixes):
                options = self.part_control_options.get(part_name)
                if options:
                    shape = cmds.optionMenu(options['shape_menu'], query=True, value=True)
                    color = cmds.optionMenu(options['color_menu'], query=True, value=True)
                    options['shape_value'], options['color_value'] = shape, color
                    return shape, color
        return 'circle', 'Default'

    def on_create_follicles_click(self, *args):
        if not self.selected_mesh_shape:
            self.update_step2_status("Mesh not selected from Step 1.", success=False)
            return
        if not self.locators_data:
            self.update_step2_status("No locators created in Step 1.", success=False)
            return

        if not self.part_control_options:
            self._populate_part_control_options()

        cmds.undoInfo(openChunk=True, chunkName="Texelator_CreateFollicles")
        try:
            step1_logic.clear_reference_follicle()

            all_successful = True
            created_count = 0
            self.follicles_data.clear()

            for prefix, locator_name in self.locators_data.items():
                if not cmds.objExists(self.selected_mesh_shape) or not cmds.objExists(locator_name):
                    self.update_step2_status(f"Mesh or locator '{locator_name}' (prefix: '{prefix}') no longer exists.", success=False)
                    all_successful = False
                    continue
                    
                ctrl_shape, ctrl_color = self._control_options_for_prefix(prefix)
                follicle_transform, main_control = step2_logic.run_step2_logic(
                    self.selected_mesh_shape, locator_name, prefix,
                    ctrl_shape=ctrl_shape, ctrl_color=ctrl_color)
                
                if follicle_transform and main_control:
                    step3_logic.organize_scene_hierarchy(
                        self.selected_mesh_transform, follicle_transform, None,
                        prefix, master_group_name=self._ensure_setup_group())
                    self.follicles_data[prefix] = {
                        'follicle': follicle_transform, 
                        'control': main_control,
                        'locator_at_creation': locator_name
                    }
                    created_count += 1
                    if cmds.objExists(locator_name):
                        cmds.setAttr(f"{locator_name}.visibility", 0)
                    for follicle_shape in cmds.listRelatives(follicle_transform, shapes=True, type='follicle') or []:
                        cmds.setAttr(f"{follicle_shape}.visibility", 0)
                else:
                    all_successful = False
                    self.update_step2_status(f"Failed to create follicle for prefix '{prefix}'.", success=False)
        finally:
            cmds.undoInfo(closeChunk=True)

        if not all_successful:
            self._delete_step2_nodes()
            self.follicles_data.clear()
            created_count = 0
            for locator in self.locators_data.values():
                if cmds.objExists(locator):
                    cmds.setAttr(f'{locator}.visibility', 1)

        self._update_locator_list_widget()

        if created_count > 0:
            self._set_setup_stage('controls')
            self.update_step2_status(f"Successfully created {created_count} follicle(s)/control(s).", success=True)
            cmds.button(self.create_follicles_button, edit=True, enable=False)
            cmds.button(self.create_locator_button, edit=True, enable=False)
            cmds.textField(self.name_field, edit=True, enable=False)
            self._set_active_revert_step(2)
            
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
        children = cmds.columnLayout(
            self.texture_selection_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)

        self.texture_path_fields.clear()
        self.select_texture_buttons.clear()
        self.sequence_checkboxes.clear()
        self.projection_checkboxes.clear()
        self.textures_data.clear()
        self.texture_order = []

        if not self.follicles_data:
            cmds.text(
                label="No follicles created. Cannot select textures.",
                parent=self.texture_selection_layout)
            return

        mirrored_aliases = {}
        for part in self.parts_data.values():
            if (part.get('mirrored') and
                    part.get('guide_key') in self.follicles_data):
                mirrored_aliases[part['guide_key']] = part['original_key']

        for prefix in self.follicles_data:
            if prefix in mirrored_aliases:
                continue
            self.texture_order.append(prefix)
            row_layout = cmds.rowColumnLayout(
                numberOfColumns=3,
                columnWidth=[(1, 120), (2, 200), (3, 100)],
                parent=self.texture_selection_layout, rowSpacing=(1, 3))
            cmds.text(label=f"Texture for '{prefix}':", align="right")
            path_field = cmds.textField(
                text="No texture selected", editable=False, width=190)
            select_button = cmds.button(
                label="Select File...",
                command=lambda _ignored, p=prefix:
                    self._on_select_single_texture_click(p))
            cmds.setParent("..")

            checkboxes_row = cmds.rowColumnLayout(
                numberOfColumns=3,
                columnWidth=[(1, 120), (2, 150), (3, 150)],
                parent=self.texture_selection_layout, rowSpacing=(1, 3))
            cmds.text(label="", align="left")
            seq_checkbox = cmds.checkBox(
                label="is sequence?", value=False,
                changeCommand=lambda state, p=prefix:
                    self._on_sequence_checkbox_changed(p, state))
            proj_checkbox = cmds.checkBox(
                label="Projection?", value=True,
                changeCommand=lambda state, p=prefix:
                    self._on_projection_checkbox_changed(p, state))
            cmds.setParent("..")

            self.texture_path_fields[prefix] = path_field
            self.select_texture_buttons[prefix] = select_button
            self.sequence_checkboxes[prefix] = seq_checkbox
            self.projection_checkboxes[prefix] = proj_checkbox
            self.textures_data[prefix] = {
                'file_path': None,
                'file_node': None,
                'projection_node': None,
                'place2d_node': None,
                'place3d_node': None,
                'layered_texture_node': None,
                'material_node': None,
                'network_details': None,
                'final_output': None,
                'is_sequence': False,
                'use_projection': True,
                'settings_owner': prefix
            }

            for target, owner in mirrored_aliases.items():
                if owner != prefix:
                    continue
                self.textures_data[target] = {
                    'file_path': None,
                    'file_node': None,
                    'projection_node': None,
                    'place2d_node': None,
                    'place3d_node': None,
                    'layered_texture_node': None,
                    'material_node': None,
                    'network_details': None,
                    'final_output': None,
                    'is_sequence': False,
                    'use_projection': True,
                    'settings_owner': prefix
                }
                self.texture_order.append(target)

            cmds.separator(
                height=5, style='single', parent=self.texture_selection_layout)

        self._refresh_order_list()

    def _on_sequence_checkbox_changed(self, prefix, state):
        for linked_prefix in self._linked_texture_prefixes(prefix):
            data = self.textures_data[linked_prefix]
            data['is_sequence'] = state
            file_node = data.get('file_node')
            if not file_node or not cmds.objExists(file_node):
                continue
            slide_ctrl = None
            follicle_data = self.follicles_data.get(linked_prefix, {})
            control_name = follicle_data.get('control')
            if control_name:
                if '_Slide_ctrl' in control_name:
                    slide_ctrl = control_name
                else:
                    for child in cmds.listRelatives(
                            control_name, allDescendents=True,
                            type='transform') or []:
                        if '_Slide_ctrl' in child:
                            slide_ctrl = child
                            break
            if slide_ctrl:
                step3_logic.setup_sequence_texture(
                    file_node, slide_ctrl, state)
        self.update_step3_status(
            f"Sequence mode {'enabled' if state else 'disabled'} "
            f"for '{prefix}'.", success=True)

    def _on_projection_checkbox_changed(self, prefix, state):
        """
        Handle projection checkbox state changes.
        
        Args:
            prefix (str): Prefix of the texture
            state (bool): New state of the checkbox
        """
        for linked_prefix in self._linked_texture_prefixes(prefix):
            self.textures_data[linked_prefix]['use_projection'] = state


    def _on_select_single_texture_click(self, prefix):
        file_paths = cmds.fileDialog2(fileMode=1, caption=f"Select Texture for Prefix: {prefix}")
        if file_paths and file_paths[0]:
            selected_file = file_paths[0]
            for linked_prefix in self._linked_texture_prefixes(prefix):
                self.textures_data[linked_prefix]['file_path'] = selected_file
            cmds.textField(self.texture_path_fields[prefix], edit=True, text=selected_file)
            self.update_step3_status(f"Texture for '{prefix}' selected. Ready to connect all.", success=True)
        else:
            self.update_step3_status(f"Texture selection cancelled for '{prefix}'.", success=False)

    def _linked_texture_prefixes(self, prefix):
        """Return the independently-built prefixes controlled by one texture row."""
        if prefix not in self.textures_data:
            return []
        owner = self.textures_data[prefix].get('settings_owner', prefix)
        return [key for key, data in self.textures_data.items()
                if data.get('settings_owner', key) == owner]


    def _ensure_uv_refs_group(self):
        """Return Texelator_<mesh>/RIG/UV_Refs, creating missing groups."""
        setup_group = self._ensure_setup_group()
        rig_group = None
        for child in cmds.listRelatives(setup_group, children=True, type='transform', fullPath=True) or []:
            if child.split('|')[-1] == 'RIG':
                rig_group = child
                break
        if not rig_group:
            rig_group = cmds.group(empty=True, name='RIG', parent=setup_group)
        for child in cmds.listRelatives(rig_group, children=True, type='transform', fullPath=True) or []:
            if child.split('|')[-1] == 'UV_Refs':
                return child
        return cmds.group(empty=True, name='UV_Refs', parent=rig_group)

    def _parent_uv_ref(self, uv_ref):
        if uv_ref and cmds.objExists(uv_ref):
            try: cmds.parent(uv_ref, self._ensure_uv_refs_group())
            except RuntimeError: pass


    def _is_mirror_texture_target(self, prefix):
        """True for the generated guide side of a mirrored part."""
        return any(
            part.get('mirrored') and part.get('guide_key') and
            (prefix == part['guide_key'] or
             prefix.startswith(f"{part['guide_key']}_"))
            for part in self.parts_data.values())

    def _apply_texture_mirror(self, prefix, place2d_node):
        """Flip the guide-side image horizontally while retaining one shared source file."""
        if not self._is_mirror_texture_target(prefix):
            return
        if not place2d_node or not cmds.objExists(place2d_node):
            return
        for attribute, value in (('repeatU', -1.0), ('offsetU', 1.0)):
            if cmds.attributeQuery(attribute, node=place2d_node, exists=True):
                cmds.setAttr(f'{place2d_node}.{attribute}', value)


    def _reorder_built_main_layers(self):
        """Apply the visible top-first order to the material layer inputs."""
        ordered_sources = []
        layered = None
        for prefix in self.texture_order:
            data = self.textures_data.get(prefix)
            if not data:
                continue
            layered = layered or data.get('layered_texture_node')
            output = data.get('final_output')
            if output:
                ordered_sources.append(output)
        if not layered or not ordered_sources:
            return False
        return step3_logic.reorder_managed_layer_sources(
            layered, ordered_sources)

    def on_connect_all_textures_click(self, *args):
        """Build all selected Main textures in the requested layer order."""
        if not self.selected_mesh_transform:
            cmds.warning(
                "No mesh selected or initial locator created. "
                "Please complete Step 1.")
            return
        if not self.textures_data:
            cmds.warning(
                "No textures selected or controls available for texture "
                "connection.")
            return

        self.material_snapshots.clear()
        snapshot = step3_logic.capture_material_state(
            self.selected_mesh_transform)
        if snapshot:
            self.material_snapshots[snapshot['color_attr']] = snapshot

        cmds.undoInfo(openChunk=True, chunkName="Texelator_ConnectTextures")
        try:
            all_successful = True
            ordered_prefixes = [
                prefix for prefix in self.texture_order
                if prefix in self.textures_data]
            ordered_prefixes.extend(
                prefix for prefix in self.textures_data
                if prefix not in ordered_prefixes)

            for prefix in ordered_prefixes:
                tex_data = self.textures_data[prefix]
                texture_path = tex_data.get('file_path')
                if not texture_path or texture_path == "No texture selected":
                    cmds.warning(
                        f"No texture file selected for prefix '{prefix}'.")
                    all_successful = False
                    continue

                follicle_info = self.follicles_data.get(prefix)
                follicle = follicle_info.get('follicle') if follicle_info else None
                if not follicle:
                    cmds.warning(
                        f"Follicle data not found for prefix '{prefix}'.")
                    all_successful = False
                    continue

                is_sequence = tex_data.get('is_sequence', False)
                use_projection = tex_data.get('use_projection', True)
                runner = (
                    step3_logic.run_step3_logic if use_projection
                    else step3_uv_logic.run_step3_uv_logic)
                result = runner(
                    mesh_transform=self.selected_mesh_transform,
                    image_file_path=texture_path,
                    name_prefix=prefix,
                    follicle_transform=follicle,
                    is_sequence=is_sequence,
                    master_group_name=self._ensure_setup_group())
                (file_node, projection_node, place2d_node, place3d_node,
                 layered_node, material_node, updated_mesh,
                 network_details) = result

                if not file_node:
                    cmds.warning(
                        f"Texture connection failed for prefix '{prefix}'.")
                    all_successful = False
                    continue

                final_output = {
                    'color': (
                        f'{projection_node}.outColor' if projection_node
                        else f'{file_node}.outColor'),
                    'alpha': (
                        f'{projection_node}.outAlpha' if projection_node
                        else f'{file_node}.outAlpha')
                }
                tex_data.update({
                    'file_node': file_node,
                    'projection_node': projection_node,
                    'place2d_node': place2d_node,
                    'place3d_node': place3d_node,
                    'layered_texture_node': layered_node,
                    'material_node': material_node,
                    'network_details': network_details,
                    'final_output': final_output
                })
                self._apply_texture_mirror(prefix, place2d_node)
                self.selected_mesh_transform = updated_mesh
                if not use_projection:
                    uv_setup = (network_details or {}).get('uv_setup') or {}
                    self._parent_uv_ref(uv_setup.get('uv_ref'))

            if all_successful:
                all_successful = self._reorder_built_main_layers()

            if all_successful:
                self._set_setup_stage('final')
                cmds.headsUpMessage(
                    "All selected textures connected and scene organized.",
                    time=5.0)
                self._enable_layer_ordering()
                self._set_active_revert_step(3)
                cmds.button(
                    self.connect_all_textures_button, edit=True, enable=False)
                self.update_step3_status(
                    "Final texture network built.", success=True)
            else:
                self._delete_step3_nodes()
                self._restore_material_snapshots()
                self._clear_texture_runtime_data()
                cmds.warning(
                    "Some textures could not be connected. "
                    "Check the Script Editor.")
        except Exception as error:
            self._delete_step3_nodes()
            self._restore_material_snapshots()
            self._clear_texture_runtime_data()
            cmds.warning(f"Build Final was rolled back: {error}")
        finally:
            cmds.undoInfo(closeChunk=True)

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
        self.texture_order = []
        cmds.treeView(self.order_list_widget, edit=True, removeAll=True)
        self.layer_tree_items.clear()
        self.layer_tree_labels.clear()
        self.layer_tree_selected = None
        self._update_layer_order_controls()

        # Reset layer ordering
        cmds.frameLayout(self.layer_frame, edit=True, enable=False, collapse=True)
        cmds.textScrollList(self.layer_list_widget, edit=True, removeAll=True)
        self.layer_texture_node = None

    def reset_tool_state(self):
        self.selected_mesh_transform = None
        self.selected_mesh_shape = None
        self.setup_group = None
        self.material_snapshots.clear()
        
        self.locators_data.clear()
        self.parts_data.clear()
        self._update_locator_list_widget()
        self._populate_part_control_options()
        self.mirror_settings = None
        self.mirror_pairs.clear()
        self._set_mirror_setup_enabled(True)
        
        self.reset_step2_and_beyond()

        cmds.button(self.select_mesh_button, edit=True, enable=True)
        cmds.button(self.create_locator_button, edit=True, enable=False)
        cmds.button(self.delete_locator_button, edit=True, enable=False)
        
        default_prefix = "Prefix"
        self.name_prefix = default_prefix
        cmds.textField(self.name_field, edit=True, text=default_prefix, enable=True)
        
        self.update_step1_status("Waiting for mesh selection...")
        step1_logic.clear_reference_follicle()

    def on_select_mesh_click(self, *args):
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

        # Start an independent in-memory session. Existing scene setups remain
        # untouched and can still be loaded through Edit Existing Setup.
        step1_logic.clear_reference_follicle()
        self.locators_data.clear()
        self.parts_data.clear()
        self.mirror_pairs.clear()
        self.mirror_settings = None
        self.setup_group = None
        self.material_snapshots.clear()
        self._update_locator_list_widget()
        self._populate_part_control_options()
        self.reset_step2_and_beyond()
        
        self.selected_mesh_transform = mesh_transform
        self.selected_mesh_shape = mesh_shape
        
        cmds.undoInfo(openChunk=True, chunkName="Texelator_SelectMesh")
        try:
            follicle_transform, follicle_shape, null_group = step1_logic.create_reference_follicle(
                mesh_transform, mesh_shape)
            
            if follicle_transform and null_group:
                cmds.parent(follicle_transform, self._ensure_setup_group())
                self.update_step1_status(f"Mesh '{mesh_transform}' selected and reference follicle created.", success=True)
                cmds.button(self.create_locator_button, edit=True, enable=True)
                self._set_active_revert_step()
            else:
                self.update_step1_status("Failed to create reference follicle.", success=False)
        finally:
            cmds.undoInfo(closeChunk=True)
    
    def on_create_locator_click(self, *args):
        if not self.selected_mesh_transform or not self.selected_mesh_shape:
            self.update_step1_status("No mesh selected. Please select a mesh first.", success=False)
            return

        current_prefix = cmds.textField(self.name_field, query=True, text=True)
        self.name_prefix = current_prefix
        
        if not current_prefix or current_prefix.isspace():
            self.update_step1_status("Prefix cannot be empty.", success=False)
            return
        if current_prefix in self.parts_data:
            self.update_step1_status(f"Part '{current_prefix}' already exists.", success=False)
            return

        # Capture and lock the mirror setup before the first locator is created.
        if not self.locators_data:
            self._capture_mirror_settings()
        is_mirror = self.mirror_settings['enabled'] if self.mirror_settings else False
        
        if is_mirror:
            # Get side selection to apply prefix, but only create ONE locator
            original_side = self.mirror_settings['original_side']
            
            original_prefix = f"{original_side}_{current_prefix}"
            
            if not self._is_prefix_unique(original_prefix):
                self.update_step1_status(f"Prefix '{original_prefix}' already exists.", success=False)
                self._unlock_mirror_setup_if_empty()
                return
            
            cmds.undoInfo(openChunk=True, chunkName="Texelator_CreateLocator")
            try:
                # Create only the original side locator; mirror will be generated in Step 2
                locator = step1_logic.create_locator_at_null_position(original_prefix)
                if not locator:
                    self.update_step1_status(f"Failed to create locator with prefix '{original_prefix}'.", success=False)
                    self._unlock_mirror_setup_if_empty()
                    return
                
                self.locators_data[original_prefix] = locator
                cmds.parent(locator, self._ensure_setup_group())
                mirror_side = 'R' if original_side == 'L' else 'L'
                mirror_prefix = f"{mirror_side}_{current_prefix}"
                mirror_locator = step1_logic.create_mirrored_locator(locator, self.selected_mesh_transform, self.mirror_settings['axis'], mirror_prefix)
                if not mirror_locator:
                    cmds.delete(locator)
                    del self.locators_data[original_prefix]
                    self._unlock_mirror_setup_if_empty()
                    self.update_step1_status("Could not create the mirror guide.", success=False)
                    return
                utility_nodes = step1_logic.connect_mirror_guide(locator, mirror_locator, self.selected_mesh_transform, self.mirror_settings['axis'], original_prefix)
                self.locators_data[mirror_prefix] = mirror_locator
                cmds.parent(mirror_locator, self._ensure_setup_group())
                self.mirror_pairs[original_prefix] = {
                    'original_prefix': original_prefix, 'original': locator,
                    'guide_prefix': mirror_prefix, 'guide': mirror_locator,
                    'utility_nodes': utility_nodes
                }
                self.parts_data[current_prefix] = {
                    'mirrored': True, 'axis': self.mirror_settings['axis'], 'original_side': original_side,
                    'original': locator, 'original_key': original_prefix,
                    'guide': mirror_locator, 'guide_key': mirror_prefix, 'utility_nodes': utility_nodes
                }
                self._update_locator_list_widget(select_part=current_prefix)
                self.update_step1_status(f"Added '{locator}' and locked guide '{mirror_locator}'. Move only the original locator.", success=True)
                cmds.button(self.delete_locator_button, edit=True, enable=True)
                self._set_active_revert_step(1)
            finally:
                cmds.undoInfo(closeChunk=True)
        else:
            # Non-mirror mode (original behavior)
            if not self._is_prefix_unique(current_prefix):
                self.update_step1_status(f"Prefix '{current_prefix}' already exists.", success=False)
                self._unlock_mirror_setup_if_empty()
                return
            
            cmds.undoInfo(openChunk=True, chunkName="Texelator_CreateLocator")
            try:
                locator = step1_logic.create_locator_at_null_position(current_prefix)
                
                if locator:
                    self.locators_data[current_prefix] = locator
                    cmds.parent(locator, self._ensure_setup_group())
                    self.parts_data[current_prefix] = {
                        'mirrored': False, 'axis': self.mirror_settings['axis'] if self.mirror_settings else 'X',
                        'original_side': self.mirror_settings['original_side'] if self.mirror_settings else 'L',
                        'original': locator, 'original_key': current_prefix,
                        'guide': None, 'guide_key': None, 'utility_nodes': []
                    }
                    self._update_locator_list_widget(select_part=current_prefix)
                    self.update_step1_status(f"Added locator '{locator}'.", success=True)
                    cmds.button(self.delete_locator_button, edit=True, enable=True)
                    self._set_active_revert_step(1)
                else:
                    self.update_step1_status(f"Failed to add locator with prefix '{current_prefix}'.", success=False)
                    self._unlock_mirror_setup_if_empty()
                    return
            finally:
                cmds.undoInfo(closeChunk=True)
        
        # Auto-increment prefix
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
        self._set_setup_stage('guides')
        self._populate_part_control_options()
        self.update_step2_status("Move locators. Create more or proceed to create follicles.")

    # --- Pre-connect Ordering Methods ---

    @staticmethod
    def _tree_safe_id(value):
        return re.sub(r'[^A-Za-z0-9_]+', '_', str(value))

    def _on_layer_tree_selection(self, *args):
        """Keep logical selection while replacing Maya's native blue row."""
        if self._clearing_layer_tree_native_selection:
            return
        if not args:
            return
        item = args[0]
        selected = bool(args[1]) if len(args) > 1 else True
        # Clearing the native highlight emits a deselect event in some Maya
        # versions. Keep the logical selection for the reorder buttons.
        if not selected or item not in self.layer_tree_items:
            return
        previous = self.layer_tree_selected
        if previous and previous != item:
            self._set_layer_tree_selection_marker(previous, False)
        self.layer_tree_selected = item
        self._set_layer_tree_selection_marker(item, True)
        self._clearing_layer_tree_native_selection = True
        try:
            cmds.treeView(
                self.order_list_widget, edit=True,
                selectItem=(item, False))
        finally:
            self._clearing_layer_tree_native_selection = False
        self._update_layer_order_controls()

    def _set_layer_tree_selection_marker(self, item, selected):
        """Place the marker after the flat row's hierarchy indentation."""
        base_label = self.layer_tree_labels.get(item)
        descriptor = self.layer_tree_items.get(item)
        if not base_label or not descriptor or not self.order_list_widget:
            return
        indent_width = max(0, int(descriptor.get('indent', 0))) * 4
        display_label = base_label
        if selected:
            display_label = (
                base_label[:indent_width] + '\u25B6 ' +
                base_label[indent_width:])
        try:
            cmds.treeView(
                self.order_list_widget, edit=True,
                displayLabel=(item, display_label))
            color = self.color_accent if selected else self.color_secondary
            cmds.treeView(
                self.order_list_widget, edit=True,
                textColor=(item, color[0], color[1], color[2]))
        except RuntimeError:
            pass

    def _main_root_order(self):
        """Return visible main layers, preserving the saved global order."""
        roots = [item for item in self.texture_order if item in self.textures_data]
        roots.extend(prefix for prefix in self.textures_data if prefix not in roots)
        return roots


    def _normalize_texture_order(self, root_order=None):
        """Keep the global order limited to valid Main texture prefixes."""
        self.texture_order = list(root_order or self._main_root_order())


    def _add_layer_tree_item(self, item_id, label, descriptor):
        indent = max(0, int(descriptor.get('indent', 0)))
        # Non-breaking spaces survive Maya/Qt label trimming while every item
        # remains a root-level row in the flat ordering model.
        display_label = ('\u00A0' * (indent * 4)) + label
        cmds.treeView(
            self.order_list_widget, edit=True,
            addItem=(item_id, ''))
        cmds.treeView(
            self.order_list_widget, edit=True,
            displayLabel=(item_id, display_label))
        try:
            cmds.treeView(
                self.order_list_widget, edit=True,
                textColor=(
                    item_id, self.color_secondary[0],
                    self.color_secondary[1], self.color_secondary[2]))
        except RuntimeError:
            pass
        self.layer_tree_items[item_id] = descriptor
        self.layer_tree_labels[item_id] = display_label


    def _refresh_order_list(self, select_item=None):
        """Rebuild the pre-build Main layer ordering tree."""
        if not self.order_list_widget:
            return
        selected = select_item or self.layer_tree_selected
        root_order = self._main_root_order()
        self._normalize_texture_order(root_order)
        cmds.treeView(self.order_list_widget, edit=True, removeAll=True)
        self.layer_tree_items = {}
        self.layer_tree_labels = {}

        for prefix in root_order:
            item_id = 'main_{}'.format(self._tree_safe_id(prefix))
            self._add_layer_tree_item(
                item_id, '[MAIN] {}'.format(prefix),
                {'kind': 'main', 'prefix': prefix, 'indent': 0})

        if selected in self.layer_tree_items:
            self.layer_tree_selected = selected
            self._set_layer_tree_selection_marker(selected, True)
        else:
            self.layer_tree_selected = None
        self._update_layer_order_controls()

    def _can_move_layer_tree_item(self, direction):
        descriptor = self.layer_tree_items.get(self.layer_tree_selected)
        if not descriptor or descriptor.get('kind') != 'main':
            return False
        roots = self._main_root_order()
        prefix = descriptor.get('prefix')
        if prefix not in roots:
            return False
        target = roots.index(prefix) + direction
        return 0 <= target < len(roots)


    def _update_layer_order_controls(self):
        """Update Main layer move availability and selection guidance."""
        if self.order_up_button:
            cmds.button(
                self.order_up_button, edit=True,
                enable=self._can_move_layer_tree_item(-1))
        if self.order_down_button:
            cmds.button(
                self.order_down_button, edit=True,
                enable=self._can_move_layer_tree_item(1))
        if self.layer_order_warning_label:
            label = (
                'Move the selected Main texture in the final layer order.'
                if self.layer_tree_selected else
                'Select a Main texture to change its layer order.')
            cmds.text(
                self.layer_order_warning_label, edit=True, label=label)


    def _move_layer_tree_item(self, direction):
        selected = self.layer_tree_selected
        descriptor = self.layer_tree_items.get(selected)
        if not descriptor or descriptor.get('kind') != 'main':
            return
        roots = self._main_root_order()
        prefix = descriptor.get('prefix')
        if prefix not in roots:
            return
        source = roots.index(prefix)
        target = source + direction
        if target < 0 or target >= len(roots):
            self._update_layer_order_controls()
            return
        roots[source], roots[target] = roots[target], roots[source]
        self.texture_order = roots
        self._refresh_order_list(select_item=selected)
        self._save_setup_metadata()

    def _on_order_move_up(self, *args):
        self._move_layer_tree_item(-1)

    def _on_order_move_down(self, *args):
        self._move_layer_tree_item(1)

    # --- Post-connect Layer Ordering Methods ---

    def _enable_layer_ordering(self):
        """Finds layeredTexture nodes from connected textures and populates the layer list."""
        # Collect unique layeredTexture nodes
        lt_nodes = set()
        for prefix, tex_data in self.textures_data.items():
            lt = tex_data.get('layered_texture_node') or tex_data.get('layered_texture')
            if lt and cmds.objExists(lt):
                lt_nodes.add(lt)
        
        if lt_nodes:
            self.layer_texture_node = list(lt_nodes)[0]  # Use first found
            cmds.frameLayout(self.layer_frame, edit=True, enable=True, collapse=False)
            self._refresh_layer_list()

    def _refresh_layer_list(self):
        """Refreshes the layer list widget from the current layeredTexture node."""
        cmds.textScrollList(self.layer_list_widget, edit=True, removeAll=True)
        if not self.layer_texture_node or not cmds.objExists(self.layer_texture_node):
            return
        
        layers = step3_logic.get_layer_info(self.layer_texture_node)
        for layer in layers:
            label = f"[{layer['index']}] {layer['display_name']}"
            cmds.textScrollList(self.layer_list_widget, edit=True, append=label)

    def _on_layer_move_up(self, *args):
        selected = cmds.textScrollList(self.layer_list_widget, query=True, selectIndexedItem=True)
        if not selected or selected[0] <= 1:
            return
        ui_idx = selected[0]
        layers = step3_logic.get_layer_info(self.layer_texture_node)
        if ui_idx > len(layers) or ui_idx < 2:
            return
        idx_a = layers[ui_idx - 1]['index']
        idx_b = layers[ui_idx - 2]['index']
        step3_logic.swap_layers(self.layer_texture_node, idx_a, idx_b)
        self._refresh_layer_list()
        cmds.textScrollList(self.layer_list_widget, edit=True, selectIndexedItem=[ui_idx - 1])

    def _on_layer_move_down(self, *args):
        selected = cmds.textScrollList(self.layer_list_widget, query=True, selectIndexedItem=True)
        if not selected:
            return
        ui_idx = selected[0]
        layers = step3_logic.get_layer_info(self.layer_texture_node)
        if ui_idx >= len(layers):
            return
        idx_a = layers[ui_idx - 1]['index']
        idx_b = layers[ui_idx]['index']
        step3_logic.swap_layers(self.layer_texture_node, idx_a, idx_b)
        self._refresh_layer_list()
        cmds.textScrollList(self.layer_list_widget, edit=True, selectIndexedItem=[ui_idx + 1])

    # --- Existing Setup Edit Methods ---

    def _on_scan_setups_click(self, *args):
        """Scans the scene for existing Texelator setups."""
        self.found_setups = step3_logic.scan_existing_setups()
        
        # Clear and repopulate the menu
        menu_items = cmds.optionMenu(self.edit_setup_menu, query=True, itemListLong=True) or []
        for item in menu_items:
            cmds.deleteUI(item)
        
        if not self.found_setups:
            cmds.menuItem(label="(none found)", parent=self.edit_setup_menu)
            self.update_step1_status("No existing Texelator setups found in scene.", success=False)
        else:
            for setup in self.found_setups:
                mesh_name = setup['mesh'] or '(unknown mesh)'
                prefixes = ', '.join(setup['prefixes']) if setup['prefixes'] else '(no prefixes)'
                label = f"{setup['master_group']} | {mesh_name} | {setup.get('stage', 'final')} | [{prefixes}]"
                cmds.menuItem(label=label, parent=self.edit_setup_menu)
            self.update_step1_status(f"Found {len(self.found_setups)} existing setup(s).", success=True)

    def _on_load_setup_click(self, *args):
        """Loads a selected existing setup for editing - populates tool state from scene."""
        if not self.found_setups:
            self.update_step1_status("No setups to load. Scan first.", success=False)
            return
        
        selected_idx = cmds.optionMenu(self.edit_setup_menu, query=True, select=True) - 1
        if selected_idx < 0 or selected_idx >= len(self.found_setups):
            self.update_step1_status("Invalid setup selection.", success=False)
            return
        
        setup = self.found_setups[selected_idx]
        master_grp = setup['master_group']
        mesh = setup['mesh']
        prefixes = setup['prefixes']
        metadata = setup.get('metadata') or {}
        
        if not mesh or not cmds.objExists(mesh):
            self.update_step1_status("Could not find mesh for this setup.", success=False)
            return
        
        # Reset current state
        self.reset_tool_state()
        
        # Set mesh
        self.selected_mesh_transform = mesh
        self.setup_group = master_grp
        shapes = cmds.listRelatives(mesh, shapes=True, type="mesh") or []
        if shapes:
            self.selected_mesh_shape = shapes[0]
        self._restore_parts_from_metadata(master_grp, metadata)

        # Resume a paused guide-stage setup without requiring a new mesh selection.
        if setup.get('stage') == 'guides':
            guide_nodes = cmds.listRelatives(master_grp, allDescendents=True, type='transform', fullPath=True) or []
            for node in guide_nodes:
                short_name = node.split('|')[-1]
                if not short_name.endswith('_locator'):
                    continue
                key = short_name[:-len('_locator')]
                self.locators_data[key] = node
            for key, locator in list(self.locators_data.items()):
                if self.parts_data:
                    break
                base_name = key[2:] if key.startswith(('L_', 'R_')) else key
                if base_name in self.parts_data:
                    continue
                left_key, right_key = f'L_{base_name}', f'R_{base_name}'
                if left_key in self.locators_data and right_key in self.locators_data:
                    original_key = left_key
                    original_side = 'L'
                    # The driven guide has an incoming translate connection.
                    if cmds.listConnections(f'{self.locators_data[left_key]}.translateX', source=True, destination=False):
                        original_key, original_side = right_key, 'R'
                    guide_key = right_key if original_key == left_key else left_key
                    self.parts_data[base_name] = {'mirrored': True, 'axis': 'X', 'original_side': original_side,
                        'original': self.locators_data[original_key], 'original_key': original_key,
                        'guide': self.locators_data[guide_key], 'guide_key': guide_key, 'utility_nodes': []}
                elif key == base_name:
                    self.parts_data[base_name] = {'mirrored': False, 'axis': 'X', 'original_side': 'L',
                        'original': locator, 'original_key': key, 'guide': None, 'guide_key': None, 'utility_nodes': []}
            self._update_locator_list_widget()
            self._populate_part_control_options()
            self._restore_control_options_from_metadata(metadata)
            cmds.button(self.select_mesh_button, edit=True, enable=False)
            cmds.button(self.create_locator_button, edit=True, enable=True)
            cmds.button(self.create_follicles_button, edit=True, enable=True)
            cmds.frameLayout(self.step2_frame, edit=True, enable=True)
            self._set_active_revert_step(1)
            self.update_step1_status(f"Resumed guide setup: {master_grp}", success=True)
            return
        
        # Populate follicles_data from the RIG hierarchy
        self.follicles_data.clear()
        main_prefixes = set()
        for part in self.parts_data.values():
            main_prefixes.add(part.get('original_key'))
            if part.get('guide_key'):
                main_prefixes.add(part['guide_key'])
        main_prefixes.discard(None)
        node_children = cmds.listRelatives(master_grp, children=True, type="transform", fullPath=True) or []
        for child in node_children:
            if child.split('|')[-1] == "RIG":
                rig_children = cmds.listRelatives(child, children=True, type="transform", fullPath=True) or []
                for rc in rig_children:
                    rc_short = rc.split('|')[-1]
                    if rc_short.endswith("_Texture_ctrl_grp"):
                        prefix = rc_short.replace("_Texture_ctrl_grp", "")
                        if main_prefixes and prefix not in main_prefixes:
                            continue
                        # Find follicle and control under this group
                        grp_children = cmds.listRelatives(rc, children=True, type="transform", fullPath=True) or []
                        follicle_trans = None
                        control = None
                        for gc in grp_children:
                            gc_short = gc.split('|')[-1]
                            # Check if it's a follicle
                            fol_shapes = cmds.listRelatives(gc, shapes=True, type="follicle") or []
                            if fol_shapes:
                                follicle_trans = gc
                                # Find control under follicle
                                fol_descendants = cmds.listRelatives(gc, allDescendents=True, type="transform") or []
                                for fd in fol_descendants:
                                    if "_Slide_ctrl" in fd:
                                        control = fd
                                        break
                        
                        if follicle_trans:
                            self.follicles_data[prefix] = {
                                'follicle': follicle_trans,
                                'control': control,
                                'locator_at_creation': None
                            }
                break
        
        # Update UI to reflect loaded state
        self._populate_part_control_options()
        self._restore_control_options_from_metadata(metadata)
        cmds.button(self.select_mesh_button, edit=True, enable=False)
        cmds.button(self.create_locator_button, edit=True, enable=False)
        self.update_step1_status(f"Loaded setup: {master_grp} | Mesh: {mesh}", success=True)
        
        # Enable Step 2 (disabled since follicles already exist)
        cmds.frameLayout(self.step2_frame, edit=True, enable=True)
        cmds.button(self.create_follicles_button, edit=True, enable=False)
        self.update_step2_status(f"Loaded {len(self.follicles_data)} existing follicle(s).", success=True)
        
        # Enable Step 3 for adding new textures
        if self.follicles_data:
            self._populate_texture_selection_ui()
            self._restore_texture_ui_from_metadata(metadata)
            cmds.frameLayout(self.step3_frame, edit=True, enable=True)
            cmds.button(self.connect_all_textures_button, edit=True, enable=True)
            self.update_step3_status(f"Select new textures for {len(self.follicles_data)} prefix(es).")
        
        # Enable layer ordering if layeredTexture exists on the mesh material
        self._enable_layer_ordering_from_mesh(mesh)
        
        # Select the master group
        if cmds.objExists(master_grp):
            cmds.select(master_grp, replace=True)
        

    def _restore_parts_from_metadata(self, master_group, metadata):
        """Restore Parts/mirror identity without guessing from L/R names."""
        saved_parts = metadata.get('parts') or {}
        if not saved_parts:
            return
        locators = {}
        for node in cmds.listRelatives(
                master_group, allDescendents=True, type='transform', fullPath=True) or []:
            short = node.split('|')[-1]
            if short.endswith('_locator'):
                locators[short[:-len('_locator')]] = node
        self.locators_data.update(locators)
        for part_name, saved in saved_parts.items():
            original_key = saved.get('original_key') or part_name
            guide_key = saved.get('guide_key')
            guide = locators.get(guide_key)
            utility_nodes = []
            if guide:
                connected = cmds.listConnections(
                    guide, source=True, destination=False) or []
                for node in connected:
                    if cmds.objectType(node) in (
                            'multiplyDivide', 'addDoubleLinear', 'multDoubleLinear',
                            'addDL', 'multDL'):
                        utility_nodes.append(node)
                        utility_nodes.extend(
                            upstream for upstream in (cmds.listConnections(
                                node, source=True, destination=False) or [])
                            if cmds.objectType(upstream) in (
                                'multiplyDivide', 'addDoubleLinear',
                                'multDoubleLinear', 'addDL', 'multDL'))
            self.parts_data[part_name] = {
                'mirrored': bool(saved.get('mirrored')),
                'axis': saved.get('axis', 'X'),
                'original_side': saved.get('original_side', 'L'),
                'original': locators.get(original_key),
                'original_key': original_key,
                'guide': guide,
                'guide_key': guide_key,
                'utility_nodes': list(set(utility_nodes))
            }
            if saved.get('mirrored') and locators.get(original_key) and guide:
                self.mirror_pairs[original_key] = {
                    'original_prefix': original_key,
                    'original': locators[original_key],
                    'guide_prefix': guide_key,
                    'guide': guide,
                    'utility_nodes': list(set(utility_nodes))
                }

    def _restore_control_options_from_metadata(self, metadata):
        for part_name, saved in (metadata.get('controls') or {}).items():
            options = self.part_control_options.get(part_name)
            if not options:
                continue
            shape = saved.get('shape', 'circle')
            color = saved.get('color', 'Default')
            cmds.optionMenu(options['shape_menu'], edit=True, value=shape)
            cmds.optionMenu(options['color_menu'], edit=True, value=color)
            options['shape_value'], options['color_value'] = shape, color


    def _restore_texture_ui_from_metadata(self, metadata):
        """Restore Core Main texture choices and shared L/R settings."""
        for prefix, saved in (metadata.get('textures') or {}).items():
            if prefix not in self.textures_data:
                continue
            for linked in self._linked_texture_prefixes(prefix):
                data = self.textures_data[linked]
                data['file_path'] = saved.get('file_path')
                data['is_sequence'] = bool(saved.get('is_sequence'))
                data['use_projection'] = bool(
                    saved.get('use_projection', True))
            if prefix in self.texture_path_fields and saved.get('file_path'):
                cmds.textField(
                    self.texture_path_fields[prefix], edit=True,
                    text=saved['file_path'])
            if prefix in self.sequence_checkboxes:
                cmds.checkBox(
                    self.sequence_checkboxes[prefix], edit=True,
                    value=bool(saved.get('is_sequence')))
            if prefix in self.projection_checkboxes:
                cmds.checkBox(
                    self.projection_checkboxes[prefix], edit=True,
                    value=bool(saved.get('use_projection', True)))

        saved_order = metadata.get('texture_order') or []
        if saved_order:
            available = list(self.textures_data)
            self.texture_order = [
                prefix for prefix in saved_order if prefix in self.textures_data]
            self.texture_order.extend(
                prefix for prefix in available
                if prefix not in self.texture_order)
            self._refresh_order_list()

    def _enable_layer_ordering_from_mesh(self, mesh_transform):
        """Finds layeredTexture nodes connected to the mesh's material and enables the layer panel."""
        if not mesh_transform or not cmds.objExists(mesh_transform):
            return
        
        shapes = cmds.listRelatives(mesh_transform, shapes=True, type="mesh") or []
        if not shapes:
            return
        
        # Find shading groups
        sgs = cmds.listConnections(shapes[0], type="shadingEngine") or []
        for sg in sgs:
            # Find materials
            materials = cmds.listConnections(f"{sg}.surfaceShader", source=True, destination=False) or []
            for mat in materials:
                # Find layeredTexture connected to the material
                lt_nodes = cmds.listConnections(mat, type="layeredTexture", source=True, destination=False) or []
                if lt_nodes:
                    self.layer_texture_node = lt_nodes[0]
                    cmds.frameLayout(self.layer_frame, edit=True, enable=True, collapse=False)
                    self._refresh_layer_list()
                    return


def show_ui():
    tool_ui = TexelatorUI()
    tool_ui.create_ui()
    return tool_ui

if __name__ == "__main__":
    ui_instance = show_ui()

