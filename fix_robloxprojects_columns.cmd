@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "ROOT=E:\RobloxProjects\Blender Export"
set "PROTECTED=E:\RobloxProjects\Blender Export\game1\flora\tree\blossom_tree_01"

if not exist "%ROOT%\" (
    echo ERROR: Root folder not found: "%ROOT%"
    pause
    exit /b 2
)

set "PYEXE=py -3"
py -3 -c "import sys; assert sys.version_info >= (3,8)" >nul 2>&1
if errorlevel 1 (
    set "PYEXE=python"
    python -c "import sys; assert sys.version_info >= (3,8)" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.8+ is needed.
        pause
        exit /b 2
    )
)

%PYEXE% -c "import pythoncom; from win32com.shell import shell, shellcon" >nul 2>&1
if errorlevel 1 (
    echo Installing pywin32...
    %PYEXE% -m pip install --user pywin32
    if errorlevel 1 (
        echo ERROR: Could not install pywin32.
        pause
        exit /b 2
    )
)

set "PYFILE=%TEMP%\roblox_folder_columns_%RANDOM%_%RANDOM%.py"
set "SELF=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:SELF,[Text.Encoding]::UTF8); $m='### PYTHON HELPER ###'; $p=$s.LastIndexOf($m); if($p -lt 0){exit 1}; [IO.File]::WriteAllText($env:PYFILE, $s.Substring($p+$m.Length), (New-Object Text.UTF8Encoding($false)))"
if errorlevel 1 (
    echo ERROR: Could not prepare the helper.
    pause
    exit /b 2
)

%PYEXE% -u "%PYFILE%" "%ROOT%" "%PROTECTED%"
set "RC=%ERRORLEVEL%"
del /q "%PYFILE%" >nul 2>&1
echo.
if "%RC%"=="0" (echo Completed. Reopen folders in File Explorer.) else (echo Finished with errors. Code: %RC%)
pause
exit /b %RC%

### PYTHON HELPER ###
import os
import stat
import struct
import sys
import uuid
import traceback
import pythoncom
from win32com.shell import shell, shellcon

ROOT = os.path.normcase(os.path.abspath(sys.argv[1]))
PROTECTED = os.path.normcase(os.path.abspath(sys.argv[2]))
EXCLUDED = {'.control-center', '.git', '.idea', '.tools', '.venv'}

# Canonical Windows property keys:
# System.ItemNameDisplay (10), System.DateModified (14),
# System.ItemTypeText (4), System.Size (12).
FMTID = uuid.UUID('B725F130-47EF-101A-A5F1-02608C9EEBAC').bytes_le
COLS = ((10, 156), (14, 144), (4, 120), (12, 80))

# The native ColInfo binary stream, with explicit DateModified (PID=14)
# instead of System.ItemDate (the ambiguous "Date" column).
COLINFO = (
    bytes(16) + bytes.fromhex('FD DF DF FD') + struct.pack('<I', 16) + bytes(8)
    + struct.pack('<II', len(COLS), 24)
    + b''.join(FMTID + struct.pack('<II', pid, width) for pid, width in COLS)
)
SORT = bytes(16) + struct.pack('<I', 1) + FMTID + struct.pack('<II', 10, 1)

# Generic is the target view for each directory; also stamp existing
# common content templates so they cannot fall back to a "Date" column.
GENERIC = '{5C4F28B5-F869-4E84-8E60-F11DB97C5CC7}'
TYPES = (
    GENERIC,
    '{7D49D726-3C21-4F05-99AA-FDC2C9474656}',  # Documents
    '{B3690E58-E961-423B-B687-386EBFD83239}',  # Pictures
    '{94D6DDCC-4A68-4175-A374-BD584A510B78}',  # Music
    '{5FA96407-7E77-483C-AC93-691D05850DE8}',  # Videos
    '{885A186E-A440-4ADA-812B-DB871B942259}',  # Downloads
)
FLAGS = shellcon.SHGVSPB_FOLDERNODEFAULTS


