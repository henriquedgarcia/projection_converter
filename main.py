import subprocess
import glob
import os
import sys
import time
import shutil

erp_params = {'SourceWidth'       : '3840',
              'SourceHeight'      : '2160',
              'InputFile'         : None,
              'InputGeometryType' : '0',
              'SourceFPStructure' : '1 1   0 0',
              'CodingGeometryType': '1',
              'CodingFPStructure' : '2 3   4 0 0 0 5 0   3 180 1 270 2 0',
              'CodingFaceWidth'   : 960,
              'CodingFaceHeight'  : 960,
              }
cmp_params = {'SourceWidth'       : '2880',
              'SourceHeight'      : '1920',
              'InputFile'         : None,
              'InputGeometryType' : '1',
              'SourceFPStructure' : '2 3   4 0 0 0 5 0   3 180 1 270 2 0',
              'CodingGeometryType': '0',
              'CodingFPStructure' : '1 1   0 0',
              'CodingFaceWidth'   : 3840,
              'CodingFaceHeight'  : 2160,
              }


def main(folder, conversion, overwrite=False, remove_yuv=False):
    for in_file in glob.glob(f'{folder}/*.mp4'):
        name = os.path.split(in_file)[1][:-4]
        compressed_file = f'output/{name}_{conversion}.mp4'
        uncompressed_file = f'temp/{name}.yuv'
        converted_file = f'temp/{name}_{conversion}.yuv'

        if os.path.exists(compressed_file) and not overwrite:
            print(f'{compressed_file} exist. Skipping.')
            continue

        os.makedirs('temp/', exist_ok=True)

        uncompress(in_file, uncompressed_file, conversion, 10, overwrite)
        converter(uncompressed_file, converted_file, conversion, overwrite)
        compress(converted_file, compressed_file, conversion, overwrite)

        if remove_yuv:
            os.remove(uncompressed_file)
            os.remove(converted_file)
    shutil.rmtree('temp')


def uncompress(in_file, out_file, conversion, duration=None, overwrite=False):
    if os.path.exists(out_file) and not overwrite:
        print(f'{out_file} exist. Skipping.')
        return

    if conversion == 'cmp2erp':
        input_scale = '2880x1920'
        dar = '3/2'
    elif conversion == 'erp2cmp':
        input_scale = '3840x2160'
        dar = '2'
    else:
        raise KeyError(f'Conversão {conversion} não suportada.')

    cmd = f'ffmpeg -y -i {in_file} -vf "scale={input_scale},setdar={dar}" '
    if duration:
        cmd += f'-t {duration} '
    cmd += f'{out_file}'
    run_command(cmd)


def converter(in_file, out_file, conversion, overwrite=False):
    if conversion == 'erp2cmp':
        params = erp_params
        output_scale = '2880x1920'
        cf = 1
    elif conversion == 'cmp2erp':
        params = cmp_params
        output_scale = '3840x2160'
        cf = 0
    else:
        raise KeyError(f'Conversão {conversion} não suportada.')

    boring_name = out_file.replace('.yuv', f'_{output_scale}x8_cf1.yuv')
    if os.path.exists(boring_name):
        os.renames(boring_name, out_file)

    if os.path.exists(out_file) and not overwrite:
        print(f'{out_file} exist. Skipping.')
        return

    template = read_template()
    params['InputFile'] = f'{in_file}'
    config = template.format(**params)
    config_file = f'temp/{out_file[:-4]}.cfg'
    save_config(config, config_file)

    command = f'bin/TApp360ConvertStatic -c {config_file} -OutputFile {out_file}'

    if sys.platform.startswith('win32'):
        command = f'bash -c "{command}"'
    run_command(command)


def compress(in_file, out_file, conversion, overwrite=False):
    if conversion == 'erp2cmp':
        output_scale = '2880x1920'
    elif conversion == 'cmp2erp':
        output_scale = '3840x2160'
    else:
        raise KeyError(f'Conversão {conversion} não suportada.')

    command = (f'ffmpeg -y -f rawvideo -video_size {output_scale} -framerate 30 '
               f'-i {in_file} -crf 17 {out_file}')
    run_command(command)


def save_config(config, filename):
    with open(filename, 'w', encoding='utf-8') as fd:
        fd.write(config)


def read_template() -> str:
    with open('template.cfg', 'r') as fd:
        template = fd.read()
    return template


# def run_command(command: str) -> subprocess.Popen:
def run_command(command: str):
    """
    Run a shell command with subprocess module with realtime output.
    :param command: A command string to run.
    :return: A subprocess instance.
    """
    print(command)
    # subprocess.run(command, shell=True, stderr=subprocess.STDOUT,
    #                encoding='utf-8')
    start_time = time.time()
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, encoding='utf-8')
    while True:
        if process.poll() is not None:
            break
        print('.', end='', flush=True)
        time.sleep(1)
    print(f'\nCompleted in {int(time.time() - start_time)} seg')


if __name__ == '__main__':
    main('erp', 'erp2cmp')
    # main('cmp', 'cmp2erp')
