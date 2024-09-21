from enum import Enum
from typing import Optional

from qtpy import QtGui
from qtpy.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from careamics_napari.utils import REF_AXES, are_axes_valid, filter_dimensions
from careamics_napari.widgets.signals import ConfigurationSignal

class Highlight(Enum):
    VALID = 0
    UNRECOGNIZED = 1
    NOT_ACCEPTED = 2


class LettersValidator(QtGui.QValidator):
    def __init__(self, options, *args, **kwargs):
        QtGui.QValidator.__init__(self, *args, **kwargs)
        self._options = options

    def validate(self, value, pos):
        if len(value) > 0:
            if value[-1] in self._options:
                return QtGui.QValidator.Acceptable, value, pos
        else:
            if value == "":
                return QtGui.QValidator.Intermediate, value, pos
        return QtGui.QValidator.Invalid, value, pos

class AxesWidget(QWidget):
    """A widget allowing users to specify axes.
    
    Axes are validated based on the number of axes and whether 3D is enabled.
    """

    def __init__(self, signal: Optional[ConfigurationSignal] = None, n_axes=3, is_3D=False):
        super().__init__()
        self.signal = signal

        # max axes is 6
        assert 0 < n_axes <= 6

        self.n_axes = n_axes
        self.is_3D = is_3D
        self.is_text_valid = True

        # QtPy
        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)

        # folder selection button
        self.label = QLabel("Axes")
        self.layout().addWidget(self.label)

        # text field
        self.text_field = QLineEdit(self.get_default_text())
        self.text_field.setMaxLength(6)
        self.text_field.setValidator(LettersValidator(REF_AXES))

        self.layout().addWidget(self.text_field)
        self.text_field.textChanged.connect(self._validate_text)
        self.text_field.setToolTip(
            "Enter the axes order as they are in your images, e.g. SZYX.\n"
            "Accepted axes are S(ample), T(ime), C(hannel), Z, Y, and X. Red\n"
            "color highlighting means that a character is not recognized,\n"
            "orange means that the axes order is not allowed. YX axes are\n"
            "mandatory."
        )

        # validate text
        self._validate_text()

        # set up signal handling when axes change
        self.text_field.textChanged.connect(self._axes_changed)

    def _axes_changed(self):
        if self.signal is not None and self.is_text_valid:
            self.signal.use_channels = "C" in self.get_axes()

    def _validate_text(self):
        axes = self.get_axes()

        # change text color according to axes validation
        if are_axes_valid(axes):
            if axes.upper() in filter_dimensions(self.n_axes, self.is_3D):
                self._set_text_color(Highlight.VALID)
            else:
                self._set_text_color(Highlight.NOT_ACCEPTED)
        else:
            self._set_text_color(Highlight.UNRECOGNIZED)

    def _set_text_color(self, highlight: Highlight):
        self.is_text_valid = highlight == Highlight.VALID

        if highlight == Highlight.UNRECOGNIZED:
            self.text_field.setStyleSheet("color: red;")
        elif highlight == Highlight.NOT_ACCEPTED:
            self.text_field.setStyleSheet("color: orange;")
        else:  # VALID
            self.text_field.setStyleSheet("color: white;")

    def get_default_text(self):
        if self.is_3D:
            defaults = ["YX", "ZYX", "SZYX", "STZYX", "STCZYX"]
        else:
            defaults = ["YX", "SYX", "STYX", "STCYX", "STC?YX"]

        return defaults[self.n_axes - 2]

    def update_axes_number(self, n):
        self.n_axes = n
        self._validate_text()  # force new validation

    def update_is_3D(self, is_3D):
        self.is_3D = is_3D
        self._validate_text()  # force new validation

    def get_axes(self):
        return self.text_field.text()

    def is_valid(self):
        self._validate_text()  # probably unnecessary
        return self.is_text_valid

    def set_text_field(self, text):
        self.text_field.setText(text)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    import sys

    # Create a QApplication instance
    app = QApplication(sys.argv)

    # Signals
    myalgo = ConfigurationSignal()

    @myalgo.events.use_channels.connect
    def print_axes():
        print(f"Use channels: {myalgo.use_channels}")

    # Instantiate widget
    widget = AxesWidget(signal=myalgo)

    # Show the widget
    widget.show()

    # Run the application event loop
    sys.exit(app.exec_())