def reparse(path):
    try:
        return bool(os.stat(path, follow_symlinks=False).st_file_attributes
                    & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return os.path.islink(path)


def bag(pidl, name):
    return shell.SHGetViewStatePropertyBag(pidl, name, FLAGS,
                                        pythoncom.IID_IPropertyBag)


def write_stream(pb, name, raw):
    # Each target owns a completely independent stream.
    source = pythoncom.CreateStreamOnHGlobal()
    source.Write(raw)
    source.Seek(0, 0)
    pb.Write(name, source)
    target = pb.Read(name, pythoncom.VT_UNKNOWN).QueryInterface(pythoncom.IID_IStream)
    target.Seek(0, 0)
    target.Write(raw)
    target.SetSize(len(raw))
    target.Seek(0, 0)
    if bytes(target.Read(len(raw))) != raw:
        raise RuntimeError(name + ': data verification failed')


def set_columns(pidl, name):
    pb = bag(pidl, name)
    pb.Write('Rev', 0)
    pb.Write('Vid', '{137E7700-3573-11CF-AE69-08002B2E1262}')
    pb.Write('Mode', 4)               # Details
    pb.Write('LogicalViewMode', 1)    # Details
    pb.Write('IconSize', 16)
    pb.Write('GroupView', 0)
    pb.Write('GroupByKey:FMTID', '{00000000-0000-0000-0000-000000000000}')
    pb.Write('GroupByKey:PID', 0)
    write_stream(pb, 'ColInfo', COLINFO)
    write_stream(pb, 'Sort', SORT)


def main():
    if not os.path.isdir(ROOT):
        print('ERROR: Root folder is missing.', flush=True)
        return 2
    if ROOT == PROTECTED:
        print('ERROR: Root and protected folder are identical.', flush=True)
        return 2

    print('VIEW: Details', flush=True)
    print('COLUMNS: Name | Date modified | Type | Size', flush=True)
    print('SORT: Name ascending; grouping off', flush=True)
    print('EXCLUDED: ' + ', '.join(sorted(EXCLUDED)), flush=True)
    print('ROOT and blossom_tree_01 will not be modified.', flush=True)
    print('Close Explorer windows for E:\\RobloxProjects before running.', flush=True)
    print('', flush=True)

    pythoncom.CoInitialize()
    try:
        updated = skipped = errors = 0

        def onerror(error):
            nonlocal errors
            errors += 1
            print('SCAN ERROR:', error, flush=True)

        for parent, directories, _ in os.walk(ROOT, topdown=True,
                                               followlinks=False, onerror=onerror):
            for name in directories[:]:
                path = os.path.normcase(os.path.abspath(os.path.join(parent, name)))
                if name.casefold() in EXCLUDED or reparse(path):
                    directories.remove(name)
                    skipped += 1
                    continue
                if path == PROTECTED:
                    # Do not modify the reference itself; its subfolders are eligible.
                    skipped += 1
                    continue
                print('[{}] {}'.format(updated + errors + 1, path), end=' ... ', flush=True)
                try:
                    pidl = shell.SHILCreateFromPath(path, 0)[0]
                    # Force generic folder classification on these target folders,
                    # avoiding the content-sniffer's default "Date" column.
                    base = bag(pidl, 'Shell')
                    base.Write('SniffedFolderType', 'Generic')
                    base.Write('FolderType', 'NotSpecified')
                    # Stamp "Shell" as well as the common typed bags.
                    set_columns(pidl, 'Shell')
                    for folder_type in TYPES:
                        set_columns(pidl, 'Shell\\' + folder_type)
                    updated += 1
                    print('OK', flush=True)
                except Exception as exc:
                    errors += 1
                    print('ERROR:', exc, flush=True)
                    if updated == 0 and errors == 1:
                        print('Stopped: first folder failed.', flush=True)
                        return 2

        print('', flush=True)
        print('Updated: {} | excluded/protected: {} | errors: {}'.format(
            updated, skipped, errors), flush=True)
        return 1 if errors else 0
    finally:
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\nInterrupted.', flush=True)
        sys.exit(130)
    except Exception:
        traceback.print_exc()
        sys.exit(2)
