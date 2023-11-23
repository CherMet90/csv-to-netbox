import csv
import ipaddress
import os

import yaml

from custom_modules.log import logger
from custom_modules.netbox_connector import NetboxDevice
from custom_modules.error_handling import print_errors
from custom_modules.errors import Error, NonCriticalError


class VM:
    def __init__(self, site, name, vlan, ip, fqdn, user, access, description, os, os_last_update, vmtools_version, backup):
        self.site = site
        self.name = name
        self.vlan = [int(i) for i in vlan.split(',') if i.isnumeric()]
        self.fqdn = fqdn
        self.user = user
        self.access = access
        self.description = description
        self.os = os
        self.os_last_update = os_last_update
        self.vmtools_version = vmtools_version
        self.backup = backup
        
        # Дроп не IPv4 адресов
        self.ip = []
        for i in ip.split(','):
            try:
                if ipaddress.IPv4Address(i.strip()):
                    self.ip.append(i.strip())
            except ipaddress.AddressValueError:
                pass
        
        # Создание списка интерфейсов
        self.interfaces = []
        for v, i in zip(self.vlan, self.ip):
            try:
                interface = Interface(v, i)
                self.interfaces.append(interface)
            except Error:
                continue

class Interface:
    def __init__(self, vlan, ip, name=None, type=None):
        self.name = name if name else f'Vlan{vlan}'
        self.type = type if type else 'virtual'
        if isinstance(vlan, str):
            self.untagged = vlan
            self.tagged = []
        self.ip_address = ip
        self.ip_with_prefix = f'{ip}/{NetboxDevice.get_prefix_for_ip(ip).prefix.split("/")[1]}'


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
            try:
                logger.info(f'Processing VM: {row["VMName"]}...')
                # Парсим
                vm = VM(
                    site=row.get('Office', None),
                    name=row.get('VMName', None),
                    vlan=row.get('VLAN', None),
                    ip=row.get('IPAddress', None),
                    fqdn=row.get('FQDN', None),
                    user=row.get('User', None),
                    access=row.get('Access', None),
                    description=row.get('Description', None),
                    os=row.get('OSVersion', None),
                    os_last_update=row.get('OSLastUpdate', None),
                    vmtools_version=row.get('VMwareToolsVersion', None),
                    backup=row.get('Backup', None),
                )
                # Создаем ВМ в Netbox
                netbox_vm = NetboxDevice(
                    site_slug=SITE_SLUGS[vm.site],
                    role=None,
                    hostname=vm.name,
                    vm=True,
                    serial_number=vm.vmtools_version,
                    ip_address=vm.ip[0] if vm.ip else None,
                    # если площадки имеют имя CORE или TEST - создается одноименный кластер 
                    # (костыль по причине отсутствия данных в текущих csv файлах)
                    cluster=vm.site if vm.site == "CORE" or vm.site == "TEST" else None,
                )
                # Добавляем платформу(ОС)
                if vm.os:
                    netbox_vm.set_platform(vm.os)
                # Назначаем владельца
                if vm.user:
                    netbox_vm.set_tenant(vm.user, vm.name)
                # Добавляем интерфейсы
                for i in vm.interfaces:
                    netbox_vm.add_interface(i)
                logger.debug(f'VM {vm.name} was processed')
            except Error:
                continue
# Вывод результата работы
print_errors()