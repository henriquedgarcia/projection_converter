#!/usr/bin/env
import glob
import os
import time
import json
from pathlib import Path


class Converter:
    in_file: str = None
    config: dict = None
    app = 'bin/360ConvertAppStatic'
    uncompressed = False

    @property
    def compressed_file(self):
        return f'output/{self.name}_{self.conversion}.mp4'

    @property
    def name(self):
        return os.path.split(self.in_file)[1][:-4]

    @property
    def uncompressed_file(self):
        if self.uncompressed:
            path = f'{self.folder}/{self.name}.yuv'
        else:
            path = f'temp/{self.name}.yuv'

        return path

    @property
    def converted_file(self):
        return f'temp/{self.name}_converted_{self.conversion}.yuv'

    def __init__(self, origin_folder, conversion, duration=None, overwrite=False, remove_yuv=False):
        self.folder = Path(origin_folder)
        self.conversion = conversion
        self.duration = duration
        self.overwrite = overwrite
        self.remove_yuv = remove_yuv

        os.makedirs('temp/', exist_ok=True)

        self._config()
        self._run()

    def _config(self):
        with open('config.json', 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        try:
            self.params = self.config[self.conversion]
        except KeyError:
            KeyError('Conversion mode not exist.')

    def _run(self):
        for self.in_file in glob.glob(f'{self.folder}/*.mp4'):
            self.uncompress()
            self.converter()
            self.compress()

            if self.remove_yuv:
                os.remove(self.uncompressed_file)
                os.remove(self.converted_file)

        for self.in_file in glob.glob(f'{self.folder}/*.yuv'):
            self.uncompressed = True
            self.converter()
            self.compress()

            os.remove(self.converted_file)

    def uncompress(self):
        input_scale = self.params['input_scale']
        dar = self.params['dar']
        in_file = self.in_file
        out_file = self.uncompressed_file
        duration = self.duration
        log_file = f'{out_file[:-4]}.log'
        overwrite = self.overwrite

        if os.path.exists(out_file) and not overwrite:
            print(f'{self.uncompressed_file} exist. Skipping.')
            return

        command = f'ffmpeg -y -i {in_file} -vf "scale={input_scale},setdar={dar}" '
        if duration:
            command += f'-t {duration} '

        command += f'{out_file} |& tee {log_file}'
        self.run_command(command)

    def converter(self):
        in_file = self.uncompressed_file
        out_file = self.converted_file
        log_file = f'{out_file[:-4]}.log'
        output_scale = self.params['output_scale']
        boring_name = out_file.replace('.yuv', f'_{output_scale}_30Hz_8b_420.yuv')
        overwrite = self.overwrite

        print(f'Converting {in_file} to {out_file}\n'
              f'mode = {self.conversion}\n'
              f'overwrite = {self.overwrite}\n'
              )

        if os.path.exists(boring_name):
            os.renames(boring_name, out_file)

        if os.path.exists(out_file) and not overwrite:
            print(f'{out_file} exist. Skipping Conversion.')
            return

        params = self.params['params']
        params['InputFile'] = f'{in_file}'
        params['OutputFile'] = f'{out_file}'

        template = self.read_template()
        config = template.format(**params)

        config_file = f'{out_file[:-4]}.cfg'
        with open(config_file, 'w', encoding='utf-8') as fd:
            fd.write(config)

        command = f'{self.app} -c {config_file} |& tee {log_file}'

        self.run_command(command)
        os.renames(boring_name, out_file)

    def compress(self):
        in_file = self.converted_file
        out_file = self.compressed_file
        log_file = f'{out_file[:-4]}.log'
        overwrite = self.overwrite
        output_scale = self.params['output_scale']

        print(f'Compressing {in_file} to {out_file}\n'
              f'output_scale = {output_scale}\n'
              f'overwrite = {self.overwrite}\n'
              )
        if os.path.exists(out_file) and not overwrite:
            print(f'{out_file} exist. Skipping.')
            return

        command = (f'ffmpeg -y -f rawvideo -video_size {output_scale} -framerate 30'
                   f' -i {in_file} -crf 0 {out_file}')
        command = f'{command} |& tee {log_file}'

        self.run_command(command)

    @staticmethod
    def save_config(config, filename):
        with open(filename, 'w', encoding='utf-8') as fd:
            fd.write(config)

    @staticmethod
    def read_template() -> str:
        with open('template.cfg', 'r') as fd:
            template = fd.read()
        return template

    @staticmethod
    def run_command(command: str):
        start_time = time.time()

        command = f'bash -c \'{command}\''
        print(command)
        os.system(command)

        print(f'\nCompleted in {int(time.time() - start_time)} seg.')


if __name__ == '__main__':
    # Converter(origin_folder='erp', conversion='erp2cmp', duration=1, overwrite=False, remove_yuv=False)
    Converter(origin_folder='cmp', conversion='cmp2erp', duration=1, overwrite=False, remove_yuv=False)
