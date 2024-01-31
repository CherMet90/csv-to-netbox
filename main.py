import csv
import ipaddress
import os

import yaml

from custom_modules.log import logger
from custom_modules.netbox_connector import NetboxDevice
from custom_modules.error_handling import print_errors
from custom_modules.errors import Error, NonCriticalError


class VM:
    def __init__(self, site, name, description, os, ip, cluster, state, vcpus, mem, *args, **kwargs):
        self.site = site
        self.name = name
        self.os = os
        self.cluster = cluster
        self.vcpus = vcpus
        
        # Convert memory from GB to MB
        self.mem = int(mem.split()[0]) * 1024
        
        # Handle state
        self.status = 'active'
        if state == 'Powered Off':
            self.status = 'offline'
        
        # Extract user from description
        lines = description.strip().split('\n')
        if len(lines) > 1:
            self.description = '\n'.join(lines[:-1])
            self.user = lines[-1].strip()
        else:
            self.description = description.strip()
            self.user = ''

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
        for i, ip_addr in enumerate(self.ip):
            interface = Interface(i+1, ip_addr)
            self.interfaces.append(interface)
        
        

class Interface:
    def __init__(self, i, ip, name=None, type=None):
        self.name = name if name else f'NIC {i}'
        self.type = type if type else 'virtual'
        self.ip_address = ip
        self.ip_with_prefix = f'{ip}/{NetboxDevice.get_prefix_for_ip(ip).prefix.split("/")[1]}'


# load settings from yaml file
with open("settings.yaml", "r", encoding='utf-8') as yaml_file:
    logger.info("Loading settings from yaml file")
    settings = yaml.safe_load(yaml_file)
    SITE_SLUGS = settings['site_slugs']

# `data` folder contains csv files with name start with `VMs_`. It neccessary to read them all
csv_folder = "input"
csv_files = [file for file in os.listdir(csv_folder) if file.startswith("VMs_") and file.endswith(".csv")]
for file in csv_files:
    file_path = os.path.join(csv_folder, file)
    with open(file_path, "r", encoding='UTF-8') as csv_file:
        logger.info(f"Reading file: {file_path}")
        csv_content = csv.DictReader(csv_file, delimiter=',')
        for row in csv_content:
            if 'vCLS' in row['Name']:
                continue
            NetboxDevice.create_connection()
            
            try:
                logger.info(f'Processing VM: {row["Name"]}...')
                # Парсим
                vm = VM(
                    site=row.get('Office', None),
                    name=row.get('Name', None),
                    state=row.get('State', None),
                    device=row.get('Host', None),
                    # vlan=row.get('VLAN', None),
                    ip=row.get('IP Address', None),
                    # fqdn=row.get('FQDN', None),
                    # user=row.get('User', None),
                    # access=row.get('Access', None),
                    description=row.get('Notes', None),
                    os=row.get('Guest OS', None),
                    # os_last_update=row.get('OSLastUpdate', None),
                    # vmtools_version=row.get('VMwareToolsVersion', None),
                    # backup=row.get('Backup', None),
                    cluster=row.get('Cluster', None),
                    vcpus=row.get('CPUs', None),
                    mem=row.get('Memory Size', None),
                )
                # Создаем ВМ в Netbox
                netbox_vm = NetboxDevice(
                    site_slug=SITE_SLUGS[vm.site],
                    role=None,
                    hostname=vm.name,
                    vm=True,
                    ip_address=vm.ip[0] if vm.ip else None,
                    cluster_name=vm.cluster,
                    cluster_type="VMware vSphere",
                    status=vm.status,
                    vcpus=vm.vcpus,
                    mem=vm.mem,
                    description=vm.description,
                )
                # Добавляем платформу(ОС)
                if vm.os:
                    netbox_vm.set_platform(vm.os.rstrip())
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