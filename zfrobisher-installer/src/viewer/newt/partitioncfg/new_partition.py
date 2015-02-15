#
# IMPORTS
#
import blivet  # For debug only
from partition_util import *
from snack import *
from partitioner import *
from partition import *
from blivet.devicefactory import DEVICE_TYPE_LVM, DEVICE_TYPE_PARTITION

#
# CONSTANTS
#
from viewer.__data__ import PART_TITLE_NEWPART
from viewer.__data__ import PART_PROMPT_NEWPART

from viewer.__data__ import PART_LABEL_NAME
from viewer.__data__ import PART_LABEL_MNT
from viewer.__data__ import PART_LABEL_LABEL
from viewer.__data__ import PART_LABEL_CAP
from viewer.__data__ import PART_LABEL_TYPE
from viewer.__data__ import PART_LABEL_FS

from viewer.__data__ import PART_FS_XFS
from viewer.__data__ import PART_FS_EXT3
from viewer.__data__ import PART_FS_EXT4
from viewer.__data__ import PART_FS_SWAP

from viewer.__data__ import PART_LABEL_AVAIL
from viewer.__data__ import PART_LABEL_TOTAL

from viewer.__data__ import PART_LABEL_LVM
from viewer.__data__ import PART_LABEL_STD

from viewer.__data__ import PART_BUTTON_OK
from viewer.__data__ import PART_BUTTON_BACK
#
# CODE
#


