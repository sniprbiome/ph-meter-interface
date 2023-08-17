import abc
from abc import ABC, abstractmethod

import pandas as pd

import PumpTasks


class PhysicalSystemsInterface(abc.ABC):

    @abstractmethod
    def __init__(self, settings) -> None:
        pass

    @abstractmethod
    def initialize_systems(self) -> None:
        pass

    @abstractmethod
    def initialize_pumps_used_in_protocol(self, protocol: pd.DataFrame) -> None:
        pass

    @abstractmethod
    def get_current_pump_address(self) -> bytes:
        pass

    @abstractmethod
    def set_and_get_address_for_current_pump(self, address: int) -> bytes:
        pass

    @abstractmethod
    def pump(self, pump_id):
        pass

    # Ph

    @abstractmethod
    def get_mv_values_of_selected_probes(self, selected_probes: list[str]) -> dict[str, float]:
        pass

    @abstractmethod
    def measure_ph_with_probe_associated_with_task(self, current_task: PumpTasks) -> float:
        pass

    @abstractmethod
    def get_ph_values_of_selected_probes(self, ph_probes: list[str]) -> dict[str, float]:
        pass

    @abstractmethod
    def recalibrate_ph_meter(self) -> None:
        pass

    def get_ph_calibration_data(self) -> dict[str, dict[str, int]]:
        pass

    @abstractmethod
    def set_pump_dose_multiplication_factor(self, protocol: pd.DataFrame, dose_multiplication_factor) -> None:
        pass

    @abstractmethod
    def pump_n_times(self, pump_id, pump_multiplier) -> None:
        pass


    @abstractmethod
    def disconnect(self, protocol: pd.DataFrame) -> None:
        pass