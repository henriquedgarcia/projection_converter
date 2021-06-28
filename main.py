#!/usr/bin/env
import os
import time
import json
from pathlib import Path
from enum import Enum
from fractions import Fraction


class Projection(Enum):
    ERP = 'erp'
    CMP = 'cmp'


class Config:
    json_data: dict
    config_raw: dict
    input_scale: str
    input_dar: str
    output_scale: str
    proj_in: Projection
    proj_out: Projection

    SourceWidth: str
    SourceHeight: str
    FrameRate: str
    InputFile: str
    InputGeometryType: str
    SourceFPStructure: str
    CodingGeometryType: str
    CodingFPStructure: str
    CodingFaceWidth: str
    CodingFaceHeight: str

    def __init__(self, filename, conversion: str):
        self.conversion = conversion
        self.filename = filename

        # Get projections from conversion
        proj_in, proj_out = conversion.split('2')
        self.proj_in = Projection(proj_in)
        self.proj_out = Projection(proj_out)

        # Open json
        with open(self.filename, 'r', encoding='utf-8') as f:
            self.json_data = json.load(f)

        # Set conversion config_raw
        self.config_raw = self.json_data[self.conversion]

        # Convert key to class attributes
        for key in self.config_raw:
            setattr(self, key, self.config_raw[key])

        # Make scale string to input and output
        self.input_scale = f'{self.SourceWidth}x{self.SourceHeight}'

        coding_face_h = self.CodingFaceHeight
        coding_face_w = self.CodingFaceWidth
        if self.proj_out is Projection.ERP:
            self.output_scale = f'{coding_face_w}x{coding_face_h}'
        elif self.proj_out is Projection.CMP:
            self.output_scale = f'{coding_face_w * 3}x{coding_face_h * 2}'

        # Find input DAR
        frac = Fraction(int(self.SourceWidth), int(self.SourceHeight))
        self.input_dar = '/'.join(map(str, frac.as_integer_ratio()))


class Converter:
    app = Path('bin/360ConvertAppStatic')
    template = Path('./template.cfg')
    output_folder = Path('output/')
    temp_folder = Path('temp/')
    uncompressed: bool = False
    in_file: Path

    @property
    def name(self) -> str:
        return self.in_file.stem

    @property
    def uncompressed_file(self) -> Path:
        if self.uncompressed:
            path = self.in_file
        else:
            path = self.temp_folder / f'{self.name}.yuv'
        return path

    @property
    def converted_file(self):
        stem = self.uncompressed_file.stem
        name = stem + f'_converted_{self.config.proj_out.name}.yuv'
        return self.temp_folder / name

    @property
    def compressed_file(self) -> Path:
        name = self.name + f'{self.config.output_scale}_{self.config.FrameRate}_{self.config.proj_out}'
        return self.output_folder / f'{name}.mp4'

    @property
    def boring_name(self):
        output_scale = self.config.output_scale
        stem = self.converted_file.stem
        new_stem = stem + f'_{output_scale}_30Hz_8b_420'
        return self.converted_file.with_stem(new_stem)

    def __init__(self, origin_folder, conversion: str, duration=None, overwrite=False, remove_yuv=False):
        self.origin_folder = Path(origin_folder)
        self.duration = duration
        self.overwrite = overwrite
        self.remove_yuv = remove_yuv

        self.temp_folder.mkdir(exist_ok=True)
        self.output_folder.mkdir(exist_ok=True)
        self.config = Config('config.json', conversion)
        self._run()

    def _run(self):
        for self.in_file in self.origin_folder.glob(f'*.mp4'):
            self._process()

        for self.in_file in self.origin_folder.glob(f'*.yuv'):
            self.uncompressed = True
            self._process()

    def _process(self):
        self.uncompress()
        self.converter()
        self.compress()
        if self.remove_yuv:
            if not self.uncompressed:
                self.uncompressed_file.unlink()
            self.converted_file.unlink()

    def uncompress(self):
        if self.uncompressed: return

        input_scale = self.config.input_scale
        dar = self.config.input_dar
        in_file = self.in_file
        uncompressed_file = self.uncompressed_file
        duration = self.duration
        log_file = uncompressed_file.with_suffix('.log')

        if os.path.exists(uncompressed_file) and not self.overwrite:
            print(f'{self.uncompressed_file} exist. Skipping.')
            return

        cmd = ['ffmpeg']
        cmd += [f'-y']
        cmd += [f'-i {in_file.as_posix()}']
        if duration: cmd += [f'-t {duration}']
        cmd += [f'-vf "scale={input_scale},setdar={dar}"']
        cmd += [f'{uncompressed_file.as_posix()}']
        cmd += [f'&> {log_file.as_posix()}']

        command = ' '.join(cmd)
        self.run_command(command)

    def converter(self):
        in_file = self.uncompressed_file
        out_file = self.converted_file
        boring_name = self.boring_name
        overwrite = self.overwrite

        print(f'Converting {in_file} to {out_file}\n'
              f'mode = {self.config.conversion}\n'
              f'overwrite = {self.overwrite}\n')

        if boring_name.exists():
            boring_name.rename(out_file)

        if out_file.exists() and not overwrite:
            print(f'{out_file} exist. Skipping Conversion.')
            return

        params = self.config.config_raw
        params['InputFile'] = in_file.as_posix()
        # params['OutputFile'] = f'{out_file}'

        config_file = out_file.with_suffix('.cfg')
        template = self.template.read_text(encoding='utf-8')
        config = template.format(**params)
        config_file.write_text(config, encoding='utf-8')

        log_file = out_file.with_suffix('.log')
        cmd = [f'{self.app.as_posix()}']
        cmd += [f'-c {config_file.as_posix()}']
        cmd += [f'-o {out_file.as_posix()}']
        cmd += [f'&> {log_file.as_posix()}']
        command = ' '.join(cmd)

        self.run_command(command)
        if boring_name.exists():
            boring_name.rename(out_file)

    def compress(self):
        in_file = self.converted_file
        out_file = self.compressed_file
        log_file = out_file.with_suffix('.log')
        overwrite = self.overwrite
        output_scale = self.config.output_scale
        fps = self.config.FrameRate

        print(f'Compressing {in_file} to {out_file}\n'
              f'output_scale = {output_scale}\n'
              f'overwrite = {overwrite}\n')

        if os.path.exists(out_file) and not overwrite:
            print(f'{out_file} exist. Skipping.')
            return

        cmd = ['ffmpeg']
        cmd += ['-y ']
        cmd += [f'-f rawvideo -video_size {output_scale} -framerate {fps}']
        cmd += [f'-i {in_file.as_posix()}']
        cmd += [f'-crf 0 {out_file.as_posix()}']
        cmd += [f'&> {log_file.as_posix()}']
        command = ' '.join(cmd)

        self.run_command(command)

    @staticmethod
    def run_command(command: str):
        start_time = time.time()
        command = f'bash -c "{command}"'
        print(command)
        os.system(command)
        print(f'\nCompleted in {int(time.time() - start_time)} seg.')


if __name__ == '__main__':
    # Converter(origin_folder='erp', conversion='erp2cmp', duration=1, overwrite=False, remove_yuv=False)
    Converter(origin_folder='cmp', conversion='cmp2erp', duration=1, overwrite=False, remove_yuv=False)
