from dataclasses import dataclass, field
from .colormapper import ColorMapper
import PyQt5.QtGui as qtg
from src.data_classes.annotation import Annotation
from src.utility.decorators import accepts, returns


@dataclass(order=True)
class Sample:
    _sort_index: int = field(init=False, repr=False)
    _start_pos: int = field(init=True)
    _end_pos: int = field(init=True)
    _annotation: Annotation = field(init=True)
    _default_color: qtg.QColor = field(init=False)
    _color: qtg.QColor = field(init=False, default=None)

    def __post_init__(self):
        assert isinstance(self._annotation, Annotation)
        self._default_color = qtg.QColor("#696969")
        self._default_color.setAlpha(127)
        self._sort_index = self._start_pos
        color_mapper = ColorMapper.instance()
        self._color = color_mapper.annotation_to_color(self._annotation)

    def __len__(self):
        return (self._end_pos - self._start_pos) + 1

    @property
    @returns(int)
    def start_position(self):
        return self._start_pos

    @start_position.setter
    @accepts(object, int)
    def start_position(self, value):
        if value < 0:
            raise ValueError
        else:
            self._start_pos = value

    @property
    @returns(int)
    def end_position(self):
        return self._end_pos

    @end_position.setter
    @accepts(object, int)
    def end_position(self, value):
        if value < 0:
            raise ValueError
        else:
            self._end_pos = value

    @property
    @returns(Annotation)
    def annotation(self):
        return self._annotation

    @annotation.setter
    @accepts(object, Annotation)
    def annotation(self, value):
        if value is None:
            raise ValueError("None not allowed")

        self._annotation = value
        # empty annotation
        color_mapper = ColorMapper.instance()
        self._color = color_mapper.annotation_to_color(value)

    @property
    @returns(qtg.QColor)
    def color(self):
        if self.annotation.is_empty:
            return self._default_color
        else:
            return self._color
