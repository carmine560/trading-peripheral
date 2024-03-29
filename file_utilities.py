from datetime import datetime
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

try:
    import gnupg
    GNUPG_IMPORT_ERROR = None
except ModuleNotFoundError as import_error:
    GNUPG_IMPORT_ERROR = import_error

try:
    import winreg

    from PIL import Image, ImageDraw, ImageFont
    import pywintypes
    import win32api
    import win32com.client
    WINDOWS_IMPORT_ERROR = None
except ModuleNotFoundError as import_error:
    WINDOWS_IMPORT_ERROR = import_error

def archive_encrypt_directory(source, output_directory, fingerprint=''):
    if GNUPG_IMPORT_ERROR:
        print(GNUPG_IMPORT_ERROR)
        return

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w:xz') as tar:
        tar.add(source, arcname=os.path.basename(source))

    tar_stream.seek(0)
    gpg = gnupg.GPG()
    if not fingerprint:
        fingerprint = gpg.list_keys()[0]['fingerprint']

    output = os.path.join(output_directory,
                          os.path.basename(source) + '.tar.xz.gpg')
    gpg.encrypt_file(tar_stream, fingerprint, armor=False, output=output)

def backup_file(source, backup_directory=None, number_of_backups=-1,
                should_compare=True):
    encrypted_source = source + '.gpg'
    if os.path.exists(encrypted_source):
        source = encrypted_source
        should_compare = False

    if os.path.exists(source):
        if not backup_directory:
            backup_directory = os.path.join(os.path.dirname(source), 'backups')

        if number_of_backups:
            check_directory(backup_directory)
            if not should_compare:
                source_base = os.path.splitext(os.path.splitext(
                    os.path.basename(source))[0])[0]
                source_suffix = os.path.splitext(os.path.splitext(
                    source)[0])[1] + '.gpg'
            else:
                source_base = os.path.splitext(os.path.basename(source))[0]
                source_suffix = os.path.splitext(source)[1]

            backup = os.path.join(
                backup_directory,
                source_base + datetime.fromtimestamp(
                    os.path.getmtime(source)).strftime('-%Y%m%dT%H%M%S')
                + source_suffix)
            backups = sorted(
                [f for f in os.listdir(backup_directory)
                 if re.fullmatch(
                         fr'{source_base}-\d{{8}}T\d{{6}}{source_suffix}', f)])

            if not os.path.exists(backup):
                should_copy = True
                if should_compare and backups:
                    with open(source, 'rb') as f:
                        source_contents = f.read()
                    with open(os.path.join(backup_directory, backups[-1]),
                              'rb') as f:
                        last_backup_contents = f.read()
                    if source_contents == last_backup_contents:
                        should_copy = False
                if should_copy:
                    try:
                        shutil.copy2(source, backup)
                        backups.append(os.path.basename(backup))
                    except OSError as e:
                        print(e)
                        sys.exit(1)

            if number_of_backups > 0:
                excess = len(backups) - number_of_backups
                if excess > 0:
                    for f in backups[:excess]:
                        try:
                            os.remove(os.path.join(backup_directory, f))
                        except OSError as e:
                            print(e)
                            sys.exit(1)

        elif os.path.isdir(backup_directory):
            try:
                shutil.rmtree(backup_directory)
            except OSError as e:
                print(e)
                sys.exit(1)

def check_directory(directory):
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            print(e)
            sys.exit(1)

def create_bash_completion(script_base, options, values, interpreters,
                           completion):
    variable_str = '    values="'
    line = ''
    lines = []
    for value in values:
        if len(variable_str) + len(line) + len(value) + 4 > 79:
            lines.append(line.rstrip(' '))
            line = ''

        line += f"'{value}' "

    lines.append(line.rstrip(' '))
    values_str = f"\n{' ' * len(variable_str)}".join(lines)

    expression_str = ' || '.join(f'$previous == {option}'
                                 for option in options)
    completion_str = fr'''_{script_base}()
{{
    local script current previous options values
    script=${{COMP_WORDS[1]}}
    current=${{COMP_WORDS[COMP_CWORD]}}
    previous=${{COMP_WORDS[COMP_CWORD-1]}}
    options="{' '.join(options)}"
{variable_str}{values_str}"

    if [[ $script =~ {script_base}\.py ]]; then
        if [[ $current == -* ]]; then
            COMPREPLY=($(compgen -W "$options" -- $current))
            return 0
        fi
        if [[ {expression_str} ]]; then
            COMPREPLY=($(compgen -W "$values" -- $current))
            return 0
        fi
    else
        COMPREPLY=($(compgen -f -- $current))
        return 0
    fi
}}
complete -F _{script_base} {' '.join(interpreters)}
'''

    with open(completion, 'w', encoding='utf-8', newline='\n') as f:
        f.write(completion_str)

