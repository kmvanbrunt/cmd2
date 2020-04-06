#!/usr/bin/env python
# coding=utf-8
"""Examples of using the new table API"""
import functools
import sys
from typing import List

from cmd2 import ansi, utils
from cmd2.table_creator import Column, TableCreator


def ansi_print(text):
    ansi.style_aware_write(sys.stdout, text + '\n')


style_1 = functools.partial(ansi.style, fg=ansi.fg.bright_yellow, bold=True)
style_2 = functools.partial(ansi.style, fg=ansi.fg.bright_blue)
style_3 = functools.partial(ansi.style, fg=ansi.fg.green)
style_bg = functools.partial(ansi.style, bg=ansi.bg.bright_black)

# Table Columns
columns: List[Column] = list()
columns.append(Column("Name", width=20, wrap_data=True))
columns.append(Column("Address", width=40, wrap_data=True))
columns.append(Column("Income", width=13,
                      header_alignment=utils.TextAlignment.RIGHT,
                      data_alignment=utils.TextAlignment.RIGHT))

# Table data
data_rows: List[List[str]] = list()
data_rows.append(["Billy Smith",
                  "123 Sesame St.\n"
                  "Fake Town, USA 33445", "$100,333.03"])
data_rows.append(["William LongFellow Marmaduke III",
                  "984 Really Long Street Name Which Will Wrap Nicely\n"
                  "Apt 22G\n"
                  "Pensacola, FL 99888", "$55,135.22"])
data_rows.append(["James " + style_2("  Anderson"),
                  style_1("This address has line feeds,\n"
                          "text style,") + style_2(" and changes color while wrapping."),
                  "$300,876.10"])
data_rows.append(["John Jones",
                  "9235 Highway 32\n" +
                  style_3("Color") + ", VA 88222", "$82,987.71"])


def simple_table():
    """
    Create a borderless table which has a divider row after the header
    Blank lines separate each row
    """
    tc = TableCreator(columns)
    header = tc.generate_header_row()
    divider = tc.generate_data_row(['', '', ''], fill_char='-', inter_cell="--")
    ansi_print(header)
    ansi_print(divider)

    for index, data in enumerate(data_rows):
        if index > 0:
            ansi_print('')
        row = tc.generate_data_row(data)
        ansi_print(row)


def bordered_table():
    """Create a table with borders around and between rows"""
    # Made the headers bold
    for col in columns:
        col.header = ansi.style(col.header, bold=True)
    tc = TableCreator(columns)

    # Create the bordered header
    header_top = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╔═", inter_cell="═╤═", post_line="═╗")
    header = tc.generate_header_row(pre_line="║ ", inter_cell=" │ ", post_line=" ║")
    header_bottom = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╠═", inter_cell="═╪═", post_line="═╣")
    ansi_print(header_top)
    ansi_print(header)
    ansi_print(header_bottom)

    # Add each row
    for index, data in enumerate(data_rows):
        if index > 0:
            border = tc.generate_data_row(['', '', ''], fill_char="─", pre_line="╟─", inter_cell="─┼─", post_line="─╢")
            ansi_print(border)
        row = tc.generate_data_row(data, pre_line="║ ", inter_cell=" │ ", post_line=" ║")
        ansi_print(row)

    table_bottom = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╚═", inter_cell="═╧═", post_line="═╝")
    ansi_print(table_bottom)


def alternating_table():
    """Create a table with borders around the table and alternating background color used to separate rows"""
    # Made the headers bold
    for col in columns:
        col.header = ansi.style(col.header, bold=True)
    tc = TableCreator(columns)

    # Create the bordered header
    header_top = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╔═", inter_cell="═╤═", post_line="═╗")
    header = tc.generate_header_row(pre_line="║ ", inter_cell=" │ ", post_line=" ║")
    header_bottom = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╠═", inter_cell="═╪═", post_line="═╣")
    ansi_print(header_top)
    ansi_print(header)
    ansi_print(header_bottom)

    # Add each row
    for index, data in enumerate(data_rows):
        fill_char = ' '
        pre_line = "║ "
        inter_cell = " │ "
        post_line = " ║"

        if index % 2 != 0:
            fill_char = style_bg(fill_char)
            pre_line = style_bg(pre_line)
            inter_cell = style_bg(inter_cell)
            post_line = style_bg(post_line)

            for col_index, col in enumerate(data):
                data[col_index] = style_bg(col)

        row = tc.generate_data_row(data, fill_char=fill_char, pre_line=pre_line, inter_cell=inter_cell, post_line=post_line)
        ansi_print(row)

    table_bottom = tc.generate_data_row(['', '', ''], fill_char='═', pre_line="╚═", inter_cell="═╧═", post_line="═╝")
    ansi_print(table_bottom)


def main():
    ansi.allow_style = ansi.STYLE_TERMINAL
    ansi_print('')
    simple_table()
    ansi_print('')
    bordered_table()
    ansi_print('')
    alternating_table()


if __name__ == '__main__':
    main()