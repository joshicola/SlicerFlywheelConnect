import datetime
import logging
import os
import os.path as op
import shutil
import tempfile
from glob import glob
from importlib import import_module
from pathlib import Path
from zipfile import ZipFile

import ctk
import DICOMLib
import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)

from management.utils import check_requirements

# fmt: off
# Check for and install missing requirements
check_requirements()

import flywheel

from management.tree_management import TreeManagement

# fmt: on

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

#
# flywheel_connect
#


class flywheel_connect(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        # TODO make this more human readable by adding spaces
        self.parent.title = "Flywheel Connect"
        self.parent.categories = ["Flywheel"]
        self.parent.dependencies = []
        self.parent.contributors = ["Joshua Jacobs (flywheel.io)"]
        self.parent.helpText = 'See <a href="https://github.com/flywheel-apps/SlicerFlywheelConnect">Flywheel Connect website</a> for more information.'
        self.parent.helpText += self.getDefaultModuleDocumentationLink()
        self.parent.acknowledgementText = ""


#
# flywheel_connectWidget
#


class flywheel_connectWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setup(self):
        """
        Initialize all form elements
        """
        super(flywheel_connectWidget, self).setup()

        # Declare Cache path
        self.cache_dir = os.path.expanduser("~") + "/flywheelIO/"

        # #################Declare form elements#######################

        # Give a line_edit and label for the API key
        self.apiKeyCollapsibleGroupBox = ctk.ctkCollapsibleGroupBox()
        self.apiKeyCollapsibleGroupBox.setTitle("API Key Entry")

        self.layout.addWidget(self.apiKeyCollapsibleGroupBox)
        apiKeyFormLayout = qt.QFormLayout(self.apiKeyCollapsibleGroupBox)

        #
        # api Key Text Box
        #
        self.apiKeyTextLabel = qt.QLabel("API Key:")
        apiKeyFormLayout.addWidget(self.apiKeyTextLabel)
        self.apiKeyTextBox = qt.QLineEdit()
        self.apiKeyTextBox.setEchoMode(qt.QLineEdit.Password)
        apiKeyFormLayout.addWidget(self.apiKeyTextBox)
        self.connectAPIButton = qt.QPushButton("Connect Flywheel")
        self.connectAPIButton.enabled = True
        apiKeyFormLayout.addWidget(self.connectAPIButton)

        self.logAlertTextLabel = qt.QLabel("")
        apiKeyFormLayout.addWidget(self.logAlertTextLabel)

        #
        # cache_dir Text Box
        #
        self.cache_dirTextLabel = qt.QLabel("Disk Cache:")
        apiKeyFormLayout.addWidget(self.cache_dirTextLabel)
        self.cache_dirTextBox = qt.QLineEdit()
        self.cache_dirTextBox.setText(self.cache_dir)
        apiKeyFormLayout.addWidget(self.cache_dirTextBox)

        #
        # Use Cache CheckBox
        #
        self.useCacheCheckBox = qt.QCheckBox("Cache Images")
        self.useCacheCheckBox.toolTip = (
            """Images cached to "Disk Cache"."""
            "Otherwise, deleted at every new retrieval."
        )

        apiKeyFormLayout.addWidget(self.useCacheCheckBox)
        self.useCacheCheckBox.setCheckState(True)
        self.useCacheCheckBox.setTristate(False)

        # Data View Section
        self.dataCollapsibleGroupBox = ctk.ctkCollapsibleGroupBox()
        self.dataCollapsibleGroupBox.setTitle("Data")
        self.layout.addWidget(self.dataCollapsibleGroupBox)

        dataFormLayout = qt.QFormLayout(self.dataCollapsibleGroupBox)

        #
        #  collection toggle button
        #

        self.radioButtonGroup = qt.QButtonGroup()
        self.useCollections = qt.QRadioButton("Browse Collections")
        self.useProjects = qt.QRadioButton("Browse Groups and Projects")
        self.radioButtonGroup.addButton(self.useCollections)
        self.radioButtonGroup.addButton(self.useProjects)
        self.useProjects.setChecked(True)
        self.useProjects.enabled = False
        self.useCollections.enabled = False
        dataFormLayout.addWidget(self.useProjects)
        dataFormLayout.addWidget(self.useCollections)

        #
        # group Selector ComboBox
        #
        self.groupSelectorLabel = qt.QLabel("Current group:")
        dataFormLayout.addWidget(self.groupSelectorLabel)

        # Selector ComboBox
        self.groupSelector = qt.QComboBox()
        self.groupSelector.enabled = False
        self.groupSelector.setMinimumWidth(200)
        dataFormLayout.addWidget(self.groupSelector)

        #
        # project Selector ComboBox
        #
        self.projectSelectorLabel = qt.QLabel("Current project:")
        dataFormLayout.addWidget(self.projectSelectorLabel)

        # Selector ComboBox
        self.projectSelector = qt.QComboBox()
        self.projectSelector.enabled = False
        self.projectSelector.setMinimumWidth(200)
        dataFormLayout.addWidget(self.projectSelector)

        #
        # collection Selector ComboBox
        #

        # Selector ComboBox
        self.collectionSelector = qt.QComboBox()
        self.collectionSelector.enabled = False
        self.collectionSelector.visible = False
        self.collectionSelector.setMinimumWidth(200)
        dataFormLayout.addWidget(self.collectionSelector)

        # TreeView for Single Projects containers:
        self.treeView = qt.QTreeView()

        self.treeView.enabled = False
        self.treeView.setMinimumWidth(200)
        self.treeView.setMinimumHeight(350)
        self.tree_management = TreeManagement(self)
        dataFormLayout.addWidget(self.treeView)

        # Load Files Button
        self.loadFilesButton = qt.QPushButton("Load Selected Files")
        self.loadFilesButton.enabled = False
        dataFormLayout.addWidget(self.loadFilesButton)

        # Upload to Flywheel Button
        self.uploadFilesButton = qt.QPushButton(
            "Upload to Flywheel\nas Container Files"
        )
        self.uploadFilesButton.enabled = False
        dataFormLayout.addWidget(self.uploadFilesButton)

        # As Analysis Checkbox
        self.asAnalysisCheck = qt.QCheckBox("As Analysis")
        self.asAnalysisCheck.toolTip = (
            "Upload Files to Flywheel as an Analysis Container."
        )
        self.asAnalysisCheck.enabled = False

        dataFormLayout.addWidget(self.asAnalysisCheck)

        # ################# Connect form elements #######################
        self.connectAPIButton.connect("clicked(bool)", self.onConnectAPIPushed)

        # self.useCollectionCheckBox.connect("clicked(bool)", self.onUseCollectionChecked)
        self.useCollections.connect("clicked(bool)", self.onProjectsOrCollections)
        self.useProjects.connect("clicked(bool)", self.onProjectsOrCollections)

        self.collectionSelector.connect(
            "currentIndexChanged(QString)", self.onCollectionSelected
        )

        self.groupSelector.connect("currentIndexChanged(QString)", self.onGroupSelected)

        self.projectSelector.connect(
            "currentIndexChanged(QString)", self.onProjectSelected
        )

        self.loadFilesButton.connect("clicked(bool)", self.onLoadFilesPushed)

        self.uploadFilesButton.connect("clicked(bool)", self.save_scene_to_flywheel)

        self.asAnalysisCheck.stateChanged.connect(self.onAnalysisCheckChanged)

        # Add vertical spacer
        self.layout.addStretch(1)

    def onConnectAPIPushed(self):
        """
        Connect to a Flywheel instance for valid api-key.
        """
        try:
            # Instantiate and connect widgets ...
            if self.apiKeyTextBox.text:
                self.fw_client = flywheel.Client(self.apiKeyTextBox.text)
            else:
                self.fw_client = flywheel.Client()
            fw_user = self.fw_client.get_current_user()["email"]
            fw_site = self.fw_client.get_config()["site"]["api_url"]
            self.logAlertTextLabel.setText(
                f"You are logged in as {fw_user} to {fw_site}"
            )
            # if client valid: TODO

            self.useProjects.enabled = True
            self.useCollections.enabled = True
            # initialize collections
            collections = self.fw_client.collections()
            self.collectionSelector.enabled = False
            self.collectionSelector.clear()
            for collection in collections:
                self.collectionSelector.addItem(collection.label, collection.id)
            self.useProjects.setChecked(True)

            # initialize groups and projects
            groups = self.fw_client.groups()
            self.groupSelector.enabled = True
            self.groupSelector.clear()
            for group in groups:
                self.groupSelector.addItem(group.label, group.id)

            # Clear out any other instance's data from Slicer before proceeding.
            slicer.mrmlScene.Clear(0)
        except Exception as e:
            self.groupSelector.clear()
            self.groupSelector.enabled = False
            self.apiKeyTextBox.clear()
            self.projectSelector.clear()
            self.projectSelector.enabled = False
            self.collectionSelector.clear()
            self.collectionSelector.enabled = False
            slicer.util.errorDisplay(e)

    def onProjectsOrCollections(self):
        """
        Toggle between browsing projects and collections.
        """
        tree_rows = self.tree_management.source_model.rowCount()
        if self.useCollections.checked:
            self.projectSelectorLabel.setText("Current collection:")
            self.projectSelector.enabled = False
            self.projectSelector.visible = False
            self.groupSelectorLabel.visible = False
            self.groupSelector.enabled = False
            self.groupSelector.visible = False
            self.collectionSelector.enabled = True
            self.collectionSelector.visible = True
            collection_id = self.collectionSelector.currentData
            if collection_id:
                self.collection = self.fw_client.get(collection_id)
                # Remove the rows from the tree and repopulate
                if tree_rows > 0:
                    self.tree_management.source_model.removeRows(0, tree_rows)
                self.tree_management.populateTreeFromCollection(self.collection)
                self.treeView.enabled = True
            else:
                self.treeView.enabled = False
        else:
            self.projectSelectorLabel.setText("Current project:")
            self.projectSelector.enabled = True
            self.projectSelector.visible = True
            self.groupSelectorLabel.visible = True
            self.groupSelector.enabled = True
            self.groupSelector.visible = True
            self.collectionSelector.enabled = False
            self.collectionSelector.visible = False
            project_id = self.projectSelector.currentData
            if project_id:
                self.project = self.fw_client.get(project_id)
                # Remove the rows from the tree and repopulate
                if tree_rows > 0:
                    self.tree_management.source_model.removeRows(0, tree_rows)
                self.tree_management.populateTreeFromProject(self.project)
                self.treeView.enabled = True
            else:
                self.treeView.enabled = False

    def onCollectionSelected(self, item):
        """
        On selected collection from dropdown, update the tree

        Args:
            item (str): Name of collection or empty string
        """
        tree_rows = self.tree_management.source_model.rowCount()
        if item:
            collection_id = self.collectionSelector.currentData
            self.collection = self.fw_client.get(collection_id)

            # Remove the rows from the tree and repopulate
            if tree_rows > 0:
                self.tree_management.source_model.removeRows(0, tree_rows)
            self.tree_management.populateTreeFromCollection(self.collection)
            self.treeView.enabled = True
        else:
            self.treeView.enabled = False
            # Remove the rows from the tree and don't repopulate
            if tree_rows > 0:
                self.tree_management.source_model.removeRows(0, tree_rows)
            self.loadFilesButton.enabled = False

    def onGroupSelected(self, item):
        """
        On selected Group from dropdown, update casecade

        Args:
            item (str): Group name or empty string
        """
        if item:
            group_id = self.groupSelector.currentData
            self.group = self.fw_client.get(group_id)
            projects = self.group.projects()
            self.projectSelector.enabled = len(projects) > 0
            self.projectSelector.clear()
            for project in projects:
                self.projectSelector.addItem(project.label, project.id)

    def onProjectSelected(self, item):
        """
        On selected project from dropdown, update the tree

        Args:
            item (str): Name of project or empty string
        """
        tree_rows = self.tree_management.source_model.rowCount()
        if item:
            project_id = self.projectSelector.currentData
            self.project = self.fw_client.get(project_id)

            # Remove the rows from the tree and repopulate
            if tree_rows > 0:
                self.tree_management.source_model.removeRows(0, tree_rows)
            self.tree_management.populateTreeFromProject(self.project)
            self.treeView.enabled = True
        else:
            self.treeView.enabled = False
            # Remove the rows from the tree and don't repopulate
            if tree_rows > 0:
                self.tree_management.source_model.removeRows(0, tree_rows)
            self.loadFilesButton.enabled = False

    def is_compressed_dicom(self, file_path, file_type):
        """
        Check file_path and file_type for a flywheel compressed dicom archive.

        Args:
            file_path (str): Path to cached file
            file_type (str): Type of Flywheel file

        Returns:
            boolean: True for supported compressed dicom type
        """
        if file_path.endswith(".zip") and file_type == "dicom":
            return True

        return False

    def load_dicom_archive(self, file_path):
        """
        Load unzipped DICOMs into Slicer.

        Args:
            file_path (str): path to the cached dicom archive.

        https://discourse.slicer.org/t/fastest-way-to-load-dicom/9317/2
        """
        with tempfile.TemporaryDirectory() as dicomDataDir:
            dicom_zip = ZipFile(file_path)
            dicom_zip.extractall(path=dicomDataDir)
            DICOMLib.importDicom(dicomDataDir)
            dicomFiles = slicer.util.getFilesInDirectory(dicomDataDir)
            loadablesByPlugin, loadEnabled = DICOMLib.getLoadablesFromFileLists(
                [dicomFiles]
            )
            loadedNodeIDs = DICOMLib.loadLoadables(loadablesByPlugin)

    def load_slicer_file(self, file_path, file_type):
        """
        Load filepath based on type.

        Args:
            file_path (str): Path to file to load
            file_type (str): String representatin of file type
        """
        # Check for Flywheel compressed dicom
        if self.is_compressed_dicom(file_path, file_type):
            try:
                self.load_dicom_archive(file_path)
                return True
            except Exception as e:
                log.error("Not a valid DICOM archive.")
                return False
        # Load using Slicer default node reader
        elif not slicer.app.ioManager().loadFile(file_path):
            log.error("Failed to read file: " + file_path)
            return False
        return True

    def onLoadFilesPushed(self):
        """
        Load tree-selected files into 3D Slicer for viewing.
        """

        # If Cache not checked, delete cache_dir recursively
        if not self.useCacheCheckBox.checkState():
            shutil.rmtree(self.cache_dir)
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        # TODO: How to:
        #       * Cache Paired files without loading the data file?
        #           - If we select a header file, cache the data file
        #           - If we have a pair selected, remove data file from cache_files
        #           - If we have a data file selected, remove it.
        #       * Cache all files referenced by an .mrml file?
        # Cache all selected files
        self.tree_management.cache_selected_for_open()

        # Walk through cached files... This could use "types"
        for _, file_dict in self.tree_management.cache_files.items():
            file_path = file_dict["file_path"]
            file_type = file_dict["file_type"]
            success = self.load_slicer_file(file_path, file_type)

    def save_analysis(self, parent_container_item, output_path):
        """
        Save selected files to a new analysis container under a parent container.

        Args:
            parent_container_item (ContainerItem): Tree Item representation of parent
                container.
            output_path (Path): Temporary path to where Slicer files are saved.
        """
        parent_container = self.fw_client.get(parent_container_item.data())

        # Get all cached paths represented in Slicer
        input_files_paths = [
            Path(node.GetFileName())
            for node in slicer.util.getNodesByClass("vtkMRMLStorageNode")
            if self.cache_dir in node.GetFileName()
        ]

        # Represent those files as file reference from their respective parents
        input_files = [
            self.fw_client.get(str(input_path.parents[0]).split("/")[-1])
            .get_file(input_path.name)
            .ref()
            if input_path.is_symlink()
            else self.fw_client.get(str(input_path.parents[1]).split("/")[-1])
            .get_file(input_path.name)
            .ref()
            for input_path in input_files_paths
        ]

        # Generic name... could be improved.
        analysis_name = "3D Slicer " + datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Create analysis container
        analysis = parent_container.add_analysis(
            label=analysis_name, inputs=input_files
        )

        # Get all files from temp directory
        outputs = [
            file_path
            for file_path in glob(str(output_path / "*"))
            if Path(file_path).is_file()
        ]

        # Finalize analysis
        analysis.upload_file(outputs)

    def save_files_to_container(self, parent_container_item, output_path):
        """
        Save selected files to a parent Flywheel container.

        Files that already exist in the container are ignored.

        TODO: Update tree to reflect that a new file version is not cached.
        TODO: parameterize "overwrite" and connect to a checkbox.

        Args:
            parent_container_item (ContainerItem):  Tree Item representation of parent
                container.
            output_path (Path): Temporary path to where Slicer files are saved.
        """
        overwrite = True
        parent_container = self.fw_client.get(parent_container_item.data()).reload()
        parent_container_files = [fl.name for fl in parent_container.files]
        for output_file in [
            file_path
            for file_path in glob(str(output_path / "*"))
            if (
                Path(file_path).is_file()
                and (Path(file_path).name not in parent_container_files or overwrite)
            )
        ]:
            parent_container.upload_file(output_file)

    def save_scene_to_flywheel(self):
        """
        Save selected files in the current Slicer scene to a Flywheel Analysis or
        Container.
        """
        with tempfile.TemporaryDirectory() as tmp_output_path:
            output_path = Path(tmp_output_path)
            slicer.mrmlScene.SetRootDirectory(str(output_path))
            slicer.mrmlScene.SetURL(str(output_path / "Slicer_Scene.mrml"))
            save_as_analysis = self.asAnalysisCheck.isChecked()
            if not save_as_analysis:
                for node in slicer.util.getNodesByClass("vtkMRMLStorageNode"):
                    node.SetFileName(Path(node.GetFileName()).name)
            if slicer.util.openSaveDataDialog():
                index = self.treeView.selectedIndexes()[0]
                container_item = self.tree_management.source_model.itemFromIndex(index)

                if save_as_analysis:
                    self.save_analysis(container_item, output_path)
                else:
                    self.save_files_to_container(container_item, output_path)

            # Remove storage nodes with the tmp_output_path in them
            for node in [
                node
                for node in slicer.util.getNodesByClass("vtkMRMLStorageNode")
                if tmp_output_path in node.GetFileName()
            ]:
                slicer.mrmlScene.RemoveNode(node)

    def onAnalysisCheckChanged(self, item):
        """
        Update the text on the "Upload" button depending on item state

        Args:
            item (ItemData): Data from item... not used.
        """
        if self.asAnalysisCheck.isChecked():
            text = "Upload to Flywheel\nas Analysis"
        else:
            text = "Upload to Flywheel\nas Container Files"
        self.uploadFilesButton.setText(text)

    def cleanup(self):
        pass


#
# flywheel_connectLogic
#


class flywheel_connectLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def hasImageData(self, volumeNode):
        """This is an example logic method that
        returns true if the passed in volume
        node has valid image data
        """
        if not volumeNode:
            logging.debug("hasImageData failed: no volume node")
            return False
        if volumeNode.GetImageData() is None:
            logging.debug("hasImageData failed: no image data in volume node")
            return False
        return True

    def isValidInputOutputData(self, inputVolumeNode, outputVolumeNode):
        """Validates if the output is not the same as input"""
        if not inputVolumeNode:
            logging.debug("isValidInputOutputData failed: no input volume node defined")
            return False
        if not outputVolumeNode:
            logging.debug(
                "isValidInputOutputData failed: no output volume node defined"
            )
            return False
        if inputVolumeNode.GetID() == outputVolumeNode.GetID():
            logging.debug(
                "isValidInputOutputData failed: input and output volume is the same. "
                "Create a new volume for output to avoid this error."
            )
            return False
        return True

    def run(self, inputVolume, outputVolume, imageThreshold, enableScreenshots=0):
        """
        Run the actual algorithm
        """

        if not self.isValidInputOutputData(inputVolume, outputVolume):
            slicer.util.errorDisplay(
                "Input volume is the same as output volume. "
                "Choose a different output volume."
            )
            return False

        logging.info("Processing started")

        # Compute the thresholded output volume using the Threshold Scalar Volume
        # CLI module
        cliParams = {
            "InputVolume": inputVolume.GetID(),
            "OutputVolume": outputVolume.GetID(),
            "ThresholdValue": imageThreshold,
            "ThresholdType": "Above",
        }
        cliNode = slicer.cli.run(
            slicer.modules.thresholdscalarvolume,
            None,
            cliParams,
            wait_for_completion=True,
        )

        # Capture screenshot
        if enableScreenshots:
            self.takeScreenshot("flywheel_connectTest-Start", "MyScreenshot", -1)

        logging.info("Processing completed")

        return True


class flywheel_connectTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """
        Do whatever is needed to reset the state -
        typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear(0)
        log.setLevel(logging.DEBUG)
        self.flywheel_connect_widget = slicer.modules.flywheel_connectWidget
        self.root_path = Path(__file__).parents[0]

    def cleanUp(self):
        """
        Clean up after tests.
        """
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_load_nifti()
        self.test_load_compressed_dicom()
        self.test_load_metaimage()
        self.test_load_analyze()
        self.test_load_NRRD()
        self.cleanUp()

    def test_load_nifti(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        log.info("Test loading NIFTI files.")
        nifti_path = self.root_path / "Testing/data/T1w_MPR.nii.gz"
        nifti_type = "nifti"
        succeeded = self.flywheel_connect_widget.load_slicer_file(
            str(nifti_path), nifti_type
        )
        assert succeeded

        log.info("Test of NIFTI Load Complete!")

    def test_load_compressed_dicom(self):
        log.info("Testing loading compressed dicoms.")
        log.debug("Load labeled compressed dicom.zip file.")
        file_path = str(self.root_path / "Testing/data/T1w_MPR.zip")
        file_type = "dicom"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded
        file_type = "not dicom"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert not suceeded
        log.info("Suceeded loading compressed dicoms.")

    def test_load_metaimage(self):
        log.info("Testing load of metaimage files.")
        log.debug("Load the header with the .raw file present.")
        file_path = str(
            self.root_path / "Testing/data/MFJK1C1F2_20200824_151907_S7to10_FWI_Fat.mhd"
        )
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded

        log.debug("Load a header without the .raw file present")
        file_path = str(
            self.root_path
            / "Testing/data/MFJK1C1F2_20200824_151907_S7to10_FWI_FatPct.mhd"
        )
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert not suceeded

        log.debug("attempt to load the .raw file")
        file_path = str(
            self.root_path / "Testing/data/MFJK1C1F2_20200824_151907_S7to10_FWI_Fat.raw"
        )
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert not suceeded
        log.info("Tests of metaimage files complete.")

    def test_load_analyze(self):
        log.info("Testing load of Analyze files.")
        log.debug("Load the header with the .img file present")
        file_path = str(self.root_path / "Testing/data/T1w_MPR.hdr")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded

        log.debug("Load the .img without the header")
        file_path = str(self.root_path / "Testing/data/T1w_MPR.img")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded

        log.debug("Load a .hdr without .img file")
        file_path = str(self.root_path / "Testing/data/T1w_MPR3.hdr")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert not suceeded
        log.info("Tests of Analyze files complete.")

    def test_load_NRRD(self):
        log.info("Testing load of NRRD files.")
        log.debug("Load stanalone .nrrd file")
        file_path = str(self.root_path / "Testing/data/27 T1w_MPR.nrrd")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded

        log.debug("Load the .nhdr with data (.raw.gz) present")
        file_path = str(self.root_path / "Testing/data/27 T1w_MPR.nhdr")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert suceeded

        log.debug("Load a .raw.gz without .nhdr file")
        file_path = str(self.root_path / "Testing/data/27 T1w_MPR.raw.gz")
        file_type = "file"
        suceeded = self.flywheel_connect_widget.load_slicer_file(file_path, file_type)
        assert not suceeded
        log.info("Tests of NRRD files complete.")
