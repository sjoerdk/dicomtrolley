"""For dealing with http details that are not fully addressed in requests"""
import email.parser
from typing import Iterator, Optional

from requests.exceptions import ChunkedEncodingError
from requests.structures import CaseInsensitiveDict
from urllib3.exceptions import ProtocolError

from dicomtrolley.exceptions import DICOMTrolleyError


class HTMLPart:
    """One part of a multipart http response, without the boundaries"""

    def __init__(self, content, encoding):
        if not encoding:
            encoding = "utf-8"
        self.encoding = encoding
        headers = {}
        # Split into header section (if any) and the content
        if b"\r\n\r\n" in content:
            first, self.content = split_on_find(content, b"\r\n\r\n")
            if first != b"":
                headers = parse_headers(first.lstrip(), encoding)
        else:
            raise MultipartContentError("content does not contain CR-LF-CR-LF")
        self.headers = CaseInsensitiveDict(headers)

    @property
    def text(self):
        return self.content.decode(self.encoding)


class SafeChunks:
    """Iterator that returns byte chunks from stream

    Takes into account servers might ignore chunk_size. If returned
    chunks are smaller than expected, collates chunks until chunk of at least
    stream_chunk_size is received
    """

    def __init__(self, response, chunk_size):
        self.chunk_size = chunk_size
        self._chunk_iterator = response.iter_content(chunk_size=chunk_size)

    def __iter__(self):
        return self

    def __next__(self):
        sized_chunk = bytearray()
        while len(sized_chunk) < self.chunk_size:
            try:
                sized_chunk += next(self._chunk_iterator)
            except StopIteration:
                if sized_chunk:
                    return (
                        sized_chunk  # some data was received, return last bit
                    )
                else:
                    raise  # no data was received and no more chunks. End.
        return sized_chunk


class HTTPMultiPartStream:
    """Converts a streamed http multipart response into separate parts.

    Main use is as an iterator:

        parts = [x for x in HTTPMultiPartStream(response)]

    This iterator is stateful and can only be called once as it consumes the
    response stream
    """

    def __init__(self, response, stream_chunk_size=65536):
        self.response = response
        self.boundary = self._find_boundary(response)
        self._part_iterator = PartIterator(
            bytes_iterator=SafeChunks(response, stream_chunk_size),
            boundary=b"--" + self._find_boundary(response),
        )

    @staticmethod
    def _split_on_find(content, bound):
        point = content.find(bound)
        return content[:point], content[point + len(bound) :]

    @classmethod
    def _find_boundary(cls, multipart_response):
        """Find the string that separates the parts"""
        content_type_info = tuple(
            x.strip()
            for x in multipart_response.headers.get("content-type").split(";")
        )
        mimetype = content_type_info[0]
        if mimetype.split("/")[0].lower() != "multipart":
            raise MultipartContentError(
                f"Unexpected mimetype in content-type: '{mimetype}'"
            )
        for item in content_type_info[1:]:
            attr, value = cls._split_on_find(item, "=")
            if attr.lower() == "boundary":
                return value.strip('"').encode("utf-8")

    def __iter__(self):
        return self

    def __next__(self):
        """
        Returns
        -------
        HTMLPart
            One part in a multipart response
        """
        return HTMLPart(
            next(self._part_iterator), encoding=self.response.encoding
        )


class PartIterator:
    """Splits incoming multipart bytes into parts based on boundary.

    Tries to be efficient with scanning the buffer for boundary byte strings by
    remembering what was scanned before.
    """

    def __init__(self, bytes_iterator: Iterator[bytes], boundary: bytes):
        self.boundary = boundary
        self._bytes_iterator = bytes_iterator
        self._buffer_fresh = bytearray()
        self._buffer_scanned = bytearray()

        self.last_scanned = 0

    def __next__(self):
        """

        Returns
        -------
        Bytes
            bytes between two boundaries, or None if none can be found

        Raises
        ------
        StopIteration
            When no next chunks can be read

        """
        part = None
        while part is None:
            part = self.scan_for_part()  # find part in buffer
            if part is None:  # if nothing in buffer, try to add data
                self._buffer_fresh += self.read_next_chunk()

        return part

    def __iter__(self):
        return self

    def read_next_chunk(self):
        """Read next chunk of bytes from iterator"""
        try:
            return next(self._bytes_iterator)
        except ChunkedEncodingError as e:
            raise DICOMTrolleyError(str(e)) from e
        except ProtocolError as e:
            raise DICOMTrolleyError(str(e)) from e

    def scan_for_part(self) -> Optional[bytes]:
        """Search buffer to try to return a part between two boundaries.
        Shifts data between fresh and scanned buffer to reduce search time

        Returns
        -------
        Bytes
           All bytes before the next boundary. Removes bytes and boundary from
           buffer. If no boundary is found, return empty bytes
        None
            If no part could be found

        Notes
        -----
        Boundary bytes themselves are never returned. If incoming bytes start with
        a boundary bytestring this is discarded. The alternative, returning an empty
        bytestring does not seem useful in this case.
        """

        if not self._buffer_fresh:
            return None  # Avoid exception for valid empty input
        elif len(self._buffer_fresh) < len(self.boundary):
            return None  # Not enough bytes to find boundary yet

        #  find the next boundary
        boundary_index = self._buffer_fresh.find(self.boundary)
        if boundary_index == -1:  # no boundary found
            # a part of the boundary might be clipped at the end of the buffer
            boundary_size = len(self.boundary)
            scanned = self._buffer_fresh[:-boundary_size]
            might_contain_boundary = self._buffer_fresh[-boundary_size:]
            self._buffer_scanned += scanned
            self._buffer_fresh = might_contain_boundary
            return None
        if boundary_index == 0:  # boundary is at the start of buffer.
            # discard boundary and scan again (see notes)
            self._buffer_fresh = self._buffer_fresh[len(self.boundary) :]
            return self.scan_for_part()
        else:  # boundary found
            up_to_boundary = self._buffer_fresh[:boundary_index]
            rest = self._buffer_fresh[(boundary_index + len(self.boundary)) :]
            self._buffer_fresh = rest
            part = self._buffer_scanned + up_to_boundary
            self._buffer_scanned = bytearray()
            return part


class MultipartContentError(DICOMTrolleyError):
    pass


def split_on_find(content, bound):
    """Split content string on a substring"""
    point = content.find(bound)
    return content[:point], content[point + len(bound) :]


def parse_headers(content, encoding):
    string = content.decode(encoding)
    return email.parser.HeaderParser().parsestr(string).items()
