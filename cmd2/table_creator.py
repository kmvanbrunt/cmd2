# coding=utf-8
"""Table creation API"""
import io
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
    def _wrap_long_word(word: str, max_width: int, max_lines: Union[int, float], is_last_word: bool) -> Tuple[str, int, int]:
        """
        Used by _wrap_text to wrap a long word over multiple lines

        :param word: word being wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :param is_last_word: True if this is the last word of the total text being wrapped
        :return: Tuple(wrapped text, lines used, display width of last line)
        """
        if not word:
            return '', 0, 0

        styles = utils.get_styles_in_text(word)
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 1

        # Display width of the current line we are building
        cur_line_width = 0

        char_index = 0
        while char_index < len(word):
            # We've reached the last line. Let truncate_line do the rest.
            if total_lines == max_lines:
                # If this isn't the last word, but it's gonna fill the final line, then force truncate_line
                # to place an ellipsis at the end of it by appending 1 character to it.
                remaining_word = word[char_index:]
                if not is_last_word and ansi.style_aware_wcswidth(remaining_word) == max_width:
                    remaining_word += 'a'

                truncated_line = utils.truncate_line(remaining_word, max_width)
                cur_line_width = ansi.style_aware_wcswidth(truncated_line)
                wrapped_buf.write(truncated_line)
                break

            # Check if we're at a style sequence. These don't count toward display width.
            if char_index in styles:
                wrapped_buf.write(styles[char_index])
                char_index += len(styles[char_index])
                continue

            cur_char = word[char_index]
            cur_char_width = wcwidth(cur_char)

            if cur_char_width > max_width:
                # We have a case where the character is wider than max_width. This can happen if max_width
                # is 1 and the text contains wide characters (e.g. East Asian). Replace it with an ellipsis.
                cur_char = constants.HORIZONTAL_ELLIPSIS
                cur_char_width = wcwidth(cur_char)

            if cur_line_width + cur_char_width > max_width:
                if total_lines < max_lines:
                    # Adding this char will exceed the max_width. Start a new line.
                    wrapped_buf.write('\n')
                    total_lines += 1
                    cur_line_width = 0
                    continue
                else:
                    # We've use all allowed lines. Add an ellipsis and exit loop.
                    wrapped_buf.write(constants.HORIZONTAL_ELLIPSIS)
                    cur_line_width += ansi.style_aware_wcswidth(constants.HORIZONTAL_ELLIPSIS)
                    break

            # Add this character and move to the next one
            cur_line_width += cur_char_width
            wrapped_buf.write(cur_char)
            char_index += 1

        return wrapped_buf.getvalue(), total_lines, cur_line_width

    @staticmethod
    def _wrap_text(text: str, max_width: int, max_lines: Union[int, float]) -> str:
        """
        Wrap text into lines with a display width no longer than max_width. This function breaks words on whitespace
        boundaries. If a word is longer than the space remaining on a line, then it will start on a new line.
        ANSI escape sequences do not count toward the width of a line.

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :return: wrapped text
        """
        def is_last_word() -> bool:
            """Check if we've reached the last word of the text being wrapped"""
            return data_line_index == len(data_str_lines) - 1 and char_index == len(data_line) - 1

        def add_word(word_to_add: str):
            """
            Add a word to the wrapped text
            :param word_to_add: the word being added
            """
            nonlocal cur_line_width
            nonlocal total_lines

            word_width = ansi.style_aware_wcswidth(word_to_add)

            # If the word is wider than max width of a line, wrap it across multiple lines
            if word_width > max_width:
                if cur_line_width > 0:
                    # Start the long word on its own line
                    wrapped_buf.write('\n')
                    total_lines += 1

                wrapped_word, lines_used, cur_line_width = TableCreator._wrap_long_word(word_to_add,
                                                                                        max_width,
                                                                                        max_lines - total_lines + 1,
                                                                                        is_last_word())
                # Write the word to the buffer
                wrapped_buf.write(wrapped_word)
                total_lines += lines_used - 1
            else:
                remaining_width = max_width - cur_line_width
                start_new_line = False

                # If this isn't the first word on the line and it has display width,
                # add a space before it if there is room or print it on the next line.
                if cur_line_width > 0 and word_width > 0:
                    if word_width < remaining_width:
                        word_to_add = ' ' + word_to_add
                        word_width += 1
                    else:
                        start_new_line = True

                if word_width > remaining_width or start_new_line:
                    wrapped_buf.write('\n')
                    total_lines += 1
                    cur_line_width = 0
                    remaining_width = max_width

                # If this isn't the last word, but it's gonna fill the final line, then force truncate_line
                # to place an ellipsis at the end of it by appending 1 character to it.
                if not is_last_word() and total_lines == max_lines and word_width == remaining_width:
                    word_to_add = utils.truncate_line(word_to_add + "a", remaining_width)

                cur_line_width += word_width
                wrapped_buf.write(word_to_add)

        # Buffer of the wrapped text
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 0

        # Respect the existing line breaks
        data_str_lines = text.splitlines()
        for data_line_index, data_line in enumerate(data_str_lines):
            total_lines += 1

            if data_line_index > 0:
                wrapped_buf.write('\n')

            # Locate the styles in this line
            styles = utils.get_styles_in_text(data_line)

            # Display width of the current line we are building
            cur_line_width = 0

            # Current word being built
            cur_word_buf = io.StringIO()

            char_index = 0
            while char_index < len(data_line):
                if total_lines == max_lines and cur_line_width == max_width:
                    break

                # Check if we're at a style sequence. These don't count toward display width.
                if char_index in styles:
                    cur_word_buf.write(styles[char_index])
                    char_index += len(styles[char_index])
                    continue

                cur_char = data_line[char_index]
                cur_char_width = ansi.style_aware_wcswidth(cur_char)
                char_index += 1

                if cur_char == ' ':
                    # If we've reached the end of a word, then add the word to the wrapped text
                    if cur_word_buf.tell() > 0:
                        add_word(cur_word_buf.getvalue())
                        cur_word_buf = io.StringIO()

                    # Otherwise add this space to the wrapped text
                    else:
                        # Check if we need to start a new line
                        if cur_char_width + cur_line_width > max_width:
                            wrapped_buf.write('\n')
                            total_lines += 1
                            cur_line_width = 0

                        wrapped_buf.write(cur_char)
                        cur_line_width += cur_char_width
                else:
                    # Add this character to the word buffer
                    cur_word_buf.write(cur_char)

            # Add the final word of this line if its been started
            if cur_word_buf.tell() > 0:
                add_word(cur_word_buf.getvalue())

            # Stop line loop if we've written to max_lines
            if total_lines == max_lines:
                # If all the text didn't fit, make the last character an ellipsis.
                # It won't already be one if the last line didn't need to be truncated.
                if not is_last_word() and cur_line_width < max_width:
                    wrapped_buf.write(constants.HORIZONTAL_ELLIPSIS)
                break

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
