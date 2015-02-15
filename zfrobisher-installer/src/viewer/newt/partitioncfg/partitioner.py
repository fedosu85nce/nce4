#
# IMPORTS
#
from partition_util import *
import blivet
from blivet.devices import *
import blivet.devicefactory
from blivet.devicefactory import *
from blivet.deviceaction \
    import ACTION_TYPE_DESTROY, ACTION_OBJECT_DEVICE
from partition import *
import logging

#
# CONSTANTS
#
LOG_FILE_NAME = '/var/log/partitioner.log'
LOG_FORMATTER = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

SIZE_UNITS_IN_FACTORY = "M"  # Default units in device factory

#
# CODE
#


class Partitioner:
    """
    Represents the disk selelction screen
    """
    def __init__(self, logger=None, storage=None):
        if storage is None:
            self._storage = blivet.Blivet()
            self._storage.reset()
        else:
            self._storage = storage

        # map of vgname:vgsize which type is number and unit is M
        # vgsize used to judge the vg policy with value > 0
        # vgsize is assigned by the select_vg.size property
        self._newVgs = {}
        self._configureLog(logger)
        self._partitions = []
        self._setEssentialPartitions()
        self._tempPartition = Partition()

    def detectPreviousInstalls(self):
        pass

    def detectedPreviousInstall(self):
        pass

    def getPreviousInstalledDisk(self):
        pass

    def getDiskIdByPath(self, disk_path):
        for disk in _storage.disks:
            if disk.path == disk_path:
                return "/dev/%s" % disk.serial
        return "NO DISK-BY-ID FOUND"

    def getDelPvs(self):
        delPvs = []
        for action in self.actions:
            if action.type == ACTION_TYPE_DESTROY and \
               action.obj == ACTION_OBJECT_DEVICE:
                if type(action.device) == PartitionDevice:
                    delPvs.append(action.device.name)
        return ','.join(delPvs)

    def getDelVgs(self):
        delVgs = []
        for action in self.actions:
            if action.type == ACTION_TYPE_DESTROY and \
               action.obj == ACTION_OBJECT_DEVICE:
                if type(action.device) == LVMVolumeGroupDevice:
                    delVgs.append(action.device.name)
        return ','.join(delVgs)

    def _configureLog(self, logger=None):
        # logger instance was given: use it!
        if logger != None and isinstance(logger, logging.Logger):
            self._logger = logger
            return
        # create logger
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)

        # create file handler and set level to debug
        fileHandler = logging.FileHandler(LOG_FILE_NAME)
        fileHandler.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter(LOG_FORMATTER)

        # add formatter to file handler
        fileHandler.setFormatter(formatter)

        # add fileHandler to logger
        self._logger.addHandler(fileHandler)

    def reset(self):
        self._storage.reset()
        #self._initialzePartitions()

        # map of vgname:vgsize which type is number and unit is M
        # vgsize used to judge the vg policy with value > 0
        # vgsize is assigned by the select_vg.size property
        self._newVgs = {}

    def getDiskSizes(self, disks):
        total = avail = 0.0
        for disk in disks:
            total += disk.size
            sizes = self._storage.getFreeSpace((disk, ))
            avail += (float)(sizes[disk.name][0].convertTo("m"))
        return {"Total": total, "Avail": avail}

    def vgInDisk(self, vg, disk):
        for anc in [temp for temp in vg.ancestors if type(temp) == DiskDevice]:
            if disk.name == anc.name:
                return True
        return False

    def vgInDisks(self, vg, disks):
        allInDisk = True
        for anc in [temp for temp in vg.ancestors if type(temp) == DiskDevice]:
            ancInDisk = False
            for disk in disks:
                if disk.name == anc.name:
                    ancInDisk = True
                    break
            if not ancInDisk:
                allInDisk = False
                break
        return allInDisk

    def vgCrossDiskCheck(self, selectedDisks):
        """ Check vgs on the selected disks, return a list of disks which are
            required by these vgs but have not been selected by user.
        """
        lackedDisks = []
        checkedVgs = []
        for disk in selectedDisks:
            disks = self._storage.devicetree.getDependentDevices(disk)
            for vg in [ d for d in disks if d.type == "lvmvg" ]:
                if vg in checkedVgs:
                   continue
                checkedVgs.append(vg)
                for anc in vg.ancestors:
                    if isinstance(anc,DiskDevice) and anc not in selectedDisks + lackedDisks:
                       lackedDisks.append(anc)
        #lackedDisks.sort()
        return lackedDisks

    def getDeviceType(self, device):
        return get_device_type(device)

    def clearDisks(self, disks):
        for disk in disks:
            # Clear only if disk has content
            # if not disk.isleaf:
                self._storage.recursiveRemove(disk)
                self._storage.initializeDisk(disk)

    def deletePartition(self,curPartition):
        if curPartition.device is not None:
            if type(curPartition.device) == \
                    LVMLogicalVolumeDevice:
                # Remove vg which contains only this LVM
                if curPartition.device.vg.kids == 1:
                    self.removeLogicalVolumeGroup(
                        curPartition.device.vg,
                        self._partitions)
                else:
                    self.removeLogicalVolume(curPartition)
            else:
                self.removeStandardPartition(curPartition)
        # Remove partiton information from partition list
        self._partitions.remove(curPartition)

    def removeStandardPartition(self, partition):
        self._storage.destroyDevice(partition.device)
        partition.device = None

    def removeLogicalVolume(self, partition):
        vgName = partition.device.vg.name
        self._storage.destroyDevice(partition.device)
        partition.device = None
        # adjust VG to size of remaining LVs
        factory = blivet.devicefactory.get_device_factory(self._storage,
                                          DEVICE_TYPE_LVM, 0,
                                          container_name=vgName,
                                          container_size=SIZE_POLICY_AUTO)
        factory.configure()

    def removeLogicalVolumeGroup(self, vg, partitions):
        if vg in self._newVgs.keys():
            del(self._newVgs[vg])
        # Update the references in partitions list
        for partition in partitions:
            if (partition.device is not None) and \
               (type(partition.device) == LVMLogicalVolumeDevice) and \
               (partition.device.vg == vg):
                partition.device = None
        self._storage.recursiveRemove(vg)
        # Also clear the leaf parent Partition
        for parent in [temp for temp in vg.parents
                       if type(temp) == PartitionDevice]:
            if parent.isleaf:
                self._storage.recursiveRemove(parent)

    def updatePartWithDev(self, partition, device):
        filesystem = device.format.type
        type = self.getDeviceType(device)
        size = device.size  # size from device is a number with unit M
        if type == DEVICE_TYPE_LVM:
            name = device.lvname
        else:
            name = device.name
        if hasattr(device.format, "mountpoint") and \
           (device.format.mountpoint is not None):
            mountpoint = device.format.mountpoint
        else:
            mountpoint = ""
        if hasattr(device.format, "label") and \
           (device.format.label is not None):
            label = device.format.label
        else:
            label = ""

        partition.device = device
        partition.name = name
        partition.label = label
        partition.capacity = strToSize(str(size))  # convert from number to blivet Size
        partition.devicetype = type
        partition.mountpoint = mountpoint
        partition.filesystem = filesystem

    def createStandardPartition(self, partition, disk):
        factory = blivet.devicefactory.PartitionFactory(
            self._storage,
            # blivet.errors.DeviceFactoryError: value (512 MB) must be either a number or None
            float(partition.capacity.convertTo(spec=SIZE_UNITS_IN_FACTORY)),
            [disk],
            mountpoint=partition.mountpoint,
            label=partition.label,
            fstype=partition.filesystem)
        factory.configure()
        partition.device = factory.device
        # Update partition with created device information
        self.updatePartWithDev(partition, partition.device)

    def createLogicalVolume(self, partition, vgName, vgSize, disks):
        '''
        dev_info["container_name"] = vgName
        dev_info["container_size"] = vgSize
        dev_info["disks"] = disks
        dev_info["fstype"] = partition.filesystem
        dev_info["label"] = partition.label
        dev_info["name"] = partition.name
        dev_info["mountpoint"] = partition.mountpoint
        partition.device = self._storage.factoryDevice(
            blivet.devicefactory.DEVICE_TYPE_LVM,
            partition.capacity,
            **dev_info)
        '''
        factory = blivet.devicefactory.LVMFactory(
            self._storage,
            # blivet.errors.DeviceFactoryError: value (512 MB) must be either a number or None
            float(partition.capacity.convertTo(spec=SIZE_UNITS_IN_FACTORY)),
            disks,
            mountpoint=partition.mountpoint,
            fstype=partition.filesystem,
            label=partition.label,
            name=partition.name,
            container_name=vgName,
            container_size=vgSize)  # container_size is number
        factory.configure()
        partition.device = factory.device
        # Update partition with created device information
        self.updatePartWithDev(partition, partition.device)
        self._newVgs[partition.device.vg] = vgSize

    def copy(self):
        storage_copy = self._storage.copy()
        return Partitioner(storage_copy)

    def submitChanges(self):
        self._storage.doIt()

    def getMultipathMode(self, selectedDisks):
        for disk in selectedDisks:
            if type(disk) == MultipathDevice:
                return True
        return False

    def _setEssentialPartitions(self):
        self._boot = Partition()
        self._boot.title = "boot"
        self._boot.name = "boot"
        self._boot.mountpoint = "/boot"
        self._boot.label = ""
        self._boot.capacity = strToSize("512")
        self._boot.devicetype = DEVICE_TYPE_PARTITION
        self._boot.filesystem = "ext3"
        self._boot.current = True
        self._boot.required = True
        self._boot.configured = False

        self._swap = Partition()
        self._swap.title = "swap"
        self._swap.name = "swap"
        self._swap.mountpoint = ""
        self._swap.label = ""
        self._swap.capacity = strToSize("4G")
        self._swap.devicetype = DEVICE_TYPE_PARTITION
        self._swap.filesystem = "swap"
        self._swap.current = False
        self._swap.required = True
        self._swap.configured = False

        self._root = Partition()
        self._root.title = "root"
        self._root.name = "root"
        self._root.mountpoint = "/root"
        self._root.label = ""
        self._root.capacity = strToSize("5.5G")
        self._root.devicetype = DEVICE_TYPE_LVM
        self._root.filesystem = "ext3"
        self._root.current = False
        self._root.required = True
        self._root.configured = False

        self._essentialPartitions = {}
        self._essentialPartitions['/boot'] = self._boot
        self._essentialPartitions['/root'] = self._root
        self._essentialPartitions['swap'] = self._swap

    def checkEssentialPartitons(self):
        essentialParts = ["/root","/boot","swap"]
        for part in self._partitions:
            if part.mountpoint == "/root":
               essentialParts.remove("/root")
            if part.mountpoint == "/boot":
               essentialParts.remove("/boot")
            if part.filesystem == "swap":
               essentialParts.remove("swap")
        return essentialParts

    @property
    def storage(self):
        return self._storage

    @property
    def actions(self):
        self._storage.devicetree.pruneActions()
        self._storage.devicetree.sortActions()
        return self._storage.devicetree.findActions()

    @property
    def newVgs(self):
        return self._newVgs

    def getFreeSpace(self, disks):
        return self._storage.getFreeSpace(disks)

    # Proxies to blivet instance
    @property
    def disks(self):
        return self._storage.disks

    @property
    def vgs(self):
        return self._storage.vgs

    @property
    def boot(self):
        return self._boot.device

    @property
    def root(self):
        return self._root.device

    @property
    def swap(self):
        return self._swap.device

    @property
    def partitions(self):
        return self._partitions
