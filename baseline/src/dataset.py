import os
import urllib2
import socket
import locale
import zipfile
import tarfile
import csv
import math
import numpy
from sklearn.cross_validation import StratifiedShuffleSplit, KFold
from IPython import embed
import pdb

from ui import *
from general import *
from files import *


# Base class
class Dataset(object):
    def __init__(self, data_path='data'):
        if not hasattr(self, 'name'):
            self.name = 'dataset'
        if not hasattr(self, 'evaluation_setup_folder'):
            self.evaluation_setup_folder = 'evaluation_setup'
        if not hasattr(self, 'meta_filename'):
            self.meta_filename = 'meta.txt'
        if not hasattr(self, 'filelisthash_filename'):
            self.filelisthash_filename = 'filelist.hash'

        self.local_path = os.path.join(data_path, self.name)

        if not os.path.isdir(self.local_path):
            os.makedirs(self.local_path)

        self.meta_file = os.path.join(self.local_path, self.meta_filename)
        self.evaluation_setup_path = os.path.join(self.local_path, self.evaluation_setup_folder)

        self.package_list = []

        self.files = None
        self.meta_data = None
        self.evaluation_data_train = {}
        self.evaluation_data_test = {}
        self.audio_extensions = {'wav', 'flac'}

    def print_bytes(self, num_bytes):
        """
        Output number of bytes according to locale and with IEC binary prefixes
        """
        KiB = 1024
        MiB = KiB * KiB
        GiB = KiB * MiB
        TiB = KiB * GiB
        PiB = KiB * TiB
        EiB = KiB * PiB
        ZiB = KiB * EiB
        YiB = KiB * ZiB
        locale.setlocale(locale.LC_ALL, '')
        output = locale.format("%d", num_bytes, grouping=True) + ' bytes'
        if num_bytes > YiB:
            output += ' (%.3g YiB)' % (num_bytes / YiB)
        elif num_bytes > ZiB:
            output += ' (%.3g ZiB)' % (num_bytes / ZiB)
        elif num_bytes > EiB:
            output += ' (%.3g EiB)' % (num_bytes / EiB)
        elif num_bytes > PiB:
            output += ' (%.3g PiB)' % (num_bytes / PiB)
        elif num_bytes > TiB:
            output += ' (%.3g TiB)' % (num_bytes / TiB)
        elif num_bytes > GiB:
            output += ' (%.3g GiB)' % (num_bytes / GiB)
        elif num_bytes > MiB:
            output += ' (%.3g MiB)' % (num_bytes / MiB)
        elif num_bytes > KiB:
            output += ' (%.3g KiB)' % (num_bytes / KiB)
        return output

    def download(self):
        """
        Download dataset over the internet
        """
        section_header('Download dataset')
        for item in self.package_list:
            try:
                if item['remote_package'] and not os.path.isfile(item['local_package']):
                    data = None
                    req = urllib2.Request(item['remote_package'], data, {})
                    handle = urllib2.urlopen(req)

                    if "Content-Length" in handle.headers.items():
                        size = int(handle.info()["Content-Length"])
                    else:
                        size = None
                    actualSize = 0
                    blocksize = 64 * 1024
                    tmp_file = os.path.join(self.local_path, 'tmp_file')
                    fo = open(tmp_file, "wb")
                    terminate = False
                    while not terminate:
                        block = handle.read(blocksize)
                        actualSize += len(block)
                        if size:
                            progress(title=self.name,
                                     percentage=actualSize / float(size),
                                     note=self.print_bytes(actualSize))
                        else:
                            progress(title=self.name,
                                     note=self.print_bytes(actualSize))

                        if len(block) == 0:
                            break
                        fo.write(block)
                    fo.close()
                    os.rename(tmp_file, item['local_package'])

            except (urllib2.URLError, socket.timeout), e:
                try:
                    fo.close()
                except:
                    raise IOError('Download failed [%s]' % (item['remote_package']))
        foot()

    def extract(self):
        """
        Extract the dataset package
        """
        section_header('Extract dataset')
        for item in self.package_list:
            if item['local_package']:
                if item['local_package'].endswith('.zip'):
                    with zipfile.ZipFile(item['local_package'], "r") as z:
                        members = z.infolist()
                        file_count = 1
                        for i, member in enumerate(members):
                            if not os.path.isfile(os.path.join(self.local_path, member.filename)):
                                z.extract(member, self.local_path)
                            progress(title='Extracting', percentage=(file_count / float(len(members))),
                                     note=member.filename)
                            file_count += 1

                elif item['local_package'].endswith('.tar.gz'):
                    tar = tarfile.open(item['local_package'], "r:gz")
                    for i, tar_info in enumerate(tar):
                        if not os.path.isfile(os.path.join(self.local_path, tar_info.name)):
                            tar.extract(tar_info, self.local_path)
                        progress(title='Extracting', note=tar_info.name)
                        tar.members = []
                    tar.close()
        foot()

    def on_after_extract(self):
        """
        Dataset meta data preparation
        """
        pass

    def get_filelist(self):
        filelist = []
        for path, subdirs, files in os.walk(self.local_path):
            for name in files:
                filelist.append(os.path.join(path, name))
        return filelist

    def check_filelist(self):
        if os.path.isfile(os.path.join(self.local_path, self.filelisthash_filename)):
            hash = load_text(os.path.join(self.local_path, self.filelisthash_filename))[0]
            if hash != get_parameter_hash(sorted(self.get_filelist())):
                return False
            else:
                return True
        else:
            return False

    def save_filelist_hash(self):
        filelist = self.get_filelist()

        filelist_hash_not_found = True
        for file in filelist:
            if self.filelisthash_filename in file:
                filelist_hash_not_found = False

        if filelist_hash_not_found:
            filelist.append(os.path.join(self.local_path, self.filelisthash_filename))

        save_text(os.path.join(self.local_path, self.filelisthash_filename), get_parameter_hash(sorted(filelist)))

    def fetch(self):
        """
        Download, extract and prepare the dataset.
        :return:
        """

        if not self.check_filelist():
            self.download()
            self.extract()
            self.on_after_extract()
            self.save_filelist_hash()

        return self

    @property
    def audio_files(self):
        """
        Get all audio files in the dataset
        :return: file list with absolute paths
        """
        if self.files is None:
            self.files = []
            for item in self.package_list:
                path = item['local_audio_path']
                if path:
                    l = os.listdir(path)
                    for f in l:
                        file_name, file_extension = os.path.splitext(f)
                        if file_extension[1:] in self.audio_extensions:
                            self.files.append(os.path.abspath(os.path.join(path, f)))
            self.files.sort()
        return self.files

    @property
    def audio_file_count(self):
        """
        Get number of audio files in dataset
        :return: 
        """
        return len(self.audio_files)

    @property
    def meta(self):
        if self.meta_data is None:
            self.meta_data = []
            meta_id = 0
            if os.path.isfile(self.meta_file):
                f = open(self.meta_file, 'rt')
                try:
                    reader = csv.reader(f, delimiter='\t')
                    for row in reader:
                        if len(row) == 2:
                            # Scene meta
                            self.meta_data.append({'file': row[0], 'scene_label': row[1].rstrip().strip()})
                        elif len(row) == 4:
                            # Audio tagging meta
                            self.meta_data.append(
                                {'file': row[0], 'scene_label': row[1].rstrip().strip(), 'tag_string': row[2],
                                 'tags': row[3].split(';')})
                        elif len(row) == 6:
                            # Event meta
                            self.meta_data.append({'file': row[0],
                                                   'scene_label': row[1].rstrip().strip(),
                                                   'event_onset': float(row[2]),
                                                   'event_offset': float(row[3]),
                                                   'event_label': row[4],
                                                   'event_type': row[5],
                                                   'id': meta_id
                                                   })
                        meta_id += 1
                finally:
                    f.close()
            else:
                raise IOError("Meta file missing [%s]" % self.meta_file)

        return self.meta_data

    @property
    def meta_count(self):
        return len(self.meta)

    @property
    def fold_count(self):
        return self.evaluation_folds

    @property
    def scene_label_count(self):
        return len(self.scene_labels)

    @property
    def scene_labels(self):
        labels = []
        for item in self.meta:
            if 'scene_label' in item and item['scene_label'] not in labels:
                labels.append(item['scene_label'])
        labels.sort()
        return labels

    @property
    def event_label_count(self):
        return len(self.event_labels)

    @property
    def event_labels(self):
        labels = []
        for item in self.meta:
            if 'event_label' in item and item['event_label'] not in labels:
                labels.append(item['event_label'])
        labels.sort()
        return labels

    @property
    def audio_tags(self):
        tags = []
        for item in self.meta:
            if 'tags' in item:
                for tag in item['tags']:
                    if tag and tag not in tags:
                        tags.append(tag)
        tags.sort()
        return tags

    @property
    def audio_tag_count(self):
        return len(self.audio_tags)

    def __getitem__(self, i):
        if i < len(self.meta):
            return self.meta[i]
        else:
            return None

    def __iter__(self):
        i = 0
        meta = self[i]

        # yield window while it's valid
        while (meta is not None):
            yield meta
            # get next item
            i += 1
            meta = self[i]

    def train(self, fold=0):
        if fold not in self.evaluation_data_train:
            self.evaluation_data_train[fold] = []
            if fold > 0:
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt'), 'rt') as f:
                    for row in csv.reader(f, delimiter='\t'):
                        if len(row) == 2:
                            # Scene meta
                            self.evaluation_data_train[fold].append({
                                'file': self.relative_to_absolute_path(row[0]),
                                'scene_label': row[1]
                            })
                        elif len(row) == 4:
                            # Audio tagging meta
                            self.evaluation_data_train[fold].append({
                                'file': self.relative_to_absolute_path(row[0]),
                                'scene_label': row[1],
                                'tag_string': row[2],
                                'tags': row[3].split(';')
                            })
                        elif len(row) == 5:
                            # Event meta
                            self.evaluation_data_train[fold].append({
                                'file': self.relative_to_absolute_path(row[0]),
                                'scene_label': row[1],
                                'event_onset': float(row[2]),
                                'event_offset': float(row[3]),
                                'event_label': row[4]
                            })
            else:
                data = []
                for item in self.meta:
                    if 'event_label' in item:
                        data.append({'file': self.relative_to_absolute_path(item['file']),
                                     'scene_label': item['scene_label'],
                                     'event_onset': item['event_onset'],
                                     'event_offset': item['event_offset'],
                                     'event_label': item['event_label'],
                                     })
                    else:
                        data.append({'file': self.relative_to_absolute_path(item['file']),
                                     'scene_label': item['scene_label']
                                     })
                self.evaluation_data_train[0] = data

        return self.evaluation_data_train[fold]

    def test(self, fold=0):
        if fold not in self.evaluation_data_test:
            self.evaluation_data_test[fold] = []
            if fold > 0:
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt'), 'rt') as f:
                    for row in csv.reader(f, delimiter='\t'):
                        self.evaluation_data_test[fold].append({'file': self.relative_to_absolute_path(row[0])})
            else:
                data = []
                files = []
                for item in self.meta:
                    if self.relative_to_absolute_path(item['file']) not in files:
                        data.append({'file': self.relative_to_absolute_path(item['file'])})
                        files.append(self.relative_to_absolute_path(item['file']))

                self.evaluation_data_test[fold] = data

        return self.evaluation_data_test[fold]

    def folds(self, mode='folds'):
        if mode == 'folds':
            return range(1, self.evaluation_folds + 1)
        elif mode == 'full':
            return [0]

    def file_meta(self, file):
        file = self.absolute_to_relative(file)
        file_meta = []
        for item in self.meta:
            if item['file'] == file:
                file_meta.append(item)

        return file_meta

    def relative_to_absolute_path(self, path):
        return os.path.abspath(os.path.join(self.local_path, path))

    def absolute_to_relative(self, path):
        if path.startswith(os.path.abspath(self.local_path)):
            return os.path.relpath(path, self.local_path)
        else:
            return path