def create_icon(base, icon_directory=None):
    if WINDOWS_IMPORT_ERROR:
        print(WINDOWS_IMPORT_ERROR)
        return False

    def get_scaled_font(text, font_path, desired_dimension, variation_name=''):
        temp_font_size = 100
        temp_font = ImageFont.truetype(font_path, temp_font_size)
        if variation_name:
            temp_font.set_variation_by_name(variation_name)

        left, top, right, bottom = ImageDraw.Draw(
            Image.new('RGB', (1, 1))).multiline_textbbox((0, 0), text,
                                                         font=temp_font)
        scaling_factor = min(desired_dimension / (right - left),
                             desired_dimension / (bottom - top))
        actual_font = ImageFont.truetype(font_path,
                                         int(temp_font_size * scaling_factor))
        if variation_name:
            actual_font.set_variation_by_name(variation_name)
        return actual_font

    if GNUPG_IMPORT_ERROR:
        print(GNUPG_IMPORT_ERROR)
        return False

    acronym = ''.join(word[0].upper()
                      for word in re.split(r'[\W_]+', base) if word)
    font_path = 'bahnschrift.ttf'
    variation_name = 'Bold'
    image_dimension = 256
    desired_dimension = image_dimension - 2
    image = Image.new('RGBA', (image_dimension, image_dimension),
                      color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes'
                        r'\Personalize') as key:
        try:
            is_light_theme, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        except OSError:
            is_light_theme = True

    fill = 'black' if is_light_theme else 'white'

    if not acronym:
        return False
    if len(acronym) < 3:
        font = get_scaled_font(acronym, font_path, desired_dimension,
                               variation_name=variation_name)
        left, top, right, bottom = draw.textbbox((0, 0), acronym, font=font)
        draw.text(((image_dimension - (right - left)) / 2 - left,
                   (image_dimension - (bottom - top)) / 2 - top), acronym,
                  fill=fill, font=font)
    else:
        text = f'{acronym[:2]}\n{acronym[2:4]}'
        font = get_scaled_font(text, font_path, desired_dimension,
                               variation_name=variation_name)
        left, top, right, bottom = draw.multiline_textbbox((0, 0), text,
                                                           font=font)
        draw.multiline_text(((image_dimension - (right - left)) / 2 - left,
                             (image_dimension - (bottom - top)) / 2 - top),
                            text, fill=fill, font=font, align='center')

    if icon_directory:
        icon = os.path.join(icon_directory, base + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            base + '.ico')

    image.save(icon, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return icon

def create_powershell_completion(script_base, options, values, interpreters,
                                 completion):
    interpreters_regex = fr"({'|'.join(interpreters)})(\.exe)?"
    interpreters_array = f"@({', '.join(map(repr, interpreters))})"
    options_str = '|'.join(options)

    variable_str = '        $options = @('
    line = ''
    lines = []
    for value in values:
        if len(variable_str) + len(line) + len(value) + 5 > 79:
            lines.append(line.rstrip(' '))
            line = ''

        line += f"'{value}', "

    lines.append(line.rstrip(', '))
    values_str = f"\n{' ' * len(variable_str)}".join(lines)

    completion_str = fr'''$scriptblock = {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $commandLine = $commandAst.ToString()
    $regex = `
      '{interpreters_regex}\s+.*{script_base}\.py(\s+.*)?\s+({options_str})'
    if ($commandLine -cmatch $regex) {{
{variable_str}{values_str})
        $options | Where-Object {{ $_ -like "$wordToComplete*" }} |
          ForEach-Object {{
              [System.Management.Automation.CompletionResult]::new(
                  $_, $_, 'ParameterValue', $_)
          }}
    }}
}}
Register-ArgumentCompleter -Native -CommandName {interpreters_array} `
  -ScriptBlock $scriptblock
'''

    with open(completion, 'w', encoding='utf-8') as f:
        f.write(completion_str)

def create_shortcut(base, target_path, arguments, program_group_base=None,
                    icon_directory=None, hotkey=None):
    if WINDOWS_IMPORT_ERROR:
        print(WINDOWS_IMPORT_ERROR)
        return

    program_group = get_program_group(program_group_base)
    check_directory(program_group)
    shell = win32com.client.Dispatch('WScript.Shell')
    title = re.sub(r'[\W_]+', ' ', base).strip().title()
    shortcut = shell.CreateShortCut(os.path.join(program_group,
                                                 title + '.lnk'))
    shortcut.WindowStyle = 7
    shortcut.IconLocation = create_icon(base,
                                        icon_directory=icon_directory)
    shortcut.TargetPath = target_path
    shortcut.Arguments = arguments
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
    if hotkey:
        shortcut.Hotkey = 'CTRL+ALT+' + hotkey

    shortcut.save()

def decrypt_extract_file(source, output_directory):
    if GNUPG_IMPORT_ERROR:
        print(GNUPG_IMPORT_ERROR)
        return

    gpg = gnupg.GPG()
    with open(source, 'rb') as f:
        decrypted_data = gpg.decrypt_file(f)

    tar_stream = io.BytesIO(decrypted_data.data)
    with tarfile.open(fileobj=tar_stream, mode='r:xz') as tar:
        root = os.path.join(output_directory, tar.getmembers()[0].name)
        backup = root + '.bak'

        if os.path.isdir(root):
            if os.path.isdir(backup):
                try:
                    shutil.rmtree(backup)
                except OSError as e:
                    print(e)
                    sys.exit(1)
            elif os.path.isfile(backup):
                print(backup, 'file exists.')
                sys.exit(1)

            os.rename(root, backup)
        elif os.path.isfile(root):
            print(root, 'file exists.')
            sys.exit(1)

        try:
            tar.extractall(path=output_directory)
        except (OSError, tarfile.FilterError) as e:
            print(e)
            sys.exit(1)

        if os.path.isdir(backup):
            try:
                shutil.rmtree(backup)
            except OSError as e:
                print(e)
                sys.exit(1)

def delete_shortcut(base, program_group_base=None, icon_directory=None):
    if icon_directory:
        icon = os.path.join(icon_directory, base + '.ico')
    else:
        icon = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])),
                            base + '.ico')
    if os.path.exists(icon):
        try:
            os.remove(icon)
        except OSError as e:
            print(e)
            sys.exit(1)

    program_group = get_program_group(program_group_base)
    title = re.sub(r'[\W_]+', ' ', base).strip().title()
    shortcut = os.path.join(program_group, title + '.lnk')
    if os.path.exists(shortcut):
        try:
            os.remove(shortcut)
        except OSError as e:
            print(e)
            sys.exit(1)
    if os.path.isdir(program_group) and not os.listdir(program_group):
        try:
            os.rmdir(program_group)
        except OSError as e:
            print(e)
            sys.exit(1)

