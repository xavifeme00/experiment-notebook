#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate, analyze, expose and catalogue dataset entries.

The FilePropertiesTable class contains the minimal information about the file
as well as basic statistical measurements.

Subclasses of this table can be created adding extra columns.

The experiment.CompressionExperiment class takes an instance of FilePropertiesTable
to know what files the experiment should be run on.
"""
__author__ = "Miguel Hernández Cabronero <miguel.hernandez@uab.cat>"
__date__ = "18/09/2019"

import os
import hashlib
import math
import collections
import numpy as np
import re
import ray

from enb import atable
from enb.config import get_options

options = get_options()

# -------------------------- Begin configurable part

# Hash algorithm used to verify file integrity
hash_algorithm = "sha256"


# -------------------------- End configurable part

def get_canonical_path(file_path):
    """:return: the canonical path to be stored in the database.
    """
    if options.verbose > 1:
        print("TODO: Verify that the base path is not introduced in the DB")
    file_path = os.path.abspath(file_path)
    if options.base_dataset_dir is not None:
        dataset_prefix = os.path.abspath(options.base_dataset_dir)
        assert file_path.startswith(dataset_prefix)
        file_path = file_path.replace(dataset_prefix, "")
    return file_path


def get_valid_filename(s):
    s = str(s).strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)


def entropy(data):
    """Compute the zero-order entropy of the provided data
    """
    counter = collections.Counter(np.array(data, copy=False).flatten())
    total_sum = sum(counter.values())
    probabilities = (count / total_sum for value, count in counter.items())
    return -sum(p * math.log2(p) for p in probabilities)


class FilePropertiesTable(atable.ATable):
    version_name = "original"
    hash_field_name = f"{hash_algorithm}"
    base_dir = None

    def __init__(self, csv_support_path=None, base_dir=None):
        super().__init__(index="file_path", csv_support_path=csv_support_path)
        self.base_dir = base_dir


class FilePropertiesTable(FilePropertiesTable):
    """Table describing basic file properties (see decorated methods below).
    Unsigned 8-bit samples are assumed.
    """

    def get_relative_path(self, file_path):
        """Get the relative path. Overwritten to handle the versioned path.
        """
        file_path = os.path.abspath(file_path)
        if self.base_dir is not None:
            file_path = file_path.replace(os.path.abspath(self.base_dir), "")
        assert file_path[0] == "/"
        file_path = file_path[1:]
        return file_path

    @FilePropertiesTable.column_function(
        FilePropertiesTable.hash_field_name,
        label=f"{FilePropertiesTable.hash_field_name} hex digest")
    def set_hash_digest(self, file_path, series):
        """Store the hexdigest of file_path's contents, using hash_algorithm as configured.
        :param file_path: path to the file to analyze
        :param series: dictionary of previously computed values for this file_path (to speed up derived values)
        """
        hasher = hashlib.new(hash_algorithm)
        with open(file_path, "rb") as f:
            hasher.update(f.read())
        series[_column_name] = hasher.hexdigest()

    @FilePropertiesTable.column_function("size_bytes", label="File size (bytes)")
    def set_file_size(self, file_path, series):
        """Store the original file size in series
        :param file_path: path to the file to analyze
        :param series: dictionary of previously computed values for this file_path (to speed up derived values)
        """
        series[_column_name] = os.path.getsize(file_path)

    @FilePropertiesTable.column_function(
        atable.ColumnProperties(name="1B_value_counts",
                                label="1-byte value counts",
                                semilog_y=True, has_dict_values=True))
    def set_1B_value_counts(self, file_path, series):
        """Calculate a dict with the counts for each found byte value in file_path
        """
        series[_column_name] = dict(collections.Counter(
            np.fromfile(file_path, dtype="uint8").flatten()))

    @FilePropertiesTable.column_function(
        "entropy_1B_bps", label="Entropy (bps), 1-byte samples", plot_min=0, plot_max=8)
    def set_file_entropy(self, file_path, series):
        """Return the zero-order entropy of the data in file_path (1-byte samples are assumed)
        """
        value_count_dict = series["1B_value_counts"]
        total_sum = sum(value_count_dict.values())
        probabilities = [count / total_sum for count in value_count_dict.values()]
        series[_column_name] = - sum(p * math.log2(p) for p in probabilities)
        assert abs(series[_column_name] - entropy(np.fromfile(file_path, dtype="uint8"))) < 1e-12

    @FilePropertiesTable.column_function(
        [f"byte_value_{s}" for s in ["min", "max", "avg", "std"]])
    def set_byte_value_extrema(self, file_path, series):
        contents = np.fromfile(file_path, dtype="uint8")
        series["byte_value_min"] = contents.min()
        series["byte_value_max"] = contents.max()
        series["byte_value_avg"] = contents.mean()
        series["byte_value_std"] = contents.std()

    @FilePropertiesTable.column_function("samples", label="Sample count", plot_min=0)
    def set_samples(self, file_path, series):
        """Set the number of samples assuming 8-bit samples
        """
        series[_column_name] = series["size_bytes"]

    @FilePropertiesTable.column_function(
        "histogram_fullness_1byte", label="Histogram usage fraction (1 byte)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_1byte(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 1-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint8)).size / (2 ** 8)
        assert 0 <= series[_column_name] <= 1

    @FilePropertiesTable.column_function(
        "histogram_fullness_2bytes", label="Histogram usage fraction (2 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_2bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 2-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint16)).size / (2 ** 16)
        assert 0 <= series[_column_name] <= 1

    @FilePropertiesTable.column_function(
        "histogram_fullness_4bytes", label="Histogram usage fraction (4 bytes)",
        plot_min=0, plot_max=1)
    def set_histogram_fullness_4bytes(self, file_path, series):
        """Set the fraction of the histogram (of all possible values that can
        be represented) is actually present in file_path, considering 4-byte samples.
        """
        series[_column_name] = np.unique(np.fromfile(
            file_path, dtype=np.uint32)).size / (2 ** 32)
        assert 0 <= series[_column_name] <= 1


class FileVersionTable(FilePropertiesTable):
    pass


class FileVersionTable(FileVersionTable):
    """Table to gather FilePropertiesTable information from a
    version of the original files.

    IMPORTANT: FileVersionTable is intended to be defined as parent class
      _before_ the table class to be versioned, e.g.:

          class MyVersion(FileVersionTable, FilePropertiesTable):
            pass
    """

    def __init__(self, original_base_dir, version_base_dir,
                 original_properties_table, version_name,
                 csv_support_path=None):
        """
        :param original_base_dir: path to the original directory
          (it must contain all indices requested later with self.get_df())
        :param version_base_dir: path to the versioned base directory
          (versioned directories preserve names and structure within
          the base dir)
        :param version_name: name of this file version
        :param csv_support_path: path to the file where results are to be
          long-term stored
        """
        super().__init__(csv_support_path=csv_support_path, base_dir=version_base_dir)
        self.original_base_dir = original_base_dir
        self.original_properties_table = original_properties_table
        self.version_base_dir = version_base_dir
        self.version_name = version_name

    def version(self, input_path, output_path, file_info):
        """Create a version of input_path and save it into output_path.
        :param input_path: path to the file to be versioned
        :param output_path: path where the version should be saved
        :param file_info: metainformation available using super().get_df
          for input_path
        """
        raise NotImplementedError()

    @FileVersionTable.column_function("original_file_path")
    def set_original_file_path(self, file_path, series):
        series[_column_name] = get_canonical_path(file_path.replace(self.version_base_dir, self.original_base_dir))

    def get_df(self, target_indices, fill=True, overwrite=False,
               parallel_versioning=True, parallel_row_processing=True,
               target_columns=None):
        """Create a version of target_indices (which must all be contained
        in self.original_base_dir) into self.version_base_dir.
        Then return a pandas DataFrame containing all given indices and defined columns.
        If fill is True, missing values will be computed.
        If fill and overwrite are True, all values will be computed, regardless of
        whether they are previously present in the table.

        :param overwrite: if True, version files are written even if they exist
        :param target_indices: list of indices that are to be contained in the table
        :param parallel_versioning: if True, files are versioned in parallel if needed
        :param parallel_row_processing: if True, file properties are gathered in parallel
        :param target_columns: if not None, the list of columns that are considered for computation
        """
        assert all(index == get_canonical_path(index) for index in target_indices)
        original_df = self.original_properties_table.get_df(
            target_indices=target_indices,
            target_columns=target_columns)

        base_path = os.path.abspath(self.original_base_dir)
        version_path = os.path.abspath(self.version_base_dir)
        target_indices = [get_canonical_path(index)
                          for index in target_indices]
        version_indices = [index.replace(base_path, version_path)
                           for index in target_indices]

        if parallel_versioning:
            version_fun_id = ray.put(self.version)
            overwrite_id = ray.put(overwrite)
            original_df_id = ray.put(original_df)
            options_id = ray.put(options)
            versioning_result_ids = []
            for original_path, version_path in zip(target_indices, version_indices):
                input_path_id = ray.put(original_path)
                output_path_id = ray.put(version_path)
                versioning_result_ids.append(version_one_path.remote(
                    version_fun=version_fun_id, input_path=input_path_id,
                    output_path=output_path_id, overwrite=overwrite_id,
                    original_info_df=original_df_id, options=options_id))
            ray.get(versioning_result_ids)
        else:
            for original_path, version_path in zip(target_indices, version_indices):
                version_one_path_local(version_fun=self.version, input_path=original_path,
                                       output_path=version_path, overwrite=overwrite,
                                       original_info_df=original_df, options=options)

        # Invoke df of the next parent that is not a FileVersionTable (an ATable subclass)
        filtered_bases = tuple(cls for cls in self.__class__.__bases__ if cls is not FileVersionTable)
        filtered_type = type(f"filtered_{self.__class__.__name__}", filtered_bases, {})
        return filtered_type.get_df(
            self, target_indices=version_indices, parallel_row_processing=parallel_row_processing,
            target_columns=target_columns, overwrite=overwrite)


@ray.remote
def version_one_path(version_fun, input_path, output_path, overwrite, options, original_info_df):
    """Run the versioning of one path
    """
    return version_one_path_local(version_fun=version_fun, input_path=input_path,
                                  output_path=output_path, overwrite=overwrite,
                                  options=options, original_info_df=original_info_df)


def version_one_path_local(version_fun, input_path, output_path, overwrite, options,
                           original_info_df):
    """Version input_path into output_path using version_fun
    :param version_fun: function with signature like FileVersionTable.version
    :param input_path: path of the file to be versioned
    :param output_path: path where the versioned file is to be stored
    :param overwrite: if True, the version is calculated even if output_path already exists
    :param options: additional runtime options
    :param original_info_df: DataFrame produced by a FilePropertiesTable instance that contains
      an entry for atable.indices_to_internal_loc(input_path).
    """
    output_path = get_canonical_path(output_path)
    if os.path.exists(output_path) and not overwrite:
        if options.verbose > 2:
            print(f"[S]kipping versioning of {input_path}")
        return

    if options.verbose > 1:
        print(f"[V]ersioning {input_path} -> {output_path} (overwrite={overwrite})")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    file_info = original_info_df.loc[atable.indices_to_internal_loc(input_path)]
    try:
        version_fun(input_path=input_path, output_path=output_path, file_info=file_info)
    except Exception as ex:
        try:
            os.remove(output_path)
        except FileNotFoundError:
            pass
        raise ex


if __name__ == '__main__':
    print("Module not executable")
