from qcodes.instrument import Instrument
from qcodes.instrument_drivers.stanford_research import SR830 as QCodesSR830


class SR830(Instrument):
    """
    Wrapper for a Stanford Research Systems SR830.
    """

    def __init__(
        self,
        name: str,
        address: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(f"wrapper_{name}")

        self.core = QCodesSR830(
            f"{name}_core",
            address,
            *args,
            **kwargs,
        )

        self.snapshot = self.core.snapshot

        self.sinc = self.core.sync_filter
        self.tc = self.core.time_constant
        self.order = self.core.filter_slope

        self.core.R.label = f"{name} R"
        self.core.P.label = f"{name} P"
    
    def get_idn(self) -> dict:
        return self.core.get_idn()