# DCASE2016
# =====================================================

class TUTAcousticScenes_2016_DevelopmentSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'TUT-acoustic-scenes-2016-development'

        self.authors = 'Annamaria Mesaros, Toni Heittola, and Tuomas Virtanen'
        self.name_remote = 'TUT Acoustic Scenes 2016 development'
        self.url = 'http://www.cs.tut.fi/sgn/arg/dcase2016/download/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Roland Edirol R-09'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 4

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio'),
            },
        ]

    def on_after_extract(self):
        if not os.path.isfile(self.meta_file):
            section_header('Generating meta file for dataset')
            meta_data = {}
            for fold in xrange(1, self.evaluation_folds):
                # Read train files in
                train_filename = os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt')
                f = open(train_filename, 'rt')
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    if row[0] not in meta_data:
                        meta_data[row[0]] = row[1]
                                    
                f.close()
                # Read evaluation files in
                eval_filename = os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_evaluate.txt')
                f = open(eval_filename, 'rt')
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    if row[0] not in meta_data:
                        meta_data[row[0]] = row[1]
                f.close()

            f = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(f, delimiter='\t')
                for file in meta_data:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)
                    label = meta_data[file]
                    writer.writerow((os.path.join(relative_path, raw_filename), label))
            finally:
                f.close()
            foot()

