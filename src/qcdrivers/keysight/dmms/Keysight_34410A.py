from typing import TYPE_CHECKING

from .Keysight_344xxA_submodules import Keysight344xxA

if TYPE_CHECKING:
    from qcodes.instrument import VisaInstrumentKWArgs
    from typing_extensions import Unpack


class Keysight34410A(Keysight344xxA):
    """QCoDeS driver for the Keysight 34410A digital multimeter."""

    def __init__(
        self,
        name: str,
        address: str,
        silent: bool = False,
        **kwargs: "Unpack[VisaInstrumentKWArgs]",
    ) -> None:
        super().__init__(name, address, silent, **kwargs)
