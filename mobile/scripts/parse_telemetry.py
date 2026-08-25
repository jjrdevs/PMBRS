#!/usr/bin/env python3
"""
Parse `pmbrs_telemetry.xml` and print a JSON summary of counters.
Usage: ./scripts/parse_telemetry.py pmbrs_telemetry.xml
"""
import sys
import xml.etree.ElementTree as ET
import json


def parse(path):
    tree = ET.parse(path)
    root = tree.getroot()
    data = {}
    for child in root:
        # Expecting <map><int name="key" value="123"/></map>
        for e in child:
            name = e.attrib.get('name')
            value = e.attrib.get('value')
            if name:
                # try int
                try:
                    iv = int(value)
                    data[name] = iv
                except Exception:
                    data[name] = value
    return data


def main():
    if len(sys.argv) < 2:
        print('Usage: parse_telemetry.py pmbrs_telemetry.xml')
        sys.exit(2)
    summary = parse(sys.argv[1])
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
