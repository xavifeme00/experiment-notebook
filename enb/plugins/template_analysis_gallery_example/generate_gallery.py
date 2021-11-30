#!/usr/bin/env python3
"""Sample script that generates the different plots used in the gallery.
Code shown in the documentation is taken from this script.
"""
__author__ = "Miguel Hernández-Cabronero"
__since__ = "2021/02/01"

import os
import subprocess
import glob
import pandas as pd
import ast

import enb
from enb.config import options

if __name__ == '__main__':

    iris_df = pd.read_csv("./input_csv/iris_dataset.csv")

    # Scalar numeric analysis
    scalar_analyzer = enb.aanalysis.ScalarNumericAnalyzer()

    ## One numeric analysis
    analysis_df = scalar_analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric"))

    ## With grouping
    analysis_df = scalar_analyzer.get_df(
        full_df=iris_df, target_columns=["sepal_length", "sepal_width", "petal_length", "petal_width"],
        output_plot_dir=os.path.join(options.plot_dir, "scalar_numeric"),
        group_by="class")

    # Two numeric analysis

    ## Scatter analysis
    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        output_plot_dir=os.path.join(options.plot_dir, "two_numeric"),
    )

    ## Scatter analysis with grouping
    two_numeric_analyzer = enb.aanalysis.TwoNumericAnalyzer()
    analysis_df = two_numeric_analyzer.get_df(
        full_df=iris_df, target_columns=[("sepal_width", "petal_length")],
        output_plot_dir=os.path.join(options.plot_dir, "two_numeric"),
        group_by="class",
    )

    # Dictionary value plotting
    ## Use HEVC mode selection results
    hevc_df = pd.read_csv(os.path.join("./input_csv/hevc_frame_prediction.csv"))
    ## These two lines are automatically applied by get_df of the appropriate experiment - they can be safely ignored
    hevc_df["mode_count"] = hevc_df["mode_count"].apply(ast.literal_eval)
    hevc_df["block_size"] = hevc_df["param_dict"].apply(lambda d: f"Block size {ast.literal_eval(d)['block_size']:02d}")

    ## Define some column properties for the mode_count column
    column_to_properties = dict(mode_count=enb.atable.ColumnProperties(
        name="mode_count", label="Mode index to selection count", has_dict_values=True))

    # Create the analyzer and plot results
    numeric_dict_analyzer = enb.aanalysis.DictNumericAnalyzer()
    numeric_dict_analyzer.secondary_alpha = 0
    analysis_df = numeric_dict_analyzer.get_df(
        output_plot_dir="./plots/numeric_dict",
        full_df=hevc_df,
        target_columns=["mode_count"],
        group_by="block_size",
        column_to_properties=column_to_properties,
        group_name_order=sorted(hevc_df["block_size"].unique()),

        # Rendering options
        x_tick_label_angle=90,
        fig_width=7.5,
        fig_height=5,
        global_y_label_pos=-0.01)

    # Make a png mirror of all the PDF files (not within enb, yet)
    enb.aanalysis.pdf_to_png(options.plot_dir, os.path.join(os.path.dirname(os.path.abspath(__file__)), "png_plots"))