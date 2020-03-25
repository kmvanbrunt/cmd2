# coding=utf-8
"""Simple table creation class"""
import io
from typing import Any, List, Optional, Tuple

from wcwidth import wcwidth

from . import ansi, utils

# Padding between table columns
COL_PADDING = '  '


class Column:
    """Table column configuration"""
    def __init__(self, header: str, *, width: Optional[int] = None,
                 header_alignment: utils.TextAlignment = utils.TextAlignment.LEFT,
                 data_alignment: utils.TextAlignment = utils.TextAlignment.LEFT,
                 wrap_data: bool = False) -> None:
        """
        Column initializer
        :param header: label for column header
        :param width: display width of column (defaults to width of header or 1 if header is blank)
        :param header_alignment: how to align header (defaults to left)
        :param data_alignment: how to align data (defaults to left)
        :param wrap_data: If True, data will wrap within the width of the column.
                          Wrapping is basic and will split words. If you require more advanced wrapping, then wrap
                          your data with another library prior to building the table.

                          If False, data that is wider than the column with print outside the column boundaries.
                          Defaults to False.
        :raises ValueError if width is less than 1
        """
        self.header = header

        if width is None:
            if not self.header:
                self.width = 1
            else:
                # Find the width of the longest line in header
                self.width = max([ansi.style_aware_wcswidth(line) for line in self.header.splitlines()])
        elif width < 1:
            raise ValueError("Column width cannot be less than 1")
        else:
            self. width = width

        self.header_alignment = header_alignment
        self.data_alignment = data_alignment
        self.wrap_data = wrap_data


class TableCreator:
    """
    Creates a table one row at a time. This avoids needing to have the whole table in memory.
    It also handles ANSI style sequences and characters with display widths greater than 1
    when performing width calculations.
    """
    def __init__(self, cols: List[Column], *, tab_width: int = 4) -> None:
        """
        TableCreator initializer
        :param cols: column definitions for this table
        :param tab_width: all tabs will be replaced with this many spaces
        """
        self.cols = cols
        self.tab_width = tab_width

    def _generate_cell_lines(self, data: Any, is_header: bool, col: Column) -> Tuple[List[str], int]:
        """
        Generate the lines of a table cell
        :param data: data to be included in cell
        :param is_header: True if writing a header cell, otherwise writing a data cell
        :param col: Column definition for this cell
        :return: Tuple of cell lines and the display width of the cell
        """
        # Align the text according to Column parameters
        if is_header:
            alignment = col.header_alignment
        else:
            alignment = col.data_alignment

        # Convert data to string and replace tabs with spaces
        data_str = str(data).replace('\t', ' ' * self.tab_width)

        # Check if we are wrapping this cell
        if not is_header and col.wrap_data:
            wrapped_buf = io.StringIO()

            # Respect the existing line breaks
            data_str_lines = data_str.splitlines()
            for line_index, data_line in enumerate(data_str_lines):
                if line_index > 0:
                    wrapped_buf.write('\n')

                styles = utils.get_styles_in_text(data_line)
                cur_width = 0
                char_index = 0

                while char_index < len(data_line):
                    # Check if a style sequence is at this index. These don't count toward display width.
                    if char_index in styles:
                        wrapped_buf.write(styles[char_index])
                        char_index += len(styles[char_index])
                        continue

                    cur_char = data_str[char_index]
                    cur_char_width = wcwidth(cur_char)

                    if cur_width + cur_char_width > col.width:
                        # Adding this char will exceed the column width. Start a new line.
                        wrapped_buf.write('\n')
                        cur_width = 0

                    cur_width += cur_char_width
                    wrapped_buf.write(cur_char)
                    char_index += 1

            data_str = wrapped_buf.getvalue()

        # Align the text
        aligned_text = utils.align_text(data_str, width=col.width,
                                        tab_width=self.tab_width, alignment=alignment)

        lines = aligned_text.splitlines()
        cell_width = max([ansi.style_aware_wcswidth(line) for line in lines])
        return lines, cell_width

    def _generate_row(self, data: List[Any], is_header: bool) -> Tuple[str, int]:
        """
        Generate a table data row
        :param data: list of data the same length as cols
        :param is_header: True if writing a header cell, otherwise writing a data cell
        :return: Tuple containing row string and display width of row
        :raises: ValueError if data isn't the same length as self.cols
        """
        class Cell:
            """Inner class which represents a table cell"""
            def __init__(self):
                # Data in this cell split into individual lines
                self.lines = []

                # Display width of this cell
                self.width = 0

                # To create a table row, we go from cell to cell, adding one line at a time. We use this string to
                # save the state of a cell's ANSI style so we can restore it when beginning its next line.
                self.current_style = ''

        if len(self.cols) != len(data):
            raise ValueError("Length of cols must match length of data")

        # Build a list of cells for this row
        total_width = 0
        cells = []
        num_lines = 0

        for col_index, col in enumerate(self.cols):
            cell = Cell()
            cell.lines, cell.width = self._generate_cell_lines(data[col_index], is_header, col)
            cells.append(cell)
            num_lines = max(len(cell.lines), num_lines)
            total_width += cell.width

            # Account for padding if this is not the last column
            if col_index < len(self.cols) - 1:
                total_width += ansi.style_aware_wcswidth(COL_PADDING)

        row_buf = io.StringIO()

        # Build this row one line at a time
        for line_index in range(num_lines):
            for cell_index, cell in enumerate(cells):
                # Check if this cell has a line at this index
                if line_index < len(cell.lines):
                    line = cell.lines[line_index]

                    # Restore any style
                    row_buf.write(cell.current_style)

                    # Save the styles used in this lin
                    styles = utils.get_styles_in_text(line)
                    cell.current_style += ''.join(styles.values())

                    # Add this line to the buffer and reset the style for the next cell
                    row_buf.write(line)
                    if cell.current_style:
                        row_buf.write(ansi.RESET_ALL)

                # Otherwise fill this cell with spaces
                else:
                    row_buf.write(' ' * cell.width)

                # Add padding if this is not the last column
                if cell_index < len(cells) - 1:
                    row_buf.write(COL_PADDING)

            # Add a newline if this is not the last row
            if line_index < num_lines - 1:
                row_buf.write('\n')

        return row_buf.getvalue(), total_width

    def generate_header_row(self, *, divider: Optional[str] = '-') -> str:
        """
        Generate the header row
        :param divider: character that makes up the divider row below the header. Set this to None if you want no
                        divider. If divider is a tab, then it will be converted to a space. Default to dash.
        :return: header row string
        :raises: TypeError if divider is more than one character (not including ANSI style sequences)
                 ValueError if divider is an unprintable character like a newline
        """
        if divider == '\t':
            divider = ' '

        if divider is not None:
            if len(ansi.strip_style(divider)) != 1:
                raise TypeError("Divider must be exactly one character long")

            if ansi.style_aware_wcswidth(divider) == -1:
                raise (ValueError("Divider is an unprintable character"))

        data = [col.header for col in self.cols]
        row_str, width = self._generate_row(data, is_header=True)

        # Check if we need a divider
        if divider is not None and width > 0:
            row_str += '\n' + utils.align_left('', fill_char=divider, width=width)

        return row_str

    def generate_data_row(self, data: List[Any]) -> str:
        """
        Generate a table data row
        :param data: list of data the same length as cols
        :return: data row string
        :raises: ValueError if data isn't the same length as self.cols
        """
        row_str, width = self._generate_row(data, is_header=False)
        return row_str
