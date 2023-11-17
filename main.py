import csv
import os

import yaml

from custom_modules.log import logger
from custom_modules.netbox_connector import NetboxDevice
from custom_modules.error_handling import print_errors
from custom_modules.errors import Error, NonCriticalError


class VM:
    def __init__(self, site, name, ip, fqdn, user, access, description, os, os_last_update, vmtools_version, backup):
        self.site = site
        self.name = name
        self.ip = ip
        self.fqdn = fqdn
        self.user = user
        self.access = access
        self.description = description
        self.os = os
        self.os_last_update = os_last_update
        self.vmtools_version = vmtools_version
        self.backup = backup

# load settings from yaml file
with open("settings.yaml", "r", encoding='utf-8') as yaml_file:
    logger.info("Loading settings from yaml file")
    settings = yaml.safe_load(yaml_file)
    SITE_SLUGS = settings['site_slugs']

NetboxDevice.create_connection()

# `data` folder contains csv files with name start with `VMs_`. It neccessary to read them all
csv_folder = "input"
csv_files = [file for file in os.listdir(csv_folder) if file.startswith("VMs_") and file.endswith(".csv")]
for file in csv_files:
    file_path = os.path.join(csv_folder, file)
    with open(file_path, "r", encoding='utf-8') as csv_file:
        logger.info(f"Reading file: {file_path}")
        csv_content = csv.DictReader(csv_file, delimiter=',')
        for row in csv_content:
            vm = VM(
                site = row['Office'],
                name = row['VMName'],
                ip = row['IPAddress'],
                fqdn = row['FQDN'],
                user = row['User'],
                access = row['Access'],
                description = row['Description'],
                os = row['OSVersion'],
                os_last_update = row['OSLastUpdate'],
                vmtools_version = row['VMwareToolsVersion'],
                backup = row['Backup'],
            )
            logger.debug(f"VM processed")

            netbox_vm = NetboxDevice(
                site_slug=SITE_SLUGS[vm.site],
                role=None,
                hostname=vm.name,
                vm=True,
                serial_number=vm.vmtools_version,
                ip_address=vm.ip,
                # если площадки имеют имя CORE или TEST - создается одноименный кластер 
                # (костыль по причине отсутствия данных в текущих csv файлах)
                cluster=vm.site if vm.site == "CORE" or vm.site == "TEST" else None,
            )
            netbox_vm.get_platform()