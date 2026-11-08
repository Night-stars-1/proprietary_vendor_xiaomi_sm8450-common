#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the WFD ELF consumed by Soong without changing vendor inputs."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import subprocess

OLD = 'android.media.audio.common.types-V4-cpp.so'
NEW = 'android.media.audio.common.types-V5-cpp.so'
PINS = {
    'libwfdservice': (
        'cd222b6f7fc1d4a86118e599efb2eadbdd6d1079b9cc18e96f3d5ee596f38eab',
        '7763d3e21259aa26ed1bf6f89b9eb1a90dd2c27dbe9421db620fc0b8b4124fc4',
        ('libaudiobase.so',),
    ),
    'libwfdmmsrc_system': (
        'bfa63ccfe2b82f015493717d2cf457aff41606c68d13b21830412058e0ed2344',
        '343861d2c5c7842a55e04733c3c29084f519784fdf47ace049ccda49d7790c57',
        ('libaudiobase.so', 'libgui_shim.so'),
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def needed(tool, path):
    return subprocess.check_output([tool, '--print-needed', str(path)], text=True).splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patchelf', required=True)
    parser.add_argument('--module', choices=PINS, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source_hash, output_hash, additions = PINS[args.module]
    if digest(args.input) != source_hash:
        raise ValueError(f'{args.input}: unexpected WFD input SHA-256; restore the unmodified upstream blob')
    before = needed(args.patchelf, args.input)
    if any(lib in before for lib in additions):
        raise ValueError(f'{args.input}: added dependency already present')
    expected = before.copy()
    if args.module == 'libwfdservice':
        if before.count(OLD) != 1 or NEW in before:
            raise ValueError(f'{args.input}: unexpected audio AIDL dependency')
        expected[expected.index(OLD)] = NEW
    shutil.copyfile(args.input, args.output)
    if args.module == 'libwfdservice':
        subprocess.run([args.patchelf, '--replace-needed', OLD, NEW, str(args.output)], check=True)
    for lib in additions:
        subprocess.run([args.patchelf, '--add-needed', lib, str(args.output)], check=True)
    if Counter(needed(args.patchelf, args.output)) != Counter(expected + list(additions)):
        raise ValueError(f'{args.output}: unexpected DT_NEEDED dependencies')
    if digest(args.output) != output_hash:
        raise ValueError(f'{args.output}: unexpected patched WFD SHA-256')


if __name__ == '__main__':
    main()
