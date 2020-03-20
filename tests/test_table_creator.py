# coding=utf-8
"""
Unit testing for cmd2/table_creator.py module
"""
import pytest

from cmd2 import ansi, utils
from cmd2.table_creator import Column, TableCreator


def test_basic_header():
    column_1 = Column("Column 1")
    column_2 = Column("Column 2")
    columns = [column_1, column_2]

    tc = TableCreator(columns)
    header = tc.generate_header_row(divider=None)
    assert header == 'Column 1  Column 2'


def test_header_divider():
    column_1 = Column("Column 1")
    column_2 = Column("Column 2")
    columns = [column_1, column_2]
    tc = TableCreator(columns)

    # Default divider
    header = tc.generate_header_row()
    assert header == ('Column 1  Column 2\n'
                      '------------------')

    # Custom divider
    header = tc.generate_header_row(divider='*')
    assert header == ('Column 1  Column 2\n'
                      '******************')

    # Divider with display width greater than 1
    header = tc.generate_header_row(divider='北')
    assert header == ('Column 1  Column 2\n'
                      '北北北北北北北北北')

    # Colored divider
    divider = ansi.style_success('*')
    header = tc.generate_header_row(divider=divider)
    label_line = header.splitlines()[0]
    assert header == ('Column 1  Column 2\n' +
                      divider * ansi.style_aware_wcswidth(label_line))

    # Tab divider
    header = tc.generate_header_row(divider='\t')
    assert header == ('Column 1  Column 2\n'
                      '                  ')

    # Divider is more than one character
    with pytest.raises(TypeError) as excinfo:
        tc.generate_header_row(divider='a string')
    assert "Divider must be exactly one character long" in str(excinfo.value)

    # Divider is unprintable
    with pytest.raises(ValueError) as excinfo:
        tc.generate_header_row(divider='\n')
    assert "Divider is an unprintable character" in str(excinfo.value)


def test_multiline_header():
    column_1 = Column("Column 1")
    column_2 = Column("Multiline\nLabel")
    columns = [column_1, column_2]

    tc = TableCreator(columns)
    header = tc.generate_header_row()
    assert header == ('Column 1  Multiline\n'
                      '          Label    \n'
                      '-------------------')


def test_column_width():
    column_1 = Column("Column 1", width=15)
    column_2 = Column("Multiline\nLabel", width=15)
    columns = [column_1, column_2]

    tc = TableCreator(columns)
    header = tc.generate_header_row()
    assert header == ('Column 1         Multiline      \n'
                      '                 Label          \n'
                      '--------------------------------')

    # Blank header label
    blank_column = Column("")
    assert blank_column.width == 1

    # Negative width
    with pytest.raises(ValueError) as excinfo:
        Column("Column 1", width=-1)
    assert "Column width cannot be less than 1" in str(excinfo.value)


def test_aligned_header():
    column_1 = Column("Column 1", header_alignment=utils.TextAlignment.RIGHT, width=15)
    column_2 = Column("Multiline\nLabel", header_alignment=utils.TextAlignment.CENTER, width=15)
    columns = [column_1, column_2]

    tc = TableCreator(columns)
    header = tc.generate_header_row()
    assert header == ('       Column 1     Multiline   \n'
                      '                      Label     \n'
                      '--------------------------------')
