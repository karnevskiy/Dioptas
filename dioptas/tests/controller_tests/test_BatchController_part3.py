import os
import gc
import shutil
import numpy as np
from mock import MagicMock

from ..utility import QtTest

from qtpy import QtWidgets, QtCore, QtGui

from ...widgets.integration import IntegrationWidget
from ...widgets.plot_widgets.ImgWidget import MyRectangle
from ...controller.integration.BatchController import BatchController
from ...model.DioptasModel import DioptasModel
from dioptas.controller.integration.phase.PhaseController import PhaseController

unittest_data_path = os.path.join(os.path.dirname(__file__), '../data')
jcpds_path = os.path.join(unittest_data_path, 'jcpds')


class BatchControllerTest(QtTest):
    def setUp(self):
        self.working_dir = {'image': ''}

        self.widget = IntegrationWidget()
        self.model = DioptasModel()

        self.controller = BatchController(
            widget=self.widget,
            dioptas_model=self.model)

        self.phase_controller = PhaseController(self.widget, self.model)

        # Load existing proc+raw data
        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_proc.nxs')
        self.model.batch_model.load_proc_data(filename)
        raw_files = self.model.batch_model.files
        raw_files = [os.path.join(os.path.dirname(filename), os.path.basename(f)) for f in raw_files]
        self.model.batch_model.set_image_files(raw_files)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(self.model.batch_model.n_img - 1)

    def tearDown(self):
        del self.phase_controller
        del self.controller
        del self.model
        del self.widget
        gc.collect()
        gc.garbage

    def test_set_unit(self):
        bottom_axis = self.widget.batch_widget.img_view.bottom_axis_cake

        self.controller.set_unit_tth()
        self.assertEqual(self.model.current_configuration.integration_unit, '2th_deg')
        self.assertAlmostEqual(bottom_axis.range[0], 8.660802, places=2)
        self.assertAlmostEqual(bottom_axis.range[1], 26.74354, places=2)

        self.controller.set_unit_d()
        self.assertTrue(self.widget.integration_pattern_widget.d_btn.isChecked())
        self.assertEqual(self.model.current_configuration.integration_unit, 'd_A')
        self.assertAlmostEqual(bottom_axis._tickLevels[0][0][0], 9.467504, places=2)

        self.controller.set_unit_q()
        self.assertTrue(self.widget.integration_pattern_widget.q_btn.isChecked())
        self.assertEqual(self.model.current_configuration.integration_unit, 'q_A^-1')
        self.assertAlmostEqual(bottom_axis._tickLevels[0][0][0], 24.43931, places=2)

    def test_show_phases(self):
        # Load phases
        self.model.phase_model.add_jcpds(os.path.join(jcpds_path, 'FeGeO3_cpx.jcpds'))

        self.assertEqual(str(self.widget.batch_widget.phases_btn.text()), 'Show Phases')
        self.controller.toggle_show_phases()
        self.assertEqual(str(self.widget.batch_widget.phases_btn.text()), 'Hide Phases')

        self.assertEqual(len(self.widget.batch_widget.img_view.phases), 1)
        self.assertEqual(len(self.widget.batch_widget.img_view.phases[0].line_items), 27)

        #last_line_position = self.widget.batch_widget.img_view.phases[0].line_items[-1].getPos()
        #self.assertGreater(last_line_position[0], 1000)

    def test_load_single_image(self):
        self.controller.load_single_image(10, 15)

        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), 'Img: 15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertEqual(self.widget.batch_widget.img_view.horizontal_line.value(), 15)

    def test_plot_pattern(self):
        self.controller.plot_pattern(10, 15)

        self.assertAlmostEqual(self.model.pattern_model.pattern.data[0][0], 9.6926780, places=3)
        self.assertEqual(self.model.pattern_model.pattern.data[1][0], np.float32(0.1))

    def test_plot_image(self):
        self.controller.plot_image(15)

        filename = os.path.join(unittest_data_path, 'lambda', 'testasapo1_1009_00002_m1_part00001.nxs')
        self.assertEqual(self.widget.batch_widget.windowTitle(), f"Batch widget. {filename} - 5")
        self.assertTrue(self.model.current_configuration.auto_integrate_pattern)

        self.assertEqual(self.widget.batch_widget.step_series_widget.pos_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)
        self.assertEqual(self.widget.batch_widget.mouse_pos_widget.clicked_pos_widget.x_pos_lbl.text(), f'Img: 15')

    def test_update_3d_axis(self):
        self.controller.update_3d_axis(np.full((10, 1000), 80))

        self.assertEqual(self.widget.batch_widget.surf_view.axis.ticks[0].text, '9.69')
        self.assertEqual(self.widget.batch_widget.surf_view.g.spacing(), [10.0, 1000., 1])

    def test_update_y_axis(self):
        self.widget.batch_widget.step_series_widget.slider.setValue(15)
        self.widget.batch_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(28)

        self.controller.update_y_axis()
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[0],
                               2.898080396, places=3)
        self.assertAlmostEqual(self.widget.batch_widget.img_view.left_axis_cake.range[1],
                               30.3251324, places=3)

    def test_integrate(self):
        self.widget.batch_widget.step_series_widget.start_txt.setValue(5)
        self.widget.batch_widget.step_series_widget.stop_txt.setValue(28)
        self.widget.batch_widget.step_series_widget.step_txt.setValue(3)

        self.controller.integrate()

        self.assertEqual(self.model.batch_model.data.shape, (8, 4038))
        self.assertEqual(self.model.batch_model.binning.shape, (4038,))
        self.assertEqual(self.model.batch_model.n_img, 8)
        self.assertEqual(self.model.batch_model.n_img_all, 50)
        self.assertEqual(self.model.batch_model.pos_map.shape, (8, 2))

    def test_set_navigation_range(self):
        self.controller.set_navigation_range((10, 50), (15, 80))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '49')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 15)

        self.widget.batch_widget.step_series_widget.slider.setValue(60)
        self.controller.set_navigation_range((10, 50), (15, 80))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '49')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 49)

        self.widget.batch_widget.step_series_widget.slider.setValue(60)
        self.controller.set_navigation_range((10, 50), (15, 40))
        self.assertEqual(self.widget.batch_widget.step_series_widget.start_txt.text(), '15')
        self.assertEqual(self.widget.batch_widget.step_series_widget.stop_txt.text(), '40')
        self.assertEqual(self.widget.batch_widget.step_series_widget.slider.value(), 40)

        # ToDo Test interaction with other controllers: Integration window vertical line. Patterns
