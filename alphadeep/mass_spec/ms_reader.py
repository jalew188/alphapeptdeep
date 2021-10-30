# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/mass_spec/ms_reader.ipynb (unless otherwise specified).

__all__ = ['MSReaderBase', 'AlphaPept_HDF_MS1_Reader', 'AlphaPept_HDF_MS2_Reader', 'read_until', 'find_line',
           'parse_pfind_scan_from_TITLE', 'is_pfind_mgf', 'MGFReader', 'MSReaderProvider', 'ms2_reader_provider',
           'ms1_reader_provider']

# Cell
import os
import numpy as np

class MSReaderBase:
    def __init__(self):
        self.scan_idx_dict = {}
        self.masses: np.array = None
        self.intens: np.array = None

    def load(self, file_path):
        raise NotImplementedError('load()')

    def get_peaks(self, scan_no):
        start_idx, end_idx = self.scan_idx_dict[scan_no]
        return (
            self.masses[start_idx:end_idx],
            self.intens[start_idx:end_idx]
        )

class AlphaPept_HDF_MS1_Reader(MSReaderBase):
    def load(self, file_path):
        from alphapept.io import HDF_File
        hdf_file = HDF_File(file_path)
        self.ms_data = {}
        for dataset_name in hdf_file.read(group_name="Raw/MS1_scans"):
            values = hdf_file.read(
                dataset_name=dataset_name,
                group_name="Raw/MS1_scans",
            )
            self.ms_data[dataset_name] = values
        self.scan_idx_dict = {}
        ms_indices = self.ms_data['indices_ms1']
        self.masses = self.ms_data['mass_list_ms1']
        self.intens = self.ms_data['int_list_ms1']
        for i,scan in enumerate(self.ms_data['scan_list_ms1']):
            self.scan_idx_dict[scan] = (ms_indices[i], ms_indices[i+1])

class AlphaPept_HDF_MS2_Reader(MSReaderBase):
    def load(self, file_path):
        from alphapept.io import HDF_File
        hdf_file = HDF_File(file_path)
        self.ms_data = {}
        for dataset_name in hdf_file.read(group_name="Raw/MS2_scans"):
            values = hdf_file.read(
                dataset_name=dataset_name,
                group_name="Raw/MS2_scans",
            )
            self.ms_data[dataset_name] = values
        self.scan_idx_dict = {}
        ms_indices = self.ms_data['indices_ms2']
        self.masses = self.ms_data['mass_list_ms2']
        self.intens = self.ms_data['int_list_ms2']
        for i,scan in enumerate(self.ms_data['scan_list_ms2']):
            self.scan_idx_dict[scan] = (ms_indices[i], ms_indices[i+1])

def read_until(file, until):
    lines = []
    while True:
        line = file.readline().strip()
        if line.startswith(until):
            break
        else:
            lines.append(line)
    return lines

def find_line(lines, start):
    for line in lines:
        if line.startswith(start):
            return line
    return None

def parse_pfind_scan_from_TITLE(pfind_title):
    return int(pfind_title.split('.')[-4])

def is_pfind_mgf(mgf):
    return mgf.upper().endswith('_HCDFT.MGF')

class MGFReader(MSReaderBase):
    def load(self, mgf):
        if isinstance(mgf, str):
            f = open(mgf)
        else:
            f = mgf
        scanset = set()
        masses_list = []
        intens_list = []
        scan_list = []
        while True:
            line = f.readline()
            if not line: break
            if line.startswith('BEGIN IONS'):
                lines = read_until(f, 'END IONS')
                masses = []
                intens = []
                scan = None
                for line in lines:
                    if line[0].isdigit():
                        mass,inten = [float(i) for i in line.strip().split()]
                        masses.append(mass)
                        intens.append(inten)
                    elif line.startswith('SCAN='):
                        scan = int(line.split('=')[1])
                if not scan:
                    title = find_line(lines, 'TITLE=')
                    scan = parse_pfind_scan_from_TITLE(title)
                if scan in scanset: continue
                scanset.add(scan)
                scan_list.append(scan)
                masses_list.append(np.array(masses))
                intens_list.append(np.array(intens))
        f.close()
        indices = np.zeros(len(masses_list)+1, dtype=np.int64)
        indices[1:] = [len(_) for _ in masses_list]
        indices = np.cumsum(indices)
        self.scan_idx_dict = {}
        for i,scan in enumerate(scan_list):
            self.scan_idx_dict[scan] = (indices[i], indices[i+1])
        self.masses = np.concatenate(masses_list)
        self.intens = np.concatenate(intens_list)

class MSReaderProvider:
    def __init__(self):
        self.reader_dict = {}
    def register_reader(self, ms2_type, reader_class):
        self.reader_dict[ms2_type.lower()] = reader_class

    def get_reader(self, file_type)->MSReaderBase:
        if file_type not in self.reader_dict: return None
        else: return self.reader_dict[file_type.lower()]()

ms2_reader_provider = MSReaderProvider()
ms2_reader_provider.register_reader('mgf', MGFReader)
ms2_reader_provider.register_reader('alphapept', AlphaPept_HDF_MS2_Reader)

ms1_reader_provider = MSReaderProvider()
ms1_reader_provider.register_reader('alphapept', AlphaPept_HDF_MS1_Reader)