class TUTAcousticScenes_2016_EvaluationSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'TUT-acoustic-scenes-2016-evaluation'

        self.authors = 'Annamaria Mesaros, Toni Heittola, and Tuomas Virtanen'
        self.name_remote = 'TUT Acoustic Scenes 2016 evaluation'
        self.url = 'http://www.cs.tut.fi/sgn/arg/dcase2016/download/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Roland Edirol R-09'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 1

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio'),
            },
        ]

    def on_after_extract(self):
        eval_filename = os.path.join(self.evaluation_setup_path, 'evaluate.txt')

        if not os.path.isfile(self.meta_file) and os.path.isfile(eval_filename):
            section_header('Generating meta file for dataset')
            meta_data = {}

            f = open(eval_filename, 'rt')
            reader = csv.reader(f, delimiter='\t')
            for row in reader:
                if row[0] not in meta_data:
                    meta_data[row[0]] = row[1]

            f.close()

            f = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(f, delimiter='\t')
                for file in meta_data:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)
                    label = meta_data[file]
                    writer.writerow((os.path.join(relative_path, raw_filename), label))
            finally:
                f.close()
            foot()


# TUT sound events 2016 development and evaluation sets
class TUTSoundEvents_2016_DevelopmentSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'TUT-sound-events-2016-development'

        self.authors = 'Annamaria Mesaros, Toni Heittola, and Tuomas Virtanen'
        self.name_remote = 'TUT Sound Events 2016 development'
        self.url = 'http://www.cs.tut.fi/sgn/arg/dcase2016/download/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Roland Edirol R-09'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 4

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio'),
            },
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio', 'residential_area'),
            },
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio', 'home'),
            },
        ]

    def event_label_count(self, scene_label=None):
        return len(self.event_labels(scene_label=scene_label))

    def event_labels(self, scene_label=None):
        labels = []
        for item in self.meta:
            if scene_label is None or item['scene_label'] == scene_label:
                if 'event_label' in item and item['event_label'] not in labels:
                    labels.append(item['event_label'])
        labels.sort()
        return labels

    def on_after_extract(self):
        if not os.path.isfile(self.meta_file):
            meta_file_handle = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(meta_file_handle, delimiter='\t')
                for filename in self.audio_files:
                    raw_path, raw_filename = os.path.split(filename)
                    relative_path = self.absolute_to_relative(raw_path)
                    scene_label = relative_path.replace('audio', '')[1:]
                    base_filename, file_extension = os.path.splitext(raw_filename)

                    annotation_filename = os.path.join(self.local_path, relative_path.replace('audio', 'meta'), base_filename + '.ann')
                    if os.path.isfile(annotation_filename):
                        annotation_file_handle = open(annotation_filename, 'rt')
                        try:
                            annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                            for annotation_file_row in annotation_file_reader:
                                writer.writerow((os.path.join(relative_path, raw_filename),
                                                 scene_label,
                                                 float(annotation_file_row[0].replace(',', '.')),
                                                 float(annotation_file_row[1].replace(',', '.')),
                                                 annotation_file_row[2], 'm'))
                        finally:
                            annotation_file_handle.close()
            finally:
                meta_file_handle.close()

    def train(self, fold=0, scene_label=None):
        if fold not in self.evaluation_data_train:
            self.evaluation_data_train[fold] = {}
            for scene_label_ in self.scene_labels:
                if scene_label_ not in self.evaluation_data_train[fold]:
                    self.evaluation_data_train[fold][scene_label_] = []

                if fold > 0:
                    with open(os.path.join(self.evaluation_setup_path, scene_label_+'_fold' + str(fold) + '_train.txt'), 'rt') as f:
                        for row in csv.reader(f, delimiter='\t'):
                            if len(row) == 5:
                                # Event meta
                                self.evaluation_data_train[fold][scene_label_].append({
                                    'file': self.relative_to_absolute_path(row[0]),
                                    'scene_label': row[1],
                                    'event_onset': float(row[2]),
                                    'event_offset': float(row[3]),
                                    'event_label': row[4]
                                })
                else:
                    data = []
                    for item in self.meta:
                        if item['scene_label'] == scene_label_:
                            if 'event_label' in item:
                                data.append({'file': self.relative_to_absolute_path(item['file']),
                                             'scene_label': item['scene_label'],
                                             'event_onset': item['event_onset'],
                                             'event_offset': item['event_offset'],
                                             'event_label': item['event_label'],
                                             })
                    self.evaluation_data_train[0][scene_label_] = data

        if scene_label:
            return self.evaluation_data_train[fold][scene_label]
        else:
            data = []
            for scene_label_ in self.scene_labels:
                for item in self.evaluation_data_train[fold][scene_label_]:
                    data.append(item)
            return data

    def test(self, fold=0, scene_label=None):
        if fold not in self.evaluation_data_test:
            self.evaluation_data_test[fold] = {}
            for scene_label_ in self.scene_labels:
                if scene_label_ not in self.evaluation_data_test[fold]:
                    self.evaluation_data_test[fold][scene_label_] = []
                if fold > 0:
                    with open(os.path.join(self.evaluation_setup_path, scene_label_+'_fold' + str(fold) + '_test.txt'), 'rt') as f:
                        for row in csv.reader(f, delimiter='\t'):
                            self.evaluation_data_test[fold][scene_label_].append({'file': self.relative_to_absolute_path(row[0])})
                else:
                    data = []
                    files = []
                    for item in self.meta:
                        if scene_label_ in item:
                            if self.relative_to_absolute_path(item['file']) not in files:
                                data.append({'file': self.relative_to_absolute_path(item['file'])})
                                files.append(self.relative_to_absolute_path(item['file']))

                    self.evaluation_data_test[0][scene_label_] = data

        if scene_label:
            return self.evaluation_data_test[fold][scene_label]
        else:
            data = []
            for scene_label_ in self.scene_labels:
                for item in self.evaluation_data_test[fold][scene_label_]:
                    data.append(item)
            return data


class TUTSoundEvents_2016_EvaluationSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'TUT-sound-events-2016-evaluation'

        self.authors = 'Annamaria Mesaros, Toni Heittola, and Tuomas Virtanen'
        self.name_remote = 'TUT Sound Events 2016 evaluation'
        self.url = 'http://www.cs.tut.fi/sgn/arg/dcase2016/download/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Roland Edirol R-09'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 5

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio'),
            },
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio', 'home'),
            },
            {
                'remote_package': None,
                'local_package': None,
                'local_audio_path': os.path.join(self.local_path, 'audio', 'residential_area'),
            },
        ]
    @property
    def scene_labels(self):
        labels = ['home', 'residential_area']
        labels.sort()
        return labels

    def event_label_count(self, scene_label=None):
        return len(self.event_labels(scene_label=scene_label))

    def event_labels(self, scene_label=None):
        labels = []
        for item in self.meta:
            if scene_label is None or item['scene_label'] == scene_label:
                if 'event_label' in item and item['event_label'] not in labels:
                    labels.append(item['event_label'])
        labels.sort()
        return labels

    def on_after_extract(self):
        if not os.path.isfile(self.meta_file) and os.path.isdir(os.path.join(self.local_path,'meta')):
            meta_file_handle = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(meta_file_handle, delimiter='\t')
                for filename in self.audio_files:
                    raw_path, raw_filename = os.path.split(filename)
                    relative_path = self.absolute_to_relative(raw_path)
                    scene_label = relative_path.replace('audio', '')[1:]
                    base_filename, file_extension = os.path.splitext(raw_filename)

                    annotation_filename = os.path.join(self.local_path, relative_path.replace('audio', 'meta'), base_filename + '.ann')
                    if os.path.isfile(annotation_filename):
                        annotation_file_handle = open(annotation_filename, 'rt')
                        try:
                            annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                            for annotation_file_row in annotation_file_reader:
                                writer.writerow((os.path.join(relative_path, raw_filename),
                                                 scene_label,
                                                 float(annotation_file_row[0].replace(',', '.')),
                                                 float(annotation_file_row[1].replace(',', '.')),
                                                 annotation_file_row[2], 'm'))
                        finally:
                            annotation_file_handle.close()
            finally:
                meta_file_handle.close()

    def train(self, fold=0, scene_label=None):
        raise IOError('Train setup not available.')

    def test(self, fold=0, scene_label=None):
        if fold not in self.evaluation_data_test:
            self.evaluation_data_test[fold] = {}
            for scene_label_ in self.scene_labels:
                if scene_label_ not in self.evaluation_data_test[fold]:
                    self.evaluation_data_test[fold][scene_label_] = []

                if fold > 0:
                    with open(os.path.join(self.evaluation_setup_path, scene_label + '_fold' + str(fold) + '_test.txt'), 'rt') as f:
                        for row in csv.reader(f, delimiter='\t'):
                            self.evaluation_data_test[fold][scene_label_].append({'file': self.relative_to_absolute_path(row[0])})
                else:
                    data = []
                    files = []
                    for item in self.audio_files:
                        if scene_label_ in item:
                            if self.relative_to_absolute_path(item) not in files:
                                data.append({'file': self.relative_to_absolute_path(item)})
                                files.append(self.relative_to_absolute_path(item))

                    self.evaluation_data_test[0][scene_label_] = data

        if scene_label:
            return self.evaluation_data_test[fold][scene_label]
        else:
            data = []
            for scene_label_ in self.scene_labels:
                for item in self.evaluation_data_test[fold][scene_label_]:
                    data.append(item)
            return data

                      
