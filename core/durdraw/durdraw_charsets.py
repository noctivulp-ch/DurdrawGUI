# durdraw_charsets.py — durdraw por Sam Foster — BSD 3-Clause License
# Ingested into DurdrawGUI; import pdb eliminado.

import configparser
import os
import pathlib
import xml.etree.ElementTree as ET


def hex_range_iterator(start_hex, end_hex):
    start_int = int(start_hex, 16)
    end_int = int(end_hex, 16)
    current_int = start_int
    while current_int <= end_int:
        yield current_int
        current_int += 1


def parse_xml_blocks_file(xml_file_path):
    block_data = {}
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    for block_element in root.findall('.//block'):
        first_cp = block_element.get('first-cp')
        last_cp = block_element.get('last-cp')
        block_name = block_element.get('name')
        if block_name is not None and first_cp is not None and last_cp is not None:
            block_data[block_name] = {'first-cp': first_cp, 'last-cp': last_cp}
    return block_data


def load_unicode_block(block_name: str):
    xml_block_filename = pathlib.Path(__file__).parent.joinpath("charsets/unicode-groups.xml")
    block_data = parse_xml_blocks_file(xml_block_filename)
    if block_name in block_data:
        block_info = block_data[block_name]
        first_cp = block_info['first-cp']
        last_cp = block_info['last-cp']
        charMap = []
        fKeyList = {'f1': '', 'f2': '', 'f3': '', 'f4': '', 'f5': '',
                    'f6': '', 'f7': '', 'f8': '', 'f9': '', 'f10': ''}
        fKeyNum = 1
        for code_point in hex_range_iterator(first_cp, last_cp):
            fKeyList[f'f{fKeyNum}'] = code_point
            if fKeyNum == 10:
                charMap.append(fKeyList.copy())
                fKeyNum = 1
            else:
                fKeyNum += 1
        return charMap
    return None


def get_unicode_blocks_list():
    xml_block_filename = pathlib.Path(__file__).parent.joinpath("charsets/unicode-groups.xml")
    block_data = parse_xml_blocks_file(xml_block_filename)
    block_list = list(block_data.keys())
    block_list = block_list[1:]  # corta Basic Latin (0000-007F, null char)
    return block_list


def scan_charmap_folders(appState):
    internal_charsets_path = pathlib.Path(__file__).parent.joinpath("charsets")
    charmap_dirs = ["~/.durdraw/charsets", internal_charsets_path]
    for directory in charmap_dirs:
        directory = os.path.expanduser(str(directory))
        if os.path.isdir(directory) and os.access(directory, os.R_OK):
            for filename in os.listdir(directory):
                if filename.endswith(".ini"):
                    file_path = os.path.join(directory, filename)
                    load_charmap_file(file_path, appState)


def load_charmap_file(file_path: str, appState, setting=False):
    file_path = os.path.expanduser(file_path)
    configFile = configparser.ConfigParser()
    configFile.read([file_path])

    if configFile == []:
        return False

    name = 'custom set'
    encoding = 'utf-8'
    if 'Character Set' in configFile:
        charSetConfig = configFile['Character Set']
        if 'name' in charSetConfig:
            name = charSetConfig['name']
        if 'encoding' in charSetConfig:
            encoding = charSetConfig['encoding']

    charMap = []
    fKeyList = {'f1': '', 'f2': '', 'f3': '', 'f4': '', 'f5': '',
                'f6': '', 'f7': '', 'f8': '', 'f9': '', 'f10': ''}

    blockNum = 1
    scanning = True
    while scanning:
        blockName = f'block {blockNum}'
        if blockName in configFile:
            blockConfig = configFile[blockName]
            fKeyNum = 1
            while fKeyNum < 11:
                fKeyString = f'f{fKeyNum}'
                if fKeyString in blockConfig:
                    try:
                        fKeyList[fKeyString] = ord(blockConfig[fKeyString][0])
                    except Exception:
                        fKeyList[fKeyString] = ord(' ')
                fKeyNum += 1
            charMap.append(fKeyList.copy())
            blockNum += 1
        else:
            scanning = False

    if len(charMap) == 0:
        return False

    if name not in appState.userCharSets:
        appState.userCharSets.append(name)
        appState.userCharSetFiles.update({name: file_path})
    if setting:
        appState.characterSet = name
    return charMap
