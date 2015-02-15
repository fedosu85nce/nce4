#
# IMPORTS
#
import logging  # For debug only
import blivet
from partition_util import *
from snack import *
from partition import *
from partitioner import *
from select_disks import *
from select_disk import *
from select_vg import *
from manual_partition import *
from msg_box import *
from new_partition import *
from list_actions import *
from blivet.devicefactory import DEVICE_TYPE_LVM, DEVICE_TYPE_PARTITION
import copy

#
# CONSTANTS
#
from viewer.__data__ import PART_TITLE_DISKERR
from viewer.__data__ import PART_ERROR_NODISK
from viewer.__data__ import PART_TITLE_DELPART_ERR
from viewer.__data__ import PART_TITLE_MANUALPART_ERR
from viewer.__data__ import PART_ERROR_DEL_REQUIRED
from viewer.__data__ import PART_ERROR_NOT_CONFIG
from viewer.__data__ import PART_TITLE_VG_CONSISTENCY_CHECK
from viewer.__data__ import PART_WARN_MSG_VG_CONSISTENCY_CHECK
from viewer.__data__ import WARNING_MSG_MISS_ESSENTIAL_PART
from viewer.__data__ import PART_TITLE_MANUALPART_MISS_ESSENTIAL_PARTS

INDEX_SELECT_DISKS = 0
INDEX_AUTOMATIC_PARTITION = 1
INDEX_MANUAL_PARTITION = 2
INDEX_SELECT_DISK = 3
INDEX_SELECT_VG = 4
INDEX_LIST_ACTIONS = 5
INDEX_BACK = -1
INDEX_FORWARD = -2

#
# CODE
#


