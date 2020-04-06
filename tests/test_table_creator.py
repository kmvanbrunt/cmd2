# coding=utf-8
"""
Unit testing for cmd2/table_creator.py module
"""
import pytest

from cmd2 import ansi, utils
from cmd2.table_creator import Column, TableCreator


def test_column_creation():
    # No width specified, blank label
    c = Column("")
    assert c.width == 1

    # No width specified, label isn't blank but has no width
    c = Column(ansi.style('', fg=ansi.fg.green))
    assert c.width == 1

    # No width specified, label has width
    c = Column("short\nreally long")
    assert c.width == ansi.style_aware_wcswidth("really long")

    # Width less than 1
    with pytest.raises(ValueError) as excinfo:
        Column("Column 1", width=0)
    assert "Column width cannot be less than 1" in str(excinfo.value)

    # Width specified
    c = Column("header", width=20)
    assert c.width == 20

    # max_data_lines less than 1
    with pytest.raises(ValueError) as excinfo:
        Column("Column 1", max_data_lines=0)
    assert "Max data lines cannot be less than 1" in str(excinfo.value)

#def test_
#
#
#
# def test_generate_header_row():
#     column_1 = Column("Column 1")
#     column_2 = Column("Column 2")
#     columns = [column_1, column_2]
#
#     tc = TableCreator(columns)
#     header = tc.generate_header_row()
#     assert header == 'Column 1  Column 2'
#
#     # Multiline labels
#     column_1 = Column("Column 1")
#     column_2 = Column("Multiline\nLabel")
#     columns = [column_1, column_2]
#
#     tc = TableCreator(columns)
#     header = tc.generate_header_row()
#     assert header == ('Column 1  Multiline\n'
#                       '          Label    ')
#
#     # Colored labels
#     column_1 = Column(ansi.style("Column 1", fg=ansi.fg.bright_yellow))
#     column_2 = Column("A " + ansi.style("Multiline\nLabel", fg=ansi.fg.green) + " with color")
#     columns = [column_1, column_2]
#
#     tc = TableCreator(columns)
#     header = tc.generate_header_row()
#     col_1_line_1 = ansi.RESET_ALL + ansi.fg.bright_yellow + "Column 1" + ansi.fg.reset + ansi.RESET_ALL
#     col_1_line_2 = '        '
#     col_2_line_1 = ansi.RESET_ALL + "A " + ansi.fg.green + "Multiline" + ansi.RESET_ALL + '     ' + ansi.RESET_ALL
#     col_2_line_2 = ansi.RESET_ALL + ansi.fg.green + 'Label' + ansi.fg.reset + ' with color' + ansi.RESET_ALL
#
#     assert header == (col_1_line_1 + '  ' + col_2_line_1 + '\n' +
#                       col_1_line_2 + '  ' + col_2_line_2)
#
#
# def test_column_width():
#     column_1 = Column("Column 1", width=15)
#     column_2 = Column("Multiline\nLabel", width=15)
#     columns = [column_1, column_2]
#
#     tc = TableCreator(columns)
#     header = tc.generate_header_row()
#     assert header == ('Column 1         Multiline      \n'
#                       '                 Label          ')
#
#     # Blank header label
#     blank_column = Column("")
#     assert blank_column.width == 1
#
#     # Negative width
#     with pytest.raises(ValueError) as excinfo:
#         Column("Column 1", width=-1)
#     assert "Column width cannot be less than 1" in str(excinfo.value)
#
#
# def test_aligned_header():
#     column_1 = Column("Column 1", header_vert_align=utils.TextAlignment.RIGHT, width=15)
#     column_2 = Column("Multiline\nLabel", header_vert_align=utils.TextAlignment.CENTER, width=15)
#     columns = [column_1, column_2]
#
#     tc = TableCreator(columns)
#     header = tc.generate_header_row()
#     assert header == ('       Column 1     Multiline   \n'
#                       '                      Label     ')
#
#
# def test_generate_data_row():
#     column_1 = Column("Column 1")
#     column_2 = Column("Column 2")
#     columns = [column_1, column_2]
#     tc = TableCreator(columns)
#
#     data = ['Data 1', 'Data 2']
#     row = tc.generate_data_row(data)
#     assert row == 'Data 1    Data 2  '
#
#     # Multiline data
#     data = ['Split\nData 1\n', 'Split\nData 2']
#     row = tc.generate_data_row(data)
#     assert row == ('Split     Split   \n'
#                    'Data 1    Data 2  ')
#
#     # Colored data
#     column_1 = Column("Column 1", width=30)
#     column_2 = Column("Column 2", width=30)
#     columns = [column_1, column_2]
#     tc = TableCreator(columns)
#
#     data_1 = ansi.style_success("Hello") + " I have\n" + ansi.style_warning("colored\n") + "and normal text"
#     data_2 = "Hello" + " I also have\n" + ansi.style_error("colored\n") + "and normal text"
#     row = tc.generate_data_row([data_1, data_2])
#     assert row == ('\x1b[0m\x1b[0m\x1b[32mHello\x1b[39m I have\x1b[0m                  \x1b[0m  Hello I also have             \n'
#                    '\x1b[0m\x1b[0m\x1b[32m\x1b[39m\x1b[93mcolored\x1b[0m                       \x1b[0m  \x1b[0m\x1b[0m\x1b[91mcolored\x1b[0m                       \x1b[0m\n'
#                    '\x1b[0m\x1b[0m\x1b[32m\x1b[39m\x1b[93m\x1b[39mand normal text\x1b[0m               \x1b[0m  \x1b[0m\x1b[0m\x1b[91m\x1b[39mand normal text\x1b[0m               \x1b[0m')
#
#     # Data with too many columns
#     data = ['Data 1', 'Data 2', 'Extra Column']
#     with pytest.raises(ValueError) as excinfo:
#         tc.generate_data_row(data)
#     assert "Length of cols must match length of data" in str(excinfo.value)
