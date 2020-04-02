# coding=utf-8
"""Table creation API"""
import io
from collections import deque
from typing import Any, List, Optional, Tuple, Union

from wcwidth import wcwidth

from . import ansi, constants, utils


class Column:
    """Table column configuration"""
    def __init__(self, header: str, *, width: Optional[int] = None,
                 header_alignment: utils.TextAlignment = utils.TextAlignment.LEFT,
                 data_alignment: utils.TextAlignment = utils.TextAlignment.LEFT,
                 max_data_lines: Union[int, float] = constants.INFINITY) -> None:
        """
        Column initializer
        :param header: label for column header
        :param width: display width of column (defaults to width of header or 1 if header is blank)
                      header and data text will wrap within this width using word-based wrapping
        :param header_alignment: how to align header (defaults to left)
        :param data_alignment: how to align data (defaults to left)
        :param max_data_lines: maximum data lines allowed in a cell. If line count exceeds this, then the final
                               line displayed will be truncated with an ellipsis. (defaults to INFINITY)
        :raises ValueError if width is less than 1
                ValueError if max_data_lines is less than 1
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
            self.width = width

        self.header_alignment = header_alignment
        self.data_alignment = data_alignment

        if max_data_lines < 1:
            raise ValueError("Max data lines cannot be less than 1")

        self.max_data_lines = max_data_lines


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
    def _wrap_long_word(text: str, max_width: int, max_lines: Union[int, float]) -> str:
        """
        Wrap a long word over multiple lines. ANSI escape sequences do not count toward the width of a line.

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :return: wrapped text
        """
        styles = utils.get_styles_in_text(text)
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 1

        # Display width of the current line we are building
        cur_width = 0

        char_index = 0
        while char_index < len(text):
            # We've reached the last line. Let truncate_line do the rest.
            if total_lines == max_lines:
                wrapped_buf.write(utils.truncate_line(text[char_index:], max_width))
                break

            # Check if a style sequence is at this index. These don't count toward display width.
            if char_index in styles:
                wrapped_buf.write(styles[char_index])
                char_index += len(styles[char_index])
                continue

            cur_char = text[char_index]
            cur_char_width = wcwidth(cur_char)

            if cur_char_width > max_width:
                # We have a case where the character is wider than max_width. This can happen if max_width
                # is 1 and the text contains wide characters (e.g. East Asian). Replace it with an ellipsis.
                cur_char = constants.HORIZONTAL_ELLIPSIS
                cur_char_width = wcwidth(cur_char)

            if cur_width + cur_char_width > max_width:
                if total_lines < max_lines:
                    # Adding this char will exceed the column width. Start a new line.
                    wrapped_buf.write('\n')
                    total_lines += 1
                    cur_width = 0
                    continue
                else:
                    # We've use all allowed lines. Add an ellipsis and exit loop.
                    wrapped_buf.write(constants.HORIZONTAL_ELLIPSIS)
                    break

            # Add this character and move to the next one
            cur_width += cur_char_width
            wrapped_buf.write(cur_char)
            char_index += 1

        return wrapped_buf.getvalue()

    @staticmethod
    def _wrap_text(text: str, max_width: int, max_lines: Union[int, float]) -> str:
        """
        Wrap text into lines with a display width no longer than max_width. This function breaks text on whitespace
        boundaries. If a word is longer than the space remaining on a line, then it will start on a new line.
        All spaces are replaced by a single space. ANSI escape sequences do not count toward the width of a line.

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :return: wrapped text
        """
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 0

        # Respect the existing line breaks
        data_str_lines = text.splitlines()
        for line_index, cur_line in enumerate(data_str_lines):
            total_lines += 1

            if line_index > 0:
                wrapped_buf.write('\n')

            # Display width of the current line we are building
            cur_width = 0

            # Use whitespace as word boundaries
            words = deque(cur_line.split())
            if not words and total_lines == max_lines and line_index < len(data_str_lines):
                # We've use all allowed lines. Add an ellipsis and exit loop.
                wrapped_buf.write(constants.HORIZONTAL_ELLIPSIS)
                break

            while words:
                if cur_width == max_width:
                    # Start a new line
                    wrapped_buf.write('\n')
                    total_lines += 1
                    cur_width = 0

                # Get the next word
                cur_word = words.popleft()
                word_width = ansi.style_aware_wcswidth(cur_word)

                # Check if the word is wider than a line allows
                if word_width > max_width:
                    if total_lines < max_lines:
                        # This word is too wide than the max width of a line. Break it up into chunks that
                        # will fit and place those words at the beginning of the list.
                        remaining_lines = max_lines - total_lines
                        wrapped_word = TableCreator._wrap_long_word(cur_word, max_width, remaining_lines)
                        chunks = wrapped_word.splitlines()
                        for line in reversed(chunks):
                            words.appendleft(line)
                    else:
                        # We've use all allowed lines. Truncate word and exit loop.
                        if cur_width > 0:
                            # Insert a space since this isn't the first word on the line
                            cur_word = ' ' + cur_word
                            word_width += 1
                        truncated_word = utils.truncate_line(cur_word, max_width - cur_width)
                        wrapped_buf.write(truncated_word)
                        break
                else:
                    # TODO handle cases
                    # 1. Word fits, but this is the last line allowed and there are more lines (truncate word)
                    # 2. Word does not fit and this is last line (truncate word)

                    # If this isn't the first word on the line and it has display width,
                    # add a space before it if there is room or print it on the next line.
                    if cur_width > 0 and word_width > 0:
                        if cur_width + word_width < max_width:
                            cur_word = ' ' + cur_word
                            word_width += 1
                        else:
                            wrapped_buf.write('\n')
                            total_lines += 1
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
        # Align the text according to Column parameters
        if is_header:
            alignment = col.header_alignment
        else:
            alignment = col.data_alignment

        # Convert data to string and replace tabs with spaces
        data_str = str(data).replace('\t', ' ' * self.tab_width)

        # Wrap text in this cell
        data_str = self._wrap_text(data_str, col.width, col.max_data_lines)

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
