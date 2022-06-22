
import unittest

import yaml

import main
from PH_Meter import PH_Meter
import mock_objects
from PumpSystem import PumpSystem
from PumpTasks import PumpTask
import matplotlib.pyplot as plt


class Test_complete_system(unittest.TestCase):


    def setUp(self):

        mock_timer = mock_objects.MockTimer()
        with open('testpumpsettings.yml', 'r') as file:
            settings = yaml.safe_load(file)
        protocol = main.select_instruction_sheet("../test_protocol.xlsx")
        main.timer = mock_timer

        #ph-meter:
        self.ph_meter = PH_Meter(None)
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.ph_meter.serial_connection = self.mock_serial_connection
        self.ph_meter.timer = mock_timer

        #Pumps
        self.pump_system = PumpSystem(protocol, settings["pumps"])
        self.mock_serial_connection = mock_objects.MockSerialConnection(None)
        self.pump_system.serial_connection = self.mock_serial_connection
        self.pump_system.timer = mock_timer

        # Tasks
        self.task_priority_queue = main.initialize_task_priority_queue(protocol)
        for task in self.task_priority_queue:
            task.timer = mock_timer
            task.datetimer = mock_timer

        # PhSolutions


    def test_complete_system(self):


        self.mock_ph_solution = mock_objects.MockPhSolution({"F.0.1.22": [800, 800, 800, 800], "F.0.1.21": [800, 10000, 10000, 10000]})

        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01"\x8f\r\n', lambda : self.mock_ph_solution.getPhCommandOfSolution("F.0.1.22"))
        self.ph_meter.serial_connection.add_write_action(b'M\x06\n\x0f\x00\x01!\x8e\r\n', lambda : self.mock_ph_solution.getPhCommandOfSolution("F.0.1.21"))

        self.pump_system.serial_connection.add_write_action(b'1 RUN\r', lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(self.pump_system.pump_associated_volumes[int(1)], "F.0.1.22", 1))
        self.pump_system.serial_connection.add_write_action(b'2 RUN\r', lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(self.pump_system.pump_associated_volumes[int(2)], "F.0.1.22", 2))
        self.pump_system.serial_connection.add_write_action(b'3 RUN\r', lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(self.pump_system.pump_associated_volumes[int(3)], "F.0.1.22", 3))
        self.pump_system.serial_connection.add_write_action(b'4 RUN\r', lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(self.pump_system.pump_associated_volumes[int(4)], "F.0.1.22", 4))
        self.pump_system.serial_connection.add_write_action(b'5 RUN\r', lambda: self.mock_ph_solution.addVolumeOfBaseToSolution(self.pump_system.pump_associated_volumes[int(5)], "F.0.1.21", 1))

        records = main.run_tasks(self.task_priority_queue, self.ph_meter, self.pump_system)

        for pumpTask in [2]: #[1, 2, 3, 4, 5]:

            currentPumpTaskRecords = records.loc[records['PumpTask'] == pumpTask]
            rows = [row for index, row in currentPumpTaskRecords.iterrows()]

            for i in range(len(rows) - 1):
                currentRow = rows[i]
                nextRow = rows[i+1]
                # expected pH should be strictly increasing:
                self.assertLess(currentRow["ExpectedPH"], nextRow["ExpectedPH"])
                # actual ph should be weakly increasing
                self.assertLessEqual(currentRow["ActualPH"], nextRow["ActualPH"])
                #Timepoint should be strictly increasing
                self.assertLess(currentRow["TimePoint"], nextRow["TimePoint"])

                # pH should increase exactly when it pumped the time before:
                if currentRow['DidPump']:
                    self.assertLess(currentRow["ActualPH"], nextRow["ActualPH"])
                else:
                    self.assertEqual(currentRow["ActualPH"], nextRow["ActualPH"])

                # it should pump when expected pH is less than actual pH
                self.assertEqual(currentRow["DidPump"], currentRow["ActualPH"] < currentRow["ExpectedPH"])

                # The actual pH should not vary by a lot compared to the expected ph. Here we say 0.2
                self.assertTrue(abs(currentRow["ActualPH"] - currentRow["ExpectedPH"]) < 0.2)

                # currentPumpTaskRecords.plot(x="TimePoint", y="ActualPH", kind="line")
                # plt.show()

        # records.to_csv("testruns.csv", index=False)









