# coding=utf-8
"""Simple table creation class"""
import io
from collections import deque
from typing import Any, List, Optional, Tuple

from wcwidth import wcwidth

from . import ansi, utils


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

    @staticmethod
    def _char_based_text_wrap(text: str, max_width: int) -> str:
        """
        Wrap text into lines with a display width no longer than max_width. This function wraps

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :return: Wrapped text
        """
        styles = utils.get_styles_in_text(text)
        wrapped_buf = io.StringIO()

        # Respect the existing line breaks
        data_str_lines = text.splitlines()
        for line_index, cur_line in enumerate(data_str_lines):
            if line_index > 0:
                wrapped_buf.write('\n')

            # Display width of the current line we are building
            cur_width = 0

            char_index = 0
            while char_index < len(cur_line):
                # Check if a style sequence is at this index. These don't count toward display width.
                if char_index in styles:
                    wrapped_buf.write(styles[char_index])
                    char_index += len(styles[char_index])
                    continue

                cur_char = cur_line[char_index]
                cur_char_width = wcwidth(cur_char)

                if cur_width + cur_char_width > max_width:
                    # Adding this char will exceed the column width. Start a new line.
                    wrapped_buf.write('\n')
                    cur_width = 0

                cur_width += cur_char_width
                wrapped_buf.write(cur_char)
                char_index += 1

        return wrapped_buf.getvalue()

    def _word_based_text_wrap(self, text: str, max_width: int) -> str:
        """
        Wrap text into lines with a display width no longer than max_width. This function wraps

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :return: Wrapped text
        """
        wrapped_buf = io.StringIO()

        # Respect the existing line breaks
        data_str_lines = text.splitlines()
        for line_index, cur_line in enumerate(data_str_lines):
            if line_index > 0:
                wrapped_buf.write('\n')

            # Display width of the current line we are building
            cur_width = 0

            # Use whitespace as word boundaries
            words = deque(cur_line.split())

            while words:
                if cur_width == max_width:
                    # Start a new line
                    wrapped_buf.write('\n')
                    cur_width = 0

                # Get the next word
                cur_word = words.popleft()
                word_width = ansi.style_aware_wcswidth(cur_word)

                if word_width > max_width:
                    # This word is too wide than the max width of a line. Break it up into chunks that
                    # will fit and place those words at the beginning of the list.
                    wrapped_word = self._char_based_text_wrap(cur_word, max_width)
                    chunks = wrapped_word.splitlines()
                    for line in reversed(chunks):
                        words.appendleft(line)
                else:
                    # If this isn't the first word on the line and it has display width,
                    # add a space before it if there is room or print it on the next line.
                    if cur_width > 0 and word_width > 0:
                        if cur_width + word_width < max_width:
                            cur_word = ' ' + cur_word
                            word_width += 1
                        else:
                            wrapped_buf.write('\n')
                            cur_width = 0

                    cur_width += word_width
                    wrapped_buf.write(cur_word)

        return wrapped_buf.getvalue()

    def _generate_cell_lines(self, data: Any, is_header: bool, col: Column, fill_char: str) -> Tuple[List[str], int]:
        """
        Generate the lines of a table cell
        :param data: data to be included in cell
        :param is_header: True if writing a header cell, otherwise writing a data cell
        :param col: Column definition for this cell
        :param fill_char: character that fills remaining space in a cell. If your text has a background color,
                          then give fill_char the same background color. (Cannot be a line breaking character)
        :return: Tuple of cell lines and the display width of the cell
        """
        advanced = True

        # Align the text according to Column parameters
        if is_header:
            alignment = col.header_alignment
        else:
            alignment = col.data_alignment

        # Convert data to string and replace tabs with spaces
        data_str = str(data).replace('\t', ' ' * self.tab_width)

        # Check if we are wrapping this cell
        if not is_header and col.wrap_data:
            if advanced:
                data_str = self._word_based_text_wrap(data_str, col.width)
            else:
                data_str = self._char_based_text_wrap(data_str, col.width)

        # Align the text
        aligned_text = utils.align_text(data_str, fill_char=fill_char, width=col.width,
                                        tab_width=self.tab_width, alignment=alignment)

        lines = aligned_text.splitlines()
        cell_width = max([ansi.style_aware_wcswidth(line) for line in lines])
        return lines, cell_width

    def _generate_row(self, data: List[Any], is_header: bool, fill_char: str,
                      pre_line, inter_cell, post_line) -> str:
        """
        Generate a table data row
        :param data: list of data the same length as cols
        :param is_header: True if writing a header cell, otherwise writing a data cell
        :param fill_char: character that fills remaining space in a cell. If your text has a background color,
                          then give fill_char the same background color. (Cannot be a line breaking character)
        :param pre_line: characters to print after a row line
        :param inter_cell: characters to print between cell lines
        :param post_line: characters to print after a row line
        :return: row string
        :raises: ValueError if data isn't the same length as self.cols
        """
        class Cell:
            """Inner class which represents a table cell"""
            def __init__(self):
                # Data in this cell split into individual lines
                self.lines = []

                # Display width of this cell
                self.width = 0

        if len(self.cols) != len(data):
            raise ValueError("Length of cols must match length of data")

        # Build a list of cells for this row
        cells = []
        num_lines = 0

        for col_index, col in enumerate(self.cols):
            cell = Cell()
            cell.lines, cell.width = self._generate_cell_lines(data[col_index], is_header, col, fill_char)
            cells.append(cell)
            num_lines = max(len(cell.lines), num_lines)

        row_buf = io.StringIO()

        # Build this row one line at a time
        for line_index in range(num_lines):
            for cell_index, cell in enumerate(cells):
                if cell_index == 0:
                    row_buf.write(pre_line)

                # Check if this cell has a line at this index
                if line_index < len(cell.lines):
                    row_buf.write(cell.lines[line_index])

                # Otherwise fill this cell with fill_char
                else:
                    row_buf.write(utils.align_left('', fill_char=fill_char, width=cell.width))

                if cell_index < len(self.cols) - 1:
                    row_buf.write(inter_cell)
                if cell_index == len(self.cols) - 1:
                    row_buf.write(post_line)

            # Add a newline if this is not the last row
            if line_index < num_lines - 1:
                row_buf.write('\n')

        return row_buf.getvalue()

    def generate_header_row(self, *, fill_char: str = ' ', pre_line: str = '',
                            inter_cell: str = '  ', post_line: str = '') -> str:
        """
        Generate the header row
        :param fill_char: character that fills remaining space in a cell. Defaults to space.
                          (Cannot be a line breaking character)
        :param pre_line: characters to print after a row line (Defaults to blank)
        :param inter_cell: characters to print between cell lines (Defaults to 2 spaces)
        :param post_line: characters to print after a row line (Defaults to blank)
        :return: header row string
        :raises: ValueError if divider is an unprintable character like a newline
        """
        data = [col.header for col in self.cols]
        return self._generate_row(data, is_header=True, fill_char=fill_char,
                                  pre_line=pre_line, inter_cell=inter_cell, post_line=post_line)

    def generate_data_row(self, data: List[Any], *, fill_char: str = ' ',
                          pre_line: str = '', inter_cell: str = '  ', post_line: str = '') -> str:
        """
        Generate a table data row
        :param data: list of data the same length as cols
        :param fill_char: character that fills remaining space in a cell. Defaults to space. If your text has a background
                          color, then give fill_char the same background color. (Cannot be a line breaking character)
        :param pre_line: characters to print after a row line (Defaults to blank)
        :param inter_cell: characters to print between cell lines (Defaults to 2 spaces)
        :param post_line: characters to print after a row line (Defaults to blank)
        :return: data row string
        :raises: ValueError if data isn't the same length as self.cols
        """
        return self._generate_row(data, is_header=False, fill_char=fill_char,
                                  pre_line=pre_line, inter_cell=inter_cell, post_line=post_line)