# DCASE2013
# =====================================================
class DCASE2013_Scene_DevelopmentSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'DCASE2013-scene-development'

        self.authors = 'Dimitrios Giannoulis, Emmanouil Benetos, Dan Stowell, and Mark Plumbley'
        self.name_remote = 'IEEE AASP 2013 CASA Challenge - Public Dataset for Scene Classification Task'
        self.url = 'http://www.elec.qmul.ac.uk/digitalmusic/sceneseventschallenge/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Unknown'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 5

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': 'http://c4dm.eecs.qmul.ac.uk/rdr/bitstream/handle/123456789/29/scenes_stereo.zip?sequence=1',
                'local_package': os.path.join(self.local_path, 'scenes_stereo.zip'),
                'local_audio_path': os.path.join(self.local_path, 'scenes_stereo'),
            }
        ]

    def on_after_extract(self):
        # Make legacy dataset compatible with DCASE2016 dataset scheme
        if not os.path.isfile(self.meta_file):
            section_header('Generating meta file for dataset')
            f = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(f, delimiter='\t')
                for file in self.audio_files:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)
                    label = os.path.splitext(os.path.split(file)[1])[0][:-2]
                    writer.writerow((os.path.join(relative_path, raw_filename), label))
            finally:
                f.close()
            foot()

        all_folds_found = True
        for fold in xrange(1, self.evaluation_folds):
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt')):
                all_folds_found = False
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt')):
                all_folds_found = False

        if not all_folds_found:
            section_header('Generating evaluation setup files for dataset')
            if not os.path.isdir(self.evaluation_setup_path):
                os.makedirs(self.evaluation_setup_path)

            classes = []
            files = []
            for item in self.meta:
                classes.append(item['scene_label'])
                files.append(item['file'])
            files = numpy.array(files)

            sss = StratifiedShuffleSplit(y=classes, n_iter=self.evaluation_folds, test_size=0.3, random_state=0)
            fold = 1
            for train_index, test_index in sss:
                # print("TRAIN:", train_index, "TEST:", test_index)
                train_files = files[train_index]

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in train_files:
                        raw_path, raw_filename = os.path.split(file)
                        label = self.file_meta(file)[0]['scene_label']
                        writer.writerow([os.path.join(raw_path, raw_filename), label])

                test_files = files[test_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        writer.writerow([os.path.join(raw_path, raw_filename)])

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_evaluate.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        label = self.file_meta(file)[0]['scene_label']
                        writer.writerow([os.path.join(raw_path, raw_filename), label])

                fold += 1
            foot()


class DCASE2013_Scene_ChallengeSet(DCASE2013_Scene_DevelopmentSet):
    def __init__(self, data_path='data'):
        self.name = 'DCASE2013-scene-challenge'

        self.authors = 'Dimitrios Giannoulis, Emmanouil Benetos, Dan Stowell, and Mark Plumbley'
        self.name_remote = 'IEEE AASP 2013 CASA Challenge - Private Dataset for Scene Classification Task'
        self.url = 'http://www.elec.qmul.ac.uk/digitalmusic/sceneseventschallenge/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Unknown'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 5

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': 'https://archive.org/download/dcase2013_scene_classification_testset/scenes_stereo_testset.zip',
                'local_package': os.path.join(self.local_path, 'scenes_stereo_testset.zip'),
                'local_audio_path': os.path.join(self.local_path, 'scenes_stereo_testset'),
            }
        ]
    def on_after_extract(self):
        # Make legacy dataset compatible with DCASE2016 dataset scheme
        if not os.path.isfile(self.meta_file) or 1:
            section_header('Generating meta file for dataset')
            f = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(f, delimiter='\t')
                for file in self.audio_files:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)
                    label = os.path.splitext(os.path.split(file)[1])[0][:-2]
                    writer.writerow((os.path.join(relative_path, raw_filename), label))
            finally:
                f.close()
            foot()

        all_folds_found = True
        for fold in xrange(1, self.evaluation_folds):
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt')):
                all_folds_found = False
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt')):
                all_folds_found = False

        if not all_folds_found:
            section_header('Generating evaluation setup files for dataset')
            if not os.path.isdir(self.evaluation_setup_path):
                os.makedirs(self.evaluation_setup_path)

            classes = []
            files = []
            for item in self.meta:
                classes.append(item['scene_label'])
                files.append(item['file'])
            files = numpy.array(files)

            sss = StratifiedShuffleSplit(y=classes, n_iter=self.evaluation_folds, test_size=0.3, random_state=0)
            fold = 1
            for train_index, test_index in sss:

                train_files = files[train_index]

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in train_files:
                        raw_path, raw_filename = os.path.split(file)
                        label = self.file_meta(file)[0]['scene_label']
                        writer.writerow([os.path.join(raw_path, raw_filename), label])

                test_files = files[test_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        writer.writerow([os.path.join(raw_path, raw_filename)])

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_evaluate.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        label = self.file_meta(file)[0]['scene_label']
                        writer.writerow([os.path.join(raw_path, raw_filename), label])

                fold += 1
            foot()


class DCASE2013_Event_DevelopmentSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'DCASE2013-event-development'

        self.authors = 'Dimitrios Giannoulis, Emmanouil Benetos, Dan Stowell, and Mark Plumbley'
        self.name_remote = 'IEEE AASP CASA Challenge - Public Dataset for Event Detection Task'
        self.url = 'http://www.elec.qmul.ac.uk/digitalmusic/sceneseventschallenge/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Unknown'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 5

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': 'https://archive.org/download/dcase2013_event_detection_development_OS/events_OS_development_v2.zip',
                'local_package': os.path.join(self.local_path, 'events_OS_development_v2.zip'),
                'local_audio_path': os.path.join(self.local_path, 'events_OS_development_v2'),
            },
            # {
            #    'remote_package':'http://c4dm.eecs.qmul.ac.uk/rdr/bitstream/handle/123456789/28/singlesounds_annotation.zip?sequence=9',
            #    'local_package': os.path.join(self.local_path, 'singlesounds_annotation.zip'),
            #    'local_audio_path': None,
            # },
            # {
            #    'remote_package':'http://c4dm.eecs.qmul.ac.uk/rdr/bitstream/handle/123456789/28/singlesounds_stereo.zip?sequence=7',
            #    'local_package': os.path.join(self.local_path, 'singlesounds_stereo.zip'),
            #    'local_audio_path': os.path.join(self.local_path, 'singlesounds_stereo'),
            # },
        ]

    def on_after_extract(self):
        # Make legacy dataset compatible with DCASE2016 dataset scheme
        scene_label = 'office'
        if not os.path.isfile(self.meta_file):
            meta_file_handle = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(meta_file_handle, delimiter='\t')
                for file in self.audio_files:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)

                    base_filename, file_extension = os.path.splitext(raw_filename)

                    if file.find('singlesounds_stereo') != -1:
                        annotation_filename = os.path.join(self.local_path, 'Annotation1', base_filename + '_bdm.txt')
                        label = base_filename[:-2]
                        if os.path.isfile(annotation_filename):
                            annotation_file_handle = open(annotation_filename, 'rt')
                            try:
                                annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                                for annotation_file_row in annotation_file_reader:
                                    writer.writerow((os.path.join(relative_path, raw_filename), scene_label,
                                                     annotation_file_row[0], annotation_file_row[1], label, 'i'))
                            finally:
                                annotation_file_handle.close()

                    elif file.find('events_OS_development_v2') != -1:
                        annotation_filename = os.path.join(self.local_path, 'events_OS_development_v2',
                                                           base_filename + '_v2.txt')
                        if os.path.isfile(annotation_filename):
                            annotation_file_handle = open(annotation_filename, 'rt')
                            try:
                                annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                                for annotation_file_row in annotation_file_reader:
                                    writer.writerow((os.path.join(relative_path, raw_filename), scene_label,
                                                     annotation_file_row[0], annotation_file_row[1],
                                                     annotation_file_row[2], 'm'))
                            finally:
                                annotation_file_handle.close()
            finally:
                meta_file_handle.close()

        all_folds_found = True
        for fold in xrange(1, self.evaluation_folds):
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt')):
                all_folds_found = False
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt')):
                all_folds_found = False

        if not all_folds_found:
            # Construct training and testing sets. Isolated sound are used for training and
            # polyphonic mixtures are used for testing.
            if not os.path.isdir(self.evaluation_setup_path):
                os.makedirs(self.evaluation_setup_path)

            files = []
            for item in self.meta:
                if item['file'] not in files:
                    files.append(item['file'])
            files = numpy.array(files)
            f = numpy.zeros(len(files))

            sss = StratifiedShuffleSplit(y=f, n_iter=5, test_size=0.3, random_state=0)
            fold = 1
            for train_index, test_index in sss:
                # print("TRAIN:", train_index, "TEST:", test_index)
                train_files = files[train_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in train_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        for item in self.meta:
                            if item['file'] == file:
                                writer.writerow([os.path.join(relative_path, raw_filename), item['scene_label'],
                                                 item['event_onset'], item['event_offset'], item['event_label']])

                test_files = files[test_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        writer.writerow([os.path.join(relative_path, raw_filename)])

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_evaluate.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        for item in self.meta:
                            if item['file'] == file:
                                writer.writerow([os.path.join(relative_path, raw_filename), item['scene_label'],
                                                 item['event_onset'], item['event_offset'], item['event_label']])

                fold += 1


class DCASE2013_Event_ChallengeSet(Dataset):
    def __init__(self, data_path='data'):
        self.name = 'DCASE2013-event-challenge'

        self.authors = 'Dimitrios Giannoulis, Emmanouil Benetos, Dan Stowell, and Mark Plumbley'
        self.name_remote = 'IEEE AASP CASA Challenge - Private Dataset for Event Detection Task'
        self.url = 'http://www.elec.qmul.ac.uk/digitalmusic/sceneseventschallenge/'
        self.audio_source = 'Field recording'
        self.audio_type = 'Natural'
        self.recording_device_model = 'Unknown'
        self.microphone_model = 'Soundman OKM II Klassik/studio A3 electret microphone'

        self.evaluation_folds = 5

        Dataset.__init__(self, data_path=data_path)

        self.package_list = [
            {
                'remote_package': 'https://archive.org/download/dcase2013_event_detection_testset_OS/dcase2013_event_detection_testset_OS.zip',
                'local_package': os.path.join(self.local_path, 'dcase2013_event_detection_testset_OS.zip'),
                'local_audio_path': os.path.join(self.local_path, 'dcase2013_event_detection_testset_OS'),
            }
        ]

    def on_after_extract(self):
        # Make legacy dataset compatible with DCASE2016 dataset scheme
        scene_label = 'office'

        if not os.path.isfile(self.meta_file):
            meta_file_handle = open(self.meta_file, 'wt')
            try:
                writer = csv.writer(meta_file_handle, delimiter='\t')
                for file in self.audio_files:
                    raw_path, raw_filename = os.path.split(file)
                    relative_path = self.absolute_to_relative(raw_path)

                    base_filename, file_extension = os.path.splitext(raw_filename)

                    if file.find('dcase2013_event_detection_testset_OS') != -1:
                        annotation_filename = os.path.join(self.local_path, 'dcase2013_event_detection_testset_OS',base_filename + '_v2.txt')
                        if os.path.isfile(annotation_filename):
                            annotation_file_handle = open(annotation_filename, 'rt')
                            try:
                                annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                                for annotation_file_row in annotation_file_reader:
                                    writer.writerow((os.path.join(relative_path, raw_filename), scene_label,
                                                     annotation_file_row[0], annotation_file_row[1],
                                                     annotation_file_row[2], 'm'))
                            finally:
                                annotation_file_handle.close()
                        else:
                            annotation_filename = os.path.join(self.local_path, 'dcase2013_event_detection_testset_OS',base_filename + '.txt')
                            if os.path.isfile(annotation_filename):
                                annotation_file_handle = open(annotation_filename, 'rt')
                                try:
                                    annotation_file_reader = csv.reader(annotation_file_handle, delimiter='\t')
                                    for annotation_file_row in annotation_file_reader:
                                        writer.writerow((os.path.join(relative_path, raw_filename), scene_label,
                                                         annotation_file_row[0], annotation_file_row[1],
                                                         annotation_file_row[2], 'm'))
                                finally:
                                    annotation_file_handle.close()
            finally:
                meta_file_handle.close()



        all_folds_found = True
        for fold in xrange(1, self.evaluation_folds):
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt')):
                all_folds_found = False
            if not os.path.isfile(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt')):
                all_folds_found = False

        if not all_folds_found:
            # Construct training and testing sets. Isolated sound are used for training and
            # polyphonic mixtures are used for testing.
            if not os.path.isdir(self.evaluation_setup_path):
                os.makedirs(self.evaluation_setup_path)

            files = []
            for item in self.meta:
                if item['file'] not in files:
                    files.append(item['file'])
            files = numpy.array(files)
            f = numpy.zeros(len(files))

            sss = StratifiedShuffleSplit(y=f, n_iter=5, test_size=0.3, random_state=0)
            fold = 1
            for train_index, test_index in sss:
                # print("TRAIN:", train_index, "TEST:", test_index)
                train_files = files[train_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_train.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in train_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        for item in self.meta:
                            if item['file'] == file:
                                writer.writerow([os.path.join(relative_path, raw_filename), item['scene_label'],
                                                 item['event_onset'], item['event_offset'], item['event_label']])

                test_files = files[test_index]
                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_test.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        writer.writerow([os.path.join(relative_path, raw_filename)])

                with open(os.path.join(self.evaluation_setup_path, 'fold' + str(fold) + '_evaluate.txt'), 'wt') as f:
                    writer = csv.writer(f, delimiter='\t')
                    for file in test_files:
                        raw_path, raw_filename = os.path.split(file)
                        relative_path = raw_path.replace(self.local_path + os.path.sep, '')
                        for item in self.meta:
                            if item['file'] == file:
                                writer.writerow([os.path.join(relative_path, raw_filename), item['scene_label'],
                                                 item['event_onset'], item['event_offset'], item['event_label']])

                fold += 1
