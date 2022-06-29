import logging

import xmltodict
from numpy import isin
from PythonQt import QtGui
from PythonQt.QtCore import Qt
from qt import QAbstractItemView, QItemSelectionModel, QMenu

from .fw_container_items import (
    AnalysisFolderItem,
    AnalysisItem,
    CollectionItem,
    ContainerItem,
    FileItem,
    GroupItem,
    ProjectItem,
)
from .slicer_constants import PAIRED_FILE_TYPES

log = logging.getLogger(__name__)


class TreeManagement:
    """
    Class that coordinates all tree-related functionality.
    """

    def __init__(self, main_window):
        """
        Initialize treeView object from Main Window.

        Args:
            main_window (QtWidgets.QMainWindow): [description]
        """
        self.main_window = main_window
        self.treeView = self.main_window.treeView
        self.cache_files = {}
        tree = self.treeView
        # https://doc.qt.io/archives/qt-4.8/qabstractitemview.html
        tree.selectionMode = QAbstractItemView.ExtendedSelection
        tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tree.clicked.connect(self.tree_clicked)
        tree.doubleClicked.connect(self.tree_dblclicked)
        tree.expanded.connect(self.on_expanded)

        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.open_menu)
        self.source_model = QtGui.QStandardItemModel()
        tree.setModel(self.source_model)
        self.selection_model = QItemSelectionModel(self.source_model)
        tree.setSelectionModel(self.selection_model)
        tree.selectionModel().selectionChanged.connect(self.on_selection_changed)

    def tree_clicked(self, index):
        """
        Cascade the tree clicked event to relevant tree node items.

        Args:
            index (QtCore.QModelIndex): Index of tree item clicked.
        """
        item = self.get_id(index)

    def tree_dblclicked(self, index):
        """
        Cascade the double clicked signal to the tree node double clicked.

        Args:
            index (QtCore.QModelIndex): Index of tree node double clicked.
        """
        item = self.get_id(index)
        if isinstance(item, AnalysisFolderItem):
            item._dblclicked()

    def populateTree(self):
        """
        Populate the tree starting with groups
        """
        groups = self.main_window.fw_client.groups()
        for group in groups:
            group_item = GroupItem(self.source_model, group, self.main_window.cache_dir)

    def populateTreeFromCollection(self, collection):
        """
        Populate Tree from a single Collection
        """
        collection_item = CollectionItem(
            self.source_model, collection, self.main_window.cache_dir
        )

    def populateTreeFromProject(self, project):
        """
        Populate Tree from a single Project
        """
        project_item = ProjectItem(
            self.source_model, project, self.main_window.cache_dir
        )

    def get_id(self, index):
        """
        Retrieve the tree item from the selected index.

        Args:
            index (QtCore.QModelIndex): Index from selected tree node.

        Returns:
            QtGui.QStandardItem: Returns the item with designated index.
        """
        item = self.source_model.itemFromIndex(index)
        id = item.data()
        # I will want to move this to "clicked" or "on select"
        # self.ui.txtID.setText(id)
        return item

    def open_menu(self, position):
        """
        Function to manage context menus.

        Args:
            position (QtCore.QPoint): Position right-clicked and where menu rendered.
        """
        indexes = self.treeView.selectedIndexes()
        if len(indexes) > 0:
            hasFile = False
            for index in indexes:
                item = self.source_model.itemFromIndex(index)
                if isinstance(item, FileItem):
                    hasFile = True

            menu = QMenu()
            if hasFile:
                action = menu.addAction("Cache Selected Files")
                action.triggered.connect(self._cache_selected)
            menu.exec_(self.treeView.viewport().mapToGlobal(position))

    def on_selection_changed(self):
        """
        Enable or disable load and upload buttons based on selected tree items.

        If a FileItem is selected, the load button is enabled.
        Else if a ContainerItem (e.g. Project, Session,...) is selected, upload is
        is enabled.
        """
        indexes = self.treeView.selectedIndexes()
        has_file = False
        containers_selected = 0
        if len(indexes) > 0:
            for index in indexes:
                item = self.source_model.itemFromIndex(index)
                if isinstance(item, FileItem):
                    has_file = True
                # Analysis Containers cannot be altered.
                elif isinstance(item, AnalysisItem):
                    containers_selected = 2
                elif isinstance(item, ContainerItem):
                    containers_selected += 1
        else:
            has_file = False

        self.main_window.loadFilesButton.enabled = has_file
        upload_enabled = containers_selected == 1
        self.main_window.uploadFilesButton.enabled = upload_enabled
        self.main_window.asAnalysisCheck.enabled = upload_enabled

    def _cache_selected(self):
        """
        Cache selected files to local directory,
        """
        # TODO: Acknowledge this is for files only or change for all files of selected
        #       Acquisitions.
        indexes = self.treeView.selectedIndexes()
        if len(indexes) > 0:
            for index in indexes:
                item = self.source_model.itemFromIndex(index)
                if isinstance(item, FileItem):
                    item._add_to_cache()

    def on_expanded(self, index):
        """
        Triggered on the expansion of any tree node.

        Used to populate subtree on expanding only.  This significantly speeds up the
        population of the tree.

        Args:
            index (QtCore.QModelIndex): Index of expanded tree node.
        """
        item = self.source_model.itemFromIndex(index)
        if hasattr(item, "_on_expand"):
            item._on_expand()

    def _is_paired_type(self, file_item):
        """
        Determine if this file is of a paired type.

        Args:
            file_item (FileItem): File item to test if it has a data pair.
        Returns:
            bool: True or False of paired type.
        """
        return file_item.container.name.split(".")[-1] in PAIRED_FILE_TYPES.keys()

    def _get_paired_file_item(self, file_item):
        """
        Get the pair of current file, if exists

        Args:
            file_item (FileItem): File item to test if it has a data pair.

        Returns:
            FileItem: Object reference to paired file item or None
        """

        parent_item = file_item.parent()
        all_file_names = [
            parent_item.child(i).text() for i in range(parent_item.rowCount())
        ]

        fl_ext = file_item.container.name.split(".")[-1]
        paired_ext = PAIRED_FILE_TYPES[fl_ext]
        paired_file_name = file_item.container.name[: -len(fl_ext)] + paired_ext

        if paired_file_name in all_file_names:
            paired_index = all_file_names.index(paired_file_name)
            return parent_item.child(paired_index)
        else:
            msg = (
                f"The pair for {file_item.text()}, {paired_file_name}, cannot be found."
            )
            log.info(msg)
            return None

    def _process_mrml_storage_node(self, parent_item, node):
        """
        Cache file item related to mrml storage node, if found in parent item.

        Args:
            parent_item (FolderItem): Folder item containing siblings of node
            node (dict): Dictionary representation of mrml node.
        """
        # list all files under the container FolderItem in question
        all_file_names = [
            parent_item.child(i).text() for i in range(parent_item.rowCount())
        ]
        if node["@fileName"] in all_file_names:
            dep_index = all_file_names.index(node["@fileName"])
            dep_item = parent_item.child(dep_index)
            # Cache file without explicitly opening in Slicer
            _, _ = dep_item._add_to_cache()
            if self._is_paired_type(dep_item):
                paired_item = self._get_paired_file_item(dep_item)
                if paired_item:
                    _, _ = paired_item._add_to_cache()
        else:
            file_name = node["@fileName"]
            msg = (
                f"The mrml dependency file, {file_name}, "
                "was not found in sibling files."
            )
            log.info(msg)

    def _get_mrml_dependencies(self, file_item: FileItem):
        """
        Retrieve the MRML dependencies from the sibling files.

        Args:
            file_item (FileItem): MRML File item to retrieve dependencies for.
        """
        parent_item = file_item.parent()

        with open(file_item._get_cache_path()) as f:
            mrml_data = xmltodict.parse(f.read())

        for key in mrml_data["MRML"].keys():
            if key.endswith("Storage"):
                if isinstance(mrml_data["MRML"][key], dict):
                    node = mrml_data["MRML"][key]
                    self._process_mrml_storage_node(parent_item, node)
                else:
                    for node in mrml_data["MRML"][key]:
                        self._process_mrml_storage_node(parent_item, node)

    def cache_item_dependencies(self, file_item):
        """
        Cache the file items dependencies.

        Paired files (.mhd/.raw, .hdr/img)
        MRML files with dependencies.

        Args:
            file_item (FileItem): A file item object to check for dependencies
        """
        if self._is_paired_type(file_item):
            paired_file_item = self._get_paired_file_item(file_item)
            if paired_file_item:
                # Paired file is cached without giving it to slicer to explicity open
                _, _ = paired_file_item._add_to_cache()
        if file_item.text().endswith(".mrml"):
            self._get_mrml_dependencies(file_item)

    def cache_selected_for_open(self):
        """
        Cache selected files if necessary for opening in application.
        """
        tree = self.treeView
        self.cache_files.clear()

        for index in tree.selectedIndexes():
            item = self.source_model.itemFromIndex(index)
            if isinstance(item, FileItem):
                file_path, file_type = item._add_to_cache()
                # A file may have dependencies to cache
                # e.g. .mhdr/.raw or .mrml file
                self.cache_item_dependencies(item)

                self.cache_files[item.container.id] = {
                    "file_path": str(file_path),
                    "file_type": file_type,
                }
