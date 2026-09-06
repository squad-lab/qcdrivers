"""
Shared interface for buffered sweep nodes.

Concrete nodes are grouped by manufacturer and imported from packages such as
``qcdrivers.buffered.basel`` and ``qcdrivers.buffered.zurich``.

"""

from qcdrivers.buffered.base import BufferedNodeBase

__all__ = ["BufferedNodeBase"]