class NewPartition:
    """
    Represents the disk selelction screen
    """
    def __init__(self, screen, partitioner, partitions, disks):
        # 1. Store parameters
        self._screen = screen
        self._disks = disks
        self._partitioner = partitioner
        self._partitions = partitions

        self._required = False

        # 2. Build form components
        # Prompt for configuring required "boot,root and swap" first
        self._partPromptMsg = TextboxReflowed(40,PART_PROMPT_NEWPART.localize())
        # Parameters Grid
        self._parmsGrid = Grid(2, 7)
        #   Partition name
        self._partNameLabel = Label(PART_LABEL_NAME.localize())
        #   We must have at least boot, swap, root, home parts
        self._partName = Entry(20, "")
        #   Partition mount point
        self._partMntLabel = Label(PART_LABEL_MNT.localize())
        self._partMnt = Entry(20, "")
        #   Partition label
        self._partLabelLabel = Label(PART_LABEL_LABEL.localize())
        self._partLabel = Entry(20, "")
        #   Partition capacity
        self._partCapLabel = Label(PART_LABEL_CAP.localize())
        self._partCap = Entry(20, "")
        #   Partition device grid includes:
        #       Partition device type
        self._partDevTypeLabel = Label(PART_LABEL_TYPE.localize())
        self._partDevTypes = Listbox(1, scroll=1, width=10)
        self._partDevTypes.append(PART_LABEL_LVM.localize(),
                                  DEVICE_TYPE_LVM)
        self._partDevTypes.append(PART_LABEL_STD.localize(),
                                  DEVICE_TYPE_PARTITION)
        #   Partition file system
        self._partFSLabel = Label(PART_LABEL_FS.localize())
        self._partFS = Listbox(1, scroll=1, width=10)
        self._partFS.append(PART_FS_XFS.localize(), PART_FS_XFS.localize())
        self._partFS.append(PART_FS_EXT3.localize(), PART_FS_EXT3.localize())
        self._partFS.append(PART_FS_EXT4.localize(), PART_FS_EXT4.localize())
        self._partFS.append(PART_FS_SWAP.localize(), PART_FS_SWAP.localize())

        #   Partition disk size information grid includes:
        self._availSizeGrid = Grid(2, 1)
        self._totalSizeGrid = Grid(2, 1)
        self._availSizeLabel = Label(PART_LABEL_AVAIL.localize())
        self._totalSizeLabel = Label(PART_LABEL_TOTAL.localize())
        sizes = self._partitioner.getDiskSizes(self._disks)
        self._availSize = Textbox(10, 1, "%.2fMB" % sizes["Avail"], 0, 1)
        self._totalSize = Textbox(10, 1, "%.2fMB" % sizes["Total"], 0, 1)

        self._availSizeGrid.setField(self._availSizeLabel, 0, 0)
        self._availSizeGrid.setField(self._availSize, 1, 0)
        self._totalSizeGrid.setField(self._totalSizeLabel, 0, 0)
        self._totalSizeGrid.setField(self._totalSize, 1, 0)

        self._parmsGrid.setField(self._partNameLabel, 0, 0, anchorLeft=1)
        self._parmsGrid.setField(self._partName, 1, 0, anchorLeft=1)
        self._parmsGrid.setField(self._partMntLabel, 0, 1, anchorLeft=1)
        self._parmsGrid.setField(self._partMnt, 1, 1, anchorLeft=1)
        self._parmsGrid.setField(self._partLabelLabel, 0, 2, anchorLeft=1)
        self._parmsGrid.setField(self._partLabel, 1, 2, anchorLeft=1)
        self._parmsGrid.setField(self._partCapLabel, 0, 3, anchorLeft=1)
        self._parmsGrid.setField(self._partCap, 1, 3, anchorLeft=1)
        self._parmsGrid.setField(self._partDevTypeLabel, 0, 4, anchorLeft=1)
        self._parmsGrid.setField(self._partDevTypes, 1, 4, anchorLeft=1)
        self._parmsGrid.setField(self._partFSLabel, 0, 5, anchorLeft=1)
        self._parmsGrid.setField(self._partFS, 1, 5, anchorLeft=1)
        self._parmsGrid.setField(self._availSizeGrid, 0, 6,
                                 padding=(0, 2, 0, 0))
        self._parmsGrid.setField(self._totalSizeGrid, 1, 6,
                                 padding=(0, 2, 0, 0))

        #   Buttons
        self._buttonBar = ButtonBar(self._screen,
                                    [(PART_BUTTON_OK.localize(),
                                      PART_BUTTON_OK.localize()),
                                     (PART_BUTTON_BACK.localize(),
                                      PART_BUTTON_BACK.localize())])
        # 3. Build form
        self._form = GridForm(self._screen,
                              PART_TITLE_NEWPART.localize(), 1, 3)
        self._form.add(self._partPromptMsg, 0, 0, (0,0,0,1))
        self._form.add(self._parmsGrid, 0, 1)
        self._form.add(self._buttonBar, 0, 2)

    def run(self):
        self._form.setCurrent(self._partName)
        result = self._form.run()
        self._screen.popWindow()
        # Parse result
        rc = self._buttonBar.buttonPressed(result)

        if rc == PART_BUTTON_OK.localize():
            partition = Partition()
            # Set title the same value of name
            partition.title = self._partName.value()
            partition.name = self._partName.value()
            partition.mountpoint = self._partMnt.value()
            partition.label = self._partLabel.value()
            partition.capacity = strToSize(self._partCap.value())
            partition.devicetype = self._partDevTypes.current()
            partition.filesystem = self._partFS.current()
            partition.required = self._required
            # Set new partition as current
            for part in self._partitions:
                if part.current:
                    part.current = False
            partition.current = True
            self._partitions.append(partition)
            return partition.devicetype

        else:
            return "back"

class AddPartition(NewPartition):
    def __init__(self, screen, partitioner, partitions, disks):
        NewPartition.__init__(self, screen, partitioner, partitions, disks)
        self._setEssentialPart()
    def _setEssentialPart(self):
        for essentialPart in self._partitioner._essentialPartitions: 
            if not essentialPart.configured:
               self._partName.set(essentialPart.name)
               self._partMnt.set(essentialPart.mountpoint)
               self._partLabel.set(essentialPart.label)
               self._partCap.set("%s"%essentialPart.capacity)
               self._partDevTypes.setCurrent(essentialPart.devicetype)
               self._partFS.setCurrent(essentialPart.filesystem)
               self._required = True
               essentialPart.configured = True
               break

class ModifyPartition(NewPartition):
    def __init__(self, screen, partitioner, partitions, disks, curPartition):
        NewPartition.__init__(self, screen, partitioner, partitions, disks)
        self._setCurrentPartition(curPartition)
    def _setCurrentPartition(self,curPartition):
        self._partName.set(curPartition.name)
        self._partMnt.set(curPartition.mountpoint)
        self._partLabel.set(curPartition.label)
        self._partCap.set("%s"%curPartition.capacity)
        self._partDevTypes.setCurrent(curPartition.devicetype)
        self._partFS.setCurrent(curPartition.filesystem)