class PartitionInterface:
    """
    The interface class to do partitioning
    """
    def __init__(self, screen, partitioner, selectedDisks):
        # 1. Store parameters
        self._partitioner = partitioner
        self._screen = screen
        self._selectedDisks = selectedDisks
        logging.basicConfig(filename="log.txt", level=logging.DEBUG)

    def run(self, runOn="LPAR"):
        index = INDEX_SELECT_DISKS
        while(True):
            if index == INDEX_BACK or index == INDEX_FORWARD:
                break
            # 1. Select the disks used for partitioning
            if index == INDEX_SELECT_DISKS:
                self._partitioner.reset()
                self._partitions = self._partitioner.partitions
                index = self._selectDisks()
            # Automatical partitioning
            if index == INDEX_AUTOMATIC_PARTITION:
                # ToDo: Call codes from Modules provided by WangTing
                index = INDEX_FORWARD
            # Manual partitioning
            if index == INDEX_MANUAL_PARTITION:
                index = self._manualPartition(runOn)
            if index == INDEX_SELECT_DISK:
                index = self._selectDisk()
            if index == INDEX_SELECT_VG:
                index = self._selectVg()
            if index == INDEX_LIST_ACTIONS:
                index = self._listActions()
        return index

    def _confirmDeleteVg(self, lackDisks):
        diskNames=""
        for disk in lackDisks:
            diskNames+="\n%22s"%disk.name
        text = PART_WARN_MSG_VG_CONSISTENCY_CHECK.localize()%diskNames
        title = PART_TITLE_VG_CONSISTENCY_CHECK.localize()
        formatedText = reflow(text,50)[0]
        rc = ButtonChoiceWindow(self._screen,title,formatedText,width=50)
        return rc

    def _selectDisks(self):
        selectDisks = SelectDisks(self._screen, self._partitioner.disks,
                                  self._selectedDisks)
        (result, self._selectedDisks) = selectDisks.run()
        # Quit Partition
        if result == PART_BUTTON_BACK.localize():
            return INDEX_BACK
        # User must select at least one disk for partitioning
        if len(self._selectedDisks) == 0:
            MsgBox(self._screen, PART_TITLE_DISKERR.localize(),
                   PART_ERROR_NODISK.localize())
            return INDEX_SELECT_DISKS
        # Check is there any VG on the selected disks having dependency on
        # the unchoosed disks, this may cause data unavailable, let user
        # decide
        lackDisks = self._partitioner.vgCrossDiskCheck(self._selectedDisks)
        if lackDisks:
            if self._confirmDeleteVg(lackDisks) == "cancel":
                return INDEX_SELECT_DISKS
        self._partitioner.clearDisks(self._selectedDisks)
        # Chosen to do automatical partitioning
        if result == PART_BUTTON_AUTO.localize():
            return INDEX_AUTOMATIC_PARTITION
        # Chosen to do manual partitioning
        else:
            return INDEX_MANUAL_PARTITION

    def _manualPartition(self, runOn="LPAR"):
        '''Entry for manual partitioning

            :runOn VM   - means could not configure three default partition /boot, swap, /(root)
                   LPAR - means run on LPAR
        '''
        manualPartition = ManualPartition(self._screen,
                                          self._partitioner,
                                          self._partitions,
                                          self._selectedDisks)
        result = manualPartition.run()
        if result == PART_BUTTON_ADD.localize():
            # Display new form to collect new partition information
            newPartition = AddPartition(self._screen,
                                        self._partitioner,
                                        self._partitions,
                                        self._selectedDisks)
            ret = newPartition.run()
            if ret == DEVICE_TYPE_LVM:
                return INDEX_SELECT_VG
            elif ret == DEVICE_TYPE_PARTITION:
                return INDEX_SELECT_DISK
            else:
                return INDEX_MANUAL_PARTITION
        if result == PART_BUTTON_DEL.localize():
            # Delete partition
            # Remove created device if exist
            curPartition = manualPartition.partList.current()
            self._partitioner.deletePartition(curPartition)
             # Change current partition to the first one
             #self._partitions[0].current = True
            return INDEX_MANUAL_PARTITION
        if result == PART_BUTTON_MODIFY.localize():
            #self._partitioner.deletePartition(curPartition)
            self._partitioner._curPartition = manualPartition.partList.current()
            modifyPartition = ModifyPartition(self._screen,
                                        self._partitioner,
                                        self._partitions,
                                        self._selectedDisks,
                                        self._partitioner._curPartition)
            ret = modifyPartition.run()
            if ret == DEVICE_TYPE_LVM:
                return INDEX_SELECT_VG
            elif ret == DEVICE_TYPE_PARTITION:
                return INDEX_SELECT_DISK
            else:
                return INDEX_MANUAL_PARTITION
        if result == PART_BUTTON_DONE.localize():
            # if run on local vm for test, do not check whether configure the device
            lackedEssentialParts = self._partitioner.checkEssentialPartitons()
            if lackedEssentialParts:
                msg = WARNING_MSG_MISS_ESSENTIAL_PART.localize()%lackedEssentialParts
                MsgBox(self._screen, PART_TITLE_MANUALPART_MISS_ESSENTIAL_PARTS.localize(), msg)
                return INDEX_MANUAL_PARTITION
                
            if runOn == "VM":
                return INDEX_LIST_ACTIONS
            # run on LPAR, this check is required
            msg = PART_ERROR_NOT_CONFIG.localize()
            hasError = False
            for partition in self._partitions:
                if partition.device is None:
                    msg = msg + "\t\t" + partition.title + "\n"
                    hasError = True
            if hasError:
                MsgBox(self._screen, PART_TITLE_MANUALPART_ERR.localize(), msg)
                return INDEX_MANUAL_PARTITION
            else:
                return INDEX_LIST_ACTIONS
        if result == PART_BUTTON_BACK.localize():
            return INDEX_SELECT_DISKS

    def _selectDisk(self):
        #curPartition = self._getCurPartition()
        # Select Disk for device type: Standard Partition
        selectDisk = SelectDisk(self._screen, self._partitioner,
                                self._selectedDisks)
        ret = selectDisk.run()
        if ret == PART_BUTTON_OK.localize():
            curPartition = self._partitioner._tempPartition
            for part in self._partitions:
                if part.current:
                    part.current = False
            curPartition.current = True
            newPart = copy.copy(curPartition)
            self._partitions.append(newPart)
        return INDEX_MANUAL_PARTITION

    def _selectVg(self):
        #curPartition = self._getCurPartition()
        selectVg = SelectVg(self._screen, self._partitioner,
                            self._selectedDisks)
        ret = selectVg.run()
        curPartition = self._partitioner._tempPartition
        if ret == PART_BUTTON_DEL.localize():
            if selectVg.vg is not None:
                self._partitioner.removeLogicalVolumeGroup(selectVg.vg,
                                                           self._partitions)
        if ret == PART_BUTTON_OK.localize():
            # Remove old device if exist
            if curPartition.device is not None:
                if type(curPartition.device) == LVMLogicalVolumeDevice:
                    self._partitioner.removeLogicalVolume(curPartition)
                else:
                    self._partitioner.removeStandardPartition(curPartition)
            # Create new VG
            if selectVg.vg is None:
                self._partitioner.createLogicalVolume(curPartition,
                                                      selectVg.name,
                                                      selectVg.size,     # size is property
                                                      selectVg.disks)
            # Select existingVG
            else:
                # This VG is created by zFrobisher
                if selectVg.vg in self._partitioner.newVgs:
                    self._partitioner.createLogicalVolume(curPartition,
                                                          selectVg.vg.name,
                                                          selectVg.size,  # size is property
                                                          selectVg.disks)
            for part in self._partitions:
                if part.current:
                    part.current = False
            curPartition.current = True
            newPart = copy.copy(curPartition)
            self._partitions.append(newPart)
        return INDEX_MANUAL_PARTITION

    def _listActions(self):
        # Apply changes
        listActions = ListActions(self._screen, self._partitioner)
        rc = listActions.run()
        if rc == PART_BUTTON_OK.localize():
            return INDEX_FORWARD
        else:
            # Back to manual partition form
            return INDEX_MANUAL_PARTITION

    def _getCurPartition(self):
        for partition in self._partitions:
            if partition.current:
                return partition

    def _isUniquePartitionName(self, name):
        for partition in self._partitions:
            if name == partition.name:
                return False
        return True