def extract_commands(source, command='command'):
    commands = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Compare):
                left = test.left
                if isinstance(left, ast.Name) and left.id == command:
                    comparator = test.comparators[0]
                    if isinstance(comparator, ast.Constant):
                        commands.append(comparator.value)
    return commands

def get_file_description(executable):
    if WINDOWS_IMPORT_ERROR:
        print(WINDOWS_IMPORT_ERROR)
        return False

    try:
        language, codepage = win32api.GetFileVersionInfo(
            executable, r'\VarFileInfo\Translation')[0]
        string_file_info = (fr'\StringFileInfo\{language:04x}{codepage:04x}'
                            r'\FileDescription')
        file_description = win32api.GetFileVersionInfo(executable,
                                                       string_file_info)
    except pywintypes.error as e:
        print(e)
        file_description = False

    return file_description

def get_program_group(program_group_base=None):
    if WINDOWS_IMPORT_ERROR:
        print(WINDOWS_IMPORT_ERROR)
        return False

    shell = win32com.client.Dispatch('WScript.Shell')
    if not program_group_base:
        base = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        program_group_base = re.sub(r'[\W_]+', ' ', base).strip().title()

    program_group = os.path.join(shell.SpecialFolders('Programs'),
                                 program_group_base)
    return program_group

def is_writing(target_path):
    return bool(os.path.exists(target_path)
                and time.time() - os.path.getmtime(target_path) < 1)

def move_to_trash(path, option=None):
    command = ['trash-put', path]
    if option:
        command.insert(1, option)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(e)

def select_executable(executables):
    for executable in executables:
        path = shutil.which(executable)
        if path:
            return path
    return False

def title_except_acronyms(string, acronyms):
    words = string.split()
    for i, _ in enumerate(words):
        if words[i] not in acronyms:
            words[i] = words[i].title()
    return ' '.join(words)

def write_chapter(video, current_title, previous_title=None, offset=None):
    if is_writing(video):
        ffmpeg_metadata = os.path.splitext(video)[0] + '.txt'
        try:
            offset = float(offset)
        except TypeError:
            offset = 0.0
        except ValueError as e:
            print(e)
            offset = 0.0

        start = int(1000 * (time.time() - os.path.getctime(video) + offset))
        default_duration = 60000
        end = start + default_duration

        if os.path.exists(ffmpeg_metadata):
            with open(ffmpeg_metadata, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for i in reversed(range(len(lines))):
                if 'END=' in lines[i]:
                    lines[i] = re.sub(r'END=\d+', f'END={start - 1}', lines[i])
                    with open(ffmpeg_metadata, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    break

            chapter = f'''
[CHAPTER]
TIMEBASE=1/1000
START={start}
END={end}
title={current_title}
'''
            with open(ffmpeg_metadata, 'a', encoding='utf-8') as f:
                f.write(chapter)
        else:
            chapters = f''';FFMETADATA1

[CHAPTER]
TIMEBASE=1/1000
START=0
END={start - 1}
title={previous_title}

[CHAPTER]
TIMEBASE=1/1000
START={start}
END={end}
title={current_title}
'''
            with open(ffmpeg_metadata, 'w', encoding='utf-8') as f:
                f.write(chapters)
