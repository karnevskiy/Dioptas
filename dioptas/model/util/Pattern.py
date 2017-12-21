# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import logging
from qtpy import QtCore

import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from . import extract_background

logger = logging.getLogger(__name__)


class Pattern(QtCore.QObject):
    pattern_changed = QtCore.Signal(np.ndarray, np.ndarray)

    def __init__(self, x=None, y=None, name=''):
        super(Pattern, self).__init__()
        if x is None:
            self._original_x = np.linspace(0.1, 15, 100)
        else:
            self._original_x = x
        if y is None:
            self._original_y = np.log(self._original_x ** 2) - (self._original_x * 0.2) ** 2
        else:
            self._original_y = y

        self.name = name
        self.filename = ""
        self._offset = 0
        self._scaling = 1
        self._smoothing = 0
        self._background_pattern = None

        self._pattern_x = self._original_x
        self._pattern_y = self._original_y

        self.auto_background_subtraction = False
        self.auto_background_subtraction_roi = None
        self.auto_background_subtraction_parameters = [0.1, 50, 50]

        self._auto_background_before_subtraction_pattern = None
        self._auto_background_pattern = None

    def load(self, filename, skiprows=0):
        factor = 1.0
        try:
            if filename.endswith('.chi'):
                skiprows = 4
            if filename.endswith('fxye'):
                factor = 1.0/100.0
                with open(filename, 'r') as fxye_file:
                    skiprows = 0
                    for line in fxye_file:
                        skiprows += 1
                        if "BANK" in line:
                            if "CONQ" in line:
                                factor = 1.0
                            break

            data = np.loadtxt(filename, skiprows=skiprows)
            self.filename = filename
            self._original_x = data.T[0]*factor
            self._original_y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]
            self.recalculate_pattern()

        except ValueError:
            print('Wrong data format for pattern file! - ' + filename)
            return -1

    def save(self, filename, header=''):
        data = np.dstack((self._original_x, self._original_y))
        np.savetxt(filename, data[0], header=header)

    @property
    def background_pattern(self):
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self, pattern):
        """
        :param pattern: new background pattern
        :type pattern: Pattern
        """
        self._background_pattern = pattern
        self._background_pattern.pattern_changed.connect(self.recalculate_pattern)
        self.recalculate_pattern()

    def unset_background_pattern(self):
        self._background_pattern = None
        self.recalculate_pattern()

    def set_auto_background_subtraction(self, parameters, roi=None, recalc_pattern=True):
        self.auto_background_subtraction = True
        self.auto_background_subtraction_parameters = parameters
        self.auto_background_subtraction_roi = roi
        if recalc_pattern:
            self.recalculate_pattern()

    def unset_auto_background_subtraction(self):
        self.auto_background_subtraction = False
        self.recalculate_pattern()

    def get_auto_background_subtraction_parameters(self):
        return self.auto_background_subtraction_parameters

    def set_smoothing(self, amount):
        self._smoothing = amount
        self.recalculate_pattern()

    def recalculate_pattern(self):
        x = self._original_x
        y = self._original_y * self._scaling + self._offset

        if self._background_pattern is not None:
            # create background function
            x_bkg, y_bkg = self._background_pattern.data

            if not np.array_equal(x_bkg, self._original_x):
                # the background will be interpolated
                f_bkg = interp1d(x_bkg, y_bkg, kind='linear')

                # find overlapping x and y values:
                ind = np.where((self._original_x <= np.max(x_bkg)) & (self._original_x >= np.min(x_bkg)))
                x = self._original_x[ind]
                y = self._original_y[ind]

                if len(x) == 0:
                    # if there is no overlapping between background and pattern, raise an error
                    raise BkgNotInRangeError(self.name)

                y = y - f_bkg(x)
            else:
                # if pattern and bkg have the same x basis we just delete y-y_bkg
                y = y - y_bkg

        if self.auto_background_subtraction:
            self._auto_background_before_subtraction_pattern = Pattern(x, y)
            if self.auto_background_subtraction_roi is not None:
                ind = (x >= np.min(self.auto_background_subtraction_roi)) & \
                      (x <= np.max(self.auto_background_subtraction_roi))
                x = x[ind]
                y = y[ind]
                self.auto_background_subtraction_roi = [np.min(x), np.max(x)]
            else:
                self.auto_background_subtraction_roi = [np.min(x), np.max(x)]

            # reset ROI if limits are larger or smaller than the actual data
            x_min, x_max = np.min(x), np.max(x)
            if self.auto_background_subtraction_roi[0]<x_min:
                self.auto_background_subtraction_roi[0]=x_min

            if self.auto_background_subtraction_roi[1]>x_max:
                self.auto_background_subtraction_roi[1]=x_max

            y_bkg = extract_background(x, y,
                                       self.auto_background_subtraction_parameters[0],
                                       self.auto_background_subtraction_parameters[1],
                                       self.auto_background_subtraction_parameters[2])
            self._auto_background_pattern = Pattern(x, y_bkg)

            y -= y_bkg

        if self._smoothing > 0:
            y = gaussian_filter1d(y, self._smoothing)

        self._pattern_x = x
        self._pattern_y = y

        self.pattern_changed.emit(self._pattern_x, self._pattern_y)

    @property
    def data(self):
        return self._pattern_x, self._pattern_y

    @data.setter
    def data(self, data):
        (x, y) = data
        self._original_x = x
        self._original_y = y
        self._scaling = 1
        self._offset = 0
        self.recalculate_pattern()

    @property
    def x(self):
        return self._pattern_x

    @property
    def y(self):
        return self._pattern_y

    @property
    def original_data(self):
        return self._original_x, self._original_y

    @property
    def original_x(self):
        return self._original_x

    @property
    def original_y(self):
        return self._original_y

    @property
    def scaling(self):
        return self._scaling

    @scaling.setter
    def scaling(self, value):
        if value < 0:
            self._scaling = 0
        else:
            self._scaling = value
        self.recalculate_pattern()

    def limit(self, x_min, x_max):
        x, y = self.data
        return Pattern(x[np.where((x_min < x) & (x < x_max))],
                       y[np.where((x_min < x) & (x < x_max))])

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, value):
        self._offset = value
        self.recalculate_pattern()

    @property
    def auto_background_before_subtraction_pattern(self):
        return self._auto_background_before_subtraction_pattern

    @property
    def auto_background_pattern(self):
        return self._auto_background_pattern

    def has_background(self):
        return (self.background_pattern is not None) or self.auto_background_subtraction

    # Operators:
    def __sub__(self, other):
        orig_x, orig_y = self.data
        other_x, other_y = other.data

        if orig_x.shape != other_x.shape:
            # the background will be interpolated
            other_fcn = interp1d(other_x, other_y, kind='cubic')

            # find overlapping x and y values:
            ind = np.where((orig_x <= np.max(other_x)) & (orig_x >= np.min(other_x)))
            x = orig_x[ind]
            y = orig_y[ind]

            if len(x) == 0:
                # if there is no overlapping between background and pattern, raise an error
                raise BkgNotInRangeError(self.name)
            return Pattern(x, y - other_fcn(x))
        else:
            return Pattern(orig_x, orig_y - other_y)

    def __add__(self, other):
        orig_x, orig_y = self.data
        other_x, other_y = other.data

        if orig_x.shape != other_x.shape:
            # the background will be interpolated
            other_fcn = interp1d(other_x, other_y, kind='linear')

            # find overlapping x and y values:
            ind = np.where((orig_x <= np.max(other_x)) & (orig_x >= np.min(other_x)))
            x = orig_x[ind]
            y = orig_y[ind]

            if len(x) == 0:
                # if there is no overlapping between background and pattern, raise an error
                raise BkgNotInRangeError(self.name)
            return Pattern(x, y + other_fcn(x))
        else:
            return Pattern(orig_x, orig_y + other_y)

    def __rmul__(self, other):
        orig_x, orig_y = self.data
        return Pattern(orig_x, orig_y * other)

    def __len__(self):
        return len(self._original_x)


class BkgNotInRangeError(Exception):
    def __init__(self, pattern_name):
        self.pattern_name = pattern_name

    def __str__(self):
        return "The background range does not overlap with the Pattern range for " + self.pattern_